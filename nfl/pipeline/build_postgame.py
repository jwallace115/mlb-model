#!/usr/bin/env python3
"""
Post-game builder: game sheets + pick verdicts for NFL.

For every graded ai_nfl / sim_nfl pick, decomposes the result into chain links,
names the link that moved most, and checks whether the stated reason happened.

Outputs per week:
  nfl/data/postgame/week=2026_WW/game_<game_id>.json   (game sheet)
  nfl/data/postgame/week=2026_WW/verdicts.parquet       (one row per graded row)

PM-1 Item 2, P49.
"""
import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(os.environ.get("MLB_REPO_ROOT") or Path(__file__).resolve().parent.parent.parent)
sys.path.insert(0, str(ROOT / "shared" / "pipeline"))
import pick_sources as ps
import picks_grader as pg
import picks_ledger as pl

RESULTS_DIR = Path(os.environ.get("RESULTS_ARCHIVE_DIR") or (ROOT / "data" / "results_archive"))
POSTGAME_DIR = Path(os.environ.get("POSTGAME_OUT_DIR") or (ROOT / "nfl" / "data" / "postgame"))
LEDGER_DIR = Path(os.environ.get("PICKS_LEDGER_DIR") or "/root/private/ledger")

ALLOWED_OWNERS = {"ai_nfl", "sim_nfl"}
GARBAGE_DIFF = 17  # Q4 |score_differential| >= 17

# Chain definitions: market -> list of link names
CHAIN_DEF = {
    "prop:rec":      ["plays", "pass_rate", "share", "catch_rate"],
    "prop:rec_yds":  ["plays", "pass_rate", "share", "yards_per_target"],
    "prop:rush_att": ["plays", "run_rate", "carry_share"],
    "prop:rush_yds": ["plays", "run_rate", "carry_share", "yards_per_carry"],
    "prop:pass_att": ["plays", "pass_rate", "qb_share"],
    "prop:pass_cmp": ["plays", "pass_rate", "qb_share", "completion_rate"],
    "prop:pass_yds": ["plays", "pass_rate", "qb_share", "yards_per_attempt"],
}

# Tag -> thesis link map (P49)
TAG_TO_THESIS = {
    "role_change":   "share",
    "usage_trend":   "share",
    "injury_news":   "share",
    "game_script":   None,  # depends on market type
    "weather":       None,  # depends on market type
    "matchup":       None,
    "price_vs_sharp": "price",
    "line_move":     "price",
    "sim_v1":        None,
    "no_view":       None,
}

# Game-script tag -> thesis link by market
def _game_script_link(market):
    if market.startswith("prop:pass") or market.startswith("prop:rec"):
        return "pass_rate"
    if market.startswith("prop:rush"):
        return "run_rate"
    if market in ("total",):
        return "points"
    return "script"

def _weather_matchup_link(market):
    if market.startswith("prop:"):
        return "efficiency"
    return "points"


# ── PBP stats computation ──

def _team_volume(pbp, team):
    """Compute team volume stats from PBP slice."""
    team_plays = pbp[pbp["posteam"] == team]
    # Exclude penalties, timeouts, etc.
    real_plays = team_plays[team_plays["play_type"].isin(
        ["pass", "run", "qb_kneel", "qb_spike"])]

    n_plays = len(real_plays)
    dropbacks = int(team_plays["pass_attempt"].sum())  # includes sacks
    rush_att = int(team_plays["rush_attempt"].sum())
    pass_rate = dropbacks / n_plays if n_plays > 0 else 0
    run_rate = 1 - pass_rate if n_plays > 0 else 0

    # pass_oe if available
    pass_oe = None
    if "pass_oe" in team_plays.columns:
        valid = team_plays["pass_oe"].dropna()
        if len(valid):
            pass_oe = float(valid.mean())

    return {
        "plays": n_plays,
        "dropbacks": dropbacks,
        "rush_attempts": rush_att,
        "pass_rate": round(pass_rate, 4),
        "run_rate": round(run_rate, 4),
        "pass_oe": pass_oe,
    }


def _player_stats_from_pbp(pbp, team):
    """Compute per-player stats from PBP for one team."""
    team_plays = pbp[pbp["posteam"] == team]
    players = {}

    # Receivers
    rec_plays = team_plays[team_plays["receiver_player_id"].notna()]
    for pid, grp in rec_plays.groupby("receiver_player_id"):
        name = str(grp["receiver_player_name"].iloc[0])
        targets = len(grp)
        receptions = int(grp["complete_pass"].sum())
        rec_yards = int(grp["receiving_yards"].fillna(0).sum())
        players[pid] = players.get(pid, {"name": name, "id": pid})
        players[pid].update({
            "targets": targets, "receptions": receptions,
            "receiving_yards": rec_yards,
        })

    # Rushers
    rush_plays = team_plays[team_plays["rusher_player_id"].notna() &
                             (team_plays["rush_attempt"] == 1)]
    for pid, grp in rush_plays.groupby("rusher_player_id"):
        name = str(grp["rusher_player_name"].iloc[0])
        carries = len(grp)
        rush_yards = int(grp["rushing_yards"].fillna(0).sum())
        if pid not in players:
            players[pid] = {"name": name, "id": pid}
        players[pid].update({
            "carries": carries, "rushing_yards": rush_yards,
        })

    # Passers
    pass_plays = team_plays[team_plays["passer_player_id"].notna() &
                             (team_plays["pass_attempt"] == 1)]
    for pid, grp in pass_plays.groupby("passer_player_id"):
        name = str(grp["passer_player_name"].iloc[0])
        attempts = len(grp)
        completions = int(grp["complete_pass"].sum())
        pass_yards = int(grp["passing_yards"].fillna(0).sum())
        if pid not in players:
            players[pid] = {"name": name, "id": pid}
        players[pid].update({
            "pass_attempts": attempts, "completions": completions,
            "passing_yards": pass_yards,
        })

    return players


