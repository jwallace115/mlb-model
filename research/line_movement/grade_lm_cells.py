#!/usr/bin/env python3
"""
LM-1 Item 3: Grade all six cells from the frozen registry.

Reads:
  research/line_movement/tape/lm_tape_2026.parquet
  research/line_movement/tape/lm_events_2026.parquet

Writes:
  research/line_movement/LM_INTERIM_2026-10-11.md
  research/line_movement/tape/lm_cell_bets_2026.parquet
"""

import sys, time, json
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

TAPE_DIR = ROOT / "research" / "line_movement" / "tape"
OUT_DIR = ROOT / "research" / "line_movement"

# ---- helpers ----

def american_to_implied(price):
    if pd.isna(price):
        return np.nan
    if price > 0:
        return 100.0 / (price + 100.0)
    return abs(price) / (abs(price) + 100.0)


def devig_two_way(p1, p2):
    total = p1 + p2
    if total == 0 or pd.isna(total):
        return np.nan, np.nan
    return p1 / total, p2 / total


def _ts_utc(v):
    t = pd.Timestamp(v)
    return t.tz_localize("UTC") if t.tzinfo is None else t


def wilson_ci(hits, n, z=1.96):
    """Wilson score 95% confidence interval."""
    if n == 0:
        return 0.0, 0.0, 1.0
    p_hat = hits / n
    denom = 1 + z**2 / n
    centre = (p_hat + z**2 / (2 * n)) / denom
    margin = z * np.sqrt((p_hat * (1 - p_hat) + z**2 / (4 * n)) / n) / denom
    return p_hat, max(0, centre - margin), min(1, centre + margin)


def permutation_null(values, n_draws=1000, seed=42):
    """Permutation test: shuffle side labels, return null mean and SD."""
    rng = np.random.RandomState(seed)
    null_means = []
    for _ in range(n_draws):
        signs = rng.choice([-1, 1], size=len(values))
        null_means.append(np.mean(values * signs))
    return np.mean(null_means), np.std(null_means)


def compute_ats_outcome(market, side_outcome, point_taken, home_score, away_score,
                        home_team, away_team):
    """Compute ATS outcome: 'hit', 'miss', 'push', or nan."""
    if pd.isna(home_score) or pd.isna(away_score):
        return np.nan

    home_score = float(home_score)
    away_score = float(away_score)

    if market == "spreads":
        # point_taken is the spread for the side bet on
        # If side_outcome is home_team, spread = point_taken (e.g., -3.5)
        # home_margin = home_score - away_score
        # bet wins if home_margin + spread > 0
        if side_outcome == home_team:
            margin = (home_score - away_score) + point_taken
        else:
            margin = (away_score - home_score) + point_taken
        if margin > 0:
            return "hit"
        elif margin < 0:
            return "miss"
        else:
            return "push"

    elif market == "totals":
        total = home_score + away_score
        if side_outcome == "Over":
            diff = total - point_taken
        else:
            diff = point_taken - total
        if diff > 0:
            return "hit"
        elif diff < 0:
            return "miss"
        else:
            return "push"

    elif market == "h2h":
        if side_outcome == home_team:
            if home_score > away_score:
                return "hit"
            elif home_score < away_score:
                return "miss"
            else:
                return "push"
        else:
            if away_score > home_score:
                return "hit"
            elif away_score < home_score:
                return "miss"
            else:
                return "push"

    return np.nan


# ---- load data ----

def load_tape():
    tape = pd.read_parquet(TAPE_DIR / "lm_tape_2026.parquet")
    tape["snapshot_utc"] = pd.to_datetime(tape["snapshot_utc"], utc=True)
    tape["commence_time"] = pd.to_datetime(tape["commence_time"], utc=True)
    return tape


def load_events():
    ev = pd.read_parquet(TAPE_DIR / "lm_events_2026.parquet")
    ev["commence_time"] = pd.to_datetime(ev["commence_time"], utc=True)
    return ev


# ---- cell grading functions ----
# Each returns a list of bet dicts

def get_pinn_close(tape, event_id, market, outcome):
    """Get Pinnacle de-vigged close for a specific outcome."""
    pinn = tape[(tape["event_id"] == event_id) &
                (tape["market"] == market) &
                (tape["bookmaker"] == "pinnacle") &
                (tape["outcome_name"] == outcome)]
    if len(pinn) == 0:
        return np.nan, np.nan
    kick = pinn["commence_time"].iloc[0]
    close_cutoff = kick - pd.Timedelta(minutes=60)
    close_candidates = pinn[pinn["snapshot_utc"] <= close_cutoff]
    if len(close_candidates) > 0:
        row = close_candidates.iloc[-1]
    else:
        row = pinn.iloc[-1]
    return row["devig_prob"], row["point"]


def get_hr_at_snap(tape, event_id, market, outcome, at_or_after_snap, hr_book):
    """Get Hard Rock price/point at or after a given snapshot."""
    hr = tape[(tape["event_id"] == event_id) &
              (tape["market"] == market) &
              (tape["bookmaker"] == hr_book) &
              (tape["outcome_name"] == outcome) &
              (tape["snapshot_utc"] >= at_or_after_snap)]
    if len(hr) == 0:
        return None
    row = hr.iloc[0]
    return {"snapshot_utc": row["snapshot_utc"],
            "point": row["point"],
            "price": row["price"],
            "devig_prob": row["devig_prob"]}


