#!/usr/bin/env python3
"""
Review Engine — Checkpoints, Alerts, and Weekly Digest.

Read-only monitoring engine. Runs alongside daily 7am automation.
Does NOT modify any model thresholds, stop rules, overlays, or configs.

Usage:
    python3 review_engine/engine.py                  # daily scan
    python3 review_engine/engine.py --weekly         # force weekly digest
    python3 review_engine/engine.py --summary        # print status
    python3 review_engine/engine.py --reset-state    # clear issued alerts
"""

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

ENGINE_DIR = Path(__file__).resolve().parent
REPO_DIR = ENGINE_DIR.parent
CONFIG_PATH = ENGINE_DIR / "checkpoint_config.json"
STATE_PATH = ENGINE_DIR / "engine_state.json"
CHECKPOINTS_DIR = REPO_DIR / "reviews" / "checkpoints"
WEEKLY_DIR = REPO_DIR / "reviews" / "weekly"

WIN = 100.0 / 110.0

# Alert levels
INFO = "INFO"
CHECKPOINT = "CHECKPOINT"
WARNING = "WARNING"
STOP_PROXIMITY = "STOP_RULE_PROXIMITY"


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)


def load_state() -> dict:
    if STATE_PATH.exists():
        with open(STATE_PATH) as f:
            return json.load(f)
    return {"issued_checkpoints": [], "last_weekly": None, "issued_monthly": []}


def save_state(state: dict):
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def _load_graded(source_file: str, cfg: dict) -> pd.DataFrame:
    """Load graded rows from a source file.

    For live-mode models, filters to split=='live' or
    market_snapshot_status=='live' to exclude historical data.
    """
    path = REPO_DIR / source_file
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_parquet(path)

        # Filter to live data for live-mode models
        if cfg.get("mode") == "live":
            live_filtered = False
            for col in ("split", "market_snapshot_status"):
                if col in df.columns:
                    df = df[df[col] == "live"]
                    live_filtered = True
                    break
            if not live_filtered:
                # No live/split column — all data is historical, return empty
                return pd.DataFrame()

        field = cfg.get("graded_field", "result")
        values = cfg.get("graded_values", ["WIN", "LOSS"])
        if field in df.columns:
            return df[df[field].isin(values)].copy()
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _metrics(df: pd.DataFrame, result_col: str = "result") -> dict:
    """Compute standard metrics from graded df."""
    if len(df) == 0:
        return {"n": 0, "hit": None, "roi": None}
    w = (df[result_col] == "WIN").sum()
    l = (df[result_col] == "LOSS").sum()
    n = w + l
    if n == 0:
        return {"n": 0, "hit": None, "roi": None}
    return {"n": n, "w": int(w), "l": int(l),
            "hit": round(w / n, 3), "roi": round((w * WIN - l) / n * 100, 1)}


def _format_metrics(m: dict, label: str) -> str:
    if m["n"] == 0:
        return f"  {label}: no data"
    return f"  {label}: N={m['n']}, hit={m['hit']:.1%}, ROI={m['roi']:+.1f}%"


# ═══════════════════════════════════════════════════════════
# CHECKPOINT PACKAGE GENERATORS
# ═══════════════════════════════════════════════════════════

