#!/usr/bin/env python3
"""
push_nba.py — Serialize NBA projections + season accuracy to nba_results.json and push to GitHub.

Called automatically from push_results.py (daily 7am run) or standalone.

Usage:
    python push_nba.py              # serialize + push
    python push_nba.py --no-push    # serialize only, skip git
    python push_nba.py --date 2026-03-14
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import date, datetime

REPO_DIR     = os.path.dirname(os.path.abspath(__file__))
OUT_PATH     = os.path.join(REPO_DIR, "nba_results.json")

NBA_PROJ_PATH    = os.path.join(REPO_DIR, "nba", "data", "nba_daily_projections.parquet")
NBA_RESULTS_PATH = os.path.join(REPO_DIR, "nba", "data", "nba_results_log.parquet")


def _safe(v):
    if v is None:
        return None
    if hasattr(v, "item"):        # numpy scalar
        return v.item()
    if isinstance(v, float) and (v != v):  # NaN
        return None
    return v


def load_today_projections(game_date: str) -> list[dict]:
    if not os.path.exists(NBA_PROJ_PATH):
        return []
    try:
        import pandas as pd
        df = pd.read_parquet(NBA_PROJ_PATH)
        today = df[df["game_date"] == game_date]
        if today.empty:
            print(f"[push_nba] No NBA projections found for {game_date}")
            return []
        rows = []
        for _, r in today.iterrows():
            rows.append({
                "game_date":    r.get("game_date"),
                "game_id":      r.get("game_id"),
                "home_team":    r.get("home_team"),
                "away_team":    r.get("away_team"),
                "game_time_et": r.get("game_time_et"),
                "pred_total":   _safe(r.get("pred_total")),
                "lean":         r.get("lean"),
                "p_over":       _safe(r.get("p_over")),
                "confidence":   r.get("confidence"),
                "line":         _safe(r.get("line")),
                "edge":         _safe(r.get("edge")),
                "market_gap_flag": bool(r.get("market_gap_flag")),
                "pred_h1":      _safe(r.get("pred_h1")),
                "h1_lean":      r.get("h1_lean"),
                "h1_p_over":    _safe(r.get("h1_p_over")),
                "h1_confidence":r.get("h1_confidence"),
                "h1_line":      _safe(r.get("h1_line")),
                "h1_edge":      _safe(r.get("h1_edge")),
                "rolling_league_avg":    _safe(r.get("rolling_league_avg")),
                "rolling_h1_league_avg": _safe(r.get("rolling_h1_league_avg")),
                # Team features (may be absent in older parquets → None)
                "home_ortg":    _safe(r.get("home_ortg")),
                "away_ortg":    _safe(r.get("away_ortg")),
                "home_drtg":    _safe(r.get("home_drtg")),
                "away_drtg":    _safe(r.get("away_drtg")),
                "home_pace":    _safe(r.get("home_pace")),
                "away_pace":    _safe(r.get("away_pace")),
                "home_3pa_rate":_safe(r.get("home_3pa_rate")),
                "away_3pa_rate":_safe(r.get("away_3pa_rate")),
                "home_ft_rate": _safe(r.get("home_ft_rate")),
                "away_ft_rate": _safe(r.get("away_ft_rate")),
                "b2b_flag_away":bool(r.get("b2b_flag_away")),
                "home_injuries":[x for x in str(r.get("home_injuries_str") or "").split(",") if x],
                "away_injuries":[x for x in str(r.get("away_injuries_str") or "").split(",") if x],
            })
        print(f"[push_nba] Loaded {len(rows)} projections for {game_date}")
        return rows
    except Exception as e:
        print(f"[push_nba] Failed to load projections: {e}", file=sys.stderr)
        return []


def build_season_accuracy() -> dict:
    """Compute running MAE + directional HR from nba_results_log.parquet."""
    if not os.path.exists(NBA_RESULTS_PATH):
        return {}
    try:
        import pandas as pd
        log = pd.read_parquet(NBA_RESULTS_PATH)
        if log.empty:
            return {}

        out = {"total_games": int(len(log))}

        by_conf = {}
        for conf in ["HIGH", "MEDIUM", "LOW"]:
            sub = log[log["confidence"] == conf]
            if len(sub) == 0:
                continue
            mae  = float(sub["full_err"].abs().mean())
            hr   = float(sub["full_correct"].mean() * 100)
            bias = float(sub["full_err"].mean())
            by_conf[conf] = {
                "n":    int(len(sub)),
                "mae":  round(mae, 2),
                "hr":   round(hr, 1),
                "bias": round(bias, 2),
            }

        # Overall
        mae_all  = float(log["full_err"].abs().mean())
        hr_all   = float(log["full_correct"].mean() * 100)
        bias_all = float(log["full_err"].mean())
        out["overall"] = {
            "n":    int(len(log)),
            "mae":  round(mae_all, 2),
            "hr":   round(hr_all, 1),
            "bias": round(bias_all, 2),
        }
        out["by_confidence"] = by_conf

        # Market gap count
        if "market_gap_flag" in log.columns:
            out["market_gap_count"] = int(log["market_gap_flag"].sum())

        print(f"[push_nba] Season accuracy: {len(log)} games graded. "
              f"Overall MAE={mae_all:.2f} HR={hr_all:.1f}%")
        return out
    except Exception as e:
        print(f"[push_nba] Season accuracy failed: {e}", file=sys.stderr)
        return {}


# ── Summary generation ─────────────────────────────────────────────────────────
# League-average benchmarks (from nba/config.py — duplicated here so push_nba.py
# has no runtime dependency on the full NBA package).
_NBA_PACE_AVG   = 101.4
_NBA_PACE_FAST  = 102.5   # above → fast pace game
_NBA_PACE_SLOW  = 100.0   # below → slow pace game
_NBA_ORTG_GOOD  = 114.0   # above → efficient offense
_NBA_DRTG_GOOD  = 110.5   # below → good defense (lower is better)
_NBA_DRTG_WEAK  = 114.0   # above → weak defense
_NBA_3PA_HEAVY  = 0.39    # above → heavy 3-point volume


def _nba_summary_driver(lean: str, home: str, away: str,
                        avg_pace, home_drtg, away_drtg, avg_ortg,
                        b2b: bool, away_team: str) -> str:
    """Build the first sentence describing the primary reason for the lean."""
    if lean == "OVER":
        if avg_pace and avg_pace >= _NBA_PACE_FAST:
            return (f"{home} and {away} both run at an above-average pace, "
                    f"generating high possession counts.")
        if avg_ortg and avg_ortg >= _NBA_ORTG_GOOD:
            return (f"Both {home} and {away} rank among the league's more "
                    f"efficient offenses this season.")
        if home_drtg and away_drtg and max(home_drtg, away_drtg) >= _NBA_DRTG_WEAK:
            weaker = home if (home_drtg or 0) > (away_drtg or 0) else away
            return (f"{weaker}'s defense has struggled to contain opponents, "
                    f"leaving points on the table.")
    elif lean == "UNDER":
        if home_drtg and away_drtg and max(home_drtg, away_drtg) <= _NBA_DRTG_GOOD:
            return (f"Both {home} and {away} feature above-average defenses, "
                    f"keeping this total in check.")
        if home_drtg and home_drtg <= _NBA_DRTG_GOOD:
            return (f"{home}'s defense has been among the stingiest in the league, "
                    f"limiting opponent scoring.")
        if away_drtg and away_drtg <= _NBA_DRTG_GOOD:
            return (f"{away}'s defense has been elite at suppressing totals "
                    f"this season.")
        if avg_pace and avg_pace <= _NBA_PACE_SLOW:
            return (f"Both {home} and {away} play at a below-average pace, "
                    f"naturally suppressing the total scoring output.")
        if b2b:
            return (f"{away_team} is on the second night of a back-to-back, "
                    f"limiting offensive output.")
    return ""


def generate_nba_summary(g: dict) -> str:
    """
    Build a 1-4 sentence natural-language summary from model features.
    Template-based — no external API calls.
    """
    home     = g.get("home_team", "")
    away     = g.get("away_team", "")
    lean     = g.get("lean", "")
    pred     = g.get("pred_total")
    line     = g.get("line")
    edge     = g.get("edge")
    p_over   = g.get("p_over")
    conf     = g.get("confidence", "LOW")
    b2b      = bool(g.get("b2b_flag_away"))
    home_inj = g.get("home_injuries") or []
    away_inj = g.get("away_injuries") or []
    gap      = bool(g.get("market_gap_flag"))

    home_pace = g.get("home_pace")
    away_pace = g.get("away_pace")
    home_ortg = g.get("home_ortg")
    away_ortg = g.get("away_ortg")
    home_drtg = g.get("home_drtg")
    away_drtg = g.get("away_drtg")
    home_3pa  = g.get("home_3pa_rate")
    away_3pa  = g.get("away_3pa_rate")

    if pred is None:
        return "Insufficient data to generate projection summary."

    pred_s = f"{pred:.1f}"
    line_s = f"{line:.1f}" if line is not None else None

    # ── NO PLAY ──────────────────────────────────────────────────────────────
    if conf == "LOW":
        if line_s is None:
            return (f"Model projects {pred_s} with no market reference available. "
                    f"No clear edge — pass.")
        abs_edge = abs(edge or 0)
        if abs_edge < 3:
            return (f"Model projects {pred_s}, close to the market line of {line_s}. "
                    f"No meaningful edge — pass.")
        return (f"Model projects {pred_s} vs market line of {line_s} "
                f"(edge {edge:+.1f} pts). Confidence too low — pass.")

    # ── PLAY (HIGH or MEDIUM) ────────────────────────────────────────────────
    avg_pace = (home_pace + away_pace) / 2 if (home_pace and away_pace) else None
    avg_ortg = (home_ortg + away_ortg) / 2 if (home_ortg and away_ortg) else None
    avg_3pa  = (home_3pa + away_3pa) / 2   if (home_3pa  and away_3pa)  else None

    parts = []

    # Sentence 1 — primary driver
    s1 = _nba_summary_driver(lean, home, away, avg_pace,
                              home_drtg, away_drtg, avg_ortg, b2b, away)
    if s1:
        parts.append(s1)

    # Sentence 2 — projection vs line
    if line_s and edge is not None:
        direction = "above" if edge > 0 else "below"
        drivers = []
        if avg_pace and avg_pace >= _NBA_PACE_FAST and lean == "OVER":
            drivers.append("fast pace")
        if avg_3pa and avg_3pa >= _NBA_3PA_HEAVY and lean == "OVER":
            drivers.append("high 3-point volume")
        driver_str = (f", driven by {' and '.join(drivers)}" if drivers else "")
        parts.append(
            f"The model projects {pred_s} points, {abs(edge):.1f} pts "
            f"{direction} the market line of {line_s}{driver_str}."
        )
    else:
        parts.append(f"Model projects {pred_s} with no market line available.")

    # Sentence 3 — edge + probability
    if line and edge is not None and p_over is not None:
        p_dir = p_over if lean == "OVER" else 1 - p_over
        side  = "over" if lean == "OVER" else "under"
        parts.append(f"Edge: {edge:+.1f} pts, P({side}) {p_dir * 100:.0f}%.")

    # Sentence 4 — caution (B2B / injuries / gap)
    warnings = []
    if b2b and lean != "UNDER":   # UNDER already mentioned B2B in s1
        warnings.append(f"{away} on B2B (second night)")
    if away_inj:
        names = ", ".join(away_inj[:2])
        warnings.append(f"{away} depleted ({names} out/doubtful)")
    if home_inj:
        names = ", ".join(home_inj[:2])
        warnings.append(f"{home} depleted ({names} out/doubtful)")
    if gap:
        warnings.append("large model/market gap — review before acting")
    if warnings:
        parts.append("Note: " + "; ".join(warnings) + ".")

    return " ".join(parts[:4])


def serialize(game_date: str, games: list[dict], accuracy: dict) -> dict:
    # Generate natural-language summaries from model features
    for g in games:
        g["summary"] = generate_nba_summary(g)

    plays    = [g for g in games if g.get("confidence") in ("HIGH", "MEDIUM")]
    no_plays = [g for g in games if g not in plays]

    # Sort plays: HIGH first, then MEDIUM; within tier by |edge| desc
    def _sort_key(g):
        tier = {"HIGH": 0, "MEDIUM": 1}.get(g.get("confidence", "LOW"), 2)
        edge = abs(g.get("edge") or 0)
        return (tier, -edge)

    plays.sort(key=_sort_key)

    return {
        "generated_at":    datetime.utcnow().isoformat() + "Z",
        "game_date":       game_date,
        "plays":           plays,
        "no_plays":        no_plays,
        "season_accuracy": accuracy,
    }


def git_push(game_date: str) -> bool:
    def run(cmd):
        result = subprocess.run(cmd, cwd=REPO_DIR, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  [git error] {' '.join(cmd)}\n  {result.stderr.strip()}",
                  file=sys.stderr)
            return False
        return True

    run(["git", "add", "nba_results.json"])

    status = subprocess.run(
        ["git", "status", "--porcelain", "nba_results.json"],
        cwd=REPO_DIR, capture_output=True, text=True,
    )
    if not status.stdout.strip():
        print("[push_nba] Nothing to commit — nba_results.json unchanged.")
        return True

    if not run(["git", "commit", "-m", f"nba: {game_date}"]):
        return False

    if not run(["git", "push"]):
        return False

    print("[push_nba] Pushed successfully.")
    return True


def write_nba_json(game_date: str = None) -> str:
    """Write nba_results.json and return the path. Does NOT git push."""
    game_date = game_date or date.today().isoformat()
    games    = load_today_projections(game_date)
    accuracy = build_season_accuracy()
    payload  = serialize(game_date, games, accuracy)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    print(f"[push_nba] Wrote {OUT_PATH} ({len(games)} games)")
    return OUT_PATH


def push_nba(game_date: str = None, push: bool = True) -> None:
    """Write nba_results.json and optionally git push it standalone."""
    write_nba_json(game_date)
    if push:
        git_push(game_date or date.today().isoformat())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date",     default=None)
    parser.add_argument("--no-push",  action="store_true")
    args = parser.parse_args()
    push_nba(game_date=args.date, push=not args.no_push)


if __name__ == "__main__":
    main()