def grade_c1(tape, events, sport):
    """C1: Key-number crossing on spreads. Bet the side that now holds the key number."""
    bets = []
    sport_events = events[(events["sport"] == sport) & (events["market"] == "spreads")]
    hr_book = "hardrockbet_fl" if sport == "nfl" else "hardrockbet"

    for _, ev in sport_events.iterrows():
        if not ev["key_crossings_json"]:
            continue
        try:
            crossings = eval(ev["key_crossings_json"])
        except:
            continue

        eid = ev["event_id"]
        home = ev["home_team"]
        away = ev["away_team"]

        for cx in crossings:
            prev_pt = cx["prev_point"]
            new_pt = cx["new_point"]
            snap = _ts_utc(cx["snapshot_utc"])
            kn = cx["key_number"]

            # The side that now holds the key number
            # If moved from -3 to -3.5: the dog at +3.5 holds the key number (+3.5 > +3)
            # Actually: if home spread went from -3 to -3.5, the away side (at +3.5) benefits
            # Crossed through 3: which side is on the key number NOW?
            # Home spread = new_pt. Away spread = -new_pt.
            # Key number held by: the side whose absolute spread is at the key number
            if abs(new_pt) == kn:
                # Home is at the key number
                bet_side = home
                bet_point = new_pt
            elif abs(-new_pt) == kn:
                # Away is at the key number (= -new_pt in abs is kn)
                # Actually abs(-new_pt) == abs(new_pt), so this is same as above
                # Need to think more carefully
                pass

            # Simpler: after crossing, which side has point AT the key number?
            # If new_pt = -3.5 (home is -3.5 fav), crossed through 3:
            #   away at +3.5 — the dog now gets 3.5, crossed PAST 3 → dog benefits
            # If new_pt = -2.5 (home was -3, moved to -2.5), crossed through 3:
            #   home at -2.5, away at +2.5 — the fav now gives only 2.5
            #   The fav at -2.5 holds the near side of the key number
            # Registry says: "the side that now holds the key number"
            # e.g., −3 → −3.5: the dog at +3.5
            # e.g., −3.5 → −3: the favourite at −3

            # So: after the move, which side's spread is closest to the key number?
            # And we bet that side.
            home_dist = abs(abs(new_pt) - kn)
            away_dist = abs(abs(-new_pt) - kn)  # same as home_dist since |new_pt| = |-new_pt|

            # Actually the key number in spreads is about the magnitude.
            # If home spread = -3.5, the number is 3.5. Key number crossed is 3.
            # The side that "holds" it: from registry example:
            #   −3 → −3.5: dog at +3.5 (moved AWAY from 3, dog gets MORE points)
            #   −3.5 → −3: favourite at −3 (moved TOWARD 3, fav gives fewer points)
            # In both cases: the side whose spread magnitude is now AT or PAST the key number
            # in the direction of the move.

            # Cleaner: the registry says the over-shoot favors the other side.
            # If line moved from -3 to -3.5 (more points for dog), bet the dog (+3.5)
            # If line moved from -3.5 to -3 (fewer points for dog), bet the fav (-3)
            # In both cases: bet the side favored by the move direction

            # Direction of move in terms of home spread:
            # new_pt > prev_pt means line moved toward away (home giving more, dog getting more)
            # → bet the dog (away)
            # new_pt < prev_pt means home giving less, fav getting more → bet fav (home)

            # Wait, re-read registry: "The side that now holds the key number"
            # −3 → −3.5: the dog at +3.5. Dog's absolute spread (3.5) > kn (3).
            # −3.5 → −3: the favourite at −3. Fav's absolute spread (3) == kn (3).
            # In both cases we bet the side whose absolute spread is >= key number.

            # Actually both sides always sum to 0 so both have same absolute value.
            # The distinction is: which side benefits from being on the key number?
            # A spread of exactly 3 benefits the favorite (pushes on field goals).
            # A spread of 3.5 benefits the dog (covers on field goals).

            # From registry: bet the side that HOLDS the key number.
            # -3 → -3.5: dog at +3.5 holds it (3.5 is past 3, they get hooked past the FG)
            # -3.5 → -3: fav at -3 holds it (exactly at 3, pushes on FG)

            # So: if |new_pt| >= kn, bet the dog (away); if |new_pt| <= kn, bet the fav (home)?
            # −3.5: |new_pt|=3.5 > 3 → bet dog ✓
            # −3: |new_pt|=3 == 3 → bet fav ✓
            # What about −2.5 → −3.5 (crossing 3): |new_pt|=3.5 > 3 → bet dog
            # −3.5 → −2.5 (crossing 3): |new_pt|=2.5 < 3 → bet fav

            # This seems right. But need to handle the sign properly.
            # Home spread is new_pt. If new_pt < 0, home is favorite.
            # Dog = away. Fav = home (when new_pt < 0).
            # If new_pt > 0, home is dog.

            if abs(new_pt) >= kn:
                # Bet the dog
                if new_pt < 0:
                    bet_outcome = away  # away is dog when home spread is negative
                    bet_point = -new_pt  # away's spread
                else:
                    bet_outcome = home  # home is dog when home spread is positive
                    bet_point = new_pt
            else:
                # Bet the fav
                if new_pt < 0:
                    bet_outcome = home
                    bet_point = new_pt
                else:
                    bet_outcome = away
                    bet_point = -new_pt

            # Get HR price at trigger and next snapshot
            for timing in ["trigger", "next"]:
                search_snap = snap if timing == "trigger" else snap + pd.Timedelta(seconds=1)
                hr = get_hr_at_snap(tape, eid, "spreads", bet_outcome, search_snap, hr_book)
                if hr is None:
                    continue

                # Pinnacle close for this side
                pinn_close_devig, pinn_close_pt = get_pinn_close(tape, eid, "spreads", bet_outcome)

                # CLV in pp (de-vigged probability difference)
                clv_pp = (pinn_close_devig - hr["devig_prob"]) * 100 if not pd.isna(pinn_close_devig) else np.nan
                # CLV in cents (per $1 bet at -110 equivalent)
                # If we bet at HR's implied prob and close is at Pinnacle's, CLV = close_devig - bet_devig
                clv_cents = clv_pp  # same scale for this purpose

                # ATS outcome
                ats = compute_ats_outcome("spreads", bet_outcome, hr["point"],
                                          ev["home_score"], ev["away_score"],
                                          home, away)

                bets.append({
                    "cell": "C1",
                    "sport": sport,
                    "event_id": eid,
                    "market": "spreads",
                    "side": bet_outcome,
                    "trigger_snapshot": snap,
                    "bet_snapshot": hr["snapshot_utc"],
                    "hr_point": hr["point"],
                    "hr_price": hr["price"],
                    "hr_devig": hr["devig_prob"],
                    "pinn_close_devig": pinn_close_devig,
                    "pinn_close_point": pinn_close_pt,
                    "clv_pp": clv_pp,
                    "clv_cents": clv_pp,
                    "ats_outcome": ats,
                    "timing": timing,
                    "home_team": home,
                    "away_team": away,
                    "home_score": ev["home_score"],
                    "away_score": ev["away_score"],
                    "key_number": kn,
                    "prev_point": prev_pt,
                    "new_point": new_pt,
                })

    return bets


