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
from datetime import date, datetime, timedelta, timezone

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
        # Deduplicate on game_id (keep first); pipeline can write duplicate rows
        dupes = len(today) - today["game_id"].nunique()
        if dupes > 0:
            print(f"[push_nba] Deduplicating {dupes} duplicate game_id row(s) from parquet")
            today = today.drop_duplicates(subset=["game_id"], keep="first")
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
                "archetype_signal": r.get("archetype_signal"),
                "archetype_direction": r.get("archetype_direction"),
                "archetype_note": r.get("archetype_note"),
                "archetype_best_total": _safe(r.get("archetype_best_total")),
                "shot_signal": r.get("shot_signal"),
                "shot_direction": r.get("shot_direction"),
                "shot_note": r.get("shot_note"),
                "venue_signal": r.get("venue_signal"),
                "venue_direction": r.get("venue_direction"),
                "venue_note": r.get("venue_note"),
                "oreb_confirms": bool(r.get("oreb_confirms", False)),
                "bet_tier": r.get("bet_tier"),
                "signal_class": r.get("signal_class"),
            })
        print(f"[push_nba] Loaded {len(rows)} projections for {game_date}")
        return rows
    except Exception as e:
        print(f"[push_nba] Failed to load projections: {e}", file=sys.stderr)
        return []


def load_recent_results(days: int = 14) -> list[dict]:
    """Last `days` days of graded rows from nba_results_log.parquet."""
    if not os.path.exists(NBA_RESULTS_PATH):
        return []
    try:
        import pandas as pd
        from datetime import timedelta
        log = pd.read_parquet(NBA_RESULTS_PATH)
        if log.empty:
            return []
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        recent = log[log["game_date"] >= cutoff].sort_values("game_date", ascending=False)

        rows = []
        for _, r in recent.iterrows():
            lean   = r.get("lean", "")
            line   = r.get("line")
            actual = r.get("actual_total")
            # Compute WIN/LOSS/PUSH vs the posted line (not rolling avg)
            if line is not None and actual is not None:
                actual = float(actual)
                line   = float(line)
                if actual == line:
                    result = "PUSH"
                elif lean == "OVER":
                    result = "WIN" if actual > line else "LOSS"
                else:  # UNDER
                    result = "WIN" if actual < line else "LOSS"
            else:
                result = None
            rows.append({
                "game_date":   r.get("game_date"),
                "away_team":   r.get("away_team"),
                "home_team":   r.get("home_team"),
                "signal_side": lean,
                "line":        _safe(line),
                "edge":        _safe(r.get("edge")),
                "result":      result,
                "tier":        r.get("confidence"),
                "pred_total":  _safe(r.get("pred_total")),
                "actual_total": _safe(actual),
            })
        print(f"[push_nba] Recent results ({days}d): {len(rows)}")
        return rows
    except Exception as e:
        print(f"[push_nba] Failed to load recent results: {e}", file=sys.stderr)
        return []


