#!/usr/bin/env python3
"""
push_nhl.py — Serialize NHL signals + historical performance to nhl_results.json.

Called from push_results.py (daily 7am) or standalone.

Usage:
    python push_nhl.py              # serialize + push
    python push_nhl.py --no-push    # serialize only
    python push_nhl.py --date 2026-03-16
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO_DIR     = Path(__file__).parent
NHL_DIR      = REPO_DIR / "nhl"
DECISIONS    = NHL_DIR / "nhl_decisions.parquet"
RESULTS_P    = NHL_DIR / "nhl_results.parquet"
OUT_PATH     = REPO_DIR / "nhl_results.json"

WIN_PER_UNIT = 100.0 / 110.0


def _safe(v):
    if v is None:
        return None
    if hasattr(v, "item"):          # numpy scalar
        return v.item()
    if isinstance(v, float) and v != v:  # NaN
        return None
    return v


def load_today_signals(game_date: str) -> list[dict]:
    """
    Live signals from nhl_decisions.parquet for today (all tiers, all sides).

    FIX 4: caution_flag suppresses display warning only — does NOT filter signals.
    Rows with caution_flag=1 are included in the output exactly like any other row.
    The dashboard renders a ⚠ badge; no signal is suppressed here.
    """
    if not DECISIONS.exists():
        return []
    try:
        import pandas as pd
        dec = pd.read_parquet(DECISIONS)
        dec["game_date"] = pd.to_datetime(dec["game_date"]).dt.date.astype(str)
        today_live = dec[
            (dec["game_date"] == game_date) &
            (dec["split"] == "live")
        ]
        rows = []
        for _, r in today_live.iterrows():
            rows.append({
                "game_id":          _safe(r.get("game_id")),
                "game_date":        r.get("game_date"),
                "home_team":        r.get("home_team"),
                "away_team":        r.get("away_team"),
                "signal_side":      r.get("signal_side"),
                "closing_total":    _safe(r.get("closing_total")),
                "edge":             _safe(r.get("edge")),
                "edge_bucket":      r.get("edge_bucket"),
                "sim_prob":         _safe(r.get("sim_prob")),
                "confidence_tier":  r.get("confidence_tier"),
                "stake_units":      float(r.get("stake_units") or {"HIGH": 1.0, "MEDIUM": 0.75, "SHADOW_MEDIUM": 0.0, "SHADOW_LOW": 0.0}.get(r.get("confidence_tier"), 0.75)),
                # caution_flag: display warning only — does not suppress signal
                "caution_flag":     int(r.get("caution_flag") or 0),
                "volatility_bucket": r.get("volatility_bucket"),
                "lambda_total_calibrated": _safe(r.get("lambda_total_calibrated")),
                "over_price":       _safe(r.get("over_price")),
                "under_price":      _safe(r.get("under_price")),
                "book":             r.get("book"),
                "commence_time":    r.get("commence_time"),
                "result":           r.get("result"),
                "graded":           int(r.get("graded") or 0),
                # Scoring-form features for summary (present in signals after Phase 6.1)
                "home_goals_scored_rolling_10":  _safe(r.get("home_goals_scored_rolling_10")),
                "away_goals_scored_rolling_10":  _safe(r.get("away_goals_scored_rolling_10")),
                "home_goals_allowed_rolling_10": _safe(r.get("home_goals_allowed_rolling_10")),
                "away_goals_allowed_rolling_10": _safe(r.get("away_goals_allowed_rolling_10")),
                "home_xgf_rolling_20":           _safe(r.get("home_xgf_rolling_20")),
                "away_xgf_rolling_20":           _safe(r.get("away_xgf_rolling_20")),
                "home_xga_rolling_20":           _safe(r.get("home_xga_rolling_20")),
                "away_xga_rolling_20":           _safe(r.get("away_xga_rolling_20")),
                "home_pp_pct_rolling_20":        _safe(r.get("home_pp_pct_rolling_20")),
                "away_pp_pct_rolling_20":        _safe(r.get("away_pp_pct_rolling_20")),
                "home_goalie_vs_team_baseline":  _safe(r.get("home_goalie_vs_team_baseline")),
                "away_goalie_vs_team_baseline":  _safe(r.get("away_goalie_vs_team_baseline")),
                "home_goalie_b2b":               int(r.get("home_goalie_b2b") or 0),
                "away_goalie_b2b":               int(r.get("away_goalie_b2b") or 0),
                "home_b2b":                      int(r.get("home_b2b") or 0),
                "away_b2b":                      int(r.get("away_b2b") or 0),
                "goalie_confirmed_home":         bool(r.get("goalie_confirmed_home", True)),
                "goalie_confirmed_away":         bool(r.get("goalie_confirmed_away", True)),
                "backup_flag_home":              int(r.get("backup_flag_home") or 0),
                "backup_flag_away":              int(r.get("backup_flag_away") or 0),
            })
        print(f"[push_nhl] Today's signals: {len(rows)}")
        return rows
    except Exception as e:
        print(f"[push_nhl] Failed to load today signals: {e}", file=sys.stderr)
        return []


def load_recent_results(days: int = 14) -> list[dict]:
    """Graded live signals from the past `days` days in nhl_decisions.parquet."""
    if not DECISIONS.exists():
        return []
    try:
        import pandas as pd
        dec = pd.read_parquet(DECISIONS)
        dec["game_date"] = pd.to_datetime(dec["game_date"]).dt.date
        cutoff = (date.today() - timedelta(days=days))
        recent = dec[
            (dec["game_date"] >= cutoff) &
            (dec["split"] == "live") &
            (dec["graded"] == 1)
        ].sort_values("game_date", ascending=False)
        rows = []
        for _, r in recent.iterrows():
            rows.append({
                "game_id":          _safe(r.get("game_id")),
                "game_date":        r["game_date"].isoformat(),
                "home_team":        r.get("home_team"),
                "away_team":        r.get("away_team"),
                "signal_side":      r.get("signal_side"),
                "closing_total":    _safe(r.get("closing_total")),
                "edge":             _safe(r.get("edge")),
                "confidence_tier":  r.get("confidence_tier"),
                "result":           r.get("result"),
                "actual_total_goals_final": _safe(r.get("actual_total_goals_final")),
            })
        print(f"[push_nhl] Recent results ({days}d): {len(rows)}")
        return rows
    except Exception as e:
        print(f"[push_nhl] Failed to load recent results: {e}", file=sys.stderr)
        return []


def build_ot_diagnostics() -> dict:
    """
    Shadow OT diagnostic stats for all graded NHL signals.
    Uses nhl_results.parquet (historical) + any graded live rows from nhl_decisions.parquet.
    Joins went_to_ot/went_to_so/reg_total_goals from nhl_games_canonical.csv.
    Reference only — does not affect official W/L/P grading.
    """
    try:
        import numpy as np
        import pandas as pd

        frames = []
        # Historical graded data (Phase 5)
        if RESULTS_P.exists():
            res = pd.read_parquet(RESULTS_P)
            graded_hist = res[res["graded"] == 1].copy()
            if not graded_hist.empty:
                frames.append(graded_hist)
        # Live graded signals
        if DECISIONS.exists():
            dec = pd.read_parquet(DECISIONS)
            graded_live = dec[(dec["split"] == "live") & (dec["graded"] == 1)].copy()
            if not graded_live.empty:
                # Align columns: results has actual_total_goals_final, decisions may not
                frames.append(graded_live)

        if not frames:
            return {}
        merged_all = pd.concat(frames, ignore_index=True)

        # Join OT fields from canonical by game_id
        can_path = NHL_DIR / "nhl_games_canonical.csv"
        if not can_path.exists():
            return {}
        canonical = pd.read_csv(can_path, usecols=[
            "game_id", "went_to_ot", "went_to_so", "reg_total_goals"
        ])
        canonical["game_id"] = canonical["game_id"].astype(int)
        merged_all["game_id"] = merged_all["game_id"].astype(int)
        merged = merged_all.merge(canonical, on="game_id", how="left")

        total    = len(merged)
        ot_games = int(merged["went_to_ot"].fillna(0).sum())
        so_games = int(merged["went_to_so"].fillna(0).sum())
        ot_rate  = round(ot_games / total, 4) if total > 0 else None

        # Compute regulation_result and ot_flip
        ot_flips        = 0
        under_ot_losses = 0
        over_ot_losses  = 0
        for _, r in merged.iterrows():
            went_ot = r.get("went_to_ot")
            if pd.isna(went_ot) or went_ot == 0:
                continue
            reg_total = r.get("reg_total_goals")
            line      = r.get("closing_total")
            side      = r.get("signal_side", "")
            result    = r.get("result", "")
            if pd.isna(reg_total) or pd.isna(line):
                continue
            reg_t = float(reg_total)
            lin   = float(line)
            if reg_t == lin:
                reg_result = "PUSH"
            elif side == "OVER":
                reg_result = "WIN" if reg_t > lin else "LOSS"
            else:
                reg_result = "WIN" if reg_t < lin else "LOSS"
            if result != reg_result:
                ot_flips += 1
            if side == "UNDER" and result == "LOSS":
                under_ot_losses += 1
            if side == "OVER" and result == "LOSS":
                over_ot_losses += 1

        ot_flip_rate = round(ot_flips / ot_games, 4) if ot_games > 0 else None

        out = {
            "total_graded":     total,
            "ot_games":         ot_games,
            "so_games":         so_games,
            "ot_rate":          ot_rate,
            "ot_flips":         ot_flips,
            "ot_flip_rate":     ot_flip_rate,
            "under_ot_losses":  under_ot_losses,
            "over_ot_losses":   over_ot_losses,
        }
        print(f"[push_nhl] OT diagnostics: {ot_games} OT games ({so_games} SO), "
              f"{ot_flips} flips, {under_ot_losses} under OT losses")
        return out
    except Exception as e:
        print(f"[push_nhl] OT diagnostics failed: {e}", file=sys.stderr)
        return {}


def build_season_performance() -> dict:
    """Aggregate WIN/LOSS/PUSH from nhl_results.parquet (Phase 5 historical data)."""
    if not RESULTS_P.exists():
        return {}
    try:
        import numpy as np
        import pandas as pd
        res = pd.read_parquet(RESULTS_P)
        graded = res[res["graded"] == 1]

        def agg(df):
            W = int((df["result"] == "WIN").sum())
            L = int((df["result"] == "LOSS").sum())
            P = int((df["result"] == "PUSH").sum())
            n = W + L + P
            hit = round(W / (W + L), 4) if (W + L) > 0 else None
            roi = round((W * WIN_PER_UNIT - L) / n * 100, 2) if n > 0 else None
            return {"W": W, "L": L, "P": P, "n": n, "hit": hit, "roi": roi}

        out = {}
        for split in ("validate", "oos"):
            out[split] = agg(graded[graded["split"] == split])
        out["combined"] = agg(graded)

        # By confidence tier (combined)
        by_tier = {}
        for tier in ("HIGH", "MEDIUM", "LOW"):
            by_tier[tier] = agg(graded[graded["confidence_tier"] == tier])
        out["by_confidence_tier"] = by_tier

        print(f"[push_nhl] Season performance: combined n={out['combined']['n']}")
        return out
    except Exception as e:
        print(f"[push_nhl] Season performance failed: {e}", file=sys.stderr)
        return {}


def _pipeline_freshness(game_date: str) -> tuple[str, str]:
    """
    Return (pipeline_run_date, signals_source).
    pipeline_run_date: most recent game_date in the live split of decisions parquet.
    signals_source: "live" if pipeline ran today, "stale" if yesterday or earlier.
    """
    if not DECISIONS.exists():
        return game_date, "stale"
    try:
        import pandas as pd
        dec = pd.read_parquet(DECISIONS, columns=["game_date", "split"])
        dec["game_date"] = pd.to_datetime(dec["game_date"]).dt.date.astype(str)
        live = dec[dec["split"] == "live"]
        if live.empty:
            return game_date, "stale"
        most_recent = live["game_date"].max()
        source = "live" if most_recent == game_date else "stale"
        return most_recent, source
    except Exception:
        return game_date, "stale"


def build_clv_summary() -> dict:
    """Compute CLV summary from nhl_decisions.parquet joined with nhl_market_snapshots.parquet."""
    NHL_SNAP = Path(__file__).parent / "nhl" / "nhl_clv_snapshots.parquet"
    if not DECISIONS.exists() or not NHL_SNAP.exists():
        return {}
    try:
        import pandas as pd
        dec  = pd.read_parquet(DECISIONS)
        snaps = pd.read_parquet(NHL_SNAP)
        graded = dec[(dec["split"] == "live") & (dec["graded"] == 1)].copy()
        if graded.empty:
            return {}
        # morning lines
        morning = snaps[snaps["snapshot_type"] == "morning"][["game_id", "line"]].rename(columns={"line": "line_taken"})
        pregame = snaps[snaps["snapshot_type"] == "pregame"][["game_id", "line"]].rename(columns={"line": "closing_line"})
        graded["game_id"] = graded["game_id"].astype(str)
        morning["game_id"] = morning["game_id"].astype(str)
        pregame["game_id"] = pregame["game_id"].astype(str)
        graded = graded.merge(morning, on="game_id", how="left")
        graded = graded.merge(pregame, on="game_id", how="left")
        # compute clv_directional
        def _clv_dir(row):
            lt = row.get("line_taken")
            cl = row.get("closing_line")
            if pd.isna(lt) or pd.isna(cl):
                return None
            if row.get("signal_side") == "OVER":
                return round(float(cl) - float(lt), 2)
            else:
                return round(float(lt) - float(cl), 2)
        graded["clv_directional"] = graded.apply(_clv_dir, axis=1)
        has_clv = graded.dropna(subset=["clv_directional"])
        n_clv   = len(has_clv)
        n_total = len(graded)
        coverage = round(n_clv / n_total * 100, 1) if n_total > 0 else 0.0
        if n_clv == 0:
            return {"total_with_clv": 0, "avg_clv": None, "median_clv": None,
                    "pct_positive_clv": None, "avg_clv_by_tier": {}, "avg_clv_by_side": {},
                    "clv_coverage": coverage}
        avg_clv    = round(float(has_clv["clv_directional"].mean()), 3)
        median_clv = round(float(has_clv["clv_directional"].median()), 3)
        pct_pos    = round(float((has_clv["clv_directional"] > 0).mean() * 100), 1)
        by_tier = {}
        for tier in ["HIGH", "MEDIUM", "LOW"]:
            sub = has_clv[has_clv["confidence_tier"] == tier]
            by_tier[tier] = round(float(sub["clv_directional"].mean()), 3) if len(sub) > 0 else None
        by_side = {}
        for side in ["OVER", "UNDER"]:
            sub = has_clv[has_clv["signal_side"] == side]
            by_side[side] = round(float(sub["clv_directional"].mean()), 3) if len(sub) > 0 else None
        print(f"[push_nhl] CLV summary: n={n_clv}, avg={avg_clv:+.3f}, coverage={coverage:.0f}%")
        return {"total_with_clv": n_clv, "avg_clv": avg_clv, "median_clv": median_clv,
                "pct_positive_clv": pct_pos, "avg_clv_by_tier": by_tier,
                "avg_clv_by_side": by_side, "clv_coverage": coverage}
    except Exception as e:
        print(f"[push_nhl] CLV summary failed: {e}", file=sys.stderr)
        return {}


def write_nhl_json(game_date: str = None) -> str:
    """Write nhl_results.json and return path. Does NOT git push."""
    import sys as _sys
    sys.path.insert(0, str(REPO_DIR / "nhl"))
    try:
        from nhl_summaries import generate_nhl_summary
    except ImportError as e:
        print(f"[push_nhl] WARNING: could not import nhl_summaries: {e}", file=sys.stderr)
        generate_nhl_summary = None  # type: ignore

    game_date = game_date or date.today().isoformat()

    today_signals   = load_today_signals(game_date)
    recent_results  = load_recent_results(days=14)
    season_perf     = build_season_performance()
    ot_diag         = build_ot_diagnostics()
    clv_summary     = build_clv_summary()

    # Generate plain-English summaries for today's signals
    if generate_nhl_summary is not None:
        for s in today_signals:
            try:
                s["summary"] = generate_nhl_summary(s)
            except Exception as e:
                s["summary"] = ""
                print(f"[push_nhl] Summary generation failed for {s.get('away_team')} @ "
                      f"{s.get('home_team')}: {e}", file=sys.stderr)
    else:
        for s in today_signals:
            s["summary"] = ""

    # Sort today's signals: HIGH first, then by edge desc
    tier_order = {"HIGH": 0, "MEDIUM": 1, "SHADOW_MEDIUM": 2, "LOW": 3, "SHADOW_LOW": 4}
    today_signals.sort(key=lambda s: (
        tier_order.get(s.get("confidence_tier", "LOW"), 2),
        -(s.get("edge") or 0),
    ))

    # FIX 5: data freshness fields
    now_utc = datetime.now(timezone.utc)
    pipeline_run_date, signals_source = _pipeline_freshness(game_date)

    # ── FIX 6: pre-serialization consistency audit ────────────────────────────
    quality_warning = False
    warnings_found  = []

    # Top-level type assertions
    if not isinstance(today_signals, list):
        warnings_found.append(f"today_signals is not a list: {type(today_signals)}")
        today_signals = []
        quality_warning = True

    if not isinstance(recent_results, list):
        warnings_found.append(f"recent_results is not a list: {type(recent_results)}")
        recent_results = []
        quality_warning = True

    if not season_perf:
        warnings_found.append("season_performance is empty or missing")
        quality_warning = True

    # Per-signal field assertions
    valid_sides = {"OVER", "UNDER"}
    valid_tiers = {"HIGH", "MEDIUM", "SHADOW_MEDIUM", "LOW", "SHADOW_LOW"}
    for i, s in enumerate(today_signals):
        if s.get("game_id") is None:
            warnings_found.append(f"signal[{i}]: game_id is null")
            quality_warning = True
        if s.get("closing_total") is None:
            warnings_found.append(f"signal[{i}]: closing_total is null")
            quality_warning = True
        edge = s.get("edge")
        if edge is None or not isinstance(edge, (int, float)) or not (0.0 <= edge <= 1.0):
            warnings_found.append(f"signal[{i}]: edge={edge!r} not in [0,1]")
            quality_warning = True
        if s.get("signal_side") not in valid_sides:
            warnings_found.append(f"signal[{i}]: signal_side={s.get('signal_side')!r} invalid")
            quality_warning = True
        if s.get("confidence_tier") not in valid_tiers:
            warnings_found.append(f"signal[{i}]: confidence_tier={s.get('confidence_tier')!r} invalid")
            quality_warning = True

    for w in warnings_found:
        print(f"[push_nhl] DATA QUALITY WARNING: {w}", file=sys.stderr)

    payload = {
        "generated_at":        now_utc.isoformat(),
        "last_updated":        now_utc.strftime("%Y-%m-%d %H:%M UTC"),
        "pipeline_run_date":   pipeline_run_date,
        "signals_source":      signals_source,
        "game_date":           game_date,
        "today_signals":       today_signals,
        "recent_results":      recent_results,
        "season_performance":  season_perf,
        "ot_diagnostics":      ot_diag,
        "clv_summary":         clv_summary,
        "data_quality_warning": quality_warning,
    }

    # AI daily (and optional weekly) review
    try:
        from modules.ai_review import (build_graded_games, generate_daily_review,
                                        maybe_weekly, build_week_games,
                                        generate_weekly_review, is_idempotent)
        _review_date = (date.fromisoformat(game_date) - timedelta(days=1)).isoformat()
        if not is_idempotent(str(OUT_PATH), _review_date):
            _graded = build_graded_games("nhl", _review_date)
            payload["daily_review"] = generate_daily_review(_graded, "nhl", _review_date)
        else:
            print(f"[push_nhl] NHL daily review already exists for {_review_date} — skipping")
        _wr = maybe_weekly("nhl")
        if _wr:
            _wg = build_week_games("nhl", *_wr)
            payload["weekly_review"] = generate_weekly_review(_wg, "nhl", *_wr)
    except Exception as e:
        print(f"[push_nhl] NHL AI review failed (non-fatal): {e}", file=sys.stderr)

    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2, default=str)

    perf_rows = len(season_perf) if season_perf else 0
    print(
        f"[push_nhl] complete: {len(today_signals)} signals, "
        f"{len(recent_results)} recent results, "
        f"{perf_rows} performance rows, "
        f"quality_warning={str(quality_warning).lower()}"
    )
    print(f"[push_nhl] Wrote {OUT_PATH}")
    return str(OUT_PATH)


def git_push(game_date: str) -> bool:
    def run(cmd):
        result = subprocess.run(cmd, cwd=str(REPO_DIR), capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  [git error] {' '.join(cmd)}\n  {result.stderr.strip()}",
                  file=sys.stderr)
            return False
        return True

    run(["git", "add", "nhl_results.json"])
    status = subprocess.run(
        ["git", "status", "--porcelain", "nhl_results.json"],
        cwd=str(REPO_DIR), capture_output=True, text=True,
    )
    if not status.stdout.strip():
        print("[push_nhl] Nothing to commit — nhl_results.json unchanged.")
        return True
    if not run(["git", "commit", "-m", f"nhl: {game_date}"]):
        return False
    if not run(["git", "push"]):
        return False
    print("[push_nhl] Pushed successfully.")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date",    default=None)
    parser.add_argument("--no-push", action="store_true")
    args = parser.parse_args()
    write_nhl_json(args.date)
    if not args.no_push:
        git_push(args.date or date.today().isoformat())


if __name__ == "__main__":
    main()
