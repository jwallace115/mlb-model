#!/usr/bin/env python3
"""
MLB Totals Model — Daily Runner
================================
Usage:
  python run_model.py            # today's games
  python run_model.py 2025-04-15 # specific date
  python run_model.py --quiet    # DB-only, no card
  python run_model.py --no-odds  # skip Odds API
"""

import argparse
import logging
import os
import sys
from datetime import date, datetime
from typing import Optional

from colorama import Fore, Style, init as colorama_init

import db
from config import LOGS_DIR, EDGE_MIN_RUNS
from modules.schedule    import fetch_schedule
from modules.pitchers    import build_pitcher_db, get_pitcher_metrics
from modules.offense     import build_offense_db, get_team_offense
from modules.weather     import fetch_weather
from modules.bullpen     import calculate_bullpen_fatigue, build_team_bullpen_db
from modules.umpires     import get_umpire_rating
from modules.projections import project_game
from modules.odds        import fetch_all_lines, get_game_lines, edge_summary
from modules.props_data        import build_pitcher_k_db, build_batter_props_db
from modules.line_tracker      import log_opening_lines
from modules.props_projections import get_game_props
from modules.props_odds        import fetch_props_lines

colorama_init(autoreset=True)

LOG_FILE = f"{LOGS_DIR}/run_model_{date.today().isoformat()}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stderr),
    ],
)
logger = logging.getLogger("run_model")

LA = 4.25   # league-average ERA / xFIP baseline


def _cap1(s: str) -> str:
    """Capitalize first character only — preserves case of abbreviations/names."""
    return s[:1].upper() + s[1:] if s else s


def _factor_dev_val(name: str, devs: dict) -> float:
    return {"sp": devs["sp_avg"], "offense": devs["off_avg"], "park": devs["park"],
            "wind": devs["wind"], "temp": devs["temp"], "ump": devs["ump"],
            "bp": devs["bp"]}.get(name, 0.0)


def _is_counter(name: str, devs: dict, lean: str) -> bool:
    """True when this factor pulls opposite to the lean direction."""
    v = _factor_dev_val(name, devs)
    return (lean == "OVER" and v < 0) or (lean == "UNDER" and v > 0)


def _factor_short_desc(name: str, devs: dict, sp_h: float, sp_a: float,
                        temp_f: float, pf: int) -> str:
    """One-phrase description of a factor for use in 'outweigh' sentences."""
    if name == "sp":
        avg = (sp_h + sp_a) / 2
        if avg < 3.5:  return "elite pitching"
        if avg < 4.1:  return "quality pitching"
        return "the pitching matchup"
    if name == "temp":
        return "cold temperatures" if devs["temp"] < 0 else f"the heat ({temp_f:.0f}°F)"
    if name == "park":
        return "the pitcher-friendly park" if devs["park"] < 0 else "the hitter-friendly park"
    if name == "offense":
        return "weak lineups" if devs["off_avg"] < 0 else "strong lineups"
    if name == "wind":    return "favorable wind"
    if name == "bp":      return "bullpen fatigue"
    return name


def _counter_intro(name: str, devs: dict, wind_mph: float, wind_desc: str,
                   temp_f: float, pf: int) -> str:
    """Opening clause describing a counter factor for 'X — but Y outweighs' sentences."""
    if name == "wind":
        wd = wind_desc.replace("Blowing ", "").replace("blowing ", "")
        return f"Wind is blowing {wd} ({wind_mph:.0f}mph)"
    if name == "temp":
        return (f"Temperatures are warm ({temp_f:.0f}°F)" if devs["temp"] > 0
                else f"It's cold ({temp_f:.0f}°F)")
    if name == "park":
        return (f"The park tilts hitter-friendly (PF {pf})" if devs["park"] > 0
                else f"The park is pitcher-friendly (PF {pf})")
    if name == "offense":
        return "The offenses are strong" if devs["off_avg"] > 0 else "The offenses are weak"
    return ""

# ── colours ──────────────────────────────────────────────────────────────────
C = {
    "over":    Fore.RED,
    "under":   Fore.CYAN,
    "neutral": Fore.WHITE,
    "high":    Fore.GREEN,
    "medium":  Fore.YELLOW,
    "low":     Fore.WHITE,
    "dim":     Style.DIM,
    "reset":   Style.RESET_ALL,
    "bold":    "\033[1m",
    "mag":     Fore.MAGENTA,
    "cyan":    Fore.CYAN,
}

STARS = {
    "⭐⭐⭐": Fore.GREEN,
    "⭐⭐":   Fore.YELLOW,
    "⭐":     Fore.WHITE,
    "NO PLAY": Style.DIM,
}


# ── classification ────────────────────────────────────────────────────────────

