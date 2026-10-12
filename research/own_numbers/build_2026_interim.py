"""
ON-1 ITEM 3: Interim look at 2026 Monday numbers vs Hard Rock's openers.
Weeks 2-6. LABEL: interim look at forward data; nothing is tuned on it.
"""
import os, sys, json, time
import numpy as np
import pandas as pd
import glob

os.environ["SSL_CERT_FILE"] = __import__("certifi").where()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from nfl.sim.engine import simulate_game
from nfl.sim.names import FULL_TO_ABBR

ROOT = os.path.join(os.path.dirname(__file__), "../..")

with open(os.path.join(ROOT, "nfl/sim/hfa_v1.json")) as f:
    H = json.load(f)["h"]

ABBR_TO_FULL = {v: k for k, v in FULL_TO_ABBR.items()}

import nflreadpy as nfl
sched = nfl.load_schedules([2026]).to_pandas()
games = sched[(sched["game_type"] == "REG") & (sched["week"].between(2, 6))].copy()
print(f"2026 wk2-6 games: {len(games)}")

# ─── LOAD TAPE ───────────────────────────────────────────────────────
files = sorted(glob.glob(os.path.join(ROOT, "data/odds_archive/nfl/line_history/season=2026/*.parquet")))
tape = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
tape["snapshot_utc"] = pd.to_datetime(tape["snapshot_utc"])
tape["commence_time"] = pd.to_datetime(tape["commence_time"])
spreads = tape[tape["market"] == "spreads"].copy()
totals = tape[tape["market"] == "totals"].copy()

# Map team names to abbreviations
spreads["team_abbr"] = spreads["outcome_name"].map(FULL_TO_ABBR)
unmapped = spreads[spreads["team_abbr"].isna()]["outcome_name"].unique()
if len(unmapped) > 0:
    print(f"HALT: unmapped teams in spreads: {unmapped}")
    sys.exit(1)

totals["outcome_abbr"] = totals["outcome_name"]  # Over/Under, not team names


def get_first_and_last_line(event_id, bookmaker, market_df, outcome_filter=None):
    """Get the first and last (pre-kick) snapshot for a book+event."""
    sub = market_df[
        (market_df["event_id"] == event_id) &
        (market_df["bookmaker"] == bookmaker)
    ]
    if outcome_filter:
        sub = sub[sub["team_abbr"] == outcome_filter]
    if len(sub) == 0:
        return None, None
    sub = sub.sort_values("snapshot_utc")
    return sub.iloc[0], sub.iloc[-1]


# ─── MAP GAMES TO EVENT IDS ─────────────────────────────────────────
# Match nflverse game_id to tape event_id via home_team + away_team + commence_time
game_events = []
for _, g in games.iterrows():
    home = g["home_team"]
    away = g["away_team"]
    home_full = ABBR_TO_FULL.get(home, home)
    away_full = ABBR_TO_FULL.get(away, away)

    # Find matching event by teams
    candidates = spreads[
        (spreads["outcome_name"].isin([home_full, away_full]))
    ]["event_id"].unique()

    # Filter to events that have BOTH teams
    for eid in candidates:
        evt = spreads[spreads["event_id"] == eid]
        evt_teams = set(evt["team_abbr"].unique())
        if home in evt_teams and away in evt_teams:
            game_events.append({
                "game_id": g["game_id"],
                "event_id": eid,
                "season": g["season"],
                "week": g["week"],
                "home_team": home,
                "away_team": away,
                "spread_line": g["spread_line"],
                "total_line": g["total_line"],
            })
            break

ge_df = pd.DataFrame(game_events)
print(f"Matched games to events: {len(ge_df)}/{len(games)}")

# ─── GET HR AND PINNACLE OPENS AND CLOSES ────────────────────────────
results = []
for _, g in ge_df.iterrows():
    eid = g["event_id"]
    home = g["home_team"]

    # HR spreads: first and last for home team
    hr_first, hr_last = get_first_and_last_line(eid, "hardrockbet_fl", spreads, home)
    pin_first, pin_last = get_first_and_last_line(eid, "pinnacle", spreads, home)

    # Totals: get Over line
    tot_sub_hr = totals[(totals["event_id"] == eid) & (totals["bookmaker"] == "hardrockbet_fl") &
                        (totals["outcome_name"] == "Over")]
    tot_sub_pin = totals[(totals["event_id"] == eid) & (totals["bookmaker"] == "pinnacle") &
                         (totals["outcome_name"] == "Over")]

    row = {
        "game_id": g["game_id"],
        "event_id": eid,
        "season": g["season"],
        "week": g["week"],
        "home_team": home,
        "away_team": g["away_team"],
        "nfl_spread_close": g["spread_line"],
        "nfl_total_close": g["total_line"],
    }

    # HR spreads (point column is the line; convention: home team's line)
    if hr_first is not None:
        row["hr_spread_open"] = hr_first["point"]
        row["hr_spread_open_price"] = hr_first["price"]
        row["hr_spread_open_time"] = hr_first["snapshot_utc"]
    if hr_last is not None:
        row["hr_spread_close"] = hr_last["point"]
        row["hr_spread_close_price"] = hr_last["price"]

    # Pinnacle spreads
    if pin_first is not None:
        row["pin_spread_open"] = pin_first["point"]
        row["pin_spread_open_time"] = pin_first["snapshot_utc"]
    if pin_last is not None:
        row["pin_spread_close"] = pin_last["point"]

    # Totals
    if len(tot_sub_hr) > 0:
        tot_hr_sorted = tot_sub_hr.sort_values("snapshot_utc")
        row["hr_total_open"] = tot_hr_sorted.iloc[0]["point"]
        row["hr_total_close"] = tot_hr_sorted.iloc[-1]["point"]
    if len(tot_sub_pin) > 0:
        tot_pin_sorted = tot_sub_pin.sort_values("snapshot_utc")
        row["pin_total_open"] = tot_pin_sorted.iloc[0]["point"]
        row["pin_total_close"] = tot_pin_sorted.iloc[-1]["point"]

    results.append(row)

