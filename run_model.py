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
from modules.bullpen     import calculate_bullpen_fatigue
from modules.umpires     import get_umpire_rating
from modules.projections import project_game
from modules.odds        import fetch_all_lines, get_game_lines, edge_summary

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
    if xfip <= 3.00: return "elite"
    if xfip <= 3.50: return "above-average"
    if xfip <= 4.10: return "solid"
    if xfip <= 4.60: return "league-average"
    if xfip <= 5.50: return "below-average"
    return "a significant liability"


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
    wind_fac = f.get("wind_factor") or 1.0
    temp_f   = f.get("temperature_f") or 72.0
    temp_fac = f.get("temp_factor") or 1.0
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
                f"{weather} is in the forecast for this game, introducing uncertainty "
                f"that makes projecting run totals unreliable. "
                f"Even with a model lean of {proj_full:.1f}, weather-affected games "
                f"carry too much variance to play."
            )

        if reason == "edge_too_thin":
            return (
                f"The model projects {proj_full:.1f} runs against the market's "
                f"{line:.1f} — a gap of only {edge_val:+.1f} runs, short of the "
                f"{EDGE_MIN_RUNS:.1f}-run minimum edge required. "
                f"The lean is there but the value is not."
            )

        if reason == "dome_neutral":
            sp_desc = (f"neither starter separates from average "
                       f"({asp_name} {sp_a:.2f} / {hsp_name} {sp_h:.2f} xFIP)")
            return (
                f"The retractable roof eliminates weather entirely, and {sp_desc}. "
                f"With both lineups within 5%% of league-average offense "
                f"({away} {wrc_a:.0f} / {home} {wrc_h:.0f} wRC+), "
                f"there are no exploitable factors in this environment."
            )

        if reason == "mixed_signals":
            # Identify the two opposing forces
            over_factors  = [(k, v) for k, v in devs.items() if v > 0.03 and k not in ("sp_home","sp_away","off_home","off_away","off_avg")]
            under_factors = [(k, v) for k, v in devs.items() if v < -0.03 and k not in ("sp_home","sp_away","off_home","off_away","off_avg")]

            def _fname(k):
                return {"sp_avg":"the pitching matchup","park":"the park factor",
                        "wind":"wind","temp":"temperature","ump":"the umpire",
                        "bp":"bullpen fatigue","offense":"the offenses"}.get(k, k)

            over_str  = _fname(over_factors[0][0])  if over_factors  else "some over factors"
            under_str = _fname(under_factors[0][0]) if under_factors else "some under factors"

            return (
                f"This game sends conflicting signals: {over_str} pushes toward the over "
                f"while {under_str} counters with an under lean. "
                f"The net projection of {proj_full:.1f} runs sits close to neutral, "
                f"and without a clear dominant factor we pass."
            )

        if reason == "factors_canceling":
            sp_line = (f"The pitching is near league average on both sides "
                       f"({asp_name} {sp_a:.2f} / {hsp_name} {sp_h:.2f} xFIP), "
                       if abs(devs["sp_avg"]) < 0.10 else
                       f"The pitching differential ({asp_name} {sp_a:.2f} vs "
                       f"{hsp_name} {sp_h:.2f} xFIP) is partially offset by other factors, ")
            off_line = (f"and the offenses are similarly matched "
                        f"({away} {wrc_a:.0f} / {home} {wrc_h:.0f} wRC+)."
                        if abs(devs["off_avg"]) < 0.05 else
                        f"and the offenses add little differentiation.")
            return (
                f"{sp_line}{off_line} "
                f"The model's projection of {proj_full:.1f} runs lands too close "
                f"to the 9.0 neutral baseline to identify a clear edge."
            )

        # low_conviction fallback
        return (
            f"The model sees a {lean.lower()} lean at {proj_full:.1f} runs but "
            f"confidence is insufficient (score {score:.2f}) to act without a "
            f"market line to confirm value. "
            f"Revisit after lines post closer to first pitch."
        )

    # ── PLAY summaries ────────────────────────────────────────────────────────
    sentences = []

    # Sentence 1 — strongest factor
    top_factor = ranked[0][0]

    if top_factor == "sp":
        if abs(devs["sp_home"]) > abs(devs["sp_away"]):
            dominant_name  = hsp_name
            dominant_xfip  = sp_h
            dominant_team  = home
            other_name     = asp_name
            other_xfip     = sp_a
            other_team     = away
            dominant_label = _sp_label(sp_h)
            other_label    = _sp_label(sp_a)
            if sp_h > LA:
                # Bad home starter → AWAY scores → over push
                s = (f"{dominant_name} ({dominant_team}, xFIP {dominant_xfip:.2f}) "
                     f"is {dominant_label} on the mound, creating a clear "
                     f"vulnerability for {away}'s offense to exploit.")
            else:
                # Good home starter → fewer runs
                s = (f"{dominant_name} ({dominant_team}, xFIP {dominant_xfip:.2f}) "
                     f"is {dominant_label} — the dominant pitching factor "
                     f"suppressing {away}'s run-scoring potential.")
        else:
            dominant_name  = asp_name
            dominant_xfip  = sp_a
            dominant_team  = away
            dominant_label = _sp_label(sp_a)
            if sp_a > LA:
                s = (f"{dominant_name} ({dominant_team}, xFIP {dominant_xfip:.2f}) "
                     f"is {dominant_label}, leaving {home}'s lineup a "
                     f"favorable matchup to score runs.")
            else:
                s = (f"{dominant_name} ({dominant_team}, xFIP {dominant_xfip:.2f}) "
                     f"is {dominant_label} — a strong under anchor keeping "
                     f"{home}'s bats in check.")
        sentences.append(s)

    elif top_factor == "wind":
        wd = wind_desc.lower().replace("blowing ", "")
        if devs["wind"] > 0:
            s = (f"Wind is the dominant factor today: {wind_mph:.0f}mph blowing "
                 f"{wd} at first pitch will carry fly balls and meaningfully "
                 f"inflate run totals.")
        else:
            s = (f"A stiff {wind_mph:.0f}mph wind blowing {wd} is the biggest "
                 f"factor here, knocking down fly balls and suppressing "
                 f"extra-base production throughout the game.")
        sentences.append(s)

    elif top_factor == "temp":
        if devs["temp"] < 0:
            s = (f"Cold conditions at first pitch ({temp_f:.0f}°F) are the "
                 f"primary drag on scoring — the ball dies in cold air and "
                 f"pitchers typically maintain grip and command better.")
        else:
            s = (f"Scorching {temp_f:.0f}°F temperatures will juice the ball "
                 f"and sap pitchers' stuff, creating a run-friendly environment "
                 f"that supports the over.")
        sentences.append(s)

    elif top_factor == "park":
        stadium = game.get("venue_name") or f"{home} stadium"
        if pf >= 115:
            s = (f"Coors Field (PF {pf}) overwhelms most other factors — "
                 f"the altitude inflates run scoring regardless of pitching "
                 f"quality, and that remains the defining feature here.")
        elif devs["park"] > 0:
            s = (f"{stadium} is a legitimate hitter's park (PF {pf}), "
                 f"adding run-scoring value that compounds the other "
                 f"over-leaning factors in this game.")
        else:
            s = (f"{stadium}'s pitcher-friendly dimensions (PF {pf}) are the "
                 f"strongest under factor, suppressing run totals beyond what "
                 f"the pitching matchup alone would suggest.")
        sentences.append(s)

    elif top_factor == "offense":
        if devs["off_avg"] > 0:
            better = (away, wrc_a) if wrc_a > wrc_h else (home, wrc_h)
            s = (f"{better[0]}'s lineup grades above average "
                 f"(wRC+ {better[1]:.0f}) and is the strongest offensive "
                 f"factor pushing this total higher.")
        else:
            weaker = (away, wrc_a) if wrc_a < wrc_h else (home, wrc_h)
            s = (f"Both lineups grade below league average in run production "
                 f"— {away} ({wrc_a:.0f}) and {home} ({wrc_h:.0f}) wRC+ "
                 f"— making quality at-bats scarce.")
        sentences.append(s)

    elif top_factor == "bp":
        if bp_h > bp_a:
            s = (f"{home}'s bullpen is the key vulnerability here — "
                 f"{bp_h_inn:.1f} relief innings over the past two days "
                 f"means degraded late-inning options and a greater risk of "
                 f"runs in the middle and back of the order.")
        else:
            s = (f"{away}'s bullpen has been heavily taxed recently "
                 f"({bp_a_inn:.1f} relief innings in 2 days), creating a "
                 f"meaningful late-inning liability that supports the over.")
        sentences.append(s)

    else:  # umpire or catch-all
        if ump_fac > 1.01:
            s = (f"{ump} behind the plate tends to generate above-average "
                 f"run environments — a wider zone means more walks and "
                 f"more baserunners.")
        else:
            s = (f"The pitching matchup ({asp_name} {sp_a:.2f} / "
                 f"{hsp_name} {sp_h:.2f} xFIP) drives the projection to "
                 f"{proj_full:.1f} runs.")
        sentences.append(s)

    # Sentence 2 — supporting factors, split into aligned vs counter-lean
    # Only wind/temp/park/offense are eligible for counter treatment (clear unambiguous direction)
    _COUNTER_ELIGIBLE = {"wind", "temp", "park", "offense"}
    aligned_list = []   # (factor_name, phrase) supporting the lean
    counter_list = []   # (factor_name, phrase) opposing the lean

    for factor_name, magnitude in ranked[1:]:
        if magnitude < 0.015:
            break
        phrase = None

        if factor_name == "sp" and top_factor != "sp":
            mismatch = abs(devs["sp_home"] - devs["sp_away"]) > 0.10
            if mismatch:
                if devs["sp_home"] > devs["sp_away"]:
                    phrase = (f"{hsp_name} (xFIP {sp_h:.2f}) is the weaker of the two "
                              f"starters, favouring {away}'s bats")
                else:
                    phrase = (f"{asp_name} (xFIP {sp_a:.2f}) is the more vulnerable arm, "
                              f"giving {home} the pitching advantage")
            else:
                phrase = (f"starters are similarly matched ({asp_name} {sp_a:.2f} / "
                          f"{hsp_name} {sp_h:.2f} xFIP)")

        elif factor_name == "wind" and top_factor != "wind" and wind_mph >= 8:
            wd = wind_desc.replace("Blowing ", "").replace("blowing ", "")
            if devs["wind"] > 0:
                phrase = f"{wind_mph:.0f}mph winds blowing {wd} add an over boost"
            else:
                phrase = f"{wind_mph:.0f}mph winds blowing {wd} provide a modest under tilt"

        elif factor_name == "temp" and top_factor != "temp" and abs(temp_f - 72) > 10:
            if devs["temp"] < 0:
                phrase = f"{temp_f:.0f}°F temperatures further suppress scoring"
            else:
                phrase = f"{temp_f:.0f}°F heat compounds the over lean"

        elif factor_name == "park" and top_factor != "park" and abs(devs["park"]) > 0.02:
            if devs["park"] > 0:
                phrase = f"the park (PF {pf}) tilts hitter-friendly"
            else:
                phrase = f"the park (PF {pf}) provides an under tilt"

        elif factor_name == "offense" and top_factor != "offense" and abs(devs["off_avg"]) > 0.03:
            better = max((wrc_h, home), (wrc_a, away))
            if devs["off_avg"] > 0:
                phrase = f"{better[1]}'s lineup (wRC+ {better[0]:.0f}) adds offensive upside"
            else:
                phrase = f"both lineups grade below average in run production"

        elif factor_name == "bp" and top_factor != "bp":
            if devs["bp"] > 0.015:
                heavier_team = home if bp_h > bp_a else away
                heavier_inn  = bp_h_inn if bp_h > bp_a else bp_a_inn
                phrase = (f"{heavier_team}'s bullpen has logged {heavier_inn:.0f} relief "
                          f"innings over two days")

        if phrase:
            is_ctr = _is_counter(factor_name, devs, lean) and factor_name in _COUNTER_ELIGIBLE
            if is_ctr:
                counter_list.append((factor_name, phrase))
            else:
                aligned_list.append((factor_name, phrase))

        if len(aligned_list) + len(counter_list) >= 2:
            break

    if aligned_list:
        ap = [p for _, p in aligned_list]
        if len(ap) == 1:
            sentences.append(f"{_cap1(ap[0])}.")
        else:
            sentences.append(f"{_cap1(ap[0])}, and {ap[1]}.")

    if counter_list:
        ctr_name, _ = counter_list[0]
        intro = _counter_intro(ctr_name, devs, wind_mph, wind_desc, temp_f, pf)
        what_wins = [_factor_short_desc(top_factor, devs, sp_h, sp_a, temp_f, pf)]
        if aligned_list:
            what_wins.append(_factor_short_desc(aligned_list[0][0], devs, sp_h, sp_a, temp_f, pf))
        outweigh_str = " and ".join(what_wins)
        sentences.append(
            f"{intro} — but {outweigh_str} outweigh that factor, "
            f"model still leans {lean.lower()}."
        )

    # Sentence 3 — closing with recommendation / line
    if line is not None:
        sign = "+" if edge_val > 0 else ""
        sentences.append(
            f"Our {proj_full:.1f}-run projection sits {sign}{edge_val:.1f} against "
            f"the market's {line:.1f} — a {lean.lower()} play."
        )
    else:
        lean_lc = lean.lower()
        sentences.append(
            f"No line is posted yet, but the {proj['confidence'].lower()}-confidence "
            f"model signal projects {proj_full:.1f} runs — watch for a {lean_lc} "
            f"opportunity when odds open."
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
    offense_db = build_offense_db()

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
        home_off = get_team_offense(home, offense_db)
        away_off = get_team_offense(away, offense_db)
        weather  = fetch_weather(home, game_time_et=game.get("game_time"))
        umpire   = get_umpire_rating(game.get("home_umpire"))
        home_bp  = calculate_bullpen_fatigue(game["home_team_id"], is_home=True)
        away_bp  = calculate_bullpen_fatigue(game["away_team_id"], is_home=False)

        proj = project_game(
            home_team=home, away_team=away,
            home_sp_metrics=home_sp, away_sp_metrics=away_sp,
            home_offense=home_off, away_offense=away_off,
            weather=weather, umpire=umpire,
            home_bullpen=home_bp, away_bullpen=away_bp,
        )

        odds = get_game_lines(home, away, all_lines)
        results.append({"game": game, "projection": proj, "odds": odds})

        f         = proj["factors"]
        full_cons = (odds.get("full") or {}).get("consensus")
        f5_cons   = (odds.get("f5")   or {}).get("consensus")

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
        })

        if full_cons is not None:
            db.log_result(
                game_pk=gk, game_date=game_date,
                actual_total=None, actual_f5_total=None,
                line_full=full_cons, line_f5=f5_cons,
            )

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