def classify_game(proj: dict, full_edge: dict) -> str:
    """Return ⭐⭐⭐ / ⭐⭐ / ⭐ / NO PLAY."""
    lean       = proj["lean"]
    conf       = proj["confidence"]
    score      = proj["confidence_score"]
    edge       = full_edge.get("edge")
    has_line   = full_edge.get("consensus") is not None

    if lean == "NEUTRAL":
        return "NO PLAY"

    if has_line and edge is not None:
        abs_e = abs(edge)
        if conf == "HIGH"   and abs_e >= 1.0:  return "⭐⭐⭐"
        if conf == "HIGH"   and abs_e >= 0.5:  return "⭐⭐⭐"
        if conf == "MEDIUM" and abs_e >= 0.5:  return "⭐⭐"
        if conf == "HIGH"   and abs_e >= 0.3:  return "⭐⭐"
        if abs_e >= 0.3 and conf != "LOW":     return "⭐"
        return "NO PLAY"
    else:
        # No line — classify on model confidence alone
        if conf == "HIGH"   and score >= 0.75: return "⭐⭐⭐"
        if conf == "HIGH"   and score >= 0.50: return "⭐⭐"
        if conf == "MEDIUM" and score >= 0.50: return "⭐⭐"
        if conf == "MEDIUM":                   return "⭐"
        if conf == "LOW"    and score >= 0.50: return "⭐"
        return "NO PLAY"


# ── factor analysis helpers ───────────────────────────────────────────────────

def _factor_devs(f: dict) -> dict:
    """Return signed deviations from neutral (positive = pushes OVER)."""
    sp_h = (f.get("sp_home_xfip") or LA) / LA - 1.0
    sp_a = (f.get("sp_away_xfip") or LA) / LA - 1.0
    return {
        "sp_home":  sp_h,                                    # bad home SP → away scores more
        "sp_away":  sp_a,                                    # bad away SP → home scores more
        "sp_avg":   (sp_h + sp_a) / 2,
        "off_home": ((f.get("home_wrc_plus") or 100) / 100) - 1.0,
        "off_away": ((f.get("away_wrc_plus") or 100) / 100) - 1.0,
        "off_avg":  (((f.get("home_wrc_plus") or 100) + (f.get("away_wrc_plus") or 100)) / 200) - 1.0,
        "park":     (f.get("park_factor") or 1.0) - 1.0,
        "wind":     (f.get("wind_factor")  or 1.0) - 1.0,
        "temp":     (f.get("temp_factor")  or 1.0) - 1.0,
        "ump":      (f.get("umpire_runs_factor") or 1.0) - 1.0,
        "bp":       ((f.get("home_bp_fatigue") or 0) + (f.get("away_bp_fatigue") or 0)) * 0.08,
    }


def _ranked_factors(devs: dict, lean: str) -> list[tuple[str, float]]:
    """Return factors sorted by magnitude, largest first."""
    groups = {
        "sp":      abs(devs["sp_avg"]),
        "offense": abs(devs["off_avg"]),
        "park":    abs(devs["park"]),
        "wind":    abs(devs["wind"]),
        "temp":    abs(devs["temp"]),
        "ump":     abs(devs["ump"]),
        "bp":      abs(devs["bp"]),
    }
    return sorted(groups.items(), key=lambda x: x[1], reverse=True)


def _no_play_reason(f: dict, proj: dict, odds: dict) -> str:
    """Categorise *why* this is a no-play."""
    lean       = proj["lean"]
    score      = proj["confidence_score"]
    is_dome    = "dome" in (f.get("wind_desc") or "").lower()
    has_precip = any(w in str(f.get("weather_desc", ""))
                     for w in ("Rain", "Thunder", "Drizzle", "Snow", "Shower"))

    full_lines = (odds or {}).get("full") or {}
    line       = full_lines.get("consensus")
    edge_abs   = abs(proj["proj_total_full"] - line) if line is not None else None

    sp_h  = (f.get("sp_home_xfip") or LA) / LA - 1.0
    sp_a  = (f.get("sp_away_xfip") or LA) / LA - 1.0
    devs  = _factor_devs(f)

    pos = sum(v for v in [devs["sp_avg"], devs["off_avg"], devs["park"],
                           devs["wind"], devs["temp"]] if v > 0.02)
    neg = sum(v for v in [devs["sp_avg"], devs["off_avg"], devs["park"],
                           devs["wind"], devs["temp"]] if v < -0.02)
    mixed = pos > 0.03 and neg < -0.03

    sp_flat  = abs(sp_h) < 0.06 and abs(sp_a) < 0.06
    off_flat = abs(devs["off_home"]) < 0.05 and abs(devs["off_away"]) < 0.05

    if has_precip:
        return "weather_uncertainty"
    if edge_abs is not None and edge_abs < EDGE_MIN_RUNS and lean != "NEUTRAL":
        return "edge_too_thin"
    if is_dome and sp_flat and off_flat:
        return "dome_neutral"
    if mixed and lean == "NEUTRAL":
        return "mixed_signals"
    if lean == "NEUTRAL":
        return "factors_canceling"
    return "low_conviction"


