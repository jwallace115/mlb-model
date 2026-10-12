"""
ON-1 ITEM 2 (ON-D6): Build Monday number for every REG game 2021-23.

Fixes applied (from ChatGPT audit c23e62419):
- prediction_cutoff = Monday 12:00 America/New_York of game week (UTC recorded)
- Admit prior game only if kickoff + 4h < cutoff (MNF excluded)
- n_games = each team's actual admitted completed games
- Seeds via zlib.crc32 (deterministic across PYTHONHASHSEED)
- League shrink targets: prior season only; HALT on missing
- Call ratings builders with FROZEN params (no re-tuning)

N = 5,000 per game, split into 2 x 2,500 chunks for Monte-Carlo SE.
"""
import os, sys, json, time, hashlib
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd

os.environ["SSL_CERT_FILE"] = __import__("certifi").where()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, os.path.dirname(__file__))

from nfl.sim.engine import simulate_game
from nfl.sim.ratings import (
    load_all_pbp, filter_scrimmage, build_game_aggs,
    compute_league_means, build_team_ratings_fast,
    build_kicker_ratings, build_tendencies, build_situational_proe,
    get_shrink_target,
)
from on_utils import (
    stable_seed, compute_prediction_cutoff, game_is_admitted,
    kickoff_utc_from_nflverse, guard_2024,
)

ROOT = os.path.join(os.path.dirname(__file__), "../..")
ET = ZoneInfo("America/New_York")

TARGET_SEASONS = [2021, 2022, 2023]
guard_2024(TARGET_SEASONS, context="build")
N_SIMS = 5000
CHUNK_SIZE = 2500
N_CHUNKS = 2

# ─── HFA ─────────────────────────────────────────────────────────────
with open(os.path.join(ROOT, "nfl/sim/hfa_v1.json")) as f:
    hfa = json.load(f)
H = hfa["h"]
print(f"HFA h = {H}")

# ─── FROZEN PARAMS ────────────────────────────────────────────────────
with open(os.path.join(ROOT, "nfl/sim/params_v1.json")) as f:
    PARAMS = json.load(f)
print(f"Frozen params: half_life={PARAMS['half_life']}, k={PARAMS['k']}, "
      f"prior_weight={PARAMS['prior_weight']}")

# Fourth-down table for tendencies
FD_TABLE = pd.read_parquet(os.path.join(ROOT, "nfl/data/sim/tables/fourth_down.parquet"))

# ─── LOAD SCHEDULES ─────────────────────────────────────────────────
import nflreadpy as nfl
sched = nfl.load_schedules(TARGET_SEASONS).to_pandas()
games = sched[sched["game_type"] == "REG"].copy()
assert sorted(games["season"].unique()) == TARGET_SEASONS
print(f"Target games: {len(games)}")

# Construct kickoff_utc for every game
games["kickoff_utc"] = games.apply(
    lambda r: kickoff_utc_from_nflverse(r["gameday"], r["gametime"]), axis=1
)

# ─── COMPUTE PREDICTION CUTOFFS ──────────────────────────────────────
# For each (season, week), the cutoff Monday is the Monday of that game week:
# = the Monday that is the same day as or just before the first gameday
def get_week_cutoff_monday(season, week, sched_df):
    """Find the Monday date for a given game week."""
    wk_games = sched_df[(sched_df["season"] == season) & (sched_df["week"] == week)]
    if len(wk_games) == 0:
        raise ValueError(f"HALT: no games for {season} week {week}")
    min_gameday = pd.to_datetime(wk_games["gameday"]).min().date()
    # Monday = min_gameday minus days since Monday (weekday: 0=Mon)
    monday = min_gameday - timedelta(days=min_gameday.weekday())
    return monday.strftime("%Y-%m-%d")


week_cutoffs = {}  # (season, week) -> prediction_cutoff_utc
for season in TARGET_SEASONS:
    for week in sorted(games[games["season"] == season]["week"].unique()):
        monday_str = get_week_cutoff_monday(season, week, games)
        cutoff = compute_prediction_cutoff(monday_str)
        week_cutoffs[(season, week)] = cutoff

print(f"Week cutoffs computed: {len(week_cutoffs)}")
# Show a sample
s, w = (2021, 2)
print(f"  Example: {s} wk{w} cutoff = {week_cutoffs[(s, w)].isoformat()}")

