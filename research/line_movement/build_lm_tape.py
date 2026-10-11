#!/usr/bin/env python3
"""
LM-1 Item 2: Build the line-movement event tape from snapshot parquets.

Reads data/odds_archive/{nfl,ncaaf}/line_history/season=2026/snap_*.parquet
Writes:
  research/line_movement/tape/lm_tape_2026.parquet   (per event × market × book × snapshot)
  research/line_movement/tape/lm_events_2026.parquet  (derived event-level signals)

No API calls. All data from disk.
"""

import sys, time, warnings
from pathlib import Path
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

TAPE_DIR = ROOT / "research" / "line_movement" / "tape"
TAPE_DIR.mkdir(parents=True, exist_ok=True)

# NFL team name mapping: Odds API full names -> nflreadpy abbreviations
_NFL_FULL_TO_ABBR = {
    "Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL", "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF", "Carolina Panthers": "CAR", "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE", "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN", "Detroit Lions": "DET", "Green Bay Packers": "GB",
    "Houston Texans": "HOU", "Indianapolis Colts": "IND", "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC", "Las Vegas Raiders": "LV", "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LA", "Miami Dolphins": "MIA", "Minnesota Vikings": "MIN",
    "New England Patriots": "NE", "New Orleans Saints": "NO", "New York Giants": "NYG",
    "New York Jets": "NYJ", "Philadelphia Eagles": "PHI", "Pittsburgh Steelers": "PIT",
    "San Francisco 49ers": "SF", "Seattle Seahawks": "SEA", "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN", "Washington Commanders": "WAS",
}

HARD_ROCK_BOOKS = {"nfl": "hardrockbet_fl", "ncaaf": "hardrockbet"}


def american_to_implied(price):
    """American odds -> raw implied probability."""
    if pd.isna(price):
        return np.nan
    if price > 0:
        return 100.0 / (price + 100.0)
    return abs(price) / (abs(price) + 100.0)


def _ts_utc(v):
    """Ensure a timestamp is tz-aware UTC."""
    t = pd.Timestamp(v)
    return t.tz_localize("UTC") if t.tzinfo is None else t


def devig_two_way(p1, p2):
    """Multiplicative de-vig: normalize two raw implied probabilities to sum to 1."""
    total = p1 + p2
    if total == 0 or pd.isna(total):
        return np.nan, np.nan
    return p1 / total, p2 / total


def load_all_snapshots(sport_dir):
    """Load all snapshot parquets from a directory, return concatenated DataFrame."""
    files = sorted(sport_dir.glob("snap_*.parquet"))
    if not files:
        raise FileNotFoundError(f"No snapshot files in {sport_dir}")
    dfs = []
    for f in files:
        df = pd.read_parquet(f)
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)


def load_nfl_results():
    """Load 2026 NFL game results via nflreadpy."""
    import nflreadpy
    pbp = nflreadpy.load_pbp([2026]).to_pandas()
    games = pbp.groupby("game_id").agg(
        home_team=("home_team", "first"),
        away_team=("away_team", "first"),
        home_score=("home_score", "max"),
        away_score=("away_score", "max"),
    ).reset_index()
    return games


def load_ncaaf_results():
    """Load 2026 NCAAF results from research/ncaaf/cfbd_games_2026.parquet."""
    path = ROOT / "research" / "ncaaf" / "cfbd_games_2026.parquet"
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    completed = df[df["completed"] == True].copy()
    return completed


def match_nfl_result(home_full, away_full, results_df):
    """Match an Odds API NFL event to nflreadpy results by team abbreviation."""
    h = _NFL_FULL_TO_ABBR.get(home_full)
    a = _NFL_FULL_TO_ABBR.get(away_full)
    if not h or not a:
        return np.nan, np.nan
    # game_id format: 2026_WW_AWAY_HOME
    match = results_df[(results_df["home_team"] == h) & (results_df["away_team"] == a)]
    if len(match) == 1:
        return match.iloc[0]["home_score"], match.iloc[0]["away_score"]
    return np.nan, np.nan


