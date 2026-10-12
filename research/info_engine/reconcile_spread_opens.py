"""
IE-1 ITEM 4: Reconcile Australian Sports Betting spread opens with nflverse.
Book: bet365 for 2021-23. Lines from HOME perspective, decimal prices.
"""
import os
os.environ["SSL_CERT_FILE"] = __import__("certifi").where()

import pandas as pd
import numpy as np
import nflreadpy as nfl

ASB_PATH = os.path.join(os.path.dirname(__file__), "../../nfl/data/info/aussportsbetting_nfl.xlsx")
OUT_DIR = os.path.join(os.path.dirname(__file__), "../../nfl/data/info")

# ─── TEAM NAME MAP ──────────────────────────────────────────────────
ASB_TO_NFL = {
    "Arizona Cardinals": "ARI",
    "Atlanta Falcons": "ATL",
    "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF",
    "Carolina Panthers": "CAR",
    "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN",
    "Cleveland Browns": "CLE",
    "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN",
    "Detroit Lions": "DET",
    "Green Bay Packers": "GB",
    "Houston Texans": "HOU",
    "Indianapolis Colts": "IND",
    "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC",
    "Las Vegas Raiders": "LV",
    "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LA",
    "Miami Dolphins": "MIA",
    "Minnesota Vikings": "MIN",
    "New England Patriots": "NE",
    "New Orleans Saints": "NO",
    "New York Giants": "NYG",
    "New York Jets": "NYJ",
    "Philadelphia Eagles": "PHI",
    "Pittsburgh Steelers": "PIT",
    "San Francisco 49ers": "SF",
    "Seattle Seahawks": "SEA",
    "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN",
    "Washington Commanders": "WAS",
    "Washington Football Team": "WAS",
}

# ─── LOAD AND FILTER ────────────────────────────────────────────────
print("Loading ASB data...")
asb = pd.read_excel(ASB_PATH, sheet_name="Data")
asb["Date"] = pd.to_datetime(asb["Date"])
asb["month"] = asb["Date"].dt.month
asb["year"] = asb["Date"].dt.year
asb["season"] = asb.apply(lambda r: r["year"] if r["month"] >= 8 else r["year"] - 1, axis=1)

# DROP season >= 2024 FIRST
asb = asb[asb["season"] < 2024].copy()
kept_seasons = sorted(asb["season"].unique())
assert set(kept_seasons) & {2021, 2022, 2023} == {2021, 2022, 2023}, \
    f"HALT: expected 2021-23, got {kept_seasons}"
# Keep only 2021-23
asb = asb[asb["season"].isin([2021, 2022, 2023])].copy()
print(f"ASB 2021-23: {len(asb)} rows (expected 854)")
assert len(asb) == 854, f"HALT: expected 854, got {len(asb)}"

# Check for unmapped teams
all_teams = set(asb["Home Team"].unique()) | set(asb["Away Team"].unique())
unmapped = all_teams - set(ASB_TO_NFL.keys())
if unmapped:
    raise ValueError(f"HALT: unmapped teams: {unmapped}")
print(f"All {len(all_teams)} team names mapped successfully")

# Map team names
asb["home_team"] = asb["Home Team"].map(ASB_TO_NFL)
asb["away_team"] = asb["Away Team"].map(ASB_TO_NFL)

# Flag playoffs and neutral
is_playoff = asb["Playoff Game?"] == "Y"
is_neutral = asb["Neutral Venue?"] == "Y"
print(f"Playoff rows: {is_playoff.sum()} (will drop for reconciliation)")
print(f"Neutral venue rows: {is_neutral.sum()} (will carry flag)")

# Drop playoffs for reconciliation
asb_reg = asb[~is_playoff].copy()
print(f"REG rows: {len(asb_reg)} (expected 815)")
assert len(asb_reg) == 815, f"HALT: expected 815, got {len(asb_reg)}"
per_season = asb_reg["season"].value_counts().sort_index().to_dict()
print(f"Per season: {per_season}")