def _extract_injuries(pbp):
    """Extract in-game injuries from PBP desc."""
    injuries = []
    injury_re = re.compile(r"was injured during the play", re.I)
    for _, row in pbp.iterrows():
        desc = str(row.get("desc", ""))
        if injury_re.search(desc):
            # Try to identify the player
            player = ""
            for col in ("receiver_player_name", "rusher_player_name",
                        "passer_player_name"):
                if row.get(col) and str(row[col]) != "nan":
                    player = str(row[col])
                    break
            if not player:
                # Try to extract from desc
                m = re.match(r".*?([A-Z]\.[A-Za-z'-]+).*was injured", desc)
                if m:
                    player = m.group(1)

            team = str(row.get("posteam", ""))
            injuries.append({
                "player": player,
                "team": team,
                "quarter": int(row.get("qtr", 0)),
                "play_id": int(row.get("play_id", 0)),
                "desc": desc[:200],
            })
    return injuries


def _game_script(pbp, home, away):
    """Compute script stats: time leading/trailing, halftime score, OT, garbage."""
    result = {}
    for team in (home, away):
        team_label = "home" if team == home else "away"
        # Score differential from team's perspective
        if team_label == "home":
            diff = pbp["home_score"] - pbp["away_score"]
        else:
            diff = pbp["away_score"] - pbp["home_score"]

        # Simplified: count plays in each state (not seconds, as PBP doesn't have reliable time)
        leading_7 = int((diff >= 7).sum())
        leading_14 = int((diff >= 14).sum())
        trailing_7 = int((diff <= -7).sum())
        trailing_14 = int((diff <= -14).sum())

        # Halftime score
        q2 = pbp[pbp["qtr"] <= 2]
        if not q2.empty:
            ht_home = int(q2["home_score"].max())
            ht_away = int(q2["away_score"].max())
        else:
            ht_home, ht_away = 0, 0

        # Garbage time: Q4 with |score_differential| >= 17
        q4 = pbp[pbp["qtr"] == 4]
        garbage_plays = int((q4["score_differential"].abs() >= GARBAGE_DIFF).sum()) if not q4.empty else 0

        result[team_label] = {
            "plays_leading_7": leading_7,
            "plays_leading_14": leading_14,
            "plays_trailing_7": trailing_7,
            "plays_trailing_14": trailing_14,
            "halftime_score": {"home": ht_home, "away": ht_away},
            "garbage_time_plays": garbage_plays,
        }

    # OT
    result["overtime"] = bool((pbp["qtr"] > 4).any())

    return result


def _turnovers(pbp, home, away):
    """Count turnovers per team."""
    result = {}
    for team in (home, away):
        label = "home" if team == home else "away"
        team_plays = pbp[pbp["posteam"] == team]
        ints = int(team_plays["interception"].sum())
        fumbles_lost = int(team_plays["fumble_lost"].sum()) if "fumble_lost" in pbp.columns else 0
        result[label] = {"interceptions": ints, "fumbles_lost": fumbles_lost,
                          "total": ints + fumbles_lost}
    return result


def _red_zone(pbp, home, away):
    """Red zone trips and TDs per team."""
    result = {}
    for team in (home, away):
        label = "home" if team == home else "away"
        team_plays = pbp[(pbp["posteam"] == team) & (pbp["yardline_100"] <= 20)]
        # Trips: unique drives entering the red zone
        if "drive" in pbp.columns:
            rz_drives = team_plays["drive"].nunique()
        else:
            rz_drives = 0
        rz_tds = int(team_plays["touchdown"].sum())
        result[label] = {"trips": rz_drives, "touchdowns": rz_tds}
    return result


def _non_offensive_tds(pbp):
    """Count non-offensive TDs (defensive, special teams)."""
    # return_touchdown, interception with TD, fumble recovery TD
    count = 0
    if "return_touchdown" in pbp.columns:
        count += int(pbp["return_touchdown"].fillna(0).sum())
    return count


# ── Chain decomposition ──

def _chain_decompose(actual, prior, L, A, market):
    """Decompose ln(A/L) into book_vs_prior + Σ link_terms.

    actual/prior: dicts with link values (plays, pass_rate, share, etc.)
    L: bettor's line
    A: actual stat value
    Returns dict with book_vs_prior, links (each with actual, prior, term), primary_link.
    """
    chain = CHAIN_DEF.get(market)
    if chain is None:
        return None

    if A == 0 or L == 0:
        return {"zero_actual": True, "A": A, "L": L, "chain": "none"}

    # E = product of priors
    E = 1.0
    for link in chain:
        if link not in prior or prior[link] is None or prior[link] == 0:
            return None  # missing prior
        E *= prior[link]

    if E == 0:
        return None

    book_vs_prior = math.log(E / L)

    links = {}
    for link in chain:
        a_val = actual.get(link, 0)
        p_val = prior.get(link, 0)
        if a_val == 0 or p_val == 0:
            links[link] = {"actual": a_val, "prior": p_val, "term": 0.0}
        else:
            links[link] = {
                "actual": a_val,
                "prior": p_val,
                "term": math.log(a_val / p_val),
            }

    # primary_link = largest |term|
    primary_link = max(links, key=lambda k: abs(links[k]["term"])) if links else None

    return {
        "book_vs_prior": book_vs_prior,
        "links": links,
        "primary_link": primary_link,
        "A": A,
        "L": L,
        "E": E,
        "zero_actual": False,
    }


# ── Build priors from PBP slices ──