def _build_ncaaf_name_map(cfbd_teams):
    """Build a mapping from Odds API full names to CFBD team names."""
    # Explicit overrides
    overrides = {
        "San Jose State Spartans": "San José State",
        "UMass Minutemen": "Massachusetts",
        "Southern Mississippi Golden Eagles": "Southern Miss",
        "Appalachian State Mountaineers": "App State",
        "Hawaii Rainbow Warriors": "Hawai'i",
        "Southeastern Louisiana Lions": "SE Louisiana",
        "William and Mary Tribe": "William & Mary",
        "LIU Sharks": "Long Island University",
        "Houston Baptist Huskies": "Houston Christian",
        "Sam Houston State Bearkats": "Sam Houston",
        "UL Monroe Warhawks": "Louisiana Monroe",
        "Louisiana Ragin Cajuns": "Louisiana",
        "Louisiana Ragin' Cajuns": "Louisiana",
        "UT San Antonio Roadrunners": "UTSA",
        "Texas State Bobcats": "Texas State",
    }
    name_map = {}
    for full_name, cfbd_name in overrides.items():
        if cfbd_name in cfbd_teams:
            name_map[full_name] = cfbd_name

    return name_map, cfbd_teams


def _odds_to_cfbd_name(name, name_map, cfbd_teams):
    """Map an Odds API NCAAF full name to CFBD name."""
    if name in name_map:
        return name_map[name]

    # Strip last word (mascot)
    parts = name.split()
    for n_drop in range(1, min(len(parts), 3)):
        candidate = " ".join(parts[:-n_drop])
        if candidate in cfbd_teams:
            return candidate

    # Try "State" variations: "Ohio State Buckeyes" -> "Ohio State"
    # Already handled by the loop above

    # Prefix match on full candidate (without mascot)
    candidate = " ".join(parts[:-1]) if len(parts) > 1 else name
    matches = [t for t in cfbd_teams if t.lower() == candidate.lower()]
    if len(matches) == 1:
        return matches[0]

    # Multi-word prefix
    if len(candidate.split()) >= 2:
        matches = [t for t in cfbd_teams if t.lower().startswith(candidate.lower())]
        if len(matches) == 1:
            return matches[0]

    return None


def match_ncaaf_result(home_full, away_full, commence_time, results_df, name_map=None, cfbd_teams=None):
    """Match an Odds API NCAAF event to CFBD results."""
    if results_df is None:
        return np.nan, np.nan

    if name_map is None or cfbd_teams is None:
        cfbd_teams = set(results_df["homeTeam"].unique()) | set(results_df["awayTeam"].unique())
        name_map = {}

    h = _odds_to_cfbd_name(home_full, name_map, cfbd_teams)
    a = _odds_to_cfbd_name(away_full, name_map, cfbd_teams)
    if not h or not a:
        return np.nan, np.nan

    candidates = results_df[
        ((results_df["homeTeam"].isin([h, a])) & (results_df["awayTeam"].isin([h, a])))
    ]
    if len(candidates) == 0:
        return np.nan, np.nan

    ct = pd.Timestamp(commence_time)
    candidates = candidates.copy()
    candidates["startDate_ts"] = pd.to_datetime(candidates["startDate"])
    close = candidates[abs((candidates["startDate_ts"] - ct).dt.total_seconds()) < 36 * 3600]
    if len(close) == 0:
        return np.nan, np.nan
    if len(close) > 1:
        close = close.copy()
        close["_dist"] = abs((close["startDate_ts"] - ct).dt.total_seconds())
        close = close.sort_values("_dist").head(1)

    row = close.iloc[0]
    if row["homeTeam"] == h:
        return row["homePoints"], row["awayPoints"]
    else:
        return row["awayPoints"], row["homePoints"]