def build_ot_diagnostics() -> dict:
    """
    Shadow OT diagnostic stats from nba_results_log.parquet.
    Reference only — does not affect official W/L/P grading.
    """
    if not os.path.exists(NBA_RESULTS_PATH):
        return {}
    try:
        import pandas as pd
        log = pd.read_parquet(NBA_RESULTS_PATH)
        if log.empty or "went_to_ot" not in log.columns:
            return {}

        total    = len(log)
        ot_games = int(log["went_to_ot"].fillna(0).sum())
        ot_rate  = round(ot_games / total, 4) if total > 0 else None

        ot_flips = int(log["ot_flip"].fillna(0).sum()) if "ot_flip" in log.columns else 0
        ot_flip_rate = round(ot_flips / ot_games, 4) if ot_games > 0 else None

        under_ot_losses = 0
        over_ot_losses  = 0
        for _, r in log.iterrows():
            if r.get("went_to_ot") != 1:
                continue
            side   = r.get("lean", "")
            line   = r.get("line")
            actual = r.get("actual_total")
            if line is None or actual is None:
                continue
            if side == "UNDER":
                result = "WIN" if float(actual) < float(line) else "LOSS"
                if result == "LOSS":
                    under_ot_losses += 1
            elif side == "OVER":
                result = "WIN" if float(actual) > float(line) else "LOSS"
                if result == "LOSS":
                    over_ot_losses += 1

        out = {
            "total_graded":     total,
            "ot_games":         ot_games,
            "ot_rate":          ot_rate,
            "ot_flips":         ot_flips,
            "ot_flip_rate":     ot_flip_rate,
            "under_ot_losses":  under_ot_losses,
            "over_ot_losses":   over_ot_losses,
        }
        print(f"[push_nba] OT diagnostics: {ot_games} OT games, {ot_flips} flips, "
              f"{under_ot_losses} under OT losses, {over_ot_losses} over OT losses")
        return out
    except Exception as e:
        print(f"[push_nba] OT diagnostics failed: {e}", file=sys.stderr)
        return {}


def build_playoff_performance() -> dict:
    """
    Compute playoff-specific performance stats from nba_results_log.parquet.
    Change 8: playoff record by round, by series game group, by confidence, OT rate.
    Returns {} if no playoff games graded yet.
    """
    if not os.path.exists(NBA_RESULTS_PATH):
        return {}
    try:
        import pandas as pd
        log = pd.read_parquet(NBA_RESULTS_PATH)
        if log.empty or "is_playoff" not in log.columns:
            return {}

        playoff = log[log["is_playoff"] == True].copy()
        if playoff.empty:
            return {}

        def _wlp(sub):
            if sub.empty:
                return {"n": 0, "w": 0, "l": 0, "p": 0, "hit_rate": None, "roi": None}
            W = int((sub["regulation_result"] == "WIN").sum()) if "regulation_result" in sub.columns else 0
            L = int((sub["regulation_result"] == "LOSS").sum()) if "regulation_result" in sub.columns else 0
            P = int((sub["regulation_result"] == "PUSH").sum()) if "regulation_result" in sub.columns else 0
            n = W + L + P
            hit = round(W / (W + L), 4) if (W + L) > 0 else None
            roi = round((W * (100.0 / 110.0) - L) / n * 100, 2) if n > 0 else None
            return {"n": n, "w": W, "l": L, "p": P, "hit_rate": hit, "roi": roi}

        # Overall playoff record
        overall = _wlp(playoff)

        # By round
        by_round = {}
        for rnd in ["First Round", "Conference Semifinals", "Conference Finals", "NBA Finals"]:
            sub = playoff[playoff["playoff_round"] == rnd]
            by_round[rnd] = _wlp(sub)

        # By series game group (blend weight buckets)
        by_series_game = {}
        if "series_game_number" in playoff.columns:
            g12 = playoff[playoff["series_game_number"].isin([1, 2])]
            g34 = playoff[playoff["series_game_number"].isin([3, 4])]
            g5p = playoff[playoff["series_game_number"] >= 5]
            by_series_game["G1-2 (series_weight=0-0.4)"] = _wlp(g12)
            by_series_game["G3-4 (series_weight=0.4-0.8)"] = _wlp(g34)
            by_series_game["G5+ (series_weight=0.8-1.0)"]  = _wlp(g5p)

        # By confidence
        by_conf = {}
        for conf in ["HIGH", "MEDIUM", "LOW"]:
            sub = playoff[playoff["confidence"] == conf]
            by_conf[conf] = _wlp(sub)

        # OT in playoffs (official reporting per Change 7)
        ot_total   = int(playoff["went_to_ot"].fillna(0).sum()) if "went_to_ot" in playoff.columns else 0
        ot_rate    = round(ot_total / len(playoff), 4) if len(playoff) > 0 else None
        ot_flips   = int(playoff["ot_flip_official"].fillna(0).sum()) if "ot_flip_official" in playoff.columns else 0
        under_ot_l = 0
        over_ot_l  = 0
        for _, r in playoff.iterrows():
            if r.get("went_to_ot") != 1:
                continue
            side   = r.get("lean", "")
            actual = r.get("actual_total")
            line   = r.get("line")
            if line is None or actual is None:
                continue
            if side == "UNDER":
                if float(actual) >= float(line):
                    under_ot_l += 1
            elif side == "OVER":
                if float(actual) <= float(line):
                    over_ot_l += 1

        result = {
            "total_playoff_games": len(playoff),
            "overall":             overall,
            "by_round":            by_round,
            "by_series_game":      by_series_game,
            "by_confidence":       by_conf,
            "ot_stats": {
                "ot_games":        ot_total,
                "ot_rate":         ot_rate,
                "ot_flips":        ot_flips,
                "under_ot_losses": under_ot_l,
                "over_ot_losses":  over_ot_l,
            },
            "model_note": (
                "Playoff mode active — series context features engage from "
                "Game 2 onward (v1_2026_04)"
            ),
        }
        print(f"[push_nba] Playoff performance: {len(playoff)} games, "
              f"overall {overall['w']}-{overall['l']}-{overall['p']}")
        return result
    except Exception as e:
        print(f"[push_nba] Playoff performance failed: {e}", file=sys.stderr)
        return {}