def _nba_phase6_package(df: pd.DataFrame, cfg: dict, checkpoint_n: int) -> str:
    """Generate NBA Phase 6 checkpoint review package."""
    overall = _metrics(df)

    ovl = df[df.get("overlay_applied", pd.Series(dtype=bool)) == True] if "overlay_applied" in df.columns else pd.DataFrame()
    non = df[df.get("overlay_applied", pd.Series(dtype=bool)) != True] if "overlay_applied" in df.columns else df

    lines = [
        f"CHECKPOINT REVIEW: {cfg['sport']} {cfg['phase']}",
        f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"Threshold reached: {checkpoint_n} graded bets",
        f"Source: {cfg['source_file']}",
        f"Date range: {df['date'].min()} to {df['date'].max()}",
        f"Review type: {cfg['review_type']}",
        "",
        "SUMMARY:",
        _format_metrics(overall, "Overall (0-1 edge)"),
        _format_metrics(_metrics(ovl), "Fast pace overlay"),
        _format_metrics(_metrics(non), "Non-overlay"),
        "",
        "EDGE SUB-BUCKETS:",
    ]

    if "model_edge" in df.columns:
        df_copy = df.copy()
        df_copy["abs_edge"] = df_copy["model_edge"].abs()
        for lo, hi in [(0, 0.25), (0.25, 0.50), (0.50, 0.75), (0.75, 1.0)]:
            sub = df_copy[(df_copy["abs_edge"] >= lo) & (df_copy["abs_edge"] < hi)]
            lines.append(_format_metrics(_metrics(sub), f"  {lo:.2f}-{hi:.2f}"))

    if "date" in df.columns:
        lines.append("")
        lines.append("MONTHLY:")
        df_copy = df.copy()
        df_copy["month"] = pd.to_datetime(df_copy["date"]).dt.to_period("M")
        for m in sorted(df_copy["month"].unique()):
            sub = df_copy[df_copy["month"] == m]
            lines.append(_format_metrics(_metrics(sub), f"  {m}"))

    lines.append("")
    lines.append("REVIEW QUESTIONS:")
    for i, q in enumerate(cfg.get("review_questions", []), 1):
        lines.append(f"  {i}. {q}")

    return "\n".join(lines)


def _mlb_live_package(df: pd.DataFrame, cfg: dict, checkpoint_n: int) -> str:
    """Generate MLB live checkpoint review package."""
    # MLB shadow log has different schema
    lines = [
        f"CHECKPOINT REVIEW: {cfg['sport']} {cfg['phase']}",
        f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"Threshold reached: {checkpoint_n} graded entries",
        f"Source: {cfg['source_file']}",
        f"Review type: {cfg['review_type']}",
    ]

    if "actual_total" in df.columns and "market_line" in df.columns:
        df_valid = df[df["actual_total"].notna() & df["market_line"].notna()].copy()
        if "sim_tier" in df_valid.columns:
            for tier_pattern in ["STRONG", "BET", "WATCHLIST"]:
                sub = df_valid[df_valid["sim_tier"].str.contains(tier_pattern, case=False, na=False)]
                if len(sub) > 0:
                    correct = sub.get("sim_correct", pd.Series(dtype=float))
                    if correct.notna().any():
                        hit = correct.mean()
                        lines.append(f"  {tier_pattern}: N={len(sub)}, correct={hit:.1%}")

        # Overlay
        if "overlay_applied" in df_valid.columns:
            ovl = df_valid[df_valid["overlay_applied"] == True]
            non = df_valid[df_valid["overlay_applied"] != True]
            lines.append(f"\n  Overlay bets: {len(ovl)}")
            lines.append(f"  Non-overlay: {len(non)}")

    lines.append("")
    lines.append("REVIEW QUESTIONS:")
    for i, q in enumerate(cfg.get("review_questions", []), 1):
        lines.append(f"  {i}. {q}")

    return "\n".join(lines)


def _generic_package(df: pd.DataFrame, cfg: dict, checkpoint_n: int) -> str:
    """Generate generic checkpoint review package."""
    overall = _metrics(df)
    lines = [
        f"CHECKPOINT REVIEW: {cfg['sport']} {cfg['phase']}",
        f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"Threshold reached: {checkpoint_n}",
        f"Source: {cfg['source_file']}",
        f"Review type: {cfg['review_type']}",
        "",
        _format_metrics(overall, "Overall"),
        "",
        "REVIEW QUESTIONS:",
    ]
    for i, q in enumerate(cfg.get("review_questions", []), 1):
        lines.append(f"  {i}. {q}")
    return "\n".join(lines)


