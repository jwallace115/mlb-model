#!/usr/bin/env python3
"""
analytics.py — Build season_stats.json from the graded_results table.

Usage:
  python analytics.py                # print summary to terminal
  python analytics.py --json         # print JSON to stdout
"""

import argparse
import json
from datetime import datetime

import db


# ── helpers ───────────────────────────────────────────────────────────────────

def _wl(rows: list[dict]) -> dict:
    """Compute W/L/P stats for a set of graded rows."""
    decided = [r for r in rows if r["result"] in ("WIN", "LOSS", "PUSH")]
    wins    = sum(1 for r in decided if r["result"] == "WIN")
    losses  = sum(1 for r in decided if r["result"] == "LOSS")
    pushes  = sum(1 for r in decided if r["result"] == "PUSH")
    no_line = sum(1 for r in rows   if r["result"] == "NO_LINE")
    net     = wins + losses  # excludes pushes for pct/roi

    win_pct = round(wins / net * 100, 1) if net else None
    roi     = round((wins * 0.9091 - losses) / net * 100, 1) if net else None
    units   = round(wins * 0.9091 - losses, 2) if net else None

    return {
        "wins":    wins,
        "losses":  losses,
        "pushes":  pushes,
        "no_line": no_line,
        "total":   len(rows),
        "decided": net,
        "win_pct": win_pct,
        "roi":     roi,
        "units":   units,
    }


def _wind_type(wind_desc: str | None) -> str:
    if not wind_desc:
        return "unknown"
    wd = wind_desc.lower()
    if "dome" in wd:
        return "dome"
    if "in from" in wd or "blowing in" in wd:
        return "in"
    if "out to" in wd or "blowing out" in wd:
        return "out"
    return "neutral"


def _temp_bucket(temp: float | None) -> str:
    if temp is None:
        return "unknown"
    if temp < 50:
        return "cold"
    if temp < 76:
        return "mild"
    return "warm"


def _park_bucket(pf: float | None) -> str:
    if pf is None:
        return "unknown"
    if pf < 0.97:
        return "pitcher"
    if pf <= 1.03:
        return "neutral"
    return "hitter"


# ── breakdowns ────────────────────────────────────────────────────────────────

def by_stars(plays: list[dict]) -> dict:
    out = {}
    for label, sc in [("⭐⭐⭐", 3), ("⭐⭐", 2), ("⭐", 1)]:
        sub = [r for r in plays if r.get("star_count") == sc]
        out[label] = _wl(sub)
    return out


def by_confidence(plays: list[dict]) -> dict:
    out = {}
    for conf in ("HIGH", "MEDIUM", "LOW"):
        sub = [r for r in plays if r.get("confidence") == conf]
        out[conf] = _wl(sub)
    return out


def by_temperature(plays: list[dict]) -> dict:
    buckets = {
        "cold":    {"label": "< 50°F",  "rows": []},
        "mild":    {"label": "50–75°F", "rows": []},
        "warm":    {"label": "> 75°F",  "rows": []},
        "dome":    {"label": "Dome",    "rows": []},
        "unknown": {"label": "Unknown", "rows": []},
    }
    for r in plays:
        wd = (r.get("wind_desc") or "").lower()
        if "dome" in wd:
            bucket = "dome"
        else:
            bucket = _temp_bucket(r.get("temperature"))
        buckets[bucket]["rows"].append(r)

    return {
        k: {"label": v["label"], **_wl(v["rows"])}
        for k, v in buckets.items()
    }


def by_wind(plays: list[dict]) -> dict:
    buckets = {
        "out":     {"label": "Blowing Out",    "rows": []},
        "in":      {"label": "Blowing In",     "rows": []},
        "neutral": {"label": "Cross / Calm",   "rows": []},
        "dome":    {"label": "Dome",           "rows": []},
        "unknown": {"label": "Unknown",        "rows": []},
    }
    for r in plays:
        wt = _wind_type(r.get("wind_desc"))
        buckets.setdefault(wt, {"label": wt, "rows": []})["rows"].append(r)

    return {
        k: {"label": v["label"], **_wl(v["rows"])}
        for k, v in buckets.items()
    }


def by_park(plays: list[dict]) -> dict:
    buckets = {
        "pitcher": {"label": "Pitcher's Park (PF < 0.97)", "rows": []},
        "neutral": {"label": "Neutral Park (0.97–1.03)",    "rows": []},
        "hitter":  {"label": "Hitter's Park (PF > 1.03)",  "rows": []},
        "unknown": {"label": "Unknown",                     "rows": []},
    }
    for r in plays:
        bucket = _park_bucket(r.get("park_factor"))
        buckets[bucket]["rows"].append(r)

    return {
        k: {"label": v["label"], **_wl(v["rows"])}
        for k, v in buckets.items()
    }


def projection_accuracy(rows: list[dict]) -> dict:
    """How close were our projections to actuals (all tracked games, not just plays)."""
    scored = [r for r in rows if r.get("projection_error") is not None]
    if not scored:
        return {"tracked": 0}

    errors = [abs(r["projection_error"]) for r in scored]
    mae    = round(sum(errors) / len(errors), 2)
    avg_err = round(sum(r["projection_error"] for r in scored) / len(scored), 2)

    def pct_within(n):
        return round(sum(1 for e in errors if e <= n) / len(errors) * 100, 1)

    # By star rating
    by_star = {}
    for label, sc in [("⭐⭐⭐", 3), ("⭐⭐", 2), ("⭐", 1), ("NO PLAY", 0)]:
        sub = [r for r in scored if r.get("star_count") == sc]
        if sub:
            errs = [abs(r["projection_error"]) for r in sub]
            by_star[label] = round(sum(errs) / len(errs), 2)

    return {
        "tracked":      len(scored),
        "mae":          mae,
        "avg_bias":     avg_err,       # positive = we underestimate totals
        "within_1_run": pct_within(1),
        "within_2_runs": pct_within(2),
        "within_3_runs": pct_within(3),
        "mae_by_stars": by_star,
    }