def build_tape(sport_key, sport_label):
    """Build tape for one sport. Returns (tape_df, events_df, diagnostics_dict)."""
    print(f"\n{'='*60}")
    print(f"Building tape for {sport_label}")
    print(f"{'='*60}")

    t0 = time.time()

    hr_book = HARD_ROCK_BOOKS[sport_key]
    snap_dir = ROOT / "data" / "odds_archive" / sport_key / "line_history" / "season=2026"
    raw = load_all_snapshots(snap_dir)
    print(f"Loaded {len(raw):,} rows from {raw['snapshot_utc'].nunique()} snapshots "
          f"in {time.time()-t0:.1f}s")

    # Parse timestamps
    raw["snapshot_utc"] = pd.to_datetime(raw["snapshot_utc"], utc=True)
    raw["commence_time"] = pd.to_datetime(raw["commence_time"], utc=True)
    raw["book_last_update"] = pd.to_datetime(raw["book_last_update"], utc=True)

    # ---- ADMISSION CHECKS ----

    # 1. Duplicate (snapshot, event, book, market, outcome) rows
    dup_key = ["snapshot_utc", "event_id", "bookmaker", "market", "outcome_name"]
    dups = raw.duplicated(subset=dup_key, keep=False)
    n_dups = dups.sum()
    if n_dups > 0:
        print(f"HALT: {n_dups} duplicate rows on {dup_key}")
        dup_sample = raw[dups].head(10)
        print(dup_sample.to_string())
        sys.exit(1)

    # 2. Null points on spreads/totals
    sp_tot = raw[raw["market"].isin(["spreads", "totals"])]
    null_pts = sp_tot["point"].isna().sum()
    if null_pts > 0:
        print(f"HALT: {null_pts} null points on spreads/totals")
        print(sp_tot[sp_tot["point"].isna()].head(5).to_string())
        sys.exit(1)

    # 3. Prices outside range
    bad_prices = raw[(raw["price"] < -100000) | (raw["price"] > 100000)]
    if len(bad_prices) > 0:
        print(f"HALT: {len(bad_prices)} prices outside [-100000, 100000]")
        sys.exit(1)

    # 4. Home/away name consistency per event — drop inconsistent events
    drop_events = set()
    for col in ["home_team", "away_team"]:
        per_event = raw.groupby("event_id")[col].nunique()
        bad = per_event[per_event > 1]
        if len(bad) > 0:
            print(f"WARNING: {len(bad)} events with inconsistent {col} — DROPPING")
            for eid in bad.index[:5]:
                vals = raw[raw["event_id"] == eid][col].unique()
                print(f"  {eid}: {vals}")
            drop_events |= set(bad.index)
    if drop_events:
        raw = raw[~raw["event_id"].isin(drop_events)]
        print(f"Dropped {len(drop_events)} events with name swaps")

    # Filter to Pinnacle and Hard Rock only
    books_of_interest = ["pinnacle", hr_book]
    tape = raw[raw["bookmaker"].isin(books_of_interest)].copy()
    print(f"Filtered to {books_of_interest}: {len(tape):,} rows")

    # Identify kicked-off events: commence_time < now
    now = pd.Timestamp.now(tz="UTC")
    events_meta = tape.groupby("event_id").agg(
        home_team=("home_team", "first"),
        away_team=("away_team", "first"),
        commence_time=("commence_time", "first"),
    ).reset_index()
    events_meta["kicked_off"] = events_meta["commence_time"] < now

    # 5. Hard Rock NCAAF coverage check
    pinn_events = set(tape[tape["bookmaker"] == "pinnacle"]["event_id"].unique())
    hr_events = set(tape[tape["bookmaker"] == hr_book]["event_id"].unique())
    hr_coverage = len(hr_events & pinn_events) / max(len(pinn_events), 1) * 100
    print(f"Hard Rock coverage of Pinnacle events: {hr_coverage:.1f}% "
          f"({len(hr_events & pinn_events)}/{len(pinn_events)})")
    if sport_key == "ncaaf" and hr_coverage < 50:
        print(f"WARNING: Hard Rock NCAAF coverage {hr_coverage:.1f}% < 50% of Pinnacle")
        print("  This is real — HR does not list most NCAAF games. Proceeding with available data.")
        print(f"  HR events: {len(hr_events)}, Pinnacle events: {len(pinn_events)}, overlap: {len(hr_events & pinn_events)}")

    # ---- BUILD DE-VIGGED PROBABILITIES ----
    # For each (snapshot, event, bookmaker, market), pair the two outcomes
    tape["raw_implied"] = tape["price"].apply(american_to_implied)

    # Identify paired outcomes
    # spreads/totals: two outcomes per (snap, event, book, market)
    # h2h: two outcomes per (snap, event, book, market)
    # De-vig: for each (snapshot, event, book, market) pair, normalize the two
    # raw implied probabilities to sum to 1.
    pair_key = ["snapshot_utc", "event_id", "bookmaker", "market"]
    tape = tape.sort_values(pair_key + ["outcome_name"]).reset_index(drop=True)

    # Count outcomes per group; keep only groups with exactly 2
    grp_sizes = tape.groupby(pair_key).size()
    valid_pairs = grp_sizes[grp_sizes == 2].index
    print(f"Valid 2-outcome pairs: {len(valid_pairs):,} / {len(grp_sizes):,}")

    # Vectorized de-vig: assign rank within group, pivot, compute
    tape["_rank"] = tape.groupby(pair_key).cumcount()
    # For rank-0 and rank-1 rows, compute devig together
    r0 = tape[tape["_rank"] == 0].set_index(pair_key)["raw_implied"]
    r1 = tape[tape["_rank"] == 1].set_index(pair_key)["raw_implied"]
    total = r0 + r1
    devig_0 = r0 / total
    devig_1 = r1 / total

    # Map back
    tape["devig_prob"] = np.nan
    idx0 = tape[tape["_rank"] == 0].index
    idx1 = tape[tape["_rank"] == 1].index
    # Build multi-index for alignment
    mi0 = tape.loc[idx0].set_index(pair_key).index
    mi1 = tape.loc[idx1].set_index(pair_key).index
    tape.loc[idx0, "devig_prob"] = devig_0.reindex(mi0).values
    tape.loc[idx1, "devig_prob"] = devig_1.reindex(mi1).values
    tape.drop(columns=["_rank"], inplace=True)

    # ---- IDENTIFY OPEN/CLOSE PER EVENT × MARKET × BOOK ----
    kicked_events = set(events_meta[events_meta["kicked_off"]]["event_id"])
    tape_kicked = tape[tape["event_id"].isin(kicked_events)].copy()

    # Pre-kick snapshots only
    tape_kicked = tape_kicked[tape_kicked["snapshot_utc"] < tape_kicked["commence_time"]]

    # Open = first pre-kick snapshot; Close = last pre-kick ≤ 60 min before commence
    emb_key = ["event_id", "market", "bookmaker"]

    def _open_close(grp):
        grp = grp.sort_values("snapshot_utc")
        if len(grp) == 0:
            return pd.Series(dtype=float)
        open_row = grp.iloc[0]
        # Close: last snapshot ≤ 60 min before kick
        kick = grp["commence_time"].iloc[0]
        close_cutoff = kick - pd.Timedelta(minutes=60)
        close_candidates = grp[grp["snapshot_utc"] <= close_cutoff]
        if len(close_candidates) > 0:
            close_row = close_candidates.iloc[-1]
            close_flagged = False
        else:
            # Fallback: last pre-kick snapshot
            close_row = grp.iloc[-1]
            close_flagged = True
        return pd.Series({
            "open_snapshot": open_row["snapshot_utc"],
            "open_point": open_row["point"],
            "open_price": open_row["price"],
            "open_devig": open_row["devig_prob"],
            "open_outcome": open_row["outcome_name"],
            "close_snapshot": close_row["snapshot_utc"],
            "close_point": close_row["point"],
            "close_price": close_row["price"],
            "close_devig": close_row["devig_prob"],
            "close_flagged": close_flagged,
        })

    # We need open/close per outcome within each event × market × book
    oc_key = ["event_id", "market", "bookmaker", "outcome_name"]
    # This is slow with apply; do vectorized
    tape_kicked_sorted = tape_kicked.sort_values(["event_id", "market", "bookmaker",
                                                   "outcome_name", "snapshot_utc"])

    print(f"Computing open/close for {tape_kicked_sorted['event_id'].nunique()} kicked events...")

    # ---- ATTACH RESULTS ----
    print("Loading results...")
    if sport_key == "nfl":
        nfl_results = load_nfl_results()
        print(f"NFL results: {len(nfl_results)} games")
    elif sport_key == "ncaaf":
        ncaaf_results = load_ncaaf_results()
        if ncaaf_results is not None:
            print(f"NCAAF results: {len(ncaaf_results)} completed games")
            ncaaf_name_map, ncaaf_cfbd_teams = _build_ncaaf_name_map(
                set(ncaaf_results["homeTeam"].unique()) | set(ncaaf_results["awayTeam"].unique()))
        else:
            print("NCAAF results: NOT FOUND")
            ncaaf_name_map, ncaaf_cfbd_teams = {}, set()

    # Build event-level result lookup
    event_results = {}
    for eid, meta in events_meta[events_meta["kicked_off"]].iterrows():
        row = events_meta.loc[eid] if isinstance(eid, int) else meta
        home = row["home_team"]
        away = row["away_team"]
        ct = row["commence_time"]
        if sport_key == "nfl":
            hs, as_ = match_nfl_result(home, away, nfl_results)
        else:
            hs, as_ = match_ncaaf_result(home, away, ct, ncaaf_results,
                                          ncaaf_name_map, ncaaf_cfbd_teams)
        event_results[row["event_id"]] = (hs, as_)

    # ---- WRITE TAPE ----
    # The tape is the filtered Pinnacle + HR pre-kick data with de-vigged probs
    tape_out = tape_kicked_sorted[["snapshot_utc", "event_id", "commence_time",
                                    "home_team", "away_team", "bookmaker", "market",
                                    "outcome_name", "point", "price", "raw_implied",
                                    "devig_prob", "book_last_update"]].copy()
    tape_out["home_score"] = tape_out["event_id"].map(lambda eid: event_results.get(eid, (np.nan,))[0])
    tape_out["away_score"] = tape_out["event_id"].map(lambda eid: event_results.get(eid, (np.nan, np.nan))[1])

    tape_path = TAPE_DIR / "lm_tape_2026.parquet"
    tape_out.to_parquet(tape_path, index=False)
    print(f"Wrote tape: {tape_path} ({len(tape_out):,} rows, {tape_out['event_id'].nunique()} events)")

    # ---- BUILD EVENT-LEVEL SIGNALS ----
    print("Building event-level signals...")
    events_list = []

    pinn_tape = tape_kicked_sorted[tape_kicked_sorted["bookmaker"] == "pinnacle"]
    hr_tape = tape_kicked_sorted[tape_kicked_sorted["bookmaker"] == hr_book]

    for (eid, mkt), grp in pinn_tape.groupby(["event_id", "market"]):
        meta_row = events_meta[events_meta["event_id"] == eid]
        if len(meta_row) == 0:
            continue
        meta_row = meta_row.iloc[0]
        home = meta_row["home_team"]
        away = meta_row["away_team"]
        kick = meta_row["commence_time"]
        hs, as_ = event_results.get(eid, (np.nan, np.nan))

        # Get the "home side" outcome name for consistent orientation
        if mkt == "h2h":
            home_outcome = home
            away_outcome = away
        elif mkt == "spreads":
            home_outcome = home
            away_outcome = away
        elif mkt == "totals":
            home_outcome = "Over"
            away_outcome = "Under"
        else:
            continue

        # Pinnacle point series (for spreads/totals, use home side)
        home_rows = grp[grp["outcome_name"] == home_outcome].sort_values("snapshot_utc")
        if len(home_rows) == 0:
            # Try other outcome names
            outcomes = grp["outcome_name"].unique()
            if mkt == "totals":
                home_rows = grp[grp["outcome_name"] == "Over"].sort_values("snapshot_utc")
                away_rows_name = "Under"
            else:
                continue
        else:
            away_rows_name = away_outcome

        if mkt in ("spreads", "totals") and len(home_rows) == 0:
            continue

        points = home_rows["point"].values if mkt != "h2h" else np.array([np.nan] * len(home_rows))
        snapshots = home_rows["snapshot_utc"].values

        # Point changes
        changes = []
        key_number_crossings = []
        for i in range(1, len(points)):
            if mkt == "h2h":
                continue
            if points[i] != points[i-1]:
                delta = points[i] - points[i-1]
                changes.append({
                    "snapshot_utc": snapshots[i],
                    "prev_snapshot": snapshots[i-1],
                    "prev_point": points[i-1],
                    "new_point": points[i],
                    "delta": delta,
                    "abs_delta": abs(delta),
                })
                # Key-number crossings (spreads only, 3 and 7)
                if mkt == "spreads":
                    for kn in [3.0, 7.0, -3.0, -7.0]:
                        p_prev = points[i-1]
                        p_new = points[i]
                        # Check if kn is between prev and new (exclusive of neither, inclusive of crossing)
                        crossed = (min(p_prev, p_new) < kn <= max(p_prev, p_new)) or \
                                  (min(p_prev, p_new) <= kn < max(p_prev, p_new))
                        if not crossed:
                            # Also check if we moved FROM exactly kn
                            if p_prev == kn and p_new != kn:
                                crossed = True
                            elif p_new == kn and p_prev != kn:
                                crossed = True
                        if crossed:
                            key_number_crossings.append({
                                "key_number": abs(kn),
                                "snapshot_utc": snapshots[i],
                                "prev_point": p_prev,
                                "new_point": p_new,
                            })

        # Reversals: ≥1.0 then ≥0.5 back within 3 hours
        reversals = []
        for i, ch in enumerate(changes):
            if ch["abs_delta"] < 1.0:
                continue
            # Look for a reversal within 3 hours
            ch_time = _ts_utc(ch["snapshot_utc"])
            for j in range(i+1, len(changes)):
                ch2 = changes[j]
                ch2_time = _ts_utc(ch2["snapshot_utc"])
                if (ch2_time - ch_time).total_seconds() > 3 * 3600:
                    break
                # Reversal: opposite direction, ≥0.5
                if ch2["abs_delta"] >= 0.5 and np.sign(ch2["delta"]) != np.sign(ch["delta"]):
                    reversals.append({
                        "initial_snapshot": ch["snapshot_utc"],
                        "initial_delta": ch["delta"],
                        "reversal_snapshot": ch2["snapshot_utc"],
                        "reversal_delta": ch2["delta"],
                    })
                    break

        # Early-week flag: changes before Wednesday 17:00 UTC of game week
        # Game week = the week containing the game (Mon-Sun, with the game on Thu/Sat/Sun)
        # Simplification: Wednesday 17:00 UTC before the game
        kick_dt = pd.Timestamp(kick)
        # Find the Wednesday ≤ 4 days before kick
        days_since_wed = (kick_dt.weekday() - 2) % 7
        wed_before = kick_dt - pd.Timedelta(days=days_since_wed)
        wed_cutoff = wed_before.replace(hour=17, minute=0, second=0, microsecond=0)
        if wed_cutoff.tzinfo is None:
            wed_cutoff = wed_cutoff.tz_localize("UTC")
        if wed_cutoff > kick_dt:
            wed_cutoff -= pd.Timedelta(days=7)

        early_changes = [c for c in changes if _ts_utc(c["snapshot_utc"]) < wed_cutoff]

        # Close definition: last pre-kick ≤ 60 min
        close_cutoff = kick - pd.Timedelta(minutes=60)
        close_candidates = home_rows[home_rows["snapshot_utc"] <= close_cutoff]
        if len(close_candidates) > 0:
            close_snap = close_candidates.iloc[-1]
            close_flagged = False
        else:
            close_snap = home_rows.iloc[-1]
            close_flagged = True

        # Open
        open_snap = home_rows.iloc[0]

        # Pinnacle close de-vigged prob for each side
        close_cutoff_ts = close_cutoff
        pinn_close_grp = grp[grp["snapshot_utc"] <= close_cutoff_ts]
        if len(pinn_close_grp) == 0:
            pinn_close_grp = grp

        pinn_close_home = pinn_close_grp[pinn_close_grp["outcome_name"] == home_outcome]
        pinn_close_away = pinn_close_grp[pinn_close_grp["outcome_name"] == away_rows_name]

        pinn_close_home_devig = pinn_close_home.iloc[-1]["devig_prob"] if len(pinn_close_home) > 0 else np.nan
        pinn_close_away_devig = pinn_close_away.iloc[-1]["devig_prob"] if len(pinn_close_away) > 0 else np.nan
        pinn_close_point = close_snap["point"] if mkt != "h2h" else np.nan

        # Hard Rock lag after each Pinnacle change
        hr_grp = hr_tape[(hr_tape["event_id"] == eid) & (hr_tape["market"] == mkt)]
        hr_home = hr_grp[hr_grp["outcome_name"] == home_outcome].sort_values("snapshot_utc") if len(hr_grp) > 0 else pd.DataFrame()

        hr_lags = []
        for ch in changes:
            ch_time = _ts_utc(ch["snapshot_utc"])
            new_pt = ch["new_point"]
            # Find first HR snapshot after ch_time
            if len(hr_home) > 0:
                hr_after = hr_home[hr_home["snapshot_utc"] >= ch_time]
                if len(hr_after) > 0:
                    hr_first = hr_after.iloc[0]
                    hr_matches = hr_first["point"] == new_pt if mkt != "h2h" else True
                    lag_snaps = 0
                    for _, hr_row in hr_after.iterrows():
                        if mkt != "h2h" and hr_row["point"] != new_pt:
                            lag_snaps += 1
                        else:
                            break
                    hr_lags.append(lag_snaps)
                else:
                    hr_lags.append(np.nan)
            else:
                hr_lags.append(np.nan)

        # First qualifying de-vigged shade gap ≥ 2.0 pp
        # Same point at both books, HR de-vigged - Pinnacle de-vigged ≥ 2.0 pp on public side
        shade_gap = np.nan
        shade_snap = None
        if len(hr_home) > 0 and mkt != "h2h":
            # Merge on snapshot
            merged = pd.merge(
                home_rows[["snapshot_utc", "point", "devig_prob"]].rename(
                    columns={"point": "pinn_point", "devig_prob": "pinn_devig"}),
                hr_home[["snapshot_utc", "point", "devig_prob"]].rename(
                    columns={"point": "hr_point", "devig_prob": "hr_devig"}),
                on="snapshot_utc", how="inner"
            )
            same_pt = merged[merged["pinn_point"] == merged["hr_point"]]
            if len(same_pt) > 0:
                # For spreads: public side = home favourite (negative spread)
                # For totals: public side = Over (home_outcome)
                # Gap = HR devig on public side - Pinnacle devig on public side
                same_pt = same_pt.copy()
                same_pt["gap_pp"] = (same_pt["hr_devig"] - same_pt["pinn_devig"]) * 100
                qualifying = same_pt[same_pt["gap_pp"].abs() >= 2.0]
                if len(qualifying) > 0:
                    first_q = qualifying.iloc[0]
                    shade_gap = first_q["gap_pp"]
                    shade_snap = first_q["snapshot_utc"]

        ev = {
            "event_id": eid,
            "sport": sport_key,
            "market": mkt,
            "home_team": home,
            "away_team": away,
            "commence_time": kick,
            "home_score": hs,
            "away_score": as_,
            "pinn_open_point": open_snap["point"] if mkt != "h2h" else np.nan,
            "pinn_close_point": pinn_close_point,
            "pinn_open_devig_home": open_snap["devig_prob"],
            "pinn_close_devig_home": pinn_close_home_devig,
            "pinn_close_devig_away": pinn_close_away_devig,
            "close_flagged": close_flagged,
            "n_pinn_snaps": len(home_rows),
            "n_point_changes": len(changes),
            "n_key_crossings": len(key_number_crossings),
            "n_reversals": len(reversals),
            "n_early_changes": len(early_changes),
            "total_move": abs(float(pinn_close_point) - float(open_snap["point"])) if mkt != "h2h" else np.nan,
            "first_shade_gap_pp": shade_gap,
            "first_shade_snap": shade_snap,
            "hr_present": len(hr_home) > 0,
        }

        # Store changes, crossings, reversals, lags as JSON-serializable
        ev["changes_json"] = str(changes) if changes else ""
        ev["key_crossings_json"] = str(key_number_crossings) if key_number_crossings else ""
        ev["reversals_json"] = str(reversals) if reversals else ""
        ev["hr_lags_json"] = str(hr_lags) if hr_lags else ""
        ev["early_changes_json"] = str(early_changes) if early_changes else ""

        events_list.append(ev)

    events_df = pd.DataFrame(events_list)
    events_path = TAPE_DIR / "lm_events_2026.parquet"
    events_df.to_parquet(events_path, index=False)
    print(f"Wrote events: {events_path} ({len(events_df)} rows)")

    elapsed = time.time() - t0
    print(f"Elapsed: {elapsed:.1f}s")

    # ---- FIRE COUNTS PER CELL ----
    print(f"\n--- Fire counts ({sport_label}) ---")

    kicked_events_df = events_df[events_df["commence_time"] < now]

    # C1: key-number crossings (spreads only)
    c1 = kicked_events_df[(kicked_events_df["market"] == "spreads") &
                           (kicked_events_df["n_key_crossings"] > 0)]
    c1_fires = c1["n_key_crossings"].sum()
    print(f"C1 (key-number crossings): {c1_fires} fires across {len(c1)} events")

    # C2: Hard Rock lag (≥0.5 move, HR still shows old point)
    # Count from changes
    c2_fires = 0
    for _, ev in kicked_events_df.iterrows():
        if ev["changes_json"] and ev["hr_lags_json"]:
            try:
                changes = eval(ev["changes_json"])
                lags = eval(ev["hr_lags_json"])
                for ch, lag in zip(changes, lags):
                    if ch["abs_delta"] >= 0.5 and not pd.isna(lag) and lag > 0:
                        c2_fires += 1
            except:
                pass
    print(f"C2 (Hard Rock lag): {c2_fires} fires")

    # C3: Early-week ≥1.0 moves
    c3 = kicked_events_df[kicked_events_df["n_early_changes"] > 0]
    c3_fires = 0
    for _, ev in c3.iterrows():
        if ev["early_changes_json"]:
            try:
                early = eval(ev["early_changes_json"])
                c3_fires += sum(1 for c in early if c["abs_delta"] >= 1.0)
            except:
                pass
    print(f"C3 (early-week ≥1.0 move): {c3_fires} fires")

    # C4: Reversals
    c4_fires = kicked_events_df["n_reversals"].sum()
    print(f"C4 (reversals): {int(c4_fires)} fires")

    # C5: Shade gap ≥2.0 pp (one per event × market)
    c5 = kicked_events_df[kicked_events_df["first_shade_gap_pp"].notna()]
    print(f"C5 (shade gap ≥2.0 pp): {len(c5)} fires")

    # C6: totals drop ≥1.5 in final 24h + weather
    c6_fires = 0  # Will need weather data — reported separately
    print(f"C6 (weather totals): requires weather join — computed in grade step")

    return tape_out, events_df, {"elapsed": elapsed, "hr_coverage": hr_coverage}