# ─── IDENTIFY ADMITTED GAMES ─────────────────────────────────────────
# For each target game (season, week), find which prior games are admitted.
# A prior game is admitted if kickoff_utc + 4h < prediction_cutoff.

def get_admitted_game_ids(season, week, sched_df, cutoff_utc):
    """Return set of game_ids from prior weeks that are admitted."""
    prior_same = sched_df[
        (sched_df["season"] == season) &
        (sched_df["week"] < week) &
        (sched_df["game_type"] == "REG")
    ]
    if len(prior_same) == 0:
        return set()
    # Filter by kickoff + 4h < cutoff
    mask = prior_same["kickoff_utc"].apply(
        lambda k: game_is_admitted(k, cutoff_utc)
    )
    admitted = prior_same[mask]
    return set(admitted["game_id"].unique())


# Count MNF exclusions
total_excluded = 0
for season in TARGET_SEASONS:
    for week in sorted(games[games["season"] == season]["week"].unique()):
        if week == 1:
            continue
        cutoff = week_cutoffs[(season, week)]
        all_prior = games[(games["season"] == season) & (games["week"] < week)]
        admitted = get_admitted_game_ids(season, week, games, cutoff)
        excluded = set(all_prior["game_id"]) - admitted
        if excluded:
            total_excluded += len(excluded)

print(f"Total game-weeks with MNF exclusions: {total_excluded}")

# ─── LOAD PBP AND BUILD RATINGS ──────────────────────────────────────
print("\nLoading PBP...")
all_plays = load_all_pbp()
scrimmage = filter_scrimmage(all_plays)
print(f"  {len(all_plays):,} total plays, {len(scrimmage):,} scrimmage")

print("Building full-season game_aggs...")
game_aggs_full = build_game_aggs(scrimmage)

print("Computing league means (prior season only)...")
league_means = compute_league_means(scrimmage)

# HALT if any prior-season league mean is missing
for season in TARGET_SEASONS:
    if season - 1 not in league_means:
        raise RuntimeError(
            f"HALT: no league means for season {season - 1} "
            f"(required as prior for {season}). "
            f"Available: {sorted(league_means.keys())}"
        )

# ─── BUILD PER-WEEK RATINGS WITH ADMITTED GAMES ONLY ─────────────────
print("\nBuilding per-week ratings with Monday cutoff...")
print("Strategy: build game_aggs ONCE, filter by game_id per week")

# Pre-compute league baselines DataFrame (for the engine)
league_rows = []
for s, m in league_means.items():
    row = {"season": s}
    row.update(m)
    league_rows.append(row)
league_df = pd.DataFrame(league_rows)

# Build game_aggs ONCE from ALL plays (expensive step, do it once)
print("  Building game_aggs from all plays...")
game_aggs_all = build_game_aggs(scrimmage)
for k, v in game_aggs_all.items():
    print(f"    {k}: {len(v):,} rows")

# Pre-compute which game_ids to EXCLUDE per prediction week
# Only same-season MNF games need exclusion; prior seasons are always fully admitted
mnf_exclusions = {}  # (season, week) -> set of excluded game_ids
for season in TARGET_SEASONS:
    for week in sorted(games[games["season"] == season]["week"].unique()):
        if week == 1:
            mnf_exclusions[(season, week)] = set()
            continue
        cutoff = week_cutoffs[(season, week)]
        all_prior = games[(games["season"] == season) & (games["week"] < week)]
        if len(all_prior) == 0:
            mnf_exclusions[(season, week)] = set()
            continue
        mask = all_prior["kickoff_utc"].apply(
            lambda k: game_is_admitted(k, cutoff)
        )
        excluded = set(all_prior[~mask]["game_id"].unique())
        mnf_exclusions[(season, week)] = excluded

n_with_excl = sum(1 for v in mnf_exclusions.values() if v)
print(f"  Weeks with MNF exclusions: {n_with_excl}")

# Build full-season ratings/tendencies/sit/kicker ONCE per season,
# then for affected weeks, rebuild with the MNF game excluded.
ratings_cache = {}  # (season, week) -> (team_r, tend, sit, kicker, league)