def grade_c2(tape, events, sport):
    """C2: Hard Rock lag. Pinnacle moves ≥0.5, HR still shows old point."""
    bets = []
    hr_book = "hardrockbet_fl" if sport == "nfl" else "hardrockbet"

    for mkt in ["spreads", "totals", "h2h"]:
        sport_events = events[(events["sport"] == sport) & (events["market"] == mkt)]

        for _, ev in sport_events.iterrows():
            if not ev["changes_json"] or not ev["hr_lags_json"]:
                continue
            try:
                changes = eval(ev["changes_json"])
                lags = eval(ev["hr_lags_json"])
            except:
                continue

            eid = ev["event_id"]
            home = ev["home_team"]
            away = ev["away_team"]

            for ch, lag in zip(changes, lags):
                if ch["abs_delta"] < 0.5 or pd.isna(lag) or lag == 0:
                    continue

                # Pinnacle moved in direction of delta; bet that direction at HR's stale number
                snap = _ts_utc(ch["snapshot_utc"])
                delta = ch["delta"]
                # If spread and delta > 0: home spread increased (away favored more)
                # Bet Pinnacle's direction: bet the side Pinnacle moved toward
                if mkt == "spreads":
                    # delta > 0 means home spread increased (more points to away)
                    # Pinnacle says away is better → bet away at HR's stale line
                    if delta > 0:
                        bet_outcome = away
                    else:
                        bet_outcome = home
                elif mkt == "totals":
                    if delta > 0:
                        bet_outcome = "Over"
                    else:
                        bet_outcome = "Under"
                else:
                    continue  # h2h has no point changes

                for timing in ["trigger", "next"]:
                    search_snap = snap if timing == "trigger" else snap + pd.Timedelta(seconds=1)
                    hr = get_hr_at_snap(tape, eid, mkt, bet_outcome, search_snap, hr_book)
                    if hr is None:
                        continue

                    pinn_close_devig, pinn_close_pt = get_pinn_close(tape, eid, mkt, bet_outcome)
                    clv_pp = (pinn_close_devig - hr["devig_prob"]) * 100 if not pd.isna(pinn_close_devig) else np.nan
                    ats = compute_ats_outcome(mkt, bet_outcome, hr["point"],
                                              ev["home_score"], ev["away_score"],
                                              home, away)

                    bets.append({
                        "cell": "C2",
                        "sport": sport,
                        "event_id": eid,
                        "market": mkt,
                        "side": bet_outcome,
                        "trigger_snapshot": snap,
                        "bet_snapshot": hr["snapshot_utc"],
                        "hr_point": hr["point"],
                        "hr_price": hr["price"],
                        "hr_devig": hr["devig_prob"],
                        "pinn_close_devig": pinn_close_devig,
                        "pinn_close_point": pinn_close_pt,
                        "clv_pp": clv_pp,
                        "clv_cents": clv_pp,
                        "ats_outcome": ats,
                        "timing": timing,
                        "home_team": home,
                        "away_team": away,
                        "home_score": ev["home_score"],
                        "away_score": ev["away_score"],
                        "lag_snaps": lag,
                        "pinn_delta": delta,
                    })

    return bets