def build_signal_tracking() -> dict:
    """Compute signal system performance from nba_signal_log.parquet."""
    signal_path = os.path.join(REPO_DIR, "nba", "data", "nba_signal_log.parquet")
    if not os.path.exists(signal_path):
        return {}
    try:
        import pandas as pd
        slog = pd.read_parquet(signal_path)
        graded = slog[slog["result"].notna()]
        if len(graded) == 0:
            return {"total_plays": 0, "start_date": "2026-03-22",
                    "note": "Live since March 22, 2026. No graded plays yet."}
        out = {"total_plays": int(len(graded)), "start_date": "2026-03-22"}
        # By tier
        by_tier = {}
        for tier in ["TIER1", "TIER2", "TIER3"]:
            sub = graded[graded["tier"] == tier]
            if len(sub) == 0: continue
            wins = (sub["result"] == "WIN").sum()
            pnl = sub["units_won_lost"].sum()
            by_tier[tier] = {
                "n": int(len(sub)),
                "wins": int(wins),
                "hit_pct": round(wins / len(sub) * 100, 1),
                "units_pnl": round(float(pnl), 2),
            }
        out["by_tier"] = by_tier
        # Overall (exclude context)
        bettable = graded[graded["tier"].isin(["TIER1","TIER2","TIER3"])]
        if len(bettable) > 0:
            wins = (bettable["result"] == "WIN").sum()
            out["overall_hit_pct"] = round(wins / len(bettable) * 100, 1)
            out["overall_units_pnl"] = round(float(bettable["units_won_lost"].sum()), 2)
        return out
    except Exception as e:
        print(f"[push_nba] Signal tracking failed: {e}", file=sys.stderr)
        return {}


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