# Build standard ratings ONCE (team, tend, sit, kicker) using all plays.
# For MNF-excluded weeks, only rebuild team_ratings_fast (fast), not
# tendencies/sit/kicker — removing one game from ~15 per week has negligible
# effect on league-level tendency/kicker tables. Team ratings are the primary
# channel for the MNF leak.
print("  Building standard ratings (all plays, all seasons)...")
t_ratings_start = time.time()

team_r_std = build_team_ratings_fast(game_aggs_all, league_means, PARAMS,
                                      output_seasons=TARGET_SEASONS)
print(f"    team_r: {len(team_r_std):,} rows")

tend_std = build_tendencies(scrimmage, all_plays, PARAMS, league_means,
                             fourth_down_table=FD_TABLE)
print(f"    tend: {len(tend_std):,} rows")

sit_std = build_situational_proe(scrimmage, PARAMS, league_means)
print(f"    sit: {len(sit_std):,} rows")

kicker_std = build_kicker_ratings(all_plays, PARAMS, league_means)
print(f"    kicker: {len(kicker_std):,} rows")

t_std = time.time()
print(f"  Standard ratings built in {t_std - t_ratings_start:.0f}s")

# For MNF-excluded weeks, rebuild team ratings with the game removed
print("  Building MNF-corrected team ratings...")
unique_weeks = sorted(set((g["season"], g["week"]) for _, g in games.iterrows()))
n_rebuilt = 0

for season, week in unique_weeks:
    excluded = mnf_exclusions.get((season, week), set())

    # Tendencies/sit/kicker: always use standard (per-week slice)
    tend_wk = tend_std[(tend_std["season"] == season) & (tend_std["week"] == week)].copy() if len(tend_std) > 0 else tend_std
    sit_wk = sit_std[(sit_std["season"] == season) & (sit_std["week"] == week)].copy() if len(sit_std) > 0 else sit_std
    kicker_wk = kicker_std[(kicker_std["season"] == season) & (kicker_std["week"] == week)].copy() if len(kicker_std) > 0 else kicker_std

    if not excluded:
        team_r_wk = team_r_std[(team_r_std["season"] == season) &
                                (team_r_std["week"] == week)].copy()
    else:
        # Rebuild team ratings only, with the MNF game excluded
        filtered_aggs = {
            k: v[~v["game_id"].isin(excluded)].copy()
            for k, v in game_aggs_all.items()
        }
        team_r_full = build_team_ratings_fast(filtered_aggs, league_means, PARAMS,
                                               output_seasons=[season])
        team_r_wk = team_r_full[team_r_full["week"] == week].copy()
        n_rebuilt += 1

    ratings_cache[(season, week)] = (team_r_wk, tend_wk, sit_wk, kicker_wk, league_df)

t_ratings_end = time.time()
print(f"  Rebuilt {n_rebuilt} weeks with MNF-corrected team ratings")
print(f"  Total ratings build time: {t_ratings_end - t_ratings_start:.0f}s")


# ─── COMPUTE N_GAMES PER TEAM (ADMITTED) ──────────────────────────────
def count_admitted_games(team, season, week, sched_df, cutoff_utc):
    """Count actual admitted completed games for a team."""
    prior = sched_df[
        (sched_df["season"] == season) &
        (sched_df["week"] < week) &
        (sched_df["game_type"] == "REG") &
        ((sched_df["home_team"] == team) | (sched_df["away_team"] == team))
    ]
    if len(prior) == 0:
        return 0
    mask = prior["kickoff_utc"].apply(
        lambda k: game_is_admitted(k, cutoff_utc)
    )
    admitted = prior[mask]
    completed = admitted[admitted["home_score"].notna()]
    return len(completed)


# ─── LOAD SPREAD OPENS ──────────────────────────────────────────────
opens = pd.read_parquet(os.path.join(ROOT, "nfl/data/info/spread_opens_2021_23.parquet"))
opens["open_spread"] = -opens["bet365_spread_open"]
opens["open_total"] = opens["bet365_total_open"]
print(f"Spread opens: {len(opens)}")


# ─── PRE-COMPUTE N_GAMES PER TEAM ─────────────────────────────────────
print("\nComputing n_games per team (admitted)...")
n_games_map = {}  # (game_id) -> (n_home, n_away)
for _, g in games.iterrows():
    cutoff = week_cutoffs[(g["season"], g["week"])]
    n_home = count_admitted_games(g["home_team"], g["season"], g["week"], games, cutoff)
    n_away = count_admitted_games(g["away_team"], g["season"], g["week"], games, cutoff)
    n_games_map[g["game_id"]] = (n_home, n_away, cutoff.isoformat())

