#!/usr/bin/env python3
"""
NFL Sim Phase 1B Step 4 — Attribute reliability audit (D11).

Split-half reliability on RAW per-player-per-game values, 2021-2024.
Decides which per-player attributes enter the sim.
Does NOT touch ratings.py, usage.py, params_v1.json, or any parquet under
nfl/data/sim/ratings/.

Imports build_player_game_aggs from usage.py for the per-game aggregation
(same PBP load + filter + groupby logic).
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr

ROOT = Path(__file__).resolve().parent.parent.parent
PBP_DIR = ROOT / "nfl" / "data" / "pbp"
RATINGS_DIR = ROOT / "nfl" / "data" / "sim" / "ratings"
OUT_PATH = ROOT / "research" / "nfl_sim" / "phase1_attribute_reliability.md"

SEASONS = [2021, 2022, 2023, 2024]
MIN_GAMES = 8  # per player-season for split-half
SPLIT_HALF_THRESHOLD = 0.50  # r8 >= this => PASS

# ---------------------------------------------------------------------------
# STEP 0: Load PBP exactly as usage.py does
# ---------------------------------------------------------------------------
# Import the aggregation function from usage.py
sys.path.insert(0, str(ROOT / "nfl" / "sim"))
from usage import load_pbp as _usage_load_pbp, build_player_game_aggs, PBP_COLS


def load_pbp_audit():
    """Load PBP for 2021-2024 only, regular season (week <= 18)."""
    frames = []
    for s in SEASONS:
        p = PBP_DIR / f"pbp_{s}.parquet"
        if not p.exists():
            raise FileNotFoundError(f"Missing {p}")
        import pyarrow.parquet as pq
        schema_cols = pq.read_schema(p).names
        # Need defteam for defense-split analysis
        needed = PBP_COLS + ["defteam"]
        cols = [c for c in needed if c in schema_cols]
        df = pd.read_parquet(p, columns=cols)
        frames.append(df)
    pbp = pd.concat(frames, ignore_index=True)
    # Guard: no 2025+ data
    if (pbp["season"] >= 2025).any():
        raise ValueError("Data from season >= 2025 found — aborting")
    # Regular season only
    pbp = pbp[pbp["week"] <= 18].copy()
    return pbp


# ---------------------------------------------------------------------------
# STEP 1: Build per-player-per-game attribute values
# ---------------------------------------------------------------------------

def build_per_game_attributes(pbp):
    """
    Build per-(season, week, game_id, team, player_id) attribute values.
    Uses build_player_game_aggs from usage.py for the raw aggregation,
    then computes per-game ratios.
    """
    rec, team_tgt, car, team_car = build_player_game_aggs(pbp)

    # --- Receiver attributes ---
    rec = rec.merge(team_tgt, on=["season", "week", "game_id", "team"], how="left")
    rec["target_share"] = rec["n_targets"] / rec["team_targets"]
    rec["rz_target_share"] = rec["rz_targets"] / rec["team_rz_targets"].replace(0, np.nan)
    rec["adot"] = rec["air_yards_sum"] / rec["n_targets"]
    rec["catch_rate"] = rec["n_receptions"] / rec["n_targets"]
    rec["yac_per_rec"] = rec["yac_sum"] / rec["n_receptions"].replace(0, np.nan)
    rec["yards_per_target"] = rec["rec_yards"] / rec["n_targets"]
    rec["explosive_rec_rate"] = rec["exp_recs"] / rec["n_targets"]

    # --- Rusher attributes ---
    car = car.merge(team_car, on=["season", "week", "game_id", "team"], how="left")
    car["carry_share"] = car["n_carries"] / car["team_carries"]
    car["gl_carry_share"] = car["gl_carries"] / car["team_gl_carries"].replace(0, np.nan)
    car["yards_per_carry"] = car["rush_yards"] / car["n_carries"]
    car["explosive_rush_rate"] = car["exp_rushes"] / car["n_carries"]

    return rec, car


# ---------------------------------------------------------------------------
# STEP 2: Add defteam to rec/car for defense-split analysis
# ---------------------------------------------------------------------------

def add_defteam(pbp, rec, car):
    """Add defteam to each player-game row."""
    game_def = pbp[["season", "week", "game_id", "posteam", "defteam"]].drop_duplicates()
    game_def = game_def.rename(columns={"posteam": "team"})
    game_def = game_def.dropna(subset=["team", "defteam"]).drop_duplicates(
        ["season", "week", "game_id", "team"])

    rec = rec.merge(game_def, on=["season", "week", "game_id", "team"], how="left")
    car = car.merge(game_def, on=["season", "week", "game_id", "team"], how="left")
    return rec, car


# ---------------------------------------------------------------------------
# STEP 3: Split-half reliability
# ---------------------------------------------------------------------------

REC_ATTRS = {
    # attr_name: (numerator_col, denominator_col, is_share)
    # Shares: sum(player) / sum(team) for pooled ratio
    "target_share": ("n_targets", "team_targets", True),
    "rz_target_share": ("rz_targets", "team_rz_targets", True),
    "adot": ("air_yards_sum", "n_targets", False),
    "catch_rate": ("n_receptions", "n_targets", False),
    "yac_per_rec": ("yac_sum", "n_receptions", False),
    "yards_per_target": ("rec_yards", "n_targets", False),
    "explosive_rec_rate": ("exp_recs", "n_targets", False),
}

RUSH_ATTRS = {
    "carry_share": ("n_carries", "team_carries", True),
    "gl_carry_share": ("gl_carries", "team_gl_carries", True),
    "yards_per_carry": ("rush_yards", "n_carries", False),
    "explosive_rush_rate": ("exp_rushes", "n_carries", False),
}


def split_half_reliability(df, attr_spec, min_games=MIN_GAMES):
    """
    Compute split-half reliability for each attribute.

    For each player-season with >= min_games qualifying games:
    - Order games by week
    - Odd-indexed (1st, 3rd, ...) = half A; even-indexed = half B
    - Pooled ratio for each half = sum(numerator) / sum(denominator)
    - Pearson r across player-seasons, pooled over all seasons
    - Spearman-Brown to 8-game length: r8 = 2r / (1 + r)

    Returns dict of {attr: (r, r8, n_player_seasons, pass_fail)}
    """
    results = {}
    for attr_name, (num_col, denom_col, is_share) in attr_spec.items():
        # Only keep rows where denominator > 0
        valid = df[df[denom_col] > 0].copy()
        valid = valid.sort_values(["season", "player_id", "week"])

        # Assign within-player-season game index
        valid["game_idx"] = valid.groupby(["season", "player_id"]).cumcount()
        valid["half"] = (valid["game_idx"] % 2).map({0: "A", 1: "B"})

        # Count qualifying games per player-season
        gs = valid.groupby(["season", "player_id"]).size().reset_index(name="n_games")
        qual = gs[gs["n_games"] >= min_games][["season", "player_id"]]
        valid = valid.merge(qual, on=["season", "player_id"])

        if len(valid) == 0:
            results[attr_name] = (np.nan, np.nan, 0, "FAIL")
            continue

        # Compute pooled ratio per half per player-season
        halves = valid.groupby(["season", "player_id", "half"]).agg(
            num_sum=(num_col, "sum"),
            denom_sum=(denom_col, "sum"),
        ).reset_index()
        halves["ratio"] = halves["num_sum"] / halves["denom_sum"].replace(0, np.nan)
        halves = halves.dropna(subset=["ratio"])

        # Pivot to get half A and half B side by side
        pivot = halves.pivot_table(
            index=["season", "player_id"], columns="half", values="ratio"
        ).dropna()

        if len(pivot) < 3:
            results[attr_name] = (np.nan, np.nan, len(pivot), "FAIL")
            continue

        r, _ = pearsonr(pivot["A"], pivot["B"])
        r8 = 2 * r / (1 + r)  # Spearman-Brown
        n_ps = len(pivot)
        pf = "PASS" if r8 >= SPLIT_HALF_THRESHOLD else "FAIL"
        results[attr_name] = (r, r8, n_ps, pf)

    return results


# ---------------------------------------------------------------------------
# STEP 4: Year-over-year stability (informational)
# ---------------------------------------------------------------------------

def year_over_year(df, attr_spec):
    """
    For each attribute, compute full-season pooled ratio per player,
    then Pearson r between consecutive seasons for players qualifying in both.
    """
    results = {}
    for attr_name, (num_col, denom_col, is_share) in attr_spec.items():
        valid = df[df[denom_col] > 0].copy()

        # Full-season pooled ratio
        season_agg = valid.groupby(["season", "player_id"]).agg(
            num_sum=(num_col, "sum"),
            denom_sum=(denom_col, "sum"),
        ).reset_index()
        season_agg["ratio"] = season_agg["num_sum"] / season_agg["denom_sum"].replace(0, np.nan)
        season_agg = season_agg.dropna(subset=["ratio"])

        # Consecutive-season pairs
        pairs = []
        for s in sorted(season_agg["season"].unique()):
            s1 = season_agg[season_agg["season"] == s][["player_id", "ratio"]].rename(
                columns={"ratio": "r_s"})
            s2 = season_agg[season_agg["season"] == s + 1][["player_id", "ratio"]].rename(
                columns={"ratio": "r_s1"})
            merged = s1.merge(s2, on="player_id")
            pairs.append(merged)

        if not pairs:
            results[attr_name] = (np.nan, 0)
            continue

        all_pairs = pd.concat(pairs, ignore_index=True)
        if len(all_pairs) < 3:
            results[attr_name] = (np.nan, len(all_pairs))
            continue

        r, _ = pearsonr(all_pairs["r_s"], all_pairs["r_s1"])
        results[attr_name] = (r, len(all_pairs))

    return results


# ---------------------------------------------------------------------------
# STEP 5: Recent form analysis
# ---------------------------------------------------------------------------

def recent_form_analysis(rec, car):
    """
    For qualifying player-games from week 5 onward:
    - season-to-date share (weeks < w)
    - last-3-game share (weeks w-3..w-1)
    - Fit next-game share ~ season_to_date, and ~ season_to_date + (last3 - season_to_date)
    - Train on 2021-2023, score on 2024 by RMSE
    """
    results = {}

    for label, df, share_col, num_col, denom_col in [
        ("target_share (receivers)", rec, "target_share", "n_targets", "team_targets"),
        ("carry_share (rushers)", car, "carry_share", "n_carries", "team_carries"),
    ]:
        valid = df[df[denom_col] > 0].copy()
        valid = valid.sort_values(["season", "player_id", "week"])

        rows = []
        for (season, pid), grp in valid.groupby(["season", "player_id"]):
            grp = grp.sort_values("week")
            weeks = grp["week"].values
            nums = grp[num_col].values
            denoms = grp[denom_col].values

            for i in range(len(grp)):
                w = weeks[i]
                if w < 5:
                    continue

                # Season-to-date (all games before this one)
                mask_std = np.arange(len(grp)) < i
                if mask_std.sum() == 0:
                    continue
                std_num = nums[mask_std].sum()
                std_den = denoms[mask_std].sum()
                if std_den == 0:
                    continue
                std_share = std_num / std_den

                # Last 3 games before this one
                last3_idx = max(0, i - 3)
                mask_l3 = (np.arange(len(grp)) >= last3_idx) & (np.arange(len(grp)) < i)
                l3_num = nums[mask_l3].sum()
                l3_den = denoms[mask_l3].sum()
                l3_share = l3_num / l3_den if l3_den > 0 else std_share

                actual = nums[i] / denoms[i] if denoms[i] > 0 else np.nan

                rows.append({
                    "season": season,
                    "player_id": pid,
                    "week": w,
                    "std_share": std_share,
                    "l3_share": l3_share,
                    "actual": actual,
                })

        rf = pd.DataFrame(rows).dropna(subset=["actual"])

        # Train on 2021-2023, test on 2024
        train = rf[rf["season"].isin([2021, 2022, 2023])].copy()
        test = rf[rf["season"] == 2024].copy()

        if len(train) < 10 or len(test) < 10:
            results[label] = {"rmse_std": np.nan, "rmse_std_l3": np.nan,
                              "delta": np.nan, "sign": "N/A", "n_train": len(train),
                              "n_test": len(test)}
            continue

        # Model 1: actual ~ season_to_date (just use std as prediction)
        rmse_std = np.sqrt(((test["actual"] - test["std_share"]) ** 2).mean())

        # Model 2: actual ~ season_to_date + (last3 - season_to_date)
        # Fit: actual = a * std_share + b * (l3_share - std_share) + c
        from numpy.linalg import lstsq
        X_train = np.column_stack([
            train["std_share"].values,
            (train["l3_share"] - train["std_share"]).values,
            np.ones(len(train)),
        ])
        y_train = train["actual"].values
        coeffs, _, _, _ = lstsq(X_train, y_train, rcond=None)

        X_test = np.column_stack([
            test["std_share"].values,
            (test["l3_share"] - test["std_share"]).values,
            np.ones(len(test)),
        ])
        pred_l3 = X_test @ coeffs
        rmse_std_l3 = np.sqrt(((test["actual"] - pred_l3) ** 2).mean())

        delta = rmse_std - rmse_std_l3  # positive = l3 model is better
        sign = "+" if delta > 0 else "-"

        results[label] = {
            "rmse_std": rmse_std,
            "rmse_std_l3": rmse_std_l3,
            "delta": delta,
            "sign": sign,
            "n_train": len(train),
            "n_test": len(test),
        }

    return results


# ---------------------------------------------------------------------------
# STEP 6: Defense-type split reliability
# ---------------------------------------------------------------------------

def defense_split_reliability(rec, min_games_per_half=4):
    """
    For each player-game, label opposing pass defense as top-half or bottom-half
    by that week's pass_def EPA (lower = better).

    Per player-season with >= min_games_per_half against each half:
    compute yards_per_target vs top-half minus vs bottom-half.

    Split-half reliability of that DIFFERENCE (odd/even games within each half).
    """
    # Load team ratings
    ratings = pd.read_parquet(RATINGS_DIR / "team_ratings_weekly.parquet")
    ratings = ratings[
        (ratings["unit"] == "pass_def") &
        (ratings["season"].isin(SEASONS)) &
        (ratings["week"] <= 18)
    ][["season", "week", "team", "epa"]].copy()
    ratings = ratings.rename(columns={"team": "defteam", "epa": "def_epa"})

    # For each (season, week), compute median EPA across teams to split into halves
    week_medians = ratings.groupby(["season", "week"])["def_epa"].median().reset_index(
        name="median_epa")
    ratings = ratings.merge(week_medians, on=["season", "week"])
    # Lower EPA = better defense = top-half
    ratings["def_half"] = np.where(ratings["def_epa"] <= ratings["median_epa"],
                                   "top", "bottom")

    # Merge with receiver data
    valid = rec[rec["n_targets"] > 0].copy()
    valid = valid.merge(ratings[["season", "week", "defteam", "def_half"]],
                        on=["season", "week", "defteam"], how="inner")

    # Per player-season, count games vs each half
    half_counts = valid.groupby(["season", "player_id", "def_half"]).size().unstack(
        fill_value=0).reset_index()
    if "top" not in half_counts.columns or "bottom" not in half_counts.columns:
        return np.nan, np.nan, 0, "FAIL"

    qual = half_counts[
        (half_counts["top"] >= min_games_per_half) &
        (half_counts["bottom"] >= min_games_per_half)
    ][["season", "player_id"]]
    valid = valid.merge(qual, on=["season", "player_id"])

    if len(valid) == 0:
        return np.nan, np.nan, 0, "FAIL"

    # Order games within each (player-season, def_half) and assign odd/even
    valid = valid.sort_values(["season", "player_id", "def_half", "week"])
    valid["idx_within_half"] = valid.groupby(
        ["season", "player_id", "def_half"]).cumcount()
    valid["sub_half"] = valid["idx_within_half"] % 2  # 0=A, 1=B

    # Compute pooled yards_per_target per (player-season, def_half, sub_half)
    agg = valid.groupby(["season", "player_id", "def_half", "sub_half"]).agg(
        rec_yards_sum=("rec_yards", "sum"),
        targets_sum=("n_targets", "sum"),
    ).reset_index()
    agg["ypt"] = agg["rec_yards_sum"] / agg["targets_sum"].replace(0, np.nan)
    agg = agg.dropna(subset=["ypt"])

    # Compute difference (bottom - top) per (player-season, sub_half)
    # bottom = worse defense => higher expected YPT
    pivot_half = agg.pivot_table(
        index=["season", "player_id", "sub_half"],
        columns="def_half", values="ypt"
    ).dropna()

    if "top" not in pivot_half.columns or "bottom" not in pivot_half.columns:
        return np.nan, np.nan, 0, "FAIL"

    pivot_half["diff"] = pivot_half["bottom"] - pivot_half["top"]

    # Pivot sub_half A vs B
    diff_wide = pivot_half.reset_index().pivot_table(
        index=["season", "player_id"],
        columns="sub_half", values="diff"
    ).dropna()

    if len(diff_wide) < 3:
        return np.nan, np.nan, len(diff_wide), "FAIL"

    r, _ = pearsonr(diff_wide[0], diff_wide[1])
    r8 = 2 * r / (1 + r)
    n_ps = len(diff_wide)
    pf = "PASS" if r8 >= SPLIT_HALF_THRESHOLD else "FAIL"
    return r, r8, n_ps, pf


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    print("Loading PBP data (2021-2024, regular season)...")
    pbp = load_pbp_audit()
    print(f"  {len(pbp):,} plays loaded")

    print("Building per-game aggregates...")
    rec, car = build_per_game_attributes(pbp)
    rec, car = add_defteam(pbp, rec, car)
    print(f"  {len(rec):,} receiver-game rows, {len(car):,} rusher-game rows")

    # --- Split-half reliability ---
    print("Computing split-half reliability (receivers)...")
    rec_sh = split_half_reliability(rec, REC_ATTRS)

    print("Computing split-half reliability (rushers)...")
    rush_sh = split_half_reliability(car, RUSH_ATTRS)

    # --- Year-over-year ---
    print("Computing year-over-year stability (receivers)...")
    rec_yoy = year_over_year(rec, REC_ATTRS)

    print("Computing year-over-year stability (rushers)...")
    rush_yoy = year_over_year(car, RUSH_ATTRS)

    # --- Recent form ---
    print("Computing recent form analysis...")
    rf = recent_form_analysis(rec, car)

    # --- Defense-type split ---
    print("Computing defense-type split reliability...")
    ds_r, ds_r8, ds_n, ds_pf = defense_split_reliability(rec)

    # --- Build output ---
    print("\n" + "=" * 70)
    print("ATTRIBUTE RELIABILITY RESULTS")
    print("=" * 70)

    lines = []
    lines.append("# Phase 1B Step 4: Attribute Reliability Audit (D11)")
    lines.append("")
    lines.append("## Method")
    lines.append("")
    lines.append("**Data:** Play-by-play from 2021-2024, regular season only (week <= 18).")
    lines.append("Per-game aggregation uses `build_player_game_aggs` from `usage.py` (imported).")
    lines.append("All attributes computed on RAW per-player-per-game values, NOT shrunk/decayed estimates.")
    lines.append("")
    lines.append("**Split-half reliability:** For each player-season with >= 8 qualifying games,")
    lines.append("games ordered by week, odd-indexed = half A, even-indexed = half B.")
    lines.append("Each half's attribute = pooled ratio (sum numerator / sum denominator).")
    lines.append("Pearson r between halves across all qualifying player-seasons (pooled over 4 seasons).")
    lines.append("Spearman-Brown correction to 8-game length: r8 = 2r / (1 + r).")
    lines.append("Threshold: r8 >= 0.50 => PASS (frozen from D11).")
    lines.append("")
    lines.append("**Qualifying games:** A game counts for a receiver if targets >= 1,")
    lines.append("for a rusher if carries >= 1. Carries exclude qb_scramble.")
    lines.append("")
    lines.append("**Year-over-year:** Pearson r between full-season pooled ratio in season s")
    lines.append("and season s+1 for players qualifying in both. Informational only, not gated.")
    lines.append("")

    # --- Main table ---
    lines.append("## Reliability Table")
    lines.append("")
    lines.append("| Attribute | Group | N | r | r8 | YoY r | YoY N | PASS/FAIL |")
    lines.append("|---|---|---|---|---|---|---|---|")

    def fmt(v, dec=3):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return "N/A"
        return f"{v:.{dec}f}"

    all_results = []
    for attr, (r, r8, n, pf) in rec_sh.items():
        yoy_r, yoy_n = rec_yoy[attr]
        row = f"| {attr} | receivers | {n} | {fmt(r)} | {fmt(r8)} | {fmt(yoy_r)} | {yoy_n} | {pf} |"
        lines.append(row)
        all_results.append((attr, "receivers", r, r8, n, yoy_r, yoy_n, pf))
        print(f"  {attr:25s}  r={fmt(r):>7s}  r8={fmt(r8):>7s}  N={n:>5d}  YoY={fmt(yoy_r):>7s}  {pf}")

    for attr, (r, r8, n, pf) in rush_sh.items():
        yoy_r, yoy_n = rush_yoy[attr]
        row = f"| {attr} | rushers | {n} | {fmt(r)} | {fmt(r8)} | {fmt(yoy_r)} | {yoy_n} | {pf} |"
        lines.append(row)
        all_results.append((attr, "rushers", r, r8, n, yoy_r, yoy_n, pf))
        print(f"  {attr:25s}  r={fmt(r):>7s}  r8={fmt(r8):>7s}  N={n:>5d}  YoY={fmt(yoy_r):>7s}  {pf}")

    lines.append("")

    # --- Recent form ---
    lines.append("## Recent Form Analysis")
    lines.append("")
    lines.append("Does last-3-game share add information beyond season-to-date rate")
    lines.append("for predicting next-game share? Train 2021-2023, test 2024.")
    lines.append("Positive delta (RMSE_std - RMSE_std+l3) means recent form improves prediction.")
    lines.append("")
    lines.append("| Attribute | RMSE (STD only) | RMSE (STD + L3) | Delta | Sign | N_train | N_test |")
    lines.append("|---|---|---|---|---|---|---|")

    for label, vals in rf.items():
        row = (f"| {label} | {fmt(vals['rmse_std'], 5)} | {fmt(vals['rmse_std_l3'], 5)} "
               f"| {fmt(vals['delta'], 5)} | {vals['sign']} | {vals['n_train']} | {vals['n_test']} |")
        lines.append(row)
        print(f"\n  RECENT FORM: {label}")
        print(f"    RMSE(std)={fmt(vals['rmse_std'],5)}  RMSE(std+l3)={fmt(vals['rmse_std_l3'],5)}  "
              f"delta={fmt(vals['delta'],5)}  sign={vals['sign']}")

    lines.append("")

    # --- Defense-type split ---
    lines.append("## Defense-Type Split Reliability")
    lines.append("")
    lines.append("Is the difference in yards_per_target vs top-half vs bottom-half pass defenses")
    lines.append("a stable player trait? Top-half = lower EPA allowed (better defense).")
    lines.append("Split-half within each defense half (odd/even games), then reliability of the difference.")
    lines.append("Threshold: r8 >= 0.50 => PASS.")
    lines.append("")
    lines.append(f"| Attribute | Group | N | r | r8 | PASS/FAIL |")
    lines.append("|---|---|---|---|---|---|")
    lines.append(f"| ypt_defense_split | receivers | {ds_n} | {fmt(ds_r)} | {fmt(ds_r8)} | {ds_pf} |")
    lines.append("")

    print(f"\n  DEFENSE SPLIT: r={fmt(ds_r)}  r8={fmt(ds_r8)}  N={ds_n}  {ds_pf}")

    # --- Admitted attributes ---
    lines.append("## ATTRIBUTES ADMITTED TO THE SIM")
    lines.append("")
    lines.append("Threshold: r8 >= 0.50 (D11, frozen). The threshold was not moved.")
    lines.append("")

    passed = [(a, g) for a, g, r, r8, n, yr, yn, pf in all_results if pf == "PASS"]
    failed = [(a, g) for a, g, r, r8, n, yr, yn, pf in all_results if pf != "PASS"]

    lines.append("**PASSED (admitted):**")
    lines.append("")
    for a, g in passed:
        lines.append(f"- `{a}` ({g})")

    lines.append("")
    lines.append("**FAILED (excluded):**")
    lines.append("")
    for a, g in failed:
        lines.append(f"- `{a}` ({g})")

    lines.append("")
    lines.append("Excluded attributes are not used in the player layer.")
    lines.append("The defense-type split (ypt_defense_split) " +
                 (f"PASSED (r8={fmt(ds_r8)})" if ds_pf == "PASS"
                  else f"FAILED (r8={fmt(ds_r8)})") +
                 " and is " + ("admitted" if ds_pf == "PASS" else "excluded") +
                 " as a matchup adjustment.")
    lines.append("")

    # Write output
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines) + "\n")
    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()