lines_df = pd.DataFrame(results)
print(f"Lines extracted: {len(lines_df)}")
print(f"HR spread open coverage: {lines_df['hr_spread_open'].notna().sum()}/{len(lines_df)}")

# ─── RUN SIMS FOR 2026 GAMES ────────────────────────────────────────
print("\nRunning 2026 sims...")
sim_results = []
for _, g in lines_df.iterrows():
    try:
        chunk_m = []
        chunk_t = []
        for ci in range(2):
            seed = hash((g["game_id"], ci)) % (2**31)
            result = simulate_game(
                g["home_team"], g["away_team"], 2026, g["week"],
                n_sims=2500, seed=seed,
                epa_home_offset=H, epa_away_offset=-H)
            m = (result["home_score"] - result["away_score"]).values
            t = (result["home_score"] + result["away_score"]).values
            chunk_m.append(m.mean())
            chunk_t.append(t.mean())
        sim_results.append({
            "game_id": g["game_id"],
            "ours_m": np.mean(chunk_m),
            "ours_t": np.mean(chunk_t),
            "mc_se_m": np.std(chunk_m, ddof=1) / np.sqrt(2),
            "mc_se_t": np.std(chunk_t, ddof=1) / np.sqrt(2),
        })
    except Exception as e:
        print(f"  ERROR {g['game_id']}: {e}")
        sim_results.append({"game_id": g["game_id"], "ours_m": None, "ours_t": None,
                            "mc_se_m": None, "mc_se_t": None})

sim_df = pd.DataFrame(sim_results)
merged = lines_df.merge(sim_df, on="game_id")
print(f"Merged: {len(merged)}")

# Apply calibration from 2021-23 (use the last available bucket, 14+, from 2023)
# This is a rough proxy for 2026
cal = pd.read_parquet(os.path.join(ROOT, "nfl/data/own/calibration_table.parquet"))
cal_23_14 = cal[(cal["target_season"] == 2023) & (cal["bucket"] == "14+")]
cal_var_m = cal_23_14["cal_var_m"].values[0]
cal_var_t = cal_23_14["cal_var_t"].values[0]
merged["err_m"] = np.sqrt(merged["mc_se_m"]**2 + cal_var_m)
merged["err_t"] = np.sqrt(merged["mc_se_t"]**2 + cal_var_t)

# Confident subset vs HR open
has_hr = merged["hr_spread_open"].notna() & merged["ours_m"].notna()
merged_hr = merged[has_hr].copy()
merged_hr["gap_vs_hr"] = merged_hr["ours_m"] - merged_hr["hr_spread_open"]
merged_hr["confident"] = (merged_hr["gap_vs_hr"].abs() >= merged_hr["err_m"]) & (merged_hr["gap_vs_hr"].abs() >= 1.0)

print(f"\nGames with HR open: {len(merged_hr)}")
print(f"Confident: {merged_hr['confident'].sum()}")

# Direction agreement: sign(ours - HR_open) vs sign(HR_close - HR_open)
merged_hr["hr_move"] = merged_hr["hr_spread_close"] - merged_hr["hr_spread_open"]
has_move = merged_hr["hr_move"] != 0
mn_move = merged_hr[has_move].copy()
mn_move["dir_agree"] = (np.sign(mn_move["gap_vs_hr"]) == np.sign(mn_move["hr_move"]))

print(f"\nGames with HR movement: {len(mn_move)}")
print(f"Direction agreement (all): {mn_move['dir_agree'].mean():.3f} ({mn_move['dir_agree'].sum()}/{len(mn_move)})")

conf = mn_move[mn_move["confident"]]
if len(conf) > 0:
    print(f"Direction agreement (confident): {conf['dir_agree'].mean():.3f} ({conf['dir_agree'].sum()}/{len(conf)})")

# By week
print("\nBy week:")
for w in sorted(mn_move["week"].unique()):
    sub = mn_move[mn_move["week"] == w]
    sub_conf = conf[conf["week"] == w]
    print(f"  wk{w}: all {sub['dir_agree'].mean():.3f} ({sub['dir_agree'].sum()}/{len(sub)})"
          f" conf {sub_conf['dir_agree'].mean():.3f} ({sub_conf['dir_agree'].sum()}/{len(sub_conf)})" if len(sub_conf) > 0 else
          f"  wk{w}: all {sub['dir_agree'].mean():.3f} ({sub['dir_agree'].sum()}/{len(sub)}) conf N=0")

# Wilson interval on confident
if len(conf) > 0:
    from score_monday_numbers import wilson_interval
    p, lo, hi = wilson_interval(conf["dir_agree"].sum(), len(conf))
    print(f"\nConfident Wilson: {p:.3f} [{lo:.3f}, {hi:.3f}]")

# Save
out_path = os.path.join(ROOT, "nfl/data/own/monday_numbers_2026.parquet")
merged.to_parquet(out_path, index=False)
print(f"\nSaved to {out_path}")
print(f"LABEL: interim look at forward data. Nothing is tuned on it.")