# ── natural-language summary ──────────────────────────────────────────────────

def _sp_label(xfip: float) -> str:
    """Conversational label with context phrasing."""
    if xfip <= 3.20: return "elite"
    if xfip <= 3.70: return "above average"
    if xfip <= 4.20: return "solid, mid-rotation"
    if xfip <= 4.70: return "slightly above average"
    if xfip <= 5.30: return "below average"
    return "hittable"


def _wrc_context(wrc: float) -> str:
    if wrc >= 115: return "well above average"
    if wrc >= 108: return "above average"
    if wrc >= 95:  return "near league average"
    if wrc >= 85:  return "below average"
    return "well below average"


def generate_summary(game: dict, proj: dict, odds: dict, rating: str) -> str:
    f     = proj["factors"]
    home  = game["home_team"]
    away  = game["away_team"]
    lean  = proj["lean"]
    score = proj["confidence_score"]

    hsp_name = game["home_probable_pitcher"]["name"]
    asp_name = game["away_probable_pitcher"]["name"]
    sp_h     = f.get("sp_home_xfip") or LA
    sp_a     = f.get("sp_away_xfip") or LA
    wrc_h    = f.get("home_wrc_plus") or 100.0
    wrc_a    = f.get("away_wrc_plus") or 100.0
    pf_raw   = f.get("park_factor") or 1.0
    pf       = round(pf_raw * 100)
    wind_mph = f.get("wind_speed_mph") or 0.0
    wind_desc= f.get("wind_desc") or ""
    temp_f   = f.get("temperature_f") or 72.0
    ump      = f.get("umpire_name") or "Unknown"
    ump_fac  = f.get("umpire_runs_factor") or 1.0
    bp_h     = f.get("home_bp_fatigue") or 0.0
    bp_a     = f.get("away_bp_fatigue") or 0.0
    bp_h_inn = f.get("home_bp_innings_used") or 0.0
    bp_a_inn = f.get("away_bp_innings_used") or 0.0
    is_dome  = "dome" in wind_desc.lower()
    weather  = f.get("weather_desc") or "Clear"

    devs    = _factor_devs(f)
    ranked  = _ranked_factors(devs, lean)
    proj_full = proj["proj_total_full"]

    full_lines = (odds or {}).get("full") or {}
    line       = full_lines.get("consensus")
    edge_val   = round(proj_full - line, 1) if line is not None else None

    # ── NO PLAY summaries ─────────────────────────────────────────────────────
    if rating == "NO PLAY":
        reason = _no_play_reason(f, proj, odds)

        if reason == "weather_uncertainty":
            return (
                f"{weather} in the forecast makes run totals unreliable here — "
                f"weather games carry too much variance to project confidently. "
                f"Skip this one."
            )

        if reason == "edge_too_thin":
            return (
                f"Model has {proj_full:.1f} runs, market has {line:.1f} — "
                f"only {abs(edge_val):.1f} runs of separation, below the "
                f"{EDGE_MIN_RUNS:.1f}-run threshold. The {lean.lower()} lean "
                f"is there but the margin isn't wide enough to play."
            )

        if reason == "dome_neutral":
            return (
                f"Both starters are mid-range ({asp_name} {sp_a:.2f} / "
                f"{hsp_name} {sp_h:.2f} xFIP), both lineups are near league "
                f"average ({away} {wrc_a:.0f} / {home} {wrc_h:.0f} wRC+), "
                f"and the roof is closed. Nothing to exploit here — pass."
            )

        if reason == "mixed_signals":
            over_factors  = [(k, v) for k, v in devs.items()
                             if v > 0.03 and k not in ("sp_home","sp_away","off_home","off_away","off_avg")]
            under_factors = [(k, v) for k, v in devs.items()
                             if v < -0.03 and k not in ("sp_home","sp_away","off_home","off_away","off_avg")]
            def _fname_num(k):
                return {"wind": f"wind ({wind_mph:.0f}mph {wind_desc.lower().replace('blowing ','')})",
                        "temp": f"temperature ({temp_f:.0f}°F)",
                        "park": f"the park (PF {pf})",
                        "ump":  f"{ump} behind the plate",
                        "bp":   "bullpen fatigue"}.get(k, k)
            over_str  = _fname_num(over_factors[0][0])  if over_factors  else "some over factors"
            under_str = _fname_num(under_factors[0][0]) if under_factors else "some under factors"
            return (
                f"{_cap1(over_str)} pushes toward the over while {under_str} "
                f"counters in the other direction — the model nets out at "
                f"{proj_full:.1f} runs with no clear dominant force. Pass."
            )

        if reason == "factors_canceling":
            return (
                f"Starters are well-matched ({asp_name} {sp_a:.2f} / "
                f"{hsp_name} {sp_h:.2f} xFIP) and lineups are similarly average "
                f"({away} {wrc_a:.0f} / {home} {wrc_h:.0f} wRC+). "
                f"Model projects {proj_full:.1f} runs but there's no exploitable "
                f"edge — pass."
            )

        # low_conviction fallback
        return (
            f"Model leans {lean.lower()} at {proj_full:.1f} runs but confidence "
            f"is low without a market line to validate the value. "
            f"Revisit when odds post."
        )

    # ── PLAY summaries ────────────────────────────────────────────────────────
    sentences = []
    top_factor = ranked[0][0]

    # Sentence 1 — lead with the single strongest factor + real numbers
    if top_factor == "sp":
        if abs(devs["sp_home"]) >= abs(devs["sp_away"]):
            dom_name, dom_xfip = hsp_name, sp_h
            opp_wrc, opp_team  = wrc_a, away
        else:
            dom_name, dom_xfip = asp_name, sp_a
            opp_wrc, opp_team  = wrc_h, home
        label     = _sp_label(dom_xfip)
        opp_ctx   = _wrc_context(opp_wrc)
        if dom_xfip > LA:
            s = (f"{dom_name} is at a {dom_xfip:.2f} xFIP this season — {label} — "
                 f"and {opp_team}'s lineup is {opp_ctx} at {opp_wrc:.0f} wRC+. "
                 f"That's a favorable matchup for the offense.")
        else:
            s = (f"{dom_name} is at {dom_xfip:.2f} xFIP — {label} — "
                 f"going up against a {opp_ctx} {opp_team} lineup ({opp_wrc:.0f} wRC+). "
                 f"Tough spot for {opp_team}'s bats.")
        sentences.append(s)

    elif top_factor == "wind":
        wd = wind_desc.lower().replace("blowing ", "")
        if devs["wind"] > 0:
            s = (f"Wind is blowing {wd} at {wind_mph:.0f}mph — "
                 f"that's the biggest factor today, and fly balls are going to carry.")
        else:
            s = (f"Wind is blowing {wd} at {wind_mph:.0f}mph — "
                 f"a stiff headwind that will knock fly balls down and help pitchers.")
        sentences.append(s)

    elif top_factor == "temp":
        if devs["temp"] < 0:
            s = (f"It's {temp_f:.0f}°F at first pitch — cold air kills the ball "
                 f"and generally helps pitchers maintain grip and command. "
                 f"Suppressed run environment.")
        else:
            s = (f"Scorching {temp_f:.0f}°F temperatures juice fly balls and "
                 f"sap pitchers' stuff early. Run-friendly conditions.")
        sentences.append(s)

    elif top_factor == "park":
        stadium = game.get("venue_name") or f"{home} park"
        if pf >= 115:
            s = (f"Coors Field (PF {pf}) is in a category of its own — "
                 f"the altitude inflates scoring regardless of pitching quality.")
        elif devs["park"] > 0:
            s = (f"{stadium} plays at PF {pf} — a genuine hitter's environment "
                 f"that adds run-scoring value on top of everything else.")
        else:
            s = (f"{stadium} plays at PF {pf} — pitcher-friendly dimensions "
                 f"that suppress run totals beyond what the pitching matchup alone would suggest.")
        sentences.append(s)

    elif top_factor == "offense":
        if devs["off_avg"] > 0:
            s = (f"{away} ({wrc_a:.0f} wRC+) and {home} ({wrc_h:.0f} wRC+) — "
                 f"both lineups grade as above-average run producers.")
        else:
            s = (f"Both lineups grade below average — {away} at {wrc_a:.0f} wRC+ "
                 f"and {home} at {wrc_h:.0f}. Weak bats on both sides suppress the total.")
        sentences.append(s)

    elif top_factor == "bp":
        if bp_h_inn >= bp_a_inn:
            s = (f"{home}'s bullpen logged {bp_h_inn:.1f} innings the last two days — "
                 f"taxed pen, and thin late-inning coverage is where runs get scored.")
        else:
            s = (f"{away}'s bullpen has {bp_a_inn:.1f} innings of heavy work "
                 f"in the last two days — degraded options when it counts.")
        sentences.append(s)

    else:  # umpire or catch-all
        if ump_fac > 1.02:
            s = (f"{ump} behind the plate historically runs a wide zone — "
                 f"more walks, more baserunners, and an above-average run environment.")
        else:
            s = (f"{asp_name} ({sp_a:.2f} xFIP) vs {hsp_name} ({sp_h:.2f} xFIP) "
                 f"is the primary driver of the {proj_full:.1f}-run projection.")
        sentences.append(s)

    # Sentence 2 — supporting factor(s) with real numbers
    _COUNTER_ELIGIBLE = {"wind", "temp", "park", "offense"}
    aligned_list = []
    counter_list = []

    for factor_name, magnitude in ranked[1:]:
        if magnitude < 0.015:
            break
        phrase = None

        if factor_name == "sp" and top_factor != "sp":
            if abs(devs["sp_home"] - devs["sp_away"]) > 0.10:
                if devs["sp_home"] > devs["sp_away"]:
                    phrase = (f"{hsp_name} ({sp_h:.2f} xFIP) is the more hittable "
                              f"of the two starters")
                else:
                    phrase = (f"{asp_name} ({sp_a:.2f} xFIP) is the weaker arm")
            else:
                phrase = (f"starters are evenly matched "
                          f"({asp_name} {sp_a:.2f} / {hsp_name} {sp_h:.2f} xFIP)")

        elif factor_name == "wind" and top_factor != "wind" and wind_mph >= 8:
            wd = wind_desc.replace("Blowing ", "").replace("blowing ", "")
            phrase = (f"{wind_mph:.0f}mph wind blowing {wd} adds an over tilt"
                      if devs["wind"] > 0 else
                      f"{wind_mph:.0f}mph wind blowing {wd} tilts under")

        elif factor_name == "temp" and top_factor != "temp" and abs(temp_f - 72) > 10:
            phrase = (f"{temp_f:.0f}°F further suppresses scoring"
                      if devs["temp"] < 0 else
                      f"{temp_f:.0f}°F heat adds to the over lean")

        elif factor_name == "park" and top_factor != "park" and abs(devs["park"]) > 0.02:
            phrase = (f"the park (PF {pf}) is hitter-friendly"
                      if devs["park"] > 0 else
                      f"the park (PF {pf}) gives pitchers an extra edge")

        elif factor_name == "offense" and top_factor != "offense" and abs(devs["off_avg"]) > 0.03:
            phrase = (f"{away} ({wrc_a:.0f}) and {home} ({wrc_h:.0f} wRC+) both grade above average"
                      if devs["off_avg"] > 0 else
                      f"both lineups grade below average "
                      f"({away} {wrc_a:.0f} / {home} {wrc_h:.0f} wRC+)")

        elif factor_name == "bp" and top_factor != "bp" and devs["bp"] > 0.015:
            heavier_team = home if bp_h_inn >= bp_a_inn else away
            heavier_inn  = bp_h_inn if bp_h_inn >= bp_a_inn else bp_a_inn
            phrase = f"{heavier_team}'s pen is taxed ({heavier_inn:.0f} innings last 2 days)"

        if phrase:
            is_ctr = _is_counter(factor_name, devs, lean) and factor_name in _COUNTER_ELIGIBLE
            (counter_list if is_ctr else aligned_list).append((factor_name, phrase))

        if len(aligned_list) + len(counter_list) >= 2:
            break

    if aligned_list and counter_list:
        sentences.append(f"{_cap1(aligned_list[0][1])}.")
        sentences.append(
            f"{_cap1(counter_list[0][1])} pulls the other way, "
            f"but not enough to flip the lean."
        )
    elif aligned_list:
        ap = [p for _, p in aligned_list]
        sentences.append(f"{_cap1(ap[0])}" + (f", and {ap[1]}." if len(ap) > 1 else "."))
    elif counter_list:
        sentences.append(
            f"{_cap1(counter_list[0][1])} pushes back, "
            f"but the {top_factor} signal dominates."
        )

    # Sentence 3 — closing with explicit numbers and lean
    if line is not None:
        sign = "+" if edge_val > 0 else ""
        sentences.append(
            f"Model has {proj_full:.1f}, market is at {line:.1f} — "
            f"{lean.lower()} by {sign}{edge_val:.1f} runs."
        )
    else:
        sentences.append(
            f"No line yet — model is at {proj_full:.1f} runs. "
            f"Watch for a {lean.lower()} when odds open."
        )

    return " ".join(sentences)