# ─── LOAD NFLVERSE SCHEDULES ────────────────────────────────────────
print("\nLoading nflverse schedules...")
sched = nfl.load_schedules([2021, 2022, 2023]).to_pandas()
sched_reg = sched[sched["game_type"] == "REG"].copy()
sched_reg["gameday"] = pd.to_datetime(sched_reg["gameday"])
print(f"nflverse REG: {len(sched_reg)} rows")

# ─── JOIN ────────────────────────────────────────────────────────────
print("\nJoining ASB to nflverse...")
# Join by (season, home_team, away_team, date ±1 day)
asb_reg["date_only"] = asb_reg["Date"].dt.normalize()

matched = []
unmatched_asb = []

for _, row in asb_reg.iterrows():
    season = row["season"]
    home = row["home_team"]
    away = row["away_team"]
    date = row["date_only"]

    # Find matching nflverse game (±1 day for timezone differences)
    candidates = sched_reg[
        (sched_reg["season"] == season) &
        (sched_reg["home_team"] == home) &
        (sched_reg["away_team"] == away) &
        (abs((sched_reg["gameday"] - date).dt.days) <= 1)
    ]

    if len(candidates) == 1:
        nfl_row = candidates.iloc[0]
        matched.append({
            "game_id": nfl_row["game_id"],
            "season": season,
            "week": nfl_row["week"],
            "home_team": home,
            "away_team": away,
            "date_asb": date,
            "date_nfl": nfl_row["gameday"],
            "neutral_venue": row["Neutral Venue?"] == "Y",
            # ASB bet365 open/close (home perspective)
            "bet365_spread_open": row["Home Line Open"],
            "bet365_spread_close": row["Home Line Close"],
            "bet365_total_open": row["Total Score Open"],
            "bet365_total_close": row["Total Score Close"],
            # ASB prices (decimal)
            "bet365_home_line_odds_open": row["Home Line Odds Open"],
            "bet365_home_line_odds_close": row["Home Line Odds Close"],
            "bet365_total_over_open": row["Total Score Over Open"],
            "bet365_total_over_close": row["Total Score Over Close"],
            # nflverse close
            "nfl_spread_line": nfl_row["spread_line"],
            "nfl_total_line": nfl_row["total_line"],
        })
    elif len(candidates) == 0:
        unmatched_asb.append({
            "season": season, "home": home, "away": away,
            "date": date, "reason": "no nflverse match"
        })
    else:
        # Multiple matches — take closest date
        candidates = candidates.copy()
        candidates["date_diff"] = abs((candidates["gameday"] - date).dt.days)
        best = candidates.sort_values("date_diff").iloc[0]
        matched.append({
            "game_id": best["game_id"],
            "season": season,
            "week": best["week"],
            "home_team": home,
            "away_team": away,
            "date_asb": date,
            "date_nfl": best["gameday"],
            "neutral_venue": row["Neutral Venue?"] == "Y",
            "bet365_spread_open": row["Home Line Open"],
            "bet365_spread_close": row["Home Line Close"],
            "bet365_total_open": row["Total Score Open"],
            "bet365_total_close": row["Total Score Close"],
            "bet365_home_line_odds_open": row["Home Line Odds Open"],
            "bet365_home_line_odds_close": row["Home Line Odds Close"],
            "bet365_total_over_open": row["Total Score Over Open"],
            "bet365_total_over_close": row["Total Score Over Close"],
            "nfl_spread_line": best["spread_line"],
            "nfl_total_line": best["total_line"],
        })

matched_df = pd.DataFrame(matched)
print(f"Matched: {len(matched_df)} / {len(asb_reg)}")
if unmatched_asb:
    print(f"Unmatched: {len(unmatched_asb)}")
    for u in unmatched_asb:
        print(f"  {u}")

# ─── RECONCILIATION ─────────────────────────────────────────────────
print("\n=== RECONCILIATION ===")