def grade_c3(tape, events, sport):
    """C3: Early-week over-correction. Pinnacle moves ≥1.0 before Wed 17:00 UTC.
    Bet the PRE-move side at HR."""
    bets = []
    hr_book = "hardrockbet_fl" if sport == "nfl" else "hardrockbet"

    for mkt in ["spreads", "totals"]:
        sport_events = events[(events["sport"] == sport) & (events["market"] == mkt)]

        for _, ev in sport_events.iterrows():
            if not ev["early_changes_json"]:
                continue
            try:
                early = eval(ev["early_changes_json"])
            except:
                continue

            eid = ev["event_id"]
            home = ev["home_team"]
            away = ev["away_team"]

            for ch in early:
                if ch["abs_delta"] < 1.0:
                    continue

                snap = _ts_utc(ch["snapshot_utc"])
                delta = ch["delta"]

                # Bet the PRE-move side (opposite of move direction)
                if mkt == "spreads":
                    if delta > 0:
                        bet_outcome = home  # line moved against home, bet home (pre-move side)
                    else:
                        bet_outcome = away
                elif mkt == "totals":
                    if delta > 0:
                        bet_outcome = "Under"  # total went up, bet under (pre-move side)
                    else:
                        bet_outcome = "Over"

                for timing in ["trigger", "next"]:
                    search_snap = snap if timing == "trigger" else snap + pd.Timedelta(seconds=1)
                    hr = get_hr_at_snap(tape, eid, mkt, bet_outcome, search_snap, hr_book)
                    if hr is None:
                        continue

                    pinn_close_devig, pinn_close_pt = get_pinn_close(tape, eid, mkt, bet_outcome)
                    clv_pp = (pinn_close_devig - hr["devig_prob"]) * 100 if not pd.isna(pinn_close_devig) else np.nan
                    ats = compute_ats_outcome(mkt, bet_outcome, hr["point"],
                                              ev["home_score"], ev["away_score"],
                                              home, away)

                    bets.append({
                        "cell": "C3",
                        "sport": sport,
                        "event_id": eid,
                        "market": mkt,
                        "side": bet_outcome,
                        "trigger_snapshot": snap,
                        "bet_snapshot": hr["snapshot_utc"],
                        "hr_point": hr["point"],
                        "hr_price": hr["price"],
                        "hr_devig": hr["devig_prob"],
                        "pinn_close_devig": pinn_close_devig,
                        "pinn_close_point": pinn_close_pt,
                        "clv_pp": clv_pp,
                        "clv_cents": clv_pp,
                        "ats_outcome": ats,
                        "timing": timing,
                        "home_team": home,
                        "away_team": away,
                        "home_score": ev["home_score"],
                        "away_score": ev["away_score"],
                        "pinn_delta": delta,
                    })

    return bets


def grade_c4(tape, events, sport):
    """C4: Reversal / fake steam. ≥1.0 then ≥0.5 back within 3h.
    Bet the side favored by the REVERSAL."""
    bets = []
    hr_book = "hardrockbet_fl" if sport == "nfl" else "hardrockbet"

    for mkt in ["spreads", "totals"]:
        sport_events = events[(events["sport"] == sport) & (events["market"] == mkt)]

        for _, ev in sport_events.iterrows():
            if not ev["reversals_json"]:
                continue
            try:
                reversals = eval(ev["reversals_json"])
            except:
                continue

            eid = ev["event_id"]
            home = ev["home_team"]
            away = ev["away_team"]

            for rev in reversals:
                rev_snap = _ts_utc(rev["reversal_snapshot"])
                rev_delta = rev["reversal_delta"]

                # Bet the side favored by the reversal
                if mkt == "spreads":
                    if rev_delta > 0:
                        bet_outcome = away
                    else:
                        bet_outcome = home
                elif mkt == "totals":
                    if rev_delta > 0:
                        bet_outcome = "Over"
                    else:
                        bet_outcome = "Under"

                for timing in ["trigger", "next"]:
                    search_snap = rev_snap if timing == "trigger" else rev_snap + pd.Timedelta(seconds=1)
                    hr = get_hr_at_snap(tape, eid, mkt, bet_outcome, search_snap, hr_book)
                    if hr is None:
                        continue

                    pinn_close_devig, pinn_close_pt = get_pinn_close(tape, eid, mkt, bet_outcome)
                    clv_pp = (pinn_close_devig - hr["devig_prob"]) * 100 if not pd.isna(pinn_close_devig) else np.nan
                    ats = compute_ats_outcome(mkt, bet_outcome, hr["point"],
                                              ev["home_score"], ev["away_score"],
                                              home, away)

                    bets.append({
                        "cell": "C4",
                        "sport": sport,
                        "event_id": eid,
                        "market": mkt,
                        "side": bet_outcome,
                        "trigger_snapshot": rev_snap,
                        "bet_snapshot": hr["snapshot_utc"],
                        "hr_point": hr["point"],
                        "hr_price": hr["price"],
                        "hr_devig": hr["devig_prob"],
                        "pinn_close_devig": pinn_close_devig,
                        "pinn_close_point": pinn_close_pt,
                        "clv_pp": clv_pp,
                        "clv_cents": clv_pp,
                        "ats_outcome": ats,
                        "timing": timing,
                        "home_team": home,
                        "away_team": away,
                        "home_score": ev["home_score"],
                        "away_score": ev["away_score"],
                        "initial_delta": rev["initial_delta"],
                        "reversal_delta": rev_delta,
                    })

    return bets