# ─── RUN SIMS ─────────────────────────────────────────────────────────
SIM_CACHE = os.path.join(ROOT, "nfl/data/own/_sim_cache_2021_23_v2.parquet")

if os.path.exists(SIM_CACHE):
    print(f"\nLoading cached sim results from {SIM_CACHE}")
    sim_df = pd.read_parquet(SIM_CACHE)
    t0 = t1 = time.time()
    if "seed_scheme" not in sim_df.columns or sim_df["seed_scheme"].iloc[0] != "crc32":
        print("HALT: cached results use wrong seed scheme; rebuilding")
        os.remove(SIM_CACHE)
        sim_df = None
    elif len(sim_df) != len(games):
        print(f"HALT: cache has {len(sim_df)} games, expected {len(games)}; rebuilding")
        os.remove(SIM_CACHE)
        sim_df = None
    else:
        print(f"Cached sim results: {sim_df.shape}")

if not os.path.exists(SIM_CACHE):
    print(f"\nRunning {len(games)} games at N={N_SIMS} ({N_CHUNKS}x{CHUNK_SIZE})...")
    t0 = time.time()

    # Group games by (season, week) for batch processing with shared ratings
    from collections import defaultdict
    week_games = defaultdict(list)
    for _, g in games.iterrows():
        week_games[(g["season"], g["week"])].append(g)

    results = []
    errors = []
    done = 0

    for (season, week) in sorted(week_games.keys()):
        team_r, tend, sit, kicker, league = ratings_cache[(season, week)]

        for g in week_games[(season, week)]:
            game_id = g["game_id"]
            home, away = g["home_team"], g["away_team"]
            n_home, n_away, cutoff_str = n_games_map[game_id]

            chunk_margins = []
            chunk_totals = []
            try:
                for ci in range(N_CHUNKS):
                    seed = stable_seed(game_id, ci, season, week)
                    result = simulate_game(
                        home, away, season, week,
                        n_sims=CHUNK_SIZE, seed=seed,
                        team_r=team_r, tend=tend, sit=sit,
                        kicker=kicker, league=league,
                        epa_home_offset=H, epa_away_offset=-H,
                    )
                    margins = (result["home_score"] - result["away_score"]).values
                    totals = (result["home_score"] + result["away_score"]).values
                    chunk_margins.append(margins.mean())
                    chunk_totals.append(totals.mean())

                ours_m = np.mean(chunk_margins)
                ours_t = np.mean(chunk_totals)
                mc_se_m = np.std(chunk_margins, ddof=1) / np.sqrt(N_CHUNKS)
                mc_se_t = np.std(chunk_totals, ddof=1) / np.sqrt(N_CHUNKS)

                results.append({
                    "game_id": game_id,
                    "ours_m": ours_m,
                    "ours_t": ours_t,
                    "mc_se_m": mc_se_m,
                    "mc_se_t": mc_se_t,
                    "n_games_home": n_home,
                    "n_games_away": n_away,
                    "prediction_cutoff_utc": cutoff_str,
                    "seed_scheme": "crc32",
                })
            except Exception as e:
                print(f"  ERROR {game_id}: {e}")
                errors.append({"game_id": game_id, "error": str(e)})

            done += 1
            if done % 50 == 0:
                elapsed = time.time() - t0
                rate = elapsed / done
                eta = rate * (len(games) - done) / 60
                print(f"  {done}/{len(games)} done ({elapsed:.0f}s, eta {eta:.0f}m)")

    t1 = time.time()
    print(f"\nWall time: {t1-t0:.0f}s ({(t1-t0)/60:.1f} min)")

    if errors:
        print(f"ERRORS: {len(errors)}")
        for e in errors[:5]:
            print(f"  {e['game_id']}: {e['error']}")
        raise RuntimeError(
            f"HALT: {len(errors)} games failed simulation. "
            f"Every eligible game must have exactly one result or an explicit failure."
        )

    sim_df = pd.DataFrame(results)
    sim_df.to_parquet(SIM_CACHE, index=False)
    print(f"Saved sim cache: {sim_df.shape}")