def _build_team_priors(pbp_slices, team, week, season=2026):
    """Build team-level priors from weeks < week. Returns dict or None if < 2 games."""
    prior_games = []
    for gid, g_pbp in pbp_slices.items():
        w = int(g_pbp["week"].iloc[0])
        if w >= week:
            continue
        if g_pbp["season"].iloc[0] != season:
            continue
        # Check if team played in this game
        if team not in (g_pbp["home_team"].iloc[0], g_pbp["away_team"].iloc[0]):
            continue
        vol = _team_volume(g_pbp, team)
        prior_games.append(vol)

    if len(prior_games) < 2:
        return None, "insufficient_games"

    # Average across games
    avg = {}
    for key in ("plays", "dropbacks", "rush_attempts", "pass_rate", "run_rate"):
        avg[key] = np.mean([g[key] for g in prior_games])

    return avg, f"2026_w<{week}_n={len(prior_games)}"


def _build_player_priors(pbp_slices, player_id, team, week, season=2026):
    """Build player-level priors from weeks < week."""
    prior_games = []
    for gid, g_pbp in pbp_slices.items():
        w = int(g_pbp["week"].iloc[0])
        if w >= week:
            continue
        if g_pbp["season"].iloc[0] != season:
            continue
        if team not in (g_pbp["home_team"].iloc[0], g_pbp["away_team"].iloc[0]):
            continue
        p_stats = _player_stats_from_pbp(g_pbp, team)
        team_vol = _team_volume(g_pbp, team)
        if player_id in p_stats:
            ps_row = p_stats[player_id]
            prior_games.append({
                "team_vol": team_vol,
                "player": ps_row,
            })

    if len(prior_games) < 2:
        return None, "insufficient_games"

    return prior_games, f"2026_w<{week}_n={len(prior_games)}"


def _compute_chain_actual_prior(market, player_id, team, game_pbp, pbp_slices, week, bettor_line):
    """Compute actual and prior chain link values for one pick."""
    chain = CHAIN_DEF.get(market)
    if chain is None:
        return None, None, None

    team_vol = _team_volume(game_pbp, team)
    p_stats = _player_stats_from_pbp(game_pbp, team)
    player_stats = p_stats.get(player_id, {})

    # Build actual dict
    actual = {"plays": team_vol["plays"]}
    dropbacks = team_vol["dropbacks"]

    if "pass_rate" in chain:
        actual["pass_rate"] = team_vol["pass_rate"]
    if "run_rate" in chain:
        actual["run_rate"] = team_vol["run_rate"]
    if "share" in chain:
        targets = player_stats.get("targets", 0)
        actual["share"] = targets / dropbacks if dropbacks > 0 else 0
    if "catch_rate" in chain:
        targets = player_stats.get("targets", 0)
        recs = player_stats.get("receptions", 0)
        actual["catch_rate"] = recs / targets if targets > 0 else 0
    if "yards_per_target" in chain:
        targets = player_stats.get("targets", 0)
        rec_yds = player_stats.get("receiving_yards", 0)
        actual["yards_per_target"] = rec_yds / targets if targets > 0 else 0
    if "carry_share" in chain:
        carries = player_stats.get("carries", 0)
        rush_att = team_vol["rush_attempts"]
        actual["carry_share"] = carries / rush_att if rush_att > 0 else 0
    if "yards_per_carry" in chain:
        carries = player_stats.get("carries", 0)
        rush_yds = player_stats.get("rushing_yards", 0)
        actual["yards_per_carry"] = rush_yds / carries if carries > 0 else 0
    if "qb_share" in chain:
        qb_att = player_stats.get("pass_attempts", 0)
        actual["qb_share"] = qb_att / dropbacks if dropbacks > 0 else 0
    if "completion_rate" in chain:
        att = player_stats.get("pass_attempts", 0)
        cmp = player_stats.get("completions", 0)
        actual["completion_rate"] = cmp / att if att > 0 else 0
    if "yards_per_attempt" in chain:
        att = player_stats.get("pass_attempts", 0)
        yds = player_stats.get("passing_yards", 0)
        actual["yards_per_attempt"] = yds / att if att > 0 else 0

    # Build prior
    team_priors, team_src = _build_team_priors(pbp_slices, team, week)
    player_priors, player_src = _build_player_priors(pbp_slices, player_id, team, week)

    if team_priors is None or player_priors is None:
        return actual, None, "insufficient_prior"

    prior = {"plays": team_priors["plays"]}
    if "pass_rate" in chain:
        prior["pass_rate"] = team_priors["pass_rate"]
    if "run_rate" in chain:
        prior["run_rate"] = team_priors["run_rate"]

    # Player-level priors: average across games
    if "share" in chain:
        shares = []
        for g in player_priors:
            tgt = g["player"].get("targets", 0)
            db = g["team_vol"]["dropbacks"]
            if db > 0:
                shares.append(tgt / db)
        prior["share"] = np.mean(shares) if shares else 0

    if "catch_rate" in chain:
        rates = []
        for g in player_priors:
            tgt = g["player"].get("targets", 0)
            rec = g["player"].get("receptions", 0)
            if tgt > 0:
                rates.append(rec / tgt)
        prior["catch_rate"] = np.mean(rates) if rates else 0

    if "yards_per_target" in chain:
        rates = []
        for g in player_priors:
            tgt = g["player"].get("targets", 0)
            yds = g["player"].get("receiving_yards", 0)
            if tgt > 0:
                rates.append(yds / tgt)
        prior["yards_per_target"] = np.mean(rates) if rates else 0

    if "carry_share" in chain:
        shares = []
        for g in player_priors:
            car = g["player"].get("carries", 0)
            rush = g["team_vol"]["rush_attempts"]
            if rush > 0:
                shares.append(car / rush)
        prior["carry_share"] = np.mean(shares) if shares else 0

    if "yards_per_carry" in chain:
        rates = []
        for g in player_priors:
            car = g["player"].get("carries", 0)
            yds = g["player"].get("rushing_yards", 0)
            if car > 0:
                rates.append(yds / car)
        prior["yards_per_carry"] = np.mean(rates) if rates else 0

    if "qb_share" in chain:
        shares = []
        for g in player_priors:
            att = g["player"].get("pass_attempts", 0)
            db = g["team_vol"]["dropbacks"]
            if db > 0:
                shares.append(att / db)
        prior["qb_share"] = np.mean(shares) if shares else 0

    if "completion_rate" in chain:
        rates = []
        for g in player_priors:
            att = g["player"].get("pass_attempts", 0)
            cmp = g["player"].get("completions", 0)
            if att > 0:
                rates.append(cmp / att)
        prior["completion_rate"] = np.mean(rates) if rates else 0

    if "yards_per_attempt" in chain:
        rates = []
        for g in player_priors:
            att = g["player"].get("pass_attempts", 0)
            yds = g["player"].get("passing_yards", 0)
            if att > 0:
                rates.append(yds / att)
        prior["yards_per_attempt"] = np.mean(rates) if rates else 0

    prior_source = f"{team_src}; {player_src}"
    return actual, prior, prior_source