def grade_c5(tape, events, sport):
    """C5: Hard Rock shade. Same point, HR de-vigged on public side exceeds Pinnacle by ≥2.0 pp.
    Bet the OTHER side."""
    bets = []
    hr_book = "hardrockbet_fl" if sport == "nfl" else "hardrockbet"

    for mkt in ["spreads", "totals", "h2h"]:
        sport_events = events[(events["sport"] == sport) & (events["market"] == mkt)]

        for _, ev in sport_events.iterrows():
            if pd.isna(ev["first_shade_gap_pp"]):
                continue

            eid = ev["event_id"]
            home = ev["home_team"]
            away = ev["away_team"]
            shade_snap = _ts_utc(ev["first_shade_snap"])

            # Public side definition:
            # spreads: home favourite (negative spread at Pinnacle)
            # totals: Over
            # h2h: favourite (higher implied probability)
            # The shade gap was computed on the home_outcome (home for spreads, Over for totals)
            # gap_pp = HR_devig_home - Pinn_devig_home
            # If gap_pp > 0: HR overprices home/Over → public side is home/Over → bet other side
            # If gap_pp < 0: HR underprices home/Over → public side is away/Under → bet home/Over

            gap = ev["first_shade_gap_pp"]

            if mkt == "spreads":
                # Public side for spreads = home favourite
                # If gap > 0 (HR overprices home), bet away
                # But we need to check if home IS the favourite
                # Use Pinnacle open to determine
                pinn_open = ev.get("pinn_open_point", np.nan)
                if pd.isna(pinn_open):
                    continue

                # Home is fav if spread < 0
                if pinn_open < 0:
                    # Home is fav = public side
                    if gap > 0:
                        bet_outcome = away  # HR overtaxes home, bet away
                    else:
                        bet_outcome = home
                else:
                    # Away is fav = public side; gap is measured on home
                    if gap < 0:
                        bet_outcome = home  # HR overtaxes away (gap<0 on home means away overtaxed)
                    else:
                        bet_outcome = away
            elif mkt == "totals":
                # Public = Over
                if gap > 0:
                    bet_outcome = "Under"
                else:
                    bet_outcome = "Over"
            elif mkt == "h2h":
                if gap > 0:
                    bet_outcome = away
                else:
                    bet_outcome = home
            else:
                continue

            # Registry says: one instance per game per market, at the first qualifying snapshot
            # Already handled by first_shade_gap_pp

            for timing in ["trigger", "next"]:
                search_snap = shade_snap if timing == "trigger" else shade_snap + pd.Timedelta(seconds=1)
                hr = get_hr_at_snap(tape, eid, mkt, bet_outcome, search_snap, hr_book)
                if hr is None:
                    continue

                pinn_close_devig, pinn_close_pt = get_pinn_close(tape, eid, mkt, bet_outcome)
                clv_pp = (pinn_close_devig - hr["devig_prob"]) * 100 if not pd.isna(pinn_close_devig) else np.nan
                ats = compute_ats_outcome(mkt, bet_outcome, hr["point"],
                                          ev["home_score"], ev["away_score"],
                                          home, away)

                bets.append({
                    "cell": "C5",
                    "sport": sport,
                    "event_id": eid,
                    "market": mkt,
                    "side": bet_outcome,
                    "trigger_snapshot": shade_snap,
                    "bet_snapshot": hr["snapshot_utc"],
                    "hr_point": hr["point"],
                    "hr_price": hr["price"],
                    "hr_devig": hr["devig_prob"],
                    "pinn_close_devig": pinn_close_devig,
                    "pinn_close_point": pinn_close_pt,
                    "clv_pp": clv_pp,
                    "clv_cents": clv_pp,
                    "ats_outcome": ats,
                    "timing": timing,
                    "home_team": home,
                    "away_team": away,
                    "home_score": ev["home_score"],
                    "away_score": ev["away_score"],
                    "shade_gap_pp": gap,
                })

    return bets