def generate_package(model_id: str, df: pd.DataFrame, cfg: dict, checkpoint_n: int) -> str:
    """Route to sport-specific package generator."""
    if "nba_phase6" in model_id:
        return _nba_phase6_package(df, cfg, checkpoint_n)
    elif "mlb" in model_id:
        return _mlb_live_package(df, cfg, checkpoint_n)
    else:
        return _generic_package(df, cfg, checkpoint_n)


# ═══════════════════════════════════════════════════════════
# STOP RULE PROXIMITY
# ═══════════════════════════════════════════════════════════

def check_stop_proximity(model_id: str, cfg: dict) -> list[dict]:
    """Check if any model is approaching stop-rule thresholds.

    Only fires when live_n > minimum_live_bets (default 1).
    Historical/shadow data does not trigger stop-rule alerts.
    """
    alerts = []

    if not cfg.get("stop_rule_proximity_alert"):
        return alerts

    source = cfg.get("source_file", "")
    path = REPO_DIR / source
    if not path.exists():
        return alerts

    try:
        df = pd.read_parquet(path)
    except Exception:
        return alerts

    # Filter to LIVE data only — never alert on historical/shadow rows
    live_col = None
    for candidate in ["market_snapshot_status", "split"]:
        if candidate in df.columns:
            live_col = candidate
            break

    if live_col:
        live_df = df[df[live_col] == "live"]
    else:
        # No live/split column — assume all data is historical, skip alert
        return alerts

    # Apply graded filter
    graded_field = cfg.get("graded_field", "result")
    graded_values = cfg.get("graded_values", ["WIN", "LOSS"])
    if graded_field in live_df.columns:
        live_graded = live_df[live_df[graded_field].isin(graded_values)]
    else:
        return alerts

    min_live = cfg.get("minimum_live_bets", 1)
    if len(live_graded) <= min_live:
        return alerts

    m = _metrics(live_graded)
    if m["roi"] is not None and m["roi"] < -7 and m["n"] >= 15:
        alerts.append({
            "model": model_id,
            "level": STOP_PROXIMITY,
            "message": f"{cfg['sport']} {cfg['phase']}: ROI={m['roi']:+.1f}% on N={m['n']} live bets — approaching stop threshold",
        })

    return alerts


# ═══════════════════════════════════════════════════════════
# DAILY SCAN
# ═══════════════════════════════════════════════════════════

def daily_scan(today_str: str = None) -> list[dict]:
    """Run daily checkpoint and alert scan. Returns list of alerts."""
    today_str = today_str or date.today().isoformat()
    config = load_config()
    state = load_state()
    alerts = []

    for model_id, cfg in config.get("models", {}).items():
        # Skip dormant
        if cfg.get("mode") == "dormant":
            dormant_until = cfg.get("dormant_until", "9999-01-01")
            if today_str < dormant_until:
                continue

        source = cfg.get("source_file", "")
        if not source:
            continue

        df = _load_graded(source, cfg)
        n_graded = len(df)

        # Check checkpoints
        for cp in cfg.get("checkpoints", []):
            cp_id = f"{model_id}_{cp}"
            if cp_id in state["issued_checkpoints"]:
                continue
            if n_graded >= cp:
                # Fire checkpoint
                package = generate_package(model_id, df, cfg, cp)

                # Save package
                CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)
                filename = f"{today_str}_{model_id}_{cp}.txt"
                (CHECKPOINTS_DIR / filename).write_text(package)

                alerts.append({
                    "model": model_id,
                    "level": CHECKPOINT,
                    "message": f"{cfg['sport']} {cfg['phase']}: {cp}-bet checkpoint reached (N={n_graded})",
                    "file": str(CHECKPOINTS_DIR / filename),
                })

                state["issued_checkpoints"].append(cp_id)
                logger.info(f"Checkpoint: {model_id} @ {cp} bets → {filename}")

        # Check monthly review
        if cfg.get("monthly_review"):
            month_key = f"{model_id}_{today_str[:7]}"
            if month_key not in state["issued_monthly"] and today_str[8:10] == "01":
                alerts.append({
                    "model": model_id,
                    "level": INFO,
                    "message": f"{cfg['sport']} {cfg['phase']}: monthly review due",
                })
                state["issued_monthly"].append(month_key)

        # Stop-rule proximity
        alerts.extend(check_stop_proximity(model_id, cfg))

    save_state(state)
    return alerts