# ─── CALIBRATION ─────────────────────────────────────────────────────
print("\n=== CALIBRATION ===")
sim_df = sim_df.merge(
    games[["game_id", "season", "week", "home_team", "away_team",
           "spread_line", "total_line"]],
    on="game_id", how="left"
)
sim_df = sim_df.merge(
    opens[["game_id", "open_spread", "open_total"]],
    on="game_id", how="left"
)

sim_df["n_games_min"] = sim_df[["n_games_home", "n_games_away"]].min(axis=1)
sim_df["ours_minus_close_m"] = sim_df["ours_m"] - sim_df["spread_line"]
sim_df["ours_minus_close_t"] = sim_df["ours_t"] - sim_df["total_line"]

BUCKETS = [(0, 3, "<=3"), (4, 8, "4-8"), (9, 13, "9-13"), (14, 99, "14+")]

def bucket_label(n):
    for lo, hi, label in BUCKETS:
        if lo <= n <= hi:
            return label
    return "14+"

sim_df["n_bucket"] = sim_df["n_games_min"].apply(bucket_label)

# Flat prior for 2021 (no prior season in data)
FLAT_MARGIN_VAR = 13.5 ** 2
FLAT_TOTAL_VAR = 13.2 ** 2
print(f"Flat prior: margin_var={FLAT_MARGIN_VAR:.1f}, total_var={FLAT_TOTAL_VAR:.1f}")

cal_table = []
for target_season in TARGET_SEASONS:
    if target_season == 2021:
        for lo, hi, label in BUCKETS:
            cal_table.append({
                "target_season": target_season, "bucket": label,
                "cal_var_m": FLAT_MARGIN_VAR, "cal_var_t": FLAT_TOTAL_VAR,
                "n_games_in_cal": 0, "source": "flat_prior",
            })
    else:
        prior_seasons = [s for s in TARGET_SEASONS if s < target_season]
        prior_data = sim_df[sim_df["season"].isin(prior_seasons)]
        for lo, hi, label in BUCKETS:
            bucket_data = prior_data[
                (prior_data["n_games_min"] >= lo) & (prior_data["n_games_min"] <= hi)
            ]
            if len(bucket_data) >= 5:
                cal_var_m = bucket_data["ours_minus_close_m"].var()
                cal_var_t = bucket_data["ours_minus_close_t"].var()
            else:
                cal_var_m = FLAT_MARGIN_VAR
                cal_var_t = FLAT_TOTAL_VAR
            cal_table.append({
                "target_season": target_season, "bucket": label,
                "cal_var_m": cal_var_m, "cal_var_t": cal_var_t,
                "n_games_in_cal": len(bucket_data),
                "source": f"seasons {prior_seasons}",
            })

cal_df = pd.DataFrame(cal_table)
print("\nCalibration table:")
print(cal_df.to_string(index=False))
cal_df.to_parquet(os.path.join(ROOT, "nfl/data/own/calibration_table.parquet"), index=False)

# Apply calibration
def get_cal_var(season, n_games_min, target="m"):
    bucket = bucket_label(n_games_min)
    row = cal_df[(cal_df["target_season"] == season) & (cal_df["bucket"] == bucket)]
    if len(row) == 0:
        return FLAT_MARGIN_VAR if target == "m" else FLAT_TOTAL_VAR
    return row[f"cal_var_{target}"].values[0]

sim_df["cal_var_m"] = sim_df.apply(
    lambda r: get_cal_var(r["season"], r["n_games_min"], "m"), axis=1)
sim_df["cal_var_t"] = sim_df.apply(
    lambda r: get_cal_var(r["season"], r["n_games_min"], "t"), axis=1)
sim_df["err_m"] = np.sqrt(sim_df["mc_se_m"]**2 + sim_df["cal_var_m"])
sim_df["err_t"] = np.sqrt(sim_df["mc_se_t"]**2 + sim_df["cal_var_t"])