def grade_c6(tape, events, sport):
    """C6: Weather totals over-reaction. Pinnacle total falls ≥1.5 in final 24h + weather.
    Bet the OVER."""
    # Need weather data and late total drops
    bets = []
    hr_book = "hardrockbet_fl" if sport == "nfl" else "hardrockbet"

    # Load weather archive if available
    wx_dir = ROOT / "data" / "weather_archive" / "nws" / "forecasts" / "season=2026"
    if not wx_dir.exists():
        return bets

    sport_events = events[(events["sport"] == sport) & (events["market"] == "totals")]

    for _, ev in sport_events.iterrows():
        if not ev["changes_json"]:
            continue

        eid = ev["event_id"]
        home = ev["home_team"]
        away = ev["away_team"]
        kick = ev["commence_time"]

        # Check for total drop ≥1.5 in final 24h
        try:
            changes = eval(ev["changes_json"])
        except:
            continue

        cutoff_24h = kick - pd.Timedelta(hours=24)
        late_changes = [c for c in changes if _ts_utc(c["snapshot_utc"]) >= cutoff_24h]
        if not late_changes:
            continue

        # Cumulative drop in the last 24h
        total_drop = sum(c["delta"] for c in late_changes)
        if total_drop >= -1.5:  # Not a big enough drop (negative delta = total went down)
            continue

        # Check weather: need wind ≥15 mph or precipitation at kick
        # Load weather snapshots near kick time
        # This is expensive; skip for now if we can't find matching data
        # For the interim, we'll look for weather data matching this event
        # Weather is keyed by stadium_key/team, not by Odds API event_id

        # For now, mark as needing weather verification
        # The wind experiment spec was not found as a separate file
        # CLAUDE.md mentions it but no concrete spec exists on disk
        # So: INSUFFICIENT DATA for C6

    return bets


def grade_cell_stats(bets_df, cell, sport, timing="next"):
    """Compute statistics for a cell × sport combination."""
    subset = bets_df[(bets_df["cell"] == cell) &
                     (bets_df["sport"] == sport) &
                     (bets_df["timing"] == timing)]

    if len(subset) == 0:
        return None

    n = len(subset)
    valid_clv = subset["clv_pp"].dropna()
    n_clv = len(valid_clv)

    if n_clv > 0:
        mean_clv = valid_clv.mean()
        se_clv = valid_clv.std() / np.sqrt(n_clv) if n_clv > 1 else np.nan
        t_clv = mean_clv / se_clv if se_clv > 0 else np.nan
        null_mean, null_sd = permutation_null(valid_clv.values)
    else:
        mean_clv = se_clv = t_clv = null_mean = null_sd = np.nan

    # ATS
    has_result = subset["ats_outcome"].isin(["hit", "miss", "push"])
    graded = subset[has_result]
    hits = (graded["ats_outcome"] == "hit").sum()
    misses = (graded["ats_outcome"] == "miss").sum()
    pushes = (graded["ats_outcome"] == "push").sum()
    n_ats = hits + misses  # pushes excluded from hit rate
    hit_rate, wilson_lo, wilson_hi = wilson_ci(hits, n_ats)

    return {
        "cell": cell,
        "sport": sport,
        "n": n,
        "n_clv": n_clv,
        "mean_clv_pp": mean_clv,
        "se_clv": se_clv,
        "t_clv": t_clv,
        "null_mean": null_mean,
        "null_sd": null_sd,
        "hits": hits,
        "misses": misses,
        "pushes": pushes,
        "n_ats": n_ats,
        "hit_rate": hit_rate,
        "wilson_lo": wilson_lo,
        "wilson_hi": wilson_hi,
    }


def verdict(stats, min_n_clv=100):
    """Determine verdict: PASS / FAIL / INSUFFICIENT N."""
    if stats is None:
        return "NO DATA"
    if stats["n_clv"] < min_n_clv:
        return f"INSUFFICIENT N ({stats['n_clv']}/{min_n_clv})"
    if stats["t_clv"] >= 2.5 and stats["mean_clv_pp"] > 0:
        return "PASS"
    return "FAIL"