# ═══════════════════════════════════════════════════════════
# WEEKLY DIGEST
# ═══════════════════════════════════════════════════════════

def generate_weekly_digest(today_str: str = None) -> str:
    """Generate Sunday weekly digest for all active models."""
    today_str = today_str or date.today().isoformat()
    config = load_config()

    lines = [
        "=" * 60,
        f"  WEEKLY DIGEST — {today_str}",
        "=" * 60,
        "",
    ]

    for model_id, cfg in config.get("models", {}).items():
        sport = cfg.get("sport", "")
        phase = cfg.get("phase", "")
        mode = cfg.get("mode", "")

        if mode == "dormant":
            lines.append(f"  {sport} {phase}: DORMANT (until {cfg.get('dormant_until', '?')})")
            lines.append("")
            continue

        source = cfg.get("source_file", "")
        df = _load_graded(source, cfg) if source else pd.DataFrame()
        n = len(df)
        m = _metrics(df)

        lines.append(f"  {sport} {phase} [{mode}]")
        lines.append(f"  {'─'*50}")

        if n == 0:
            lines.append(f"    No graded data yet")
        else:
            lines.append(f"    Sample: {m['n']} bets")
            if m["hit"] is not None:
                lines.append(f"    Hit rate: {m['hit']:.1%}")
                lines.append(f"    ROI: {m['roi']:+.1f}%")

        # Checkpoint progress
        cps = cfg.get("checkpoints", [])
        if cps:
            next_cp = next((cp for cp in cps if n < cp), None)
            if next_cp:
                lines.append(f"    Checkpoint progress: {n}/{next_cp} ({next_cp - n} remaining)")
            else:
                lines.append(f"    All checkpoints reached ✅")

        # Alerts
        stop_alerts = check_stop_proximity(model_id, cfg)
        if stop_alerts:
            for a in stop_alerts:
                lines.append(f"    ⚠️ {a['message']}")
        else:
            lines.append(f"    No active alerts")

        lines.append("")

    return "\n".join(lines)


def run_weekly(today_str: str = None):
    """Generate and save weekly digest."""
    today_str = today_str or date.today().isoformat()
    state = load_state()

    if state.get("last_weekly") == today_str[:10]:
        logger.info("Weekly digest already generated today — skipping")
        return

    digest = generate_weekly_digest(today_str)

    WEEKLY_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"digest_{today_str}.txt"
    (WEEKLY_DIR / filename).write_text(digest)

    state["last_weekly"] = today_str[:10]
    save_state(state)

    logger.info(f"Weekly digest saved: {filename}")
    print(digest)


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Review Engine — monitoring and digest")
    parser.add_argument("--date", default=None)
    parser.add_argument("--weekly", action="store_true", help="Force weekly digest")
    parser.add_argument("--summary", action="store_true", help="Print current status")
    parser.add_argument("--reset-state", action="store_true", help="Clear issued alerts")
    args = parser.parse_args()

    today_str = args.date or date.today().isoformat()

    if args.reset_state:
        save_state({"issued_checkpoints": [], "last_weekly": None, "issued_monthly": []})
        print("State reset.")
        return

    if args.summary:
        print(generate_weekly_digest(today_str))
        return

    # Daily scan
    alerts = daily_scan(today_str)
    if alerts:
        print(f"\n[review_engine] {len(alerts)} alert(s):")
        for a in alerts:
            print(f"  [{a['level']}] {a['message']}")
            if "file" in a:
                print(f"    → {a['file']}")
    else:
        print(f"[review_engine] No new alerts for {today_str}")

    # Weekly digest on Sundays
    d = date.fromisoformat(today_str)
    config = load_config()
    if d.weekday() == config.get("weekly_digest", {}).get("day_of_week", 6) or args.weekly:
        run_weekly(today_str)


if __name__ == "__main__":
    main()