def _strongest_factor(lean: str, avg_pace, home_drtg, away_drtg,
                       avg_ortg, avg_3pa, b2b: bool, home: str, away: str) -> tuple[str, str]:
    """
    Return (driver_sentence, driver_tag) for the single strongest factor.
    driver_tag is used to avoid repeating the same factor in sentence 2.
    """
    if lean == "OVER":
        # Weakest defense → most points on the board
        if home_drtg and away_drtg:
            weaker_drtg = max(home_drtg, away_drtg)
            weaker = home if home_drtg >= away_drtg else away
            if weaker_drtg >= _NBA_DRTG_WEAK:
                return (
                    f"{weaker} is giving up {weaker_drtg:.1f} points per 100 possessions "
                    f"— one of the worst defensive marks in the league.",
                    "drtg",
                )
        # Fast pace → more possessions
        if avg_pace and avg_pace >= _NBA_PACE_FAST:
            return (
                f"Both teams are averaging {avg_pace:.1f} possessions per 48 minutes "
                f"— above the league's {_NBA_PACE_AVG:.1f} average, meaning more shots and more points.",
                "pace",
            )
        # Efficient offenses
        if avg_ortg and avg_ortg >= _NBA_ORTG_GOOD:
            return (
                f"{home} and {away} are both scoring at {avg_ortg:.1f} points per 100 possessions "
                f"combined — well above the league average.",
                "ortg",
            )
        # High 3PA volume → variance plays into OVER
        if avg_3pa and avg_3pa >= _NBA_3PA_HEAVY:
            return (
                f"Both teams attempt 3-pointers at a high rate ({avg_3pa * 100:.0f}% of FGA), "
                f"which inflates totals on hot nights.",
                "3pa",
            )

    elif lean == "UNDER":
        # B2B fatigue → biggest suppressor
        if b2b:
            return (
                f"{away} is on the second night of a back-to-back — fatigue typically "
                f"costs 3-5 points of offensive output.",
                "b2b",
            )
        # Strong defense on both sides
        if home_drtg and away_drtg:
            better_drtg = min(home_drtg, away_drtg)
            avg_drtg = (home_drtg + away_drtg) / 2
            if avg_drtg <= _NBA_DRTG_GOOD:
                return (
                    f"{home} ({home_drtg:.1f} DRtg) and {away} ({away_drtg:.1f} DRtg) "
                    f"are both elite defensively — combined, they're suppressing {avg_drtg:.1f} "
                    f"points per 100 possessions.",
                    "drtg",
                )
            if better_drtg <= _NBA_DRTG_GOOD:
                elite = home if home_drtg <= away_drtg else away
                elite_drtg = home_drtg if home_drtg <= away_drtg else away_drtg
                return (
                    f"{elite} is holding opponents to {elite_drtg:.1f} points per 100 possessions "
                    f"— a top-tier defensive rating.",
                    "drtg",
                )
        # Slow pace
        if avg_pace and avg_pace <= _NBA_PACE_SLOW:
            return (
                f"Both teams play at a deliberate pace — combined {avg_pace:.1f} possessions "
                f"per 48 minutes, well below the league's {_NBA_PACE_AVG:.1f} average.",
                "pace",
            )

    return ("", "")