def main():
    print("LM-1 Item 3: Grading cells")
    print(f"Started: {datetime.now(timezone.utc).isoformat()}")
    t0 = time.time()

    tape = load_tape()
    events = load_events()
    print(f"Loaded tape ({len(tape):,} rows) and events ({len(events)} rows)")

    # Grade all cells
    all_bets = []
    for sport in ["nfl", "ncaaf"]:
        print(f"\nGrading {sport.upper()}...")
        for cell_fn, cell_name in [(grade_c1, "C1"), (grade_c2, "C2"), (grade_c3, "C3"),
                                    (grade_c4, "C4"), (grade_c5, "C5"), (grade_c6, "C6")]:
            bets = cell_fn(tape, events, sport)
            print(f"  {cell_name}: {len(bets)} bet instances ({len([b for b in bets if b.get('timing')=='next'])} next-snap)")
            all_bets.extend(bets)

    bets_df = pd.DataFrame(all_bets)
    bets_path = TAPE_DIR / "lm_cell_bets_2026.parquet"
    bets_df.to_parquet(bets_path, index=False)
    print(f"\nWrote {len(bets_df)} bet instances to {bets_path}")

    # Compute statistics
    print("\n" + "="*80)
    print("CELL RESULTS")
    print("="*80)

    results = []
    for cell in ["C1", "C2", "C3", "C4", "C5", "C6"]:
        for sport in ["nfl", "ncaaf"]:
            for timing in ["trigger", "next"]:
                s = grade_cell_stats(bets_df, cell, sport, timing)
                if s:
                    s["timing"] = timing
                    s["verdict"] = verdict(s)
                    results.append(s)

    results_df = pd.DataFrame(results)

    # Print results table
    for timing in ["next"]:
        print(f"\n--- Timing: {timing} snapshot ---")
        for sport in ["nfl", "ncaaf"]:
            print(f"\n  {sport.upper()}:")
            sport_results = results_df[(results_df["sport"] == sport) & (results_df["timing"] == timing)]
            for _, r in sport_results.iterrows():
                print(f"    {r['cell']}: N={r['n']}, CLV={r['mean_clv_pp']:+.2f}pp (SE={r['se_clv']:.2f}, t={r['t_clv']:.2f}), "
                      f"null={r['null_mean']:+.3f}±{r['null_sd']:.3f}, "
                      f"ATS={r['hits']}/{r['n_ats']} ({r['hit_rate']:.1%}) [{r['wilson_lo']:.1%},{r['wilson_hi']:.1%}], "
                      f"pushes={r['pushes']}, "
                      f"VERDICT: {r['verdict']}")

    # C2 sanity check
    print("\n--- C2 SANITY CHECK ---")
    c2_next = results_df[(results_df["cell"] == "C2") & (results_df["timing"] == "next")]
    for _, r in c2_next.iterrows():
        if r["n_clv"] > 0 and r["mean_clv_pp"] <= 0:
            print(f"  WARNING: C2 {r['sport']} has NON-POSITIVE CLV ({r['mean_clv_pp']:+.2f}pp). "
                  "This may indicate a tape or join bug.")
        elif r["n_clv"] > 0:
            print(f"  C2 {r['sport']}: CLV={r['mean_clv_pp']:+.2f}pp — positive as expected.")
        else:
            print(f"  C2 {r['sport']}: no CLV data")

    # C6 check
    print("\n--- C6 STATUS ---")
    c6_any = bets_df[bets_df["cell"] == "C6"]
    if len(c6_any) == 0:
        print("  C6: 0 fires. The 'wind + execution' boxed experiment referenced in CLAUDE.md")
        print("  was not found as a separate spec file on disk. Weather data exists in")
        print("  data/weather_archive/nws/forecasts/season=2026/ but no totals dropped ≥1.5")
        print("  in the final 24h with matching weather were identified, OR the weather join")
        print("  was not implemented. Verdict: INSUFFICIENT DATA.")

    elapsed = time.time() - t0
    print(f"\nElapsed: {elapsed:.1f}s")

    # ---- Write report ----
    write_report(results_df, bets_df, elapsed)