# ── Why code auto ──

def _why_code_auto_prop(decomp, snap_share_ratio, has_injury, has_snap, teammates_out):
    """Assign why_code_auto for prop markets."""
    if decomp is None or decomp.get("zero_actual"):
        return "UNDEFINED"

    # AVAILABILITY: snap share < 50% of prior AND (injury or 0 snaps)
    if snap_share_ratio is not None and snap_share_ratio < 0.5:
        if has_injury or not has_snap:
            return "AVAILABILITY"

    primary = decomp.get("primary_link")
    if primary is None:
        return "UNDEFINED"

    # ROLE_SHIFT: primary is share AND teammates_out non-empty
    if primary in ("share", "carry_share", "qb_share") and teammates_out:
        return "ROLE_SHIFT"

    # SCRIPT: primary is plays, pass_rate, or run_rate
    if primary in ("plays", "pass_rate", "run_rate"):
        return "SCRIPT"

    # EFFICIENCY: primary is catch_rate/yards_per_target/yards_per_carry/etc.
    if primary in ("catch_rate", "yards_per_target", "yards_per_carry",
                    "completion_rate", "yards_per_attempt"):
        return "EFFICIENCY"

    # SHARE_OTHER: primary is share, no teammate event
    if primary in ("share", "carry_share", "qb_share"):
        return "SHARE_OTHER"

    # BOOK_VS_PRIOR: |ln(E/L)| exceeds every link term
    book_term = abs(decomp.get("book_vs_prior", 0))
    max_link = max(abs(decomp["links"][k]["term"]) for k in decomp["links"])
    if book_term > max_link:
        return "BOOK_VS_PRIOR"

    return "UNDEFINED"


def _why_code_auto_game(turnover_margin, non_off_td_flips, garbage_flips,
                        is_ot, margin_vs_expected, margin_sd):
    """Assign why_code_auto for game-level markets."""
    if turnover_margin is not None and turnover_margin >= 2:
        return "TURNOVERS"
    if non_off_td_flips:
        return "NON_OFFENSIVE_TD"
    if garbage_flips:
        return "GARBAGE"
    if is_ot:
        return "OT"
    if margin_sd is not None and margin_vs_expected is not None:
        if abs(margin_vs_expected) >= margin_sd:
            return "SCRIPT"
    return "NOISE"


# ── Thesis mapping ──

def _thesis_from_tag(tag, market, side):
    """Map old freeze tag to thesis_source='tag_map' thesis."""
    if tag is None or tag == "no_view":
        return None, "none"

    link = TAG_TO_THESIS.get(tag)
    if link is None:
        if tag == "game_script":
            link = _game_script_link(market)
        elif tag in ("weather", "matchup"):
            link = _weather_matchup_link(market)
        elif tag == "sim_v1":
            return None, "none"
        else:
            return None, "none"

    # Direction
    side_lower = str(side).lower()
    direction = "up" if side_lower in ("over", "first") else "down"

    return f"{link}:{direction}", "tag_map"


# ── Thesis z-score check ──

_link_sd_cache = {}


def _load_link_sd(root):
    """Load link_sd_2025.json. Returns dict or {}."""
    if "data" not in _link_sd_cache:
        p = root / "nfl" / "data" / "postgame" / "link_sd_2025.json"
        if p.exists():
            _link_sd_cache["data"] = json.loads(p.read_text())
        else:
            _link_sd_cache["data"] = {}
    return _link_sd_cache["data"]


def _check_thesis(thesis, decomp, link_sd, clv_row):
    """Check thesis: z = link_term / SD_link.

    held >= +0.5, failed <= -0.5, flat otherwise.
    For price thesis: CLV > 0 from clv_row.
    Returns (verdict_str, z_value).
    """
    if not thesis:
        return None, None

    claims = [c.strip() for c in thesis.split(";")]
    results = []

    for claim in claims:
        parts = claim.split(":")
        if len(parts) != 2:
            results.append(("invalid", None))
            continue
        link, direction = parts[0].strip(), parts[1].strip()

        if link == "price":
            # Price thesis: CLV > 0 → held
            if clv_row and clv_row.get("clv_points") is not None:
                clv = float(clv_row["clv_points"])
                if clv > 0:
                    results.append(("held", clv))
                elif clv < 0:
                    results.append(("failed", clv))
                else:
                    results.append(("flat", clv))
            else:
                results.append(("no_data", None))
            continue

        # Non-price: z = link_term / SD_link
        if decomp is None or decomp.get("zero_actual"):
            results.append(("no_decomp", None))
            continue

        links = decomp.get("links", {})
        if link not in links:
            results.append(("no_link", None))
            continue

        term = links[link].get("term", 0)
        sd_entry = link_sd.get(link, {})
        sd = sd_entry.get("sd")
        if sd is None or sd == 0:
            results.append(("no_sd", None))
            continue

        z = term / sd
        # Direction: "up" means positive is good, "down" means negative is good
        signed_z = z if direction == "up" else -z
        if signed_z >= 0.5:
            results.append(("held", round(signed_z, 3)))
        elif signed_z <= -0.5:
            results.append(("failed", round(signed_z, 3)))
        else:
            results.append(("flat", round(signed_z, 3)))

    if not results:
        return None, None

    # Aggregate: all claims must hold for "held"; any failed → "failed"; else "flat"
    verdicts = [r[0] for r in results]
    z_vals = [r[1] for r in results if r[1] is not None]
    z_primary = z_vals[0] if z_vals else None

    if all(v == "held" for v in verdicts):
        return "held", z_primary
    if any(v == "failed" for v in verdicts):
        return "failed", z_primary
    if any(v in ("no_data", "no_decomp", "no_link", "no_sd", "invalid") for v in verdicts):
        return "no_data", z_primary
    return "flat", z_primary