def biggest_misses(rows: list[dict], n: int = 10) -> list[dict]:
    """Top N games where projection error was largest."""
    scored = [r for r in rows if r.get("projection_error") is not None]
    scored.sort(key=lambda r: abs(r["projection_error"]), reverse=True)
    out = []
    for r in scored[:n]:
        out.append({
            "game_date":       r["game_date"],
            "matchup":         f"{r['away_team']} @ {r['home_team']}",
            "projected_total": r["projected_total"],
            "actual_total":    r["actual_total"],
            "projection_error": round(r["projection_error"], 1),
            "recommendation":  r["recommendation"],
            "result":          r["result"],
            "star_rating":     r["star_rating"],
            "confidence":      r["confidence"],
            "temperature":     r.get("temperature"),
            "wind_desc":       r.get("wind_desc"),
            "park_factor":     r.get("park_factor"),
        })
    return out


def factor_correlations(plays: list[dict]) -> dict:
    """
    Simple correlation: for each factor bucket, what fraction went WIN vs LOSS.
    Returns sorted list of (factor_description, win_pct, sample_size).
    """
    segments = []

    # Temperature
    for bucket, label in [("cold", "Temp < 50°F"), ("mild", "Temp 50–75°F"),
                           ("warm", "Temp > 75°F"), ("dome", "Dome")]:
        sub = []
        for r in plays:
            wd = (r.get("wind_desc") or "").lower()
            if bucket == "dome":
                if "dome" in wd:
                    sub.append(r)
            elif _temp_bucket(r.get("temperature")) == bucket and "dome" not in wd:
                sub.append(r)
        wl = _wl(sub)
        if wl["decided"] >= 5:
            segments.append({"factor": label, **wl})

    # Wind
    for bucket, label in [("out", "Wind: Blowing Out"), ("in", "Wind: Blowing In"),
                           ("neutral", "Wind: Cross/Calm")]:
        sub = [r for r in plays if _wind_type(r.get("wind_desc")) == bucket]
        wl = _wl(sub)
        if wl["decided"] >= 5:
            segments.append({"factor": label, **wl})

    # Park
    for bucket, label in [("pitcher", "Pitcher's Park"), ("neutral", "Neutral Park"),
                           ("hitter", "Hitter's Park")]:
        sub = [r for r in plays if _park_bucket(r.get("park_factor")) == bucket]
        wl = _wl(sub)
        if wl["decided"] >= 5:
            segments.append({"factor": label, **wl})

    # Confidence
    for conf in ("HIGH", "MEDIUM"):
        sub = [r for r in plays if r.get("confidence") == conf]
        wl = _wl(sub)
        if wl["decided"] >= 5:
            segments.append({"factor": f"Confidence: {conf}", **wl})

    # Sort by win_pct desc (only include segments with win_pct)
    segments = [s for s in segments if s.get("win_pct") is not None]
    segments.sort(key=lambda s: s["win_pct"], reverse=True)
    return segments


def is_spring_training(rows: list[dict]) -> bool:
    """Heuristic: spring training if we have few/no graded W/L results."""
    decided = sum(1 for r in rows if r.get("result") in ("WIN", "LOSS"))
    return decided == 0


# ── main builder ──────────────────────────────────────────────────────────────

def build_season_stats() -> dict:
    """Query DB and return the full season_stats dict for season_stats.json."""
    db.init_db()
    all_rows = db.get_all_graded_results()

    plays     = [r for r in all_rows if r.get("was_a_play")]
    spring    = is_spring_training(plays)

    stats = {
        "generated_at":     datetime.utcnow().isoformat() + "Z",
        "is_spring_training": spring,
        "total_tracked":    len(all_rows),
        "total_plays":      len(plays),
        "overall":          _wl(plays),
        "by_stars":         by_stars(plays),
        "by_confidence":    by_confidence(plays),
        "by_temperature":   by_temperature(plays),
        "by_wind":          by_wind(plays),
        "by_park":          by_park(plays),
        "projection_accuracy": projection_accuracy(all_rows),
        "factor_correlations": factor_correlations(plays),
        "biggest_misses":   biggest_misses(all_rows),
        "props_record":     db.get_prop_season_stats(),
    }
    return stats


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MLB Model Analytics")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    stats = build_season_stats()

    if args.json:
        print(json.dumps(stats, indent=2, default=str))
    else:
        overall = stats["overall"]
        print(f"\nSeason Stats (plays: {stats['total_plays']})")
        if overall["decided"] > 0:
            print(f"  Record: {overall['wins']}-{overall['losses']} "
                  f"({overall['win_pct']}%)  ROI: {overall['roi']:+.1f}%  "
                  f"Units: {overall['units']:+.2f}")
        else:
            print(f"  No graded plays yet (spring training or no lines posted)")
        print(f"  Accuracy MAE: {stats['projection_accuracy'].get('mae', 'N/A')} runs")
        print(f"  Within 1 run: {stats['projection_accuracy'].get('within_1_run', 'N/A')}%")
