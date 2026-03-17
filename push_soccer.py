#!/usr/bin/env python3
"""
push_soccer.py — Serialize Soccer OVER specialist signals to soccer_results.json.

Called from run_daily.py (7am) or standalone.

Usage:
    python push_soccer.py              # serialize + push
    python push_soccer.py --no-push    # serialize only
    python push_soccer.py --date 2026-03-16
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO_DIR      = Path(__file__).parent
SOCCER_DIR    = REPO_DIR / "soccer"
DECISIONS     = SOCCER_DIR / "data" / "soccer_decisions.parquet"
ODDS_CACHE    = SOCCER_DIR / "data" / "cache" / "daily"
OUT_PATH      = REPO_DIR / "soccer_results.json"

_SPORT_KEYS   = {"EPL": "soccer_epl", "BUN": "soccer_germany_bundesliga"}

WIN_PER_UNIT  = 100.0 / 110.0

# OOS performance reference (for dashboard display)
OOS_STATS = {
    "overall":       {"hit": 0.567, "roi": 0.083, "n": 356},
    "HIGH":          {"hit": 0.617, "roi": 0.178, "n": 154},
    "MEDIUM":        {"hit": 0.544, "roi": 0.039, "n":  68},
    "LOW":           {"hit": 0.536, "roi": 0.023, "n":  56},
}


def _safe(v):
    if v is None:
        return None
    if hasattr(v, "item"):
        return v.item()
    if isinstance(v, float) and v != v:  # NaN
        return None
    return v


def _last_run_label(data: dict) -> str:
    ts = data.get("generated_at")
    if not ts:
        return "never"
    try:
        from zoneinfo import ZoneInfo
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.astimezone(ZoneInfo("America/New_York")).strftime("%b %-d at %-I:%M %p ET")
    except Exception:
        return ts


# ---------------------------------------------------------------------------
# Signal generation
# ---------------------------------------------------------------------------
def generate_soccer_summary(s: dict) -> str:
    """
    Plain-English OVER 2.5 signal summary.
    Lead with strongest factor, close with edge sentence.
    """
    home = s.get("home_team", "")
    away = s.get("away_team", "")
    tier = s.get("confidence_tier", "LOW")
    edge = s.get("edge", 0.0)
    model_total = s.get("model_total", 2.9)
    move = s.get("market_move_to_over_2_5", 0.0)

    h_xg  = s.get("home_xg_for_rolling_10")
    a_xg  = s.get("away_xg_for_rolling_10")
    h_gs  = s.get("home_goals_scored_rolling_5")
    a_gs  = s.get("away_goals_scored_rolling_5")
    wind  = s.get("weather_wind_kph")
    temp  = s.get("weather_temp_c")

    factors = []

    # xG attacking quality
    if h_xg and a_xg and h_xg > 1.5 and a_xg > 1.2:
        factors.append(
            f"{home} (xG {h_xg:.1f}/game) and {away} (xG {a_xg:.1f}/game) "
            f"both carry strong attacking threat"
        )
    elif h_xg and h_xg > 1.6:
        factors.append(f"{home} has been generating {h_xg:.1f} xG per game at home")
    elif a_xg and a_xg > 1.5:
        factors.append(f"{away} has been producing {a_xg:.1f} xG per game on the road")

    # Recent goal form
    if h_gs and a_gs and h_gs > 1.5 and a_gs > 1.2:
        factors.append(
            f"both sides are in scoring form ({home} averaging {h_gs:.1f} g/game, "
            f"{away} {a_gs:.1f} g/game)"
        )
    elif h_gs and h_gs > 1.8:
        factors.append(f"{home} has found the net {h_gs:.1f} times per game over their last 5")
    elif a_gs and a_gs > 1.6:
        factors.append(f"{away} is averaging {a_gs:.1f} goals per game over their last 5")

    # Market confirmation
    if move and move > 0.03:
        factors.append(
            f"late money has pushed the market further toward the over ({move:+.0%} move)"
        )

    # Weather (mild positive for indoor-ish or neutral conditions)
    if wind and wind > 20 and not (wind > 30):
        factors.append(f"light breeze at {wind:.0f} kph won't significantly affect play")

    # Fallback if no factors found
    if not factors:
        factors.append(
            f"the model finds {away} @ {home} underpriced on the over relative to market"
        )

    # Build the summary
    lead = factors[0].capitalize()
    supporting = ""
    if len(factors) > 1:
        supporting = "; ".join(factors[1:]) + ". "

    edge_pct   = edge * 100
    over_by    = max(model_total - 2.5, 0)
    tier_label = {"HIGH": "high", "MEDIUM": "medium", "LOW": "low"}.get(tier, "low")

    close = (
        f"Model projects {model_total:.1f} goals, market is at 2.5 — "
        f"over by {over_by:.1f} goals ({tier_label} confidence, +{edge_pct:.0f}pp edge)."
    )

    return f"{lead}. {supporting}{close}"


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------
def load_today_signals(game_date: str) -> list[dict]:
    if not DECISIONS.exists():
        return []
    try:
        dec = pd.read_parquet(DECISIONS)
        # Old schema compatibility: if no "split" column, treat all rows as historical
        if "split" not in dec.columns:
            return []
        dec["game_date"] = pd.to_datetime(dec["game_date"]).dt.date.astype(str)
        today = dec[
            (dec["game_date"] == game_date) &
            (dec["split"] == "live")
        ]
        rows = []
        for _, r in today.iterrows():
            rows.append({
                "game_id":           _safe(r.get("game_id")),
                "game_date":         r.get("game_date"),
                "league_id":         r.get("league_id"),
                "home_team":         r.get("home_team"),
                "away_team":         r.get("away_team"),
                "game_time_et":      r.get("game_time_et", ""),
                "signal_side":       "OVER",
                "closing_total":     2.5,
                "edge":              _safe(r.get("edge")),
                "confidence_tier":   r.get("confidence_tier"),
                "model_total":       _safe(r.get("model_total")),
                "market_move_to_over_2_5": _safe(r.get("market_move_to_over_2_5")),
                "lineup_confirmed":  bool(r.get("lineup_confirmed", False)),
                "market_fair_p_over_2_5": _safe(r.get("market_fair_p_over_2_5")),
                "over_price":        _safe(r.get("over_price")),
                "under_price":       _safe(r.get("under_price")),
                "result":            r.get("result"),
                "graded":            int(r.get("graded") or 0),
                # For summaries
                "home_xg_for_rolling_10":    _safe(r.get("home_xg_for_rolling_10")),
                "away_xg_for_rolling_10":    _safe(r.get("away_xg_for_rolling_10")),
                "home_goals_scored_rolling_5": _safe(r.get("home_goals_scored_rolling_5")),
                "away_goals_scored_rolling_5": _safe(r.get("away_goals_scored_rolling_5")),
                "weather_wind_kph":  _safe(r.get("weather_wind_kph")),
                "weather_temp_c":    _safe(r.get("weather_temp_c")),
            })
        print(f"[push_soccer] Today's signals: {len(rows)}")
        return rows
    except Exception as e:
        print(f"[push_soccer] Failed to load today signals: {e}", file=sys.stderr)
        return []


def load_recent_results(days: int = 14) -> list[dict]:
    if not DECISIONS.exists():
        return []
    try:
        dec = pd.read_parquet(DECISIONS)
        if "split" not in dec.columns or "graded" not in dec.columns:
            return []
        dec["game_date"] = pd.to_datetime(dec["game_date"]).dt.date
        cutoff = date.today() - timedelta(days=days)
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
                "league_id":        r.get("league_id"),
                "home_team":        r.get("home_team"),
                "away_team":        r.get("away_team"),
                "signal_side":      "OVER",
                "closing_total":    2.5,
                "edge":             _safe(r.get("edge")),
                "confidence_tier":  r.get("confidence_tier"),
                "result":           r.get("result"),
                "actual_total_goals": _safe(r.get("actual_total_goals")),
            })
        print(f"[push_soccer] Recent results ({days}d): {len(rows)}")
        return rows
    except Exception as e:
        print(f"[push_soccer] Failed to load recent results: {e}", file=sys.stderr)
        return []


def build_season_performance() -> dict:
    """Aggregate live graded signals."""
    if not DECISIONS.exists():
        return {"oos_reference": OOS_STATS}

    try:
        dec = pd.read_parquet(DECISIONS)
        if "split" not in dec.columns or "graded" not in dec.columns:
            return {"oos_reference": OOS_STATS}
        graded = dec[(dec["split"] == "live") & (dec["graded"] == 1)]

        def agg(df):
            W = int((df["result"] == "WIN").sum())
            L = int((df["result"] == "LOSS").sum())
            P = int((df["result"] == "PUSH").sum())
            n = W + L + P
            hit = round(W / (W + L), 4) if (W + L) > 0 else None
            roi = round((W * WIN_PER_UNIT - L) / n * 100, 2) if n > 0 else None
            return {"W": W, "L": L, "P": P, "n": n, "hit": hit, "roi": roi}

        out: dict = {}
        out["overall"] = agg(graded)

        # By tier
        by_tier = {}
        for tier in ("HIGH", "MEDIUM", "LOW"):
            by_tier[tier] = agg(graded[graded["confidence_tier"] == tier])
        out["by_tier"] = by_tier

        # By league
        by_league = {}
        for lg in ("EPL", "BUN"):
            by_league[lg] = agg(graded[graded["league_id"] == lg])
        out["by_league"] = by_league

        # By edge bucket
        by_bucket = {}
        for lo, hi in [(0.06, 0.08), (0.08, 0.10), (0.10, 1.0)]:
            label = f"{lo:.2f}-{hi:.2f}" if hi < 1 else "0.10+"
            sub = graded[
                (graded["edge"] >= lo) & (graded["edge"] < hi)
            ]
            by_bucket[label] = agg(sub)
        out["by_edge_bucket"] = by_bucket

        # Market movement filter impact
        if "market_move_to_over_2_5" in graded.columns:
            with_confirm  = graded[graded["market_move_to_over_2_5"] > 0.03]
            no_move       = graded[graded["market_move_to_over_2_5"].abs() <= 0.03]
            out["market_movement"] = {
                "late_over_confirmation": agg(with_confirm),
                "no_significant_movement": agg(no_move),
            }

        # OOS reference
        out["oos_reference"] = OOS_STATS

        print(f"[push_soccer] Season performance: n={out['overall']['n']}")
        return out
    except Exception as e:
        print(f"[push_soccer] Season performance failed: {e}", file=sys.stderr)
        return {"oos_reference": OOS_STATS}


def _pipeline_freshness(game_date: str) -> tuple[str, str]:
    if not DECISIONS.exists():
        return game_date, "stale"
    try:
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


# ---------------------------------------------------------------------------
# Over 1.5 parlay candidates (entertainment/parlay-support only)
# ---------------------------------------------------------------------------
_BOOK_PRIORITY = ["bet365", "pinnacle", "betfair", "unibet", "williamhill"]


def _name_matches(a: str, b: str) -> bool:
    a, b = a.lower(), b.lower()
    return a in b or b in a or any(w in b for w in a.split() if len(w) > 4)


def _parse_1_5_odds_for_game(home_team: str, away_team: str,
                              game_date: str, league_id: str) -> dict:
    """
    Read today's cached odds JSON and find the 1.5 over/under line.
    Returns dict with {point, over_price, under_price, fair_over} or {}.
    Uses same bookmaker priority as the main pipeline.
    """
    sport = _SPORT_KEYS.get(league_id)
    if not sport:
        return {}
    cache_file = ODDS_CACHE / f"odds_{sport}_{game_date}.json"
    if not cache_file.exists():
        return {}
    try:
        odds_data = json.loads(cache_file.read_text())
    except Exception:
        return {}

    for game in odds_data:
        ht = game.get("home_team", "")
        at = game.get("away_team", "")
        if not (_name_matches(home_team, ht) and _name_matches(away_team, at)):
            continue
        bookmakers = sorted(
            game.get("bookmakers", []),
            key=lambda b: next(
                (i for i, bk in enumerate(_BOOK_PRIORITY) if bk in b.get("key", "")),
                len(_BOOK_PRIORITY),
            ),
        )
        for bm in bookmakers:
            for mkt in bm.get("markets", []):
                if mkt.get("key") != "totals":
                    continue
                over_price = under_price = None
                for o in mkt.get("outcomes", []):
                    if abs(o.get("point", 0) - 1.5) > 0.01:
                        continue
                    name = o.get("name", "").lower()
                    price = o.get("price")
                    if price and "over" in name:
                        over_price = price
                    elif price and "under" in name:
                        under_price = price
                if over_price and under_price and over_price > 1.0 and under_price > 1.0:
                    imp_o = 1.0 / over_price
                    imp_u = 1.0 / under_price
                    total = imp_o + imp_u
                    return {
                        "point": 1.5,
                        "over_price":  round(over_price, 3),
                        "under_price": round(under_price, 3),
                        "fair_over":   round(imp_o / total, 4),
                    }
    return {}


def load_parlay_candidates(game_date: str) -> list[dict]:
    """
    Over 1.5 parlay candidates — ENTERTAINMENT / PARLAY-SUPPORT ONLY.
    Not validated for standalone betting. Completely isolated from main signals.

    Threshold: model_p_over_1_5 >= 0.80 AND projected_total >= 3.2
    market_edge suppression: hide candidate if edge_1_5 < -0.05
    """
    from scipy.stats import poisson as _poisson

    if not DECISIONS.exists():
        return []
    try:
        dec = pd.read_parquet(DECISIONS)
        if "split" not in dec.columns:
            return []
        dec["game_date"] = pd.to_datetime(dec["game_date"]).dt.date.astype(str)
        today_games = dec[
            (dec["game_date"] == game_date) & (dec["split"] == "live")
        ].copy()
        if today_games.empty:
            return []

        candidates = []
        for _, r in today_games.iterrows():
            model_total = _safe(r.get("model_total"))
            if model_total is None or (isinstance(model_total, float) and model_total != model_total):
                continue  # NaN or missing

            # P(X >= 2) using Poisson CDF — exact equivalent of simulation sum
            model_p_over_1_5 = float(1.0 - _poisson.cdf(1, model_total))

            if model_p_over_1_5 < 0.80 or model_total < 3.2:
                continue

            tier = (
                "VERY HIGH"
                if model_p_over_1_5 >= 0.85 and model_total >= 3.5
                else "HIGH"
            )

            home_team = r.get("home_team", "")
            away_team = r.get("away_team", "")
            league_id = r.get("league_id", "")

            odds_1_5 = _parse_1_5_odds_for_game(home_team, away_team, game_date, league_id)
            market_line_1_5     = odds_1_5.get("point")
            market_implied_p_1_5 = odds_1_5.get("fair_over")
            edge_1_5 = None
            if market_implied_p_1_5 is not None:
                edge_1_5 = round(model_p_over_1_5 - market_implied_p_1_5, 4)
                if edge_1_5 < -0.05:
                    continue  # Market strongly disagrees — suppress

            candidates.append({
                "game_id":              _safe(r.get("game_id")),
                "game_date":            game_date,
                "league":               league_id,
                "home_team":            home_team,
                "away_team":            away_team,
                "game_time_et":         r.get("game_time_et", ""),
                "projected_total":      round(float(model_total), 2),
                "model_p_over_1_5":     round(model_p_over_1_5, 4),
                "confidence_tier":      tier,
                "market_line_1_5":      market_line_1_5,
                "market_implied_p_1_5": round(market_implied_p_1_5, 4) if market_implied_p_1_5 is not None else None,
                "edge_1_5":             edge_1_5,
                "lineup_confirmed":     bool(r.get("lineup_confirmed", False)),
            })

        candidates.sort(key=lambda c: -(c.get("model_p_over_1_5") or 0))
        print(f"[push_soccer] Parlay candidates (Over 1.5): {len(candidates)}")
        return candidates

    except Exception as e:
        print(f"[push_soccer] Parlay candidates failed: {e}", file=sys.stderr)
        return []


# ---------------------------------------------------------------------------
# JSON writer
# ---------------------------------------------------------------------------
def write_soccer_json(game_date: str | None = None) -> str:
    game_date = game_date or date.today().isoformat()

    today_signals     = load_today_signals(game_date)
    recent_results    = load_recent_results(days=14)
    season_perf       = build_season_performance()
    parlay_candidates = load_parlay_candidates(game_date)

    # Generate plain-English summaries
    for s in today_signals:
        try:
            s["summary"] = generate_soccer_summary(s)
        except Exception as e:
            s["summary"] = ""
            print(f"[push_soccer] Summary failed: {e}", file=sys.stderr)

    # Sort by edge descending (HIGH first, then by edge)
    tier_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    today_signals.sort(key=lambda s: (
        tier_order.get(s.get("confidence_tier", "LOW"), 2),
        -(s.get("edge") or 0),
    ))

    now_utc = datetime.now(timezone.utc)
    pipeline_run_date, signals_source = _pipeline_freshness(game_date)

    # Quality check
    quality_warning = False
    warnings_found  = []
    valid_tiers = {"HIGH", "MEDIUM", "LOW"}

    for i, s in enumerate(today_signals):
        if s.get("game_id") is None:
            warnings_found.append(f"signal[{i}]: game_id null")
            quality_warning = True
        edge = s.get("edge")
        if edge is None or not isinstance(edge, (int, float)) or not (0.0 <= edge <= 1.0):
            warnings_found.append(f"signal[{i}]: edge={edge!r} invalid")
            quality_warning = True
        if s.get("confidence_tier") not in valid_tiers:
            warnings_found.append(f"signal[{i}]: tier={s.get('confidence_tier')!r} invalid")
            quality_warning = True

    for w in warnings_found:
        print(f"[push_soccer] DATA QUALITY WARNING: {w}", file=sys.stderr)

    payload = {
        "generated_at":       now_utc.isoformat(),
        "last_updated":       now_utc.strftime("%Y-%m-%d %H:%M UTC"),
        "pipeline_run_date":  pipeline_run_date,
        "signals_source":     signals_source,
        "game_date":          game_date,
        "deployment_start_date": "2026-03-17",
        "model_description":  "Soccer Over 2.5 Specialist (V2.2 Ridge). OVER signals only.",
        "today_signals":      today_signals,
        "recent_results":     recent_results,
        "season_performance": season_perf,
        "data_quality_warning": quality_warning,
        # Entertainment/parlay-support only — not a validated standalone product
        "parlay_candidates":  parlay_candidates,
    }

    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2, default=str)

    print(
        f"[push_soccer] complete: {len(today_signals)} signals, "
        f"{len(recent_results)} recent results, "
        f"{len(parlay_candidates)} parlay candidates, "
        f"quality_warning={str(quality_warning).lower()}"
    )
    print(f"[push_soccer] Wrote {OUT_PATH}")
    return str(OUT_PATH)


def git_push(game_date: str) -> bool:
    def run(cmd):
        result = subprocess.run(cmd, cwd=str(REPO_DIR), capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  [git error] {' '.join(cmd)}\n  {result.stderr.strip()}", file=sys.stderr)
            return False
        return True

    run(["git", "add", "soccer_results.json"])
    status = subprocess.run(
        ["git", "status", "--porcelain", "soccer_results.json"],
        cwd=str(REPO_DIR), capture_output=True, text=True,
    )
    if not status.stdout.strip():
        print("[push_soccer] Nothing to commit — soccer_results.json unchanged.")
        return True
    if not run(["git", "commit", "-m", f"soccer: {game_date}"]):
        return False
    if not run(["git", "push"]):
        return False
    print("[push_soccer] Pushed successfully.")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date",    default=None)
    parser.add_argument("--no-push", action="store_true")
    args = parser.parse_args()
    write_soccer_json(args.date)
    if not args.no_push:
        git_push(args.date or date.today().isoformat())


if __name__ == "__main__":
    main()