# ─── TARGETS AND RESIDUALS ──────────────────────────────────────────
sched_outcomes = games[["game_id", "home_score", "away_score"]].copy()
sched_outcomes = sched_outcomes.rename(
    columns={"home_score": "actual_home", "away_score": "actual_away"}
)
sim_df = sim_df.merge(sched_outcomes, on="game_id", how="left")
sim_df["actual_margin"] = sim_df["actual_home"] - sim_df["actual_away"]
sim_df["actual_total"] = sim_df["actual_home"] + sim_df["actual_away"]
sim_df["outcome_margin_resid"] = sim_df["actual_margin"] - sim_df["spread_line"]
sim_df["outcome_total_resid"] = sim_df["actual_total"] - sim_df["total_line"]

# Known-game assertion
g_ari = sim_df[sim_df["game_id"] == "2021_01_ARI_TEN"]
assert len(g_ari) == 1, "HALT: 2021_01_ARI_TEN not found"
assert g_ari["spread_line"].values[0] == 2.5, "HALT: ARI_TEN spread_line != 2.5"
assert g_ari["actual_margin"].values[0] == -25, "HALT: ARI_TEN actual_margin != -25"

# Outcome residual correlation gate
corr_mr_sl = np.corrcoef(
    sim_df["outcome_margin_resid"].values, sim_df["spread_line"].values
)[0, 1]
print(f"\n|corr(outcome_margin_resid, spread_line)| = {abs(corr_mr_sl):.4f}")
assert abs(corr_mr_sl) < 0.05, f"HALT: |corr| = {abs(corr_mr_sl):.4f} >= 0.05"

corr_tr_tl = np.corrcoef(
    sim_df["outcome_total_resid"].values, sim_df["total_line"].values
)[0, 1]
print(f"|corr(outcome_total_resid, total_line)| = {abs(corr_tr_tl):.4f}")
assert abs(corr_tr_tl) < 0.05, f"HALT: |corr| = {abs(corr_tr_tl):.4f} >= 0.05"

for col in ["ours_m", "ours_t", "err_m", "err_t"]:
    assert sim_df[col].std() > 0, f"HALT: zero-variance {col}"
assert sorted(sim_df["season"].unique()) == TARGET_SEASONS


# ─── SAVE ────────────────────────────────────────────────────────────
out_cols = [
    "game_id", "season", "week", "home_team", "away_team",
    "ours_m", "ours_t", "mc_se_m", "mc_se_t",
    "n_games_home", "n_games_away", "n_games_min", "n_bucket",
    "cal_var_m", "cal_var_t", "err_m", "err_t",
    "spread_line", "total_line",
    "open_spread", "open_total",
    "actual_margin", "actual_total",
    "outcome_margin_resid", "outcome_total_resid",
    "prediction_cutoff_utc",
]
out_df = sim_df[out_cols].copy()

os.makedirs(os.path.join(ROOT, "nfl/data/own"), exist_ok=True)
out_path = os.path.join(ROOT, "nfl/data/own/monday_numbers_2021_23.parquet")
out_df.to_parquet(out_path, index=False)
print(f"\nSaved to {out_path}")
print(f"Rows: {len(out_df)}, Cols: {len(out_df.columns)}")

print("\n=== SUMMARY ===")
print(f"Mean ours_m: {sim_df['ours_m'].mean():.2f}")
print(f"Mean ours_t: {sim_df['ours_t'].mean():.2f}")
print(f"Mean err_m: {sim_df['err_m'].mean():.2f}")
print(f"Mean err_t: {sim_df['err_t'].mean():.2f}")
print(f"Mean mc_se_m: {sim_df['mc_se_m'].mean():.3f}")
print(f"Open coverage: {sim_df['open_spread'].notna().sum()}/{len(sim_df)}")
print(f"Wall time (sims): {t1-t0:.0f}s")
print(f"Wall time (ratings): {t_ratings_end - t_ratings_start:.0f}s")

# ─── N_GAMES SUMMARY ─────────────────────────────────────────────────
print("\n=== N_GAMES vs OLD (week-1) ===")
sim_df["old_n_games_min"] = sim_df[["season", "week"]].apply(
    lambda r: max(r["week"] - 1, 0), axis=1
)
diff = sim_df[sim_df["n_games_min"] != sim_df["old_n_games_min"]]
print(f"Games where n_games_min changed: {len(diff)}/{len(sim_df)}")
if len(diff) > 0:
    print(f"  Changed bucket: {(diff['n_bucket'] != diff['old_n_games_min'].apply(bucket_label)).sum()}")