# ── CLV loading ──

_clv_cache = {}


def _load_clv(ledger_dir):
    """Load clv.jsonl from ledger dir. Returns {pick_id: row}."""
    if "data" not in _clv_cache:
        clv_path = Path(ledger_dir) / "clv.jsonl"
        clv = {}
        if clv_path.exists():
            with open(clv_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            r = json.loads(line)
                            clv[r["pick_id"]] = r
                        except (json.JSONDecodeError, KeyError):
                            pass
        _clv_cache["data"] = clv
    return _clv_cache["data"]


# ── Flags ──

def _one_play_decided(player_stats, market, side, point, A):
    """Check if removing the player's longest single play flips the result.

    Only meaningful for yardage props.
    """
    if market not in ("prop:rec_yds", "prop:rush_yds", "prop:pass_yds"):
        return False
    if point is None or A is None:
        return False

    L = float(point)
    # Determine if the pick hit
    side_lower = str(side).lower()
    hit = (A > L) if side_lower == "over" else (A < L)

    # Find the longest play
    stat_key = {"prop:rec_yds": "receiving_yards",
                "prop:rush_yds": "rushing_yards",
                "prop:pass_yds": "passing_yards"}.get(market)
    if stat_key not in player_stats:
        return False

    plays = player_stats.get("_plays", [])
    if not plays:
        return False

    longest = max(plays) if plays else 0
    A_without = A - longest
    hit_without = (A_without > L) if side_lower == "over" else (A_without < L)

    return hit != hit_without


def _margin_1(A, point, side):
    """Result decided by exactly 1 unit (stat == point ± 1)."""
    if point is None or A is None:
        return False
    L = float(point)
    return abs(A - L) <= 1.0 and A != L


# ── Build verdicts ──

def _match_game(row, pbp_slices, week_filter):
    """Match a ledger row to a PBP slice via home/away team names.

    Uses ps.nfl_team() for exact normalization — no substring matching.
    Returns (game_id, game_pbp) or (None, None).
    """
    ledger_home = ps.nfl_team(row.get("home", ""))
    ledger_away = ps.nfl_team(row.get("away", ""))
    if not ledger_home or not ledger_away:
        return None, None

    for gid, g in pbp_slices.items():
        if week_filter is not None and int(g["week"].iloc[0]) != week_filter:
            continue
        pbp_home = ps.nfl_team(str(g["home_team"].iloc[0]))
        pbp_away = ps.nfl_team(str(g["away_team"].iloc[0]))
        if pbp_home == ledger_home and pbp_away == ledger_away:
            return gid, g
    return None, None


_player_stats_df = None


def _load_player_stats():
    """Load the newest nflverse player_stats_2026 parquet (cached)."""
    global _player_stats_df
    if _player_stats_df is None:
        stats_df, _ = pg._load_newest_player_stats(ROOT)
        _player_stats_df = stats_df
    return _player_stats_df


def _resolve_player_id(player_name, game_pbp, team):
    """Resolve a ledger player name to a PBP gsis player_id.

    Path: ledger name → picks_grader._resolve_player_name →
    normalized name → match against player_stats player_display_name →
    gsis player_id → look up in PBP by receiver/rusher/passer_player_id.

    NO substring or startswith matching.  Returns player_id or None.
    """
    overrides = pg._load_name_overrides()
    resolved = pg._resolve_player_name(player_name, overrides)

    # Step 1: Find gsis_id from player_stats (full display names)
    stats_df = _load_player_stats()
    if stats_df is not None and not stats_df.empty:
        candidates = stats_df[stats_df.season == 2026].copy()
        candidates["_norm"] = candidates.player_display_name.apply(pg._normalize_name)
        matched = candidates[candidates._norm == resolved]
        if not matched.empty:
            gsis_id = str(matched.iloc[0].player_id)
            # Step 2: Verify this player_id exists in the PBP for this team
            p_stats = _player_stats_from_pbp(game_pbp, team)
            if gsis_id in p_stats:
                return gsis_id

    # Fallback: direct PBP name match (for players not in weekly stats)
    p_stats = _player_stats_from_pbp(game_pbp, team)
    for pid, ps_row in p_stats.items():
        pbp_norm = pg._normalize_name(ps_row.get("name", ""))
        if pbp_norm == resolved:
            return pid
    return None


def _parse_raw(row):
    """Parse the ledger row's raw JSON field. Returns dict or {}."""
    raw = row.get("raw")
    if not raw:
        return {}
    try:
        return json.loads(raw) if isinstance(raw, str) else (raw if isinstance(raw, dict) else {})
    except (json.JSONDecodeError, TypeError):
        return {}


def _load_freeze_row(row, root):
    """Load the freeze parquet row matching this ledger row.

    Join key: source_file + (event_id, market_key, player_name, side).
    Returns dict with freeze columns or {}.
    """
    sf = row.get("source_file")
    if not sf:
        return {}

    freeze_path = root / sf
    if not freeze_path.exists():
        return {}

    try:
        df = pd.read_parquet(freeze_path)
    except Exception:
        return {}

    eid = row.get("event_id", "")
    # Ledger market → freeze market_key
    market = row.get("market", "")
    try:
        freeze_mk = ps.ledger_to_tape_market(market) if market.startswith("prop:") else \
            {"spread": "spreads", "moneyline": "h2h", "total": "totals"}.get(market, market)
    except KeyError:
        freeze_mk = market

    mask = df["event_id"] == eid
    if "market_key" in df.columns:
        mask = mask & (df["market_key"] == freeze_mk)
    if "player_name" in df.columns and row.get("player_name"):
        mask = mask & (df["player_name"] == row["player_name"])

    matched = df[mask]
    if matched.empty:
        return {}

    # If multiple, take the one matching side
    if len(matched) > 1 and "side_name" in matched.columns:
        side = row.get("side", "")
        side_matched = matched[matched["side_name"] == side]
        if not side_matched.empty:
            matched = side_matched

    fr = matched.iloc[0]
    result = {}
    for col in ("tag", "conf", "conf_rank", "window", "thesis"):
        if col in fr.index and pd.notna(fr[col]):
            result[col] = fr[col]
    return result


def build_verdicts(ledger_rows, pbp_slices, week_filter=None, season=2026):
    """Build verdict rows for graded ai_nfl/sim_nfl picks.

    ledger_rows: list of dicts (from picks_ledger.view)
    pbp_slices: dict of {game_id: DataFrame}
    week_filter: only process games in this week (None = all)
    """
    rows = [r for r in ledger_rows if r.get("owner") in ALLOWED_OWNERS]
    if not rows:
        return None

    verdicts = []
    for row in rows:
        market = row.get("market", "")
        pick_id = row.get("pick_id")
        player_name = row.get("player_name", "")
        point = row.get("point")
        side = row.get("side", "")
        ledger_result = row.get("result")

        if not ledger_result or ledger_result not in ("W", "L", "P", "V"):
            continue

        # ── Game matching via nfl_team normalization (Finding 1 fix) ──
        game_id, game_pbp = _match_game(row, pbp_slices, week_filter)
        if game_pbp is None:
            continue

        week = int(game_pbp["week"].iloc[0])
        home = str(game_pbp["home_team"].iloc[0])
        away = str(game_pbp["away_team"].iloc[0])

        # ── Freeze join: tag, conf, conf_rank, window, thesis ──
        raw_d = _parse_raw(row)
        tag = row.get("tag") or raw_d.get("tag")
        conf = row.get("conf") or raw_d.get("conf")
        conf_rank = raw_d.get("conf_rank")
        window = row.get("window") or raw_d.get("window")

        # Load freeze file for thesis and any missing fields
        freeze = _load_freeze_row(row, ROOT)
        if freeze:
            tag = freeze.get("tag", tag)
            conf = freeze.get("conf", conf)
            conf_rank = freeze.get("conf_rank", conf_rank)
            window = freeze.get("window", window)

        verdict = {
            "pick_id": pick_id,
            "owner": row.get("owner"),
            "market": market,
            "player_name": player_name,
            "side": side,
            "point": point,
            "ledger_result": ledger_result,
            "week": week,
            "game_id": game_id,
            "tag": tag,
            "conf": conf,
            "conf_rank": conf_rank,
            "window": window,
        }

        # ── Prop chain decomposition ──
        if market in CHAIN_DEF:
            # Player matching via normalized name (Finding 2 fix)
            player_id = None
            team = None
            for t in (home, away):
                pid = _resolve_player_id(player_name, game_pbp, t)
                if pid is not None:
                    team = t
                    player_id = pid
                    break

            if team and player_id:
                actual, prior, prior_source = _compute_chain_actual_prior(
                    market, player_id, team, game_pbp, pbp_slices, week, point)

                p_stats = _player_stats_from_pbp(game_pbp, team)
                ps_row = p_stats.get(player_id, {})
                stat_map = {
                    "prop:rec": "receptions", "prop:rec_yds": "receiving_yards",
                    "prop:rush_att": "carries", "prop:rush_yds": "rushing_yards",
                    "prop:pass_att": "pass_attempts", "prop:pass_cmp": "completions",
                    "prop:pass_yds": "passing_yards",
                }
                stat_key = stat_map.get(market, "")
                A = ps_row.get(stat_key, 0)
                L = float(point) if point is not None else None

                if actual and prior and L and L > 0 and A > 0:
                    decomp = _chain_decompose(actual, prior, L, A, market)
                    if decomp and not decomp.get("zero_actual"):
                        verdict["chain"] = json.dumps(decomp, default=str)
                        verdict["primary_link"] = decomp.get("primary_link")
                        verdict["book_vs_prior"] = decomp.get("book_vs_prior")
                else:
                    decomp = None
                    verdict["chain"] = None
                    verdict["primary_link"] = None

                verdict["actual_stat"] = A
                verdict["prior_source"] = prior_source if prior else "none"

                if L is not None:
                    if side.lower() == "over":
                        computed_result = "W" if A > L else ("L" if A < L else "P")
                    else:
                        computed_result = "W" if A < L else ("L" if A > L else "P")
                    verdict["computed_result"] = computed_result
                    verdict["wl_mismatch"] = computed_result != ledger_result

                verdict["why_code_auto"] = _why_code_auto_prop(
                    decomp if actual and prior else None,
                    None, False, True, [])

                # Flags
                verdict["margin_1"] = _margin_1(A, point, side)

        # ── Game-line verdicts (spread/total/moneyline) ──
        elif market in ("spread", "total", "moneyline"):
            final_home = int(game_pbp["home_score"].max())
            final_away = int(game_pbp["away_score"].max())
            margin = final_home - final_away
            total = final_home + final_away

            verdict["final_home"] = final_home
            verdict["final_away"] = final_away
            verdict["margin"] = margin
            verdict["total"] = total

            # Hard Rock close via CLV
            clv_data = _load_clv(LEDGER_DIR)
            clv_row = clv_data.get(pick_id)
            if clv_row:
                cpt = clv_row.get("close_point")
                verdict["close_point"] = float(cpt) if cpt is not None else None
                cp = clv_row.get("close_price")
                verdict["close_price"] = int(float(cp)) if cp is not None else None
                close_pt = clv_row.get("close_point")
                if close_pt is not None:
                    if market == "spread":
                        verdict["margin_vs_close"] = margin + float(close_pt)
                    elif market == "total":
                        verdict["total_vs_close"] = total - float(close_pt)

            # Game script
            script = _game_script(game_pbp, home, away)
            turnovers = _turnovers(game_pbp, home, away)
            non_off = _non_offensive_tds(game_pbp)
            is_ot = script.get("overtime", False)
            garbage_plays = (script.get("home", {}).get("garbage_time_plays", 0) +
                             script.get("away", {}).get("garbage_time_plays", 0))

            # Why code for game lines
            link_sd = _load_link_sd(ROOT)
            margin_sd = link_sd.get("margin_vs_spread", {}).get("sd")
            total_sd = link_sd.get("total_vs_line", {}).get("sd")

            # Turnover margin from perspective of the side
            home_to = turnovers.get("home", {}).get("total", 0)
            away_to = turnovers.get("away", {}).get("total", 0)
            to_margin = abs(home_to - away_to)

            # Non-offensive TDs that flip: simplified check
            non_off_flips = non_off > 0
            garbage_flips = garbage_plays >= 10

            if market == "spread":
                margin_vs = verdict.get("margin_vs_close")
                verdict["why_code_auto"] = _why_code_auto_game(
                    to_margin if to_margin >= 2 else None,
                    non_off_flips, garbage_flips, is_ot,
                    margin_vs, margin_sd)
            elif market == "total":
                total_vs = verdict.get("total_vs_close")
                verdict["why_code_auto"] = _why_code_auto_game(
                    to_margin if to_margin >= 2 else None,
                    non_off_flips, garbage_flips, is_ot,
                    total_vs, total_sd)
            else:
                verdict["why_code_auto"] = "NOISE"

        # ── Thesis: freeze thesis overrides tag_map ──
        freeze_thesis = freeze.get("thesis") if freeze else None
        if freeze_thesis:
            verdict["thesis"] = freeze_thesis
            verdict["thesis_source"] = "freeze"
        elif tag:
            thesis, thesis_source = _thesis_from_tag(tag, market, side)
            verdict["thesis"] = thesis
            verdict["thesis_source"] = thesis_source
        else:
            verdict["thesis"] = None
            verdict["thesis_source"] = "none"

        # ── Thesis z-score check ──
        thesis_str = verdict.get("thesis")
        if thesis_str:
            link_sd = _load_link_sd(ROOT)
            clv_data = _load_clv(LEDGER_DIR)
            clv_row = clv_data.get(pick_id)
            decomp_for_thesis = None
            if "chain" in verdict and verdict.get("chain"):
                try:
                    decomp_for_thesis = json.loads(verdict["chain"])
                except (json.JSONDecodeError, TypeError):
                    pass
            thesis_verdict, thesis_z = _check_thesis(
                thesis_str, decomp_for_thesis, link_sd, clv_row)
            verdict["thesis_held"] = thesis_verdict
            verdict["thesis_z"] = thesis_z

        verdicts.append(verdict)

    if not verdicts:
        return None
    return pd.DataFrame(verdicts)


# ── Game sheet builder ──

def build_game_sheet(game_pbp, snap_counts=None, ftn=None):
    """Build game sheet JSON for one game."""
    home = str(game_pbp["home_team"].iloc[0])
    away = str(game_pbp["away_team"].iloc[0])
    game_id = str(game_pbp["game_id"].iloc[0])
    week = int(game_pbp["week"].iloc[0])

    final_home = int(game_pbp["home_score"].max())
    final_away = int(game_pbp["away_score"].max())

    sheet = {
        "game_id": game_id,
        "week": week,
        "home": home,
        "away": away,
        "final_score": {"home": final_home, "away": final_away},
        "script": _game_script(game_pbp, home, away),
        "volume": {
            "home": _team_volume(game_pbp, home),
            "away": _team_volume(game_pbp, away),
        },
        "turnovers": _turnovers(game_pbp, home, away),
        "non_offensive_tds": _non_offensive_tds(game_pbp),
        "red_zone": _red_zone(game_pbp, home, away),
        "injuries": _extract_injuries(game_pbp),
    }

    # FTN drops
    if ftn is not None and not ftn.empty:
        game_ftn = ftn[ftn["nflverse_game_id"] == game_id]
        if not game_ftn.empty and "drops" in game_ftn.columns:
            sheet["ftn_drops"] = game_ftn.groupby("player_name")["drops"].sum().to_dict()
        else:
            sheet["ftn"] = "covered" if not game_ftn.empty else "not covered"
    else:
        sheet["ftn"] = "not covered"

    return sheet


# ── Main entry ──

def main():
    ap = argparse.ArgumentParser(description="Build post-game sheets and verdicts")
    ap.add_argument("--week", type=int, help="Build for specific week")
    ap.add_argument("--all-final", action="store_true", help="Build for all final games")
    args = ap.parse_args()

    results_dir = Path(os.environ.get("RESULTS_ARCHIVE_DIR") or RESULTS_DIR)
    postgame_dir = Path(os.environ.get("POSTGAME_OUT_DIR") or POSTGAME_DIR)

    # Load PBP slices
    pbp_dir = results_dir / "nfl" / "pbp" / "season=2026"
    if not pbp_dir.exists():
        print(f"HALT: PBP directory not found: {pbp_dir}", file=sys.stderr)
        sys.exit(1)

    pbp_slices = {}
    for f in sorted(pbp_dir.glob("pbp_*.parquet")):
        df = pd.read_parquet(f)
        gid = str(df["game_id"].iloc[0])
        # Take newest file per game
        pbp_slices[gid] = df

    print(f"Loaded {len(pbp_slices)} game PBP slices")

    # Load snap counts and FTN
    snap_files = sorted((results_dir / "nfl").glob("snap_counts_2026_*.parquet"))
    snap_counts = pd.read_parquet(snap_files[-1]) if snap_files else None

    ftn_files = sorted((results_dir / "nfl").glob("ftn_charting_2026_*.parquet"))
    ftn = pd.read_parquet(ftn_files[-1]) if ftn_files else None

    # Build game sheets
    weeks_built = set()
    for gid, g_pbp in pbp_slices.items():
        week = int(g_pbp["week"].iloc[0])
        if args.week and week != args.week:
            continue

        week_dir = postgame_dir / f"week=2026_{week:02d}"
        week_dir.mkdir(parents=True, exist_ok=True)

        sheet = build_game_sheet(g_pbp, snap_counts, ftn)
        sheet_path = week_dir / f"game_{gid}.json"
        sheet_path.write_text(json.dumps(sheet, indent=2, default=str) + "\n")
        weeks_built.add(week)

    print(f"Game sheets: {len(pbp_slices)} games, weeks {sorted(weeks_built)}")

    # Build verdicts from ledger
    if LEDGER_DIR.exists():
        view = pl.view(LEDGER_DIR)
        graded = [r for r in view if r.get("result") and r.get("sport") == "NFL"]
        verdicts = build_verdicts(graded, pbp_slices, week_filter=args.week,
                                  season=2026)
        if verdicts is not None and len(verdicts) > 0:
            for week in verdicts["week"].unique():
                week_dir = postgame_dir / f"week=2026_{int(week):02d}"
                week_dir.mkdir(parents=True, exist_ok=True)
                wv = verdicts[verdicts["week"] == week]
                out = week_dir / "verdicts.parquet"
                wv.to_parquet(out, index=False)

                # Write why_summary.md for --week mode
                if args.week:
                    _write_why_summary(wv, week_dir, week)
            print(f"Verdicts: {len(verdicts)} rows")
        else:
            print("Verdicts: 0 rows (no graded ai_nfl/sim_nfl picks)")
    else:
        print(f"Ledger dir not found: {LEDGER_DIR} — skipping verdicts")


def _write_why_summary(verdicts, week_dir, week):
    """Write why_summary.md for a single week."""
    lines = [f"# WHY Summary — Week {week}\n"]
    lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}\n")

    # Counts by market × owner × result
    lines.append("\n## Graded rows\n")
    for (owner, market, result), count in verdicts.groupby(
            ["owner", "market", "ledger_result"]).size().items():
        lines.append(f"- {owner} / {market} / {result}: {count}")

    # Why codes
    if "why_code_auto" in verdicts.columns:
        lines.append("\n## why_code_auto (losses)\n")
        losses = verdicts[verdicts["ledger_result"] == "L"]
        if len(losses):
            for code, count in losses["why_code_auto"].value_counts().items():
                lines.append(f"- {code}: {count}")
        lines.append("\n## why_code_auto (wins)\n")
        wins = verdicts[verdicts["ledger_result"] == "W"]
        if len(wins):
            for code, count in wins["why_code_auto"].value_counts().items():
                lines.append(f"- {code}: {count}")

    # Thesis held/failed/flat
    if "thesis" in verdicts.columns:
        lines.append("\n## Thesis verdicts\n")
        for src in verdicts["thesis_source"].unique():
            src_rows = verdicts[verdicts["thesis_source"] == src]
            lines.append(f"- thesis_source={src}: {len(src_rows)} rows")

    # FLAGGED FOR THE TUESDAY READ
    lines.append("\n## FLAGGED FOR THE TUESDAY READ\n")
    flagged = 0

    # Top-20 ranked picks
    if "conf_rank" in verdicts.columns:
        top20 = verdicts[verdicts.get("conf_rank", pd.Series(dtype=int)) <= 20]
    else:
        top20 = pd.DataFrame()
    if len(top20):
        lines.append(f"\n### Top 20 picks ({len(top20)} rows)\n")
        for _, r in top20.iterrows():
            lines.append(f"- {r.get('pick_id')}: {r.get('market')} {r.get('player_name', '')} "
                          f"→ {r.get('ledger_result')}")
        flagged += len(top20)

    # Largest losses by |ln(A/L)|
    if "actual_stat" in verdicts.columns and "point" in verdicts.columns:
        losses = verdicts[verdicts["ledger_result"] == "L"].copy()
        if len(losses):
            losses["_abslog"] = losses.apply(
                lambda r: abs(math.log(max(r["actual_stat"], 0.01) / max(float(r["point"]), 0.01)))
                if r["actual_stat"] is not None and r["point"] is not None else 0,
                axis=1)
            top10_loss = losses.nlargest(10, "_abslog")
            lines.append(f"\n### 10 largest-|ln(A/L)| losses ({len(top10_loss)} rows)\n")
            for _, r in top10_loss.iterrows():
                lines.append(f"- {r.get('pick_id')}: {r.get('market')} {r.get('player_name', '')} "
                              f"A={r.get('actual_stat')} L={r.get('point')} "
                              f"|ln|={r['_abslog']:.3f}")
            flagged += len(top10_loss)

    # AVAILABILITY and ROLE_SHIFT
    if "why_code_auto" in verdicts.columns:
        flagged_codes = verdicts[verdicts["why_code_auto"].isin(["AVAILABILITY", "ROLE_SHIFT"])]
        if len(flagged_codes):
            lines.append(f"\n### AVAILABILITY / ROLE_SHIFT ({len(flagged_codes)} rows)\n")
            for _, r in flagged_codes.iterrows():
                lines.append(f"- {r.get('pick_id')}: {r.get('why_code_auto')} "
                              f"{r.get('market')} {r.get('player_name', '')}")
            flagged += len(flagged_codes)

    lines.append(f"\nTotal flagged: {flagged}\n")

    out = week_dir / "why_summary.md"
    out.write_text("\n".join(lines))
    print(f"Wrote {out} ({flagged} flagged)")


if __name__ == "__main__":
    main()