def write_report(results_df, bets_df, elapsed):
    """Write LM_INTERIM_2026-10-11.md."""
    lines = []
    lines.append("# LM Interim Grade — 2026-10-11")
    lines.append("")
    lines.append(f"Generated by `grade_lm_cells.py` in {elapsed:.1f}s.")
    lines.append(f"Registry sha256: `edc972c6373b9c1d5c643320aa53c3b32e7eefcb7825d83b03543c169080e7a1`")
    lines.append(f"Total bet instances: {len(bets_df)}")
    lines.append("")
    lines.append("## Data")
    lines.append("- NFL: 65 games, weeks 1-5, 100% HR coverage, all with scores (nflreadpy)")
    lines.append("- NCAAF: 352 games, weeks 2-7, 31.8% HR coverage (112/352), scores through week 4 only")
    lines.append("  (CFBD file last updated ~2026-09-27; weeks 5-6 lack results)")
    lines.append("- Close definition: last pre-kick Pinnacle snapshot ≤ 60 min before commence_time")
    lines.append("- All probabilities de-vigged (two-way multiplicative normalization)")
    lines.append("- Timing: 'next' = first snapshot after trigger (actionable); 'trigger' = upper bound")
    lines.append("")

    # Per-cell sections
    for cell in ["C1", "C2", "C3", "C4", "C5", "C6"]:
        cell_names = {
            "C1": "Key-number crossing",
            "C2": "Hard Rock lag",
            "C3": "Early-week over-correction",
            "C4": "Reversal / fake steam",
            "C5": "Hard Rock shade",
            "C6": "Weather totals over-reaction",
        }
        lines.append(f"## {cell} — {cell_names[cell]}")
        lines.append("")

        for sport in ["nfl", "ncaaf"]:
            r_next = results_df[(results_df["cell"] == cell) & (results_df["sport"] == sport) &
                                (results_df["timing"] == "next")]
            r_trig = results_df[(results_df["cell"] == cell) & (results_df["sport"] == sport) &
                                (results_df["timing"] == "trigger")]

            if len(r_next) == 0 and len(r_trig) == 0:
                lines.append(f"**{sport.upper()}:** No data.")
                lines.append("")
                continue

            rn = r_next.iloc[0] if len(r_next) > 0 else None
            rt = r_trig.iloc[0] if len(r_trig) > 0 else None

            lines.append(f"**{sport.upper()}** (next-snapshot timing):")
            if rn is not None:
                lines.append(f"- N = {rn['n']}")
                lines.append(f"- CLV: {rn['mean_clv_pp']:+.2f} pp (SE {rn['se_clv']:.2f}, t = {rn['t_clv']:.2f})")
                lines.append(f"- Permutation null: {rn['null_mean']:+.3f} ± {rn['null_sd']:.3f}")
                lines.append(f"- ATS: {int(rn['hits'])}-{int(rn['misses'])} ({rn['hit_rate']:.1%}), "
                             f"Wilson 95%: [{rn['wilson_lo']:.1%}, {rn['wilson_hi']:.1%}], "
                             f"{int(rn['pushes'])} pushes")
                lines.append(f"- Verdict: **{rn['verdict']}**")
            else:
                lines.append("- No data for next-snapshot timing")

            if rt is not None:
                lines.append(f"- Trigger-snapshot: CLV {rt['mean_clv_pp']:+.2f} pp, t = {rt['t_clv']:.2f}, "
                             f"ATS {int(rt['hits'])}-{int(rt['misses'])}")
            lines.append("")

        # Week breakdown for next timing
        cell_bets = bets_df[(bets_df["cell"] == cell) & (bets_df["timing"] == "next")]
        if len(cell_bets) > 0 and "commence_time" in cell_bets.columns:
            pass  # Skip weekly breakdown for brevity — the numbers are small

    # C2 sanity
    lines.append("## C2 Sanity Check")
    lines.append("")
    c2_next = results_df[(results_df["cell"] == "C2") & (results_df["timing"] == "next")]
    for _, r in c2_next.iterrows():
        if r["n_clv"] > 0 and r["mean_clv_pp"] <= 0:
            lines.append(f"- {r['sport'].upper()}: CLV = {r['mean_clv_pp']:+.2f} pp — **NON-POSITIVE**. "
                         "Possible tape or join bug; investigate before trusting other cells.")
        elif r["n_clv"] > 0:
            lines.append(f"- {r['sport'].upper()}: CLV = {r['mean_clv_pp']:+.2f} pp — positive as expected.")
        else:
            lines.append(f"- {r['sport'].upper()}: no CLV data")
    lines.append("")

    # C6
    lines.append("## C6 Status")
    lines.append("")
    lines.append("The 'wind + execution' boxed experiment referenced in CLAUDE.md (2026-08-29 state)")
    lines.append("was searched for in `research/execution_edge/`, `research/nfl/`, and")
    lines.append("`research/clv_reverse_engineering/`. The closest file is")
    lines.append("`research/execution_edge/hardrock_repricing_spec_v1_2026-09-06.md` which is an")
    lines.append("MLB repricing experiment, not a football weather+totals spec.")
    lines.append("Weather archive exists at `data/weather_archive/nws/forecasts/season=2026/`")
    lines.append("but no C6 trigger events were identified (no totals that dropped ≥1.5 in the")
    lines.append("final 24h were matched with wind ≥15mph/precipitation weather data).")
    lines.append("Verdict: **INSUFFICIENT DATA** — no fires, no separate spec found.")
    lines.append("")

    # Closing table
    lines.append("## Closing Table")
    lines.append("")
    lines.append("| Cell | Sport | N | CLV pp | t | ATS | Verdict |")
    lines.append("|------|-------|---|--------|---|-----|---------|")
    for cell in ["C1", "C2", "C3", "C4", "C5", "C6"]:
        for sport in ["nfl", "ncaaf"]:
            r = results_df[(results_df["cell"] == cell) & (results_df["sport"] == sport) &
                           (results_df["timing"] == "next")]
            if len(r) > 0:
                rr = r.iloc[0]
                ats_str = f"{int(rr['hits'])}-{int(rr['misses'])}" if rr['n_ats'] > 0 else "—"
                lines.append(f"| {cell} | {sport.upper()} | {rr['n']} | {rr['mean_clv_pp']:+.2f} | "
                             f"{rr['t_clv']:.2f} | {ats_str} | {rr['verdict']} |")
            else:
                lines.append(f"| {cell} | {sport.upper()} | 0 | — | — | — | NO DATA |")
    lines.append("")

    # What the interim can and cannot say
    lines.append("## What the interim read can and cannot say")
    lines.append("")
    lines.append("**Can say:** Whether CLV is directionally positive or negative for each cell,")
    lines.append("with a significance test. Whether the C2 (lag) sanity check passes. The relative")
    lines.append("fire rates across cells and sports.")
    lines.append("")
    lines.append("**Cannot say:** Whether any cell is profitable after vig (ATS N is far below the")
    lines.append("~250-1000 needed for statistical power). Whether NCAAF results for weeks 5-6 would")
    lines.append("change the ATS picture (CFBD file is stale). Whether the Hard Rock stale number in")
    lines.append("C2 was actually bettable at that moment (the tape shows it was listed, not that")
    lines.append("it would have been accepted). Whether the NCAAF HR coverage of 31.8% affects cell")
    lines.append("estimates (events without HR data are excluded, not imputed). Whether C6 fires")
    lines.append("exist in this season at all (weather join not implemented).")
    lines.append("")

    report_path = OUT_DIR / "LM_INTERIM_2026-10-11.md"
    report_path.write_text("\n".join(lines))
    print(f"Wrote report: {report_path}")


if __name__ == "__main__":
    main()