# ASB Home Line Close should equal -nfl_spread_line
# (ASB: negative = home favoured; nflverse: spread_line is home team's spread,
#  but nflverse convention: spread_line is the line from the AWAY team's perspective
#  i.e. spread_line = away_spread, so home_spread = -spread_line)
# Actually nflverse: spread_line is the line, negative = home favored (same as ASB??)
# Let me check: nflverse spread_line for a game where home is favored should be negative.
# The work order says: "Home Line Close == -spread_line"

matched_df["spread_diff"] = matched_df["bet365_spread_close"] - (-matched_df["nfl_spread_line"])
matched_df["total_diff"] = matched_df["bet365_total_close"] - matched_df["nfl_total_line"]

# Spread reconciliation
spread_within_05 = (matched_df["spread_diff"].abs() <= 0.5).sum()
spread_pct = spread_within_05 / len(matched_df) * 100
print(f"\nSpread close: bet365 vs -nflverse_spread_line")
print(f"  Within 0.5 points: {spread_within_05}/{len(matched_df)} ({spread_pct:.1f}%)")

if spread_pct < 95:
    print("  HALT threshold not met. Analyzing mismatches...")
    mismatches = matched_df[matched_df["spread_diff"].abs() > 0.5]
    print(f"  Mismatches: {len(mismatches)}")
    print(mismatches[["game_id", "bet365_spread_close", "nfl_spread_line",
                       "spread_diff"]].head(20).to_string())

    # Try the other convention: Home Line Close == spread_line
    matched_df["spread_diff_alt"] = matched_df["bet365_spread_close"] - matched_df["nfl_spread_line"]
    spread_within_05_alt = (matched_df["spread_diff_alt"].abs() <= 0.5).sum()
    spread_pct_alt = spread_within_05_alt / len(matched_df) * 100
    print(f"\n  Alt convention (bet365 == nfl_spread_line):")
    print(f"  Within 0.5: {spread_within_05_alt}/{len(matched_df)} ({spread_pct_alt:.1f}%)")
else:
    print("  PASS: >= 95% within 0.5 points")

# Total reconciliation
total_within_05 = (matched_df["total_diff"].abs() <= 0.5).sum()
total_pct = total_within_05 / len(matched_df) * 100
print(f"\nTotal close: bet365 vs nflverse_total_line")
print(f"  Within 0.5 points: {total_within_05}/{len(matched_df)} ({total_pct:.1f}%)")

if total_pct < 95:
    print("  Analyzing total mismatches...")
    t_mm = matched_df[matched_df["total_diff"].abs() > 0.5]
    print(f"  Total mismatches: {len(t_mm)}")
    print(t_mm[["game_id", "bet365_total_close", "nfl_total_line",
                 "total_diff"]].head(20).to_string())
else:
    print("  PASS: >= 95% within 0.5 points")

# ─── SAVE ────────────────────────────────────────────────────────────
out_path = os.path.join(OUT_DIR, "spread_opens_2021_23.parquet")
matched_df.to_parquet(out_path, index=False)
print(f"\nSaved to {out_path}")
print(f"Rows: {len(matched_df)}, Cols: {len(matched_df.columns)}")

# Coverage report
print("\n=== COVERAGE REPORT ===")
print(f"Source: Australian Sports Betting (aussportsbetting.com)")
print(f"Book: bet365 (Sep 2018 - Feb 2025)")
print(f"Open definition: bet365 opening line")
print(f"Seasons: 2021, 2022, 2023")
print(f"Total rows (incl playoffs): 854")
print(f"REG rows: 815")
print(f"Matched to nflverse: {len(matched_df)}")
print(f"Unmatched: {len(unmatched_asb)}")
print(f"Neutral venue games: {matched_df['neutral_venue'].sum()}")
print(f"Spread opens available: YES (bet365)")
print(f"Total opens available: YES (bet365)")
print(f"Per season:")
for s in [2021, 2022, 2023]:
    sub = matched_df[matched_df["season"] == s]
    print(f"  {s}: {len(sub)} games, spread open non-null: {sub['bet365_spread_open'].notna().sum()}, "
          f"total open non-null: {sub['bet365_total_open'].notna().sum()}")