def main():
    print("LM-1 Item 2: Building event tape")
    print(f"Started: {datetime.now(timezone.utc).isoformat()}")

    t_total = time.time()

    tape_nfl, events_nfl, diag_nfl = build_tape("nfl", "NFL")
    tape_ncaaf, events_ncaaf, diag_ncaaf = build_tape("ncaaf", "NCAAF")

    # Combine
    tape_all = pd.concat([tape_nfl, tape_ncaaf], ignore_index=True)
    events_all = pd.concat([events_nfl, events_ncaaf], ignore_index=True)

    # Overwrite with combined
    tape_all.to_parquet(TAPE_DIR / "lm_tape_2026.parquet", index=False)
    events_all.to_parquet(TAPE_DIR / "lm_events_2026.parquet", index=False)

    total_elapsed = time.time() - t_total
    print(f"\n{'='*60}")
    print(f"TOTAL elapsed: {total_elapsed:.1f}s")
    print(f"Tape: {len(tape_all):,} rows, {tape_all['event_id'].nunique()} events")
    print(f"Events: {len(events_all)} rows")
    print(f"NFL HR coverage: {diag_nfl['hr_coverage']:.1f}%")
    print(f"NCAAF HR coverage: {diag_ncaaf['hr_coverage']:.1f}%")


if __name__ == "__main__":
    main()