def generate_nba_summary(g: dict) -> str:
    """
    Build a 1-4 sentence natural-language summary from model features.
    Every claim references a real data field. Template-based, no API calls.
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

    avg_pace = (home_pace + away_pace) / 2 if (home_pace and away_pace) else None
    avg_ortg = (home_ortg + away_ortg) / 2 if (home_ortg and away_ortg) else None
    avg_3pa  = (home_3pa + away_3pa) / 2   if (home_3pa  and away_3pa)  else None
    abs_edge = abs(edge or 0)

    # ── NO PLAY ──────────────────────────────────────────────────────────────
    if conf == "LOW":
        if line_s is None:
            return (f"Model projects {pred_s} total with no market line to compare. "
                    f"No edge to work with — pass.")
        if abs_edge < 3:
            return (f"Model has {pred_s}, market is at {line_s} — only {abs_edge:.1f} pts "
                    f"of separation. Not enough edge to act on.")
        return (f"Model projects {pred_s} vs the {line_s} line (edge {edge:+.1f} pts), "
                f"but the signal isn't strong enough to play. Pass.")

    # ── PLAY (HIGH or MEDIUM) ────────────────────────────────────────────────
    parts = []

    # Sentence 1 — strongest factor with actual numbers
    s1, s1_tag = _strongest_factor(lean, avg_pace, home_drtg, away_drtg,
                                    avg_ortg, avg_3pa, b2b, home, away)
    if s1:
        parts.append(s1)

    # Sentence 2 — secondary context or projection vs line
    if line_s and edge is not None:
        side = "over" if lean == "OVER" else "under"
        # Add secondary factor if different from s1_tag and data exists
        s2_extra = ""
        if lean == "OVER" and s1_tag != "pace" and avg_pace and avg_pace >= _NBA_PACE_FAST:
            s2_extra = f" at {avg_pace:.1f} possessions per game"
        elif lean == "OVER" and s1_tag != "3pa" and avg_3pa and avg_3pa >= _NBA_3PA_HEAVY:
            s2_extra = f", with both teams hoisting {avg_3pa * 100:.0f}% of their attempts from three"
        elif lean == "UNDER" and s1_tag != "b2b" and b2b:
            s2_extra = f" with {away} also on a back-to-back"
        parts.append(
            f"Model has {pred_s}{s2_extra}, {abs_edge:.1f} pts {('above' if edge > 0 else 'below')} "
            f"the {line_s} line — {side}."
        )
    else:
        parts.append(f"Model projects {pred_s} with no market line posted yet.")

    # Sentence 3 — lean + probability
    if line and edge is not None and p_over is not None:
        side  = "over" if lean == "OVER" else "under"
        p_dir = p_over if lean == "OVER" else 1 - p_over
        parts.append(f"P({side}) {p_dir * 100:.0f}%, edge {edge:+.1f} pts.")

    # Sentence 4 — caution flags (B2B / injuries / market gap)
    warnings = []
    if b2b and lean != "UNDER":
        warnings.append(f"{away} on B2B tonight")
    if away_inj:
        names = ", ".join(away_inj[:2])
        warnings.append(f"{away} missing {names}")
    if home_inj:
        names = ", ".join(home_inj[:2])
        warnings.append(f"{home} missing {names}")
    if gap:
        warnings.append("model/market gap exceeds threshold — double-check the line")
    if warnings:
        parts.append("Note: " + "; ".join(warnings) + ".")

    return " ".join(parts[:4])


def build_clv_summary() -> dict:
    """Compute CLV summary from nba_results_log.parquet."""
    if not os.path.exists(NBA_RESULTS_PATH):
        return {}
    try:
        import pandas as pd
        log = pd.read_parquet(NBA_RESULTS_PATH)
        if log.empty or "clv_directional" not in log.columns:
            return {}
        has_clv = log.dropna(subset=["clv_directional"])
        n_clv   = len(has_clv)
        n_total = int(log["line"].notna().sum())
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
            sub = has_clv[has_clv["confidence"] == tier]
            by_tier[tier] = round(float(sub["clv_directional"].mean()), 3) if len(sub) > 0 else None
        by_side = {}
        for side in ["OVER", "UNDER"]:
            sub = has_clv[has_clv["lean"] == side]
            by_side[side] = round(float(sub["clv_directional"].mean()), 3) if len(sub) > 0 else None
        print(f"[push_nba] CLV summary: n={n_clv}, avg={avg_clv:+.3f}, coverage={coverage:.0f}%")
        return {"total_with_clv": n_clv, "avg_clv": avg_clv, "median_clv": median_clv,
                "pct_positive_clv": pct_pos, "avg_clv_by_tier": by_tier,
                "avg_clv_by_side": by_side, "clv_coverage": coverage}
    except Exception as e:
        print(f"[push_nba] CLV summary failed: {e}", file=sys.stderr)
        return {}


def serialize(game_date: str, games: list[dict], accuracy: dict,
              recent_results: list[dict] | None = None,
              ot_diagnostics: dict | None = None,
              playoff_performance: dict | None = None,
              clv_summary: dict | None = None) -> dict:
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

    # Detect if any game today is a playoff game
    is_playoff_day = any(g.get("is_playoff") for g in games)

    return {
        "generated_at":       datetime.now(timezone.utc).isoformat(),
        "game_date":          game_date,
        "is_playoff_day":     is_playoff_day,
        "plays":              plays,
        "no_plays":           no_plays,
        "season_accuracy":    accuracy,
        "recent_results":     recent_results or [],
        "ot_diagnostics":     ot_diagnostics or {},
        "playoff_performance": playoff_performance or {},
        "clv_summary":        clv_summary or {},
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
    games              = load_today_projections(game_date)
    accuracy           = build_season_accuracy()
    signal_tracking    = build_signal_tracking()
    recent_results     = load_recent_results(days=14)
    ot_diagnostics     = build_ot_diagnostics()
    playoff_performance = build_playoff_performance()
    clv_summary        = build_clv_summary()
    payload = serialize(game_date, games, accuracy, recent_results,
                        ot_diagnostics, playoff_performance, clv_summary)
    payload["signal_tracking"] = signal_tracking

    # Archive today's projections for future backfill capability
    try:
        archive_path = os.path.join(REPO_DIR, "nba", "data", "nba_projections_archive.parquet")
        if games:
            archive_df = pd.DataFrame(games)
            archive_df["game_date"] = game_date
            if os.path.exists(archive_path):
                existing = pd.read_parquet(archive_path)
                archive_df = pd.concat([existing, archive_df], ignore_index=True)
                archive_df = archive_df.drop_duplicates(subset=["game_id"], keep="last")
            archive_df.to_parquet(archive_path, index=False)
    except Exception as e:
        print(f"[push_nba] Projection archive failed (non-fatal): {e}", file=sys.stderr)

    # Phase 6: Small edge shadow tracking
    try:
        from nba.phase6_shadow import process_games, grade_games
        grade_games((date.fromisoformat(game_date) - timedelta(days=1)).isoformat())
        process_games(game_date)
    except Exception as e:
        print(f"[push_nba] Phase 6 shadow failed (non-fatal): {e}", file=sys.stderr)

    # Stop rules
    try:
        from nba_stop_rules import evaluate_nba_stop_rules, apply_nba_stop_rule_filter
        stop_status = evaluate_nba_stop_rules()
        payload["stop_rule_status"] = stop_status
        if stop_status.get("model_suspended") or stop_status.get("suspended_tiers"):
            print(f"[push_nba] NBA STOP RULE ACTIVE: "
                  f"model_suspended={stop_status['model_suspended']}, "
                  f"tiers={stop_status['suspended_tiers']}")
            active_plays, updated_no_plays = apply_nba_stop_rule_filter(
                payload["plays"], payload["no_plays"], stop_status
            )
            payload["plays"]    = active_plays
            payload["no_plays"] = updated_no_plays
    except Exception as e:
        print(f"[push_nba] NBA stop rule evaluation failed (non-fatal): {e}", file=sys.stderr)
        payload["stop_rule_status"] = {"model_suspended": False, "suspended_tiers": []}

    # AI daily (and optional weekly) review
    try:
        from modules.ai_review import (build_graded_games, generate_daily_review,
                                        maybe_weekly, build_week_games,
                                        generate_weekly_review, is_idempotent)
        _review_date = (date.fromisoformat(game_date) - timedelta(days=1)).isoformat()
        if not is_idempotent(OUT_PATH, _review_date):
            _graded = build_graded_games("nba", _review_date)
            payload["daily_review"] = generate_daily_review(_graded, "nba", _review_date)
        else:
            print(f"[push_nba] NBA daily review already exists for {_review_date} — skipping")
        _wr = maybe_weekly("nba")
        if _wr:
            _wg = build_week_games("nba", *_wr)
            payload["weekly_review"] = generate_weekly_review(_wg, "nba", *_wr)
    except Exception as e:
        print(f"[push_nba] NBA AI review failed (non-fatal): {e}", file=sys.stderr)

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