# ── card rendering ────────────────────────────────────────────────────────────

def _weather_inline(f: dict) -> str:
    """Short weather string for the header line: temp always, wind if ≥5mph."""
    temp     = f.get("temperature_f")
    wind_mph = f.get("wind_speed_mph") or 0.0
    wind_raw = f.get("wind_desc") or ""
    is_dome  = "dome" in wind_raw.lower()

    parts = []
    if temp is not None:
        parts.append(f"{temp:.0f}°F")
    if not is_dome and wind_mph >= 5:
        wd = wind_raw.replace("Blowing ", "").replace("blowing ", "")
        parts.append(f"Wind {wind_mph:.0f}mph {wd}")
    return "  ·  " + "  ·  ".join(parts) if parts else ""


def _star_line(rating: str, game: dict, lean: str, proj_full: float,
               f5_proj: float, line: Optional[float], edge: Optional[float],
               f5_line: Optional[float], factors: dict) -> str:
    """First two lines of a game block."""
    home     = game["home_team"]
    away     = game["away_team"]
    gtime    = game["game_time"]
    gtime_et = game.get("game_time_et", "")
    star_col = STARS.get(rating, "")
    lean_col = C["over"] if lean == "OVER" else C["under"] if lean == "UNDER" else C["neutral"]

    rating_pad  = rating.ljust(8)
    matchup     = f"{away} @ {home}"
    time_str    = f"{gtime} ({gtime_et})" if gtime_et and gtime_et != gtime.replace(" EDT","ET").replace(" EST","ET") else gtime
    weather_str = _weather_inline(factors)

    if rating == "NO PLAY":
        bet_str = f"{Style.DIM}NEUTRAL  Proj {proj_full:.1f}{Style.RESET_ALL}"
    else:
        if line is not None:
            sign     = "+" if edge > 0 else ""
            edge_col = lean_col if abs(edge) >= EDGE_MIN_RUNS else C["dim"]
            bet_str  = (
                f"{lean_col}{lean}{Style.RESET_ALL}  "
                f"Proj {proj_full:.1f}  ·  "
                f"Line {line:.1f}  ·  "
                f"Edge {edge_col}{sign}{edge:.1f}{Style.RESET_ALL}  "
                f"│  F5: {f5_proj:.1f}"
                + (f" vs {f5_line:.1f}" if f5_line else "")
            )
        else:
            bet_str = (
                f"{lean_col}{lean}{Style.RESET_ALL}  "
                f"Proj {proj_full:.1f}  ·  No line yet  │  F5: {f5_proj:.1f}"
            )

    line1 = (f"{star_col}{rating_pad}{Style.RESET_ALL}  "
             f"{C['bold']}{matchup}{Style.RESET_ALL}  ·  {time_str}{weather_str}")
    line2 = f"          {bet_str}"
    return f"{line1}\n{line2}"


def _wrap(text: str, width: int = 72, indent: str = "          ") -> str:
    """Word-wrap a summary paragraph."""
    words  = text.split()
    lines  = []
    current = indent
    for word in words:
        if len(current) + len(word) + 1 > width:
            lines.append(current.rstrip())
            current = indent + word + " "
        else:
            current += word + " "
    if current.strip():
        lines.append(current.rstrip())
    return "\n".join(lines)


def print_card(results: list[dict]) -> None:
    today  = results[0]["game"]["game_date"] if results else date.today().isoformat()
    width  = 80
    bar    = "═" * width

    # Header
    print(f"\n{C['cyan']}{bar}")
    print(f"  MLB TOTALS MODEL  |  {today}  |  {datetime.now().strftime('%I:%M %p')}")
    print(f"{bar}{Style.RESET_ALL}\n")

    # Separate plays from no-plays
    plays    = []
    no_plays = []
    for r in results:
        proj       = r["projection"]
        odds       = r.get("odds", {})
        full_lines = odds.get("full") or {}
        f5_lines   = odds.get("f5")   or {}
        fe         = edge_summary(proj["proj_total_full"], full_lines)
        f5e        = edge_summary(proj["proj_total_f5"],   f5_lines)
        rating     = classify_game(proj, fe)
        summary    = generate_summary(r["game"], proj, odds, rating)

        block = {
            "rating":    rating,
            "game":      r["game"],
            "proj":      proj,
            "full_edge": fe,
            "f5_edge":   f5e,
            "summary":   summary,
        }
        (plays if rating != "NO PLAY" else no_plays).append(block)

    # Sort plays: ⭐⭐⭐ first, then by confidence score
    star_order = {"⭐⭐⭐": 0, "⭐⭐": 1, "⭐": 2}
    plays.sort(key=lambda b: (
        star_order.get(b["rating"], 3),
        -b["proj"]["confidence_score"]
    ))

    # ── PLAYS ─────────────────────────────────────────────────────────────────
    divider = "─" * width
    for i, b in enumerate(plays):
        if i > 0:
            print(f"{Style.DIM}{divider}{Style.RESET_ALL}")

        fe   = b["full_edge"]
        f5e  = b["f5_edge"]
        proj = b["proj"]
        g    = b["game"]

        header = _star_line(
            b["rating"], g, proj["lean"],
            proj["proj_total_full"], proj["proj_total_f5"],
            fe.get("consensus"), fe.get("edge"),
            f5e.get("consensus"), proj["factors"],
        )
        print(header)
        print(_wrap(b["summary"]))
        print()

    # ── NO PLAYS divider ──────────────────────────────────────────────────────
    if no_plays:
        print(f"{Style.DIM}{'─' * 28}  NO PLAYS  {'─' * 31}{Style.RESET_ALL}\n")

        for i, b in enumerate(no_plays):
            if i > 0:
                print()
            g    = b["game"]
            proj = b["proj"]
            fe   = b["full_edge"]
            f5e  = b["f5_edge"]

            header = _star_line(
                "NO PLAY", g, proj["lean"],
                proj["proj_total_full"], proj["proj_total_f5"],
                fe.get("consensus"), fe.get("edge"),
                f5e.get("consensus"), proj["factors"],
            )
            print(header)
            print(_wrap(b["summary"]))

        print()

    # ── PARLAY ────────────────────────────────────────────────────────────────
    parlay_legs = [b for b in plays if b["rating"] in ("⭐⭐⭐", "⭐⭐")]
    parlay_legs.sort(key=lambda b: (
        star_order.get(b["rating"], 3),
        -abs(b["full_edge"].get("edge") or 0),
        -b["proj"]["confidence_score"],
    ))
    parlay_legs = parlay_legs[:3]

    if len(parlay_legs) >= 2:
        print(f"{C['mag']}{bar}")
        print(f"  3-LEG PARLAY")
        print(f"{bar}{Style.RESET_ALL}")
        for i, b in enumerate(parlay_legs, 1):
            g    = b["game"]
            proj = b["proj"]
            fe   = b["full_edge"]
            lean = proj["lean"]
            lc   = C["over"] if lean == "OVER" else C["under"]

            matchup  = f"{g['away_team']} @ {g['home_team']}"
            proj_str = f"{proj['proj_total_full']:.1f}"
            line_str = f"{fe['consensus']:.1f}" if fe.get("consensus") else "—"
            edge_str = (f"{fe['edge']:+.1f}" if fe.get("edge") is not None else "—")
            stars    = b["rating"]

            print(f"  {i}.  {matchup:<22}  "
                  f"{lc}{lean}{Style.RESET_ALL} {proj_str:<6}  "
                  f"Line {line_str:<6}  Edge {edge_str:<6}  {stars}")
        print(f"{C['mag']}{bar}{Style.RESET_ALL}\n")


# ── pipeline ──────────────────────────────────────────────────────────────────

def run(game_date: Optional[str] = None, quiet: bool = False,
        use_odds: bool = True) -> list[dict]:

    if game_date is None:
        game_date = date.today().isoformat()

    db.init_db()
    logger.info(f"Starting MLB Totals Model for {game_date}")

    pitcher_db = build_pitcher_db()
    team_bullpen_db = build_team_bullpen_db(pitcher_db)
    offense_db = build_offense_db()

    # Props databases (loaded once, shared across all games)
    try:
        pitcher_k_db  = build_pitcher_k_db()
        batter_props_db = build_batter_props_db()
        logger.info(f"Props DBs loaded: {len(pitcher_k_db)} pitchers, {len(batter_props_db)} batters")
    except Exception as e:
        logger.warning(f"Props DB load failed (props will be skipped): {e}")
        pitcher_k_db  = {}
        batter_props_db = {}

    all_lines = {}
    if use_odds:
        logger.info("Fetching market lines from The Odds API...")
        all_lines = fetch_all_lines()

    games = fetch_schedule(game_date)
    if not games:
        logger.warning(f"No games found for {game_date}")
        return []

    logger.info(f"Processing {len(games)} games...")
    results = []

    for game in games:
        gk   = game["game_pk"]
        home = game["home_team"]
        away = game["away_team"]
        logger.info(f"  {away} @ {home} (pk={gk})")

        home_sp  = get_pitcher_metrics(game["home_probable_pitcher"], pitcher_db)
        away_sp  = get_pitcher_metrics(game["away_probable_pitcher"], pitcher_db)
        home_off = get_team_offense(home, offense_db,
                                    opp_throws=game["away_probable_pitcher"].get("throws"))
        away_off = get_team_offense(away, offense_db,
                                    opp_throws=game["home_probable_pitcher"].get("throws"))
        weather  = fetch_weather(home, game_time_et=game.get("game_time"))
        umpire   = get_umpire_rating(game.get("home_umpire"))
        home_bp  = calculate_bullpen_fatigue(game["home_team_id"], is_home=True, team_abb=home, team_bullpen_db=team_bullpen_db)
        away_bp  = calculate_bullpen_fatigue(game["away_team_id"], is_home=False, team_abb=away, team_bullpen_db=team_bullpen_db)

        proj = project_game(
            home_team=home, away_team=away,
            home_sp_metrics=home_sp, away_sp_metrics=away_sp,
            home_offense=home_off, away_offense=away_off,
            weather=weather, umpire=umpire,
            home_bullpen=home_bp, away_bullpen=away_bp,
        )

        odds = get_game_lines(home, away, all_lines)

        # ── Props ─────────────────────────────────────────────────────────────
        props = []
        try:
            odds_key = os.environ.get("ODDS_API_KEY")
            props_lines = fetch_props_lines(home, away, game_date, odds_api_key=odds_key)
            home_sp_name = game["home_probable_pitcher"].get("name") or ""
            away_sp_name = game["away_probable_pitcher"].get("name") or ""
            props = get_game_props(
                game         = game,
                home_sp_name = home_sp_name,
                away_sp_name = away_sp_name,
                factors      = proj["factors"],
                umpire       = umpire,
                pitcher_k_db = pitcher_k_db,
                batter_db    = batter_props_db,
                props_lines  = props_lines,
            )
            for p in props:
                db.write_prop({
                    "game_date":   game_date,
                    "game_pk":     gk,
                    "player_name": p["player_name"],
                    "team":        p.get("team", ""),
                    "market":      p["market"],
                    "projection":  p["projection"],
                    "line":        p.get("line"),
                    "edge":        p.get("edge"),
                    "edge_pct":    p.get("edge_pct"),
                    "lean":        p.get("lean"),
                    "is_play":     1 if p.get("is_play") else 0,
                })
        except Exception as e:
            logger.warning(f"Props fetch/store failed for {away}@{home}: {e}")

        results.append({"game": game, "projection": proj, "odds": odds, "props": props})

        f         = proj["factors"]
        full_cons = (odds.get("full") or {}).get("consensus")
        f5_cons   = (odds.get("f5")   or {}).get("consensus")
        _fe       = edge_summary(proj["proj_total_full"], odds.get("full") or {})

        db.upsert_projection({
            "game_date":        game_date,
            "game_pk":          gk,
            "home_team":        home,
            "away_team":        away,
            "home_sp":          home_sp.get("name"),
            "away_sp":          away_sp.get("name"),
            "home_sp_xfip":     home_sp.get("xfip"),
            "away_sp_xfip":     away_sp.get("xfip"),
            "home_sp_siera":    home_sp.get("siera"),
            "away_sp_siera":    away_sp.get("siera"),
            "home_wrc_plus":    home_off.get("wrc_plus"),
            "away_wrc_plus":    away_off.get("wrc_plus"),
            "park_factor":      f.get("park_factor"),
            "wind_speed":       f.get("wind_speed_mph"),
            "wind_direction":   f.get("wind_direction"),
            "temperature":      f.get("temperature_f"),
            "umpire_name":      f.get("umpire_name"),
            "umpire_factor":    f.get("umpire_runs_factor"),
            "home_bp_fatigue":  f.get("home_bp_fatigue"),
            "away_bp_fatigue":  f.get("away_bp_fatigue"),
            "proj_total_full":  proj["proj_total_full"],
            "proj_total_f5":    proj["proj_total_f5"],
            "confidence":       proj["confidence"],
            "confidence_score": proj["confidence_score"],
            "factors_json":     proj["factors"],
            "lean":             proj["lean"],
            "star_rating":      classify_game(proj, _fe),
        })

        if full_cons is not None:
            db.log_result(
                game_pk=gk, game_date=game_date,
                actual_total=None, actual_f5_total=None,
                line_full=full_cons, line_f5=f5_cons,
            )

    try:
        log_opening_lines(game_date, results)
    except Exception as e:
        logger.warning(f"Line tracker failed (non-fatal): {e}")

    if not quiet:
        print_card(results)

        record = db.get_season_record()
        if record.get("total", 0) > 0:
            correct = (record.get("correct_over", 0) or 0) + (record.get("correct_under", 0) or 0)
            total   = record["total"] - (record.get("pushes", 0) or 0)
            if total > 0:
                pct = correct / total * 100
                print(f"{C['cyan']}Season Record (vs line): "
                      f"{correct}-{total-correct} ({pct:.1f}%){Style.RESET_ALL}\n")

    logger.info(f"Complete. {len(results)} games projected.")
    return results


# ── entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MLB Totals Model")
    parser.add_argument("date", nargs="?", default=None,
                        help="Game date YYYY-MM-DD (default: today)")
    parser.add_argument("--quiet",   "-q", action="store_true")
    parser.add_argument("--no-odds", action="store_true",
                        help="Skip Odds API")
    args = parser.parse_args()
    run(game_date=args.date, quiet=args.quiet, use_odds=not args.no_odds)
