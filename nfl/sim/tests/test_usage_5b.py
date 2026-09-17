#!/usr/bin/env python3
"""
Phase 5B usage-layer tests.

(a) Params block present and read — perturbing k_share changes shares
(b) Shares per team-week sum to 1.00 +/- 0.001 for targets, carries, RZ targets, GL carries
(c) Top-3 target share for KC 2025 wk17 within 0.05 of observed PBP shares
(d) Starting-QB identity for every 2026 team-week equals depth-chart QB1
    or prev-game leading passer — 100%, no tolerance
(e) CAR case: no player with zero 2026 opportunities above the D14 prior
(f) PIT byte-identity: 2024 wk10 from truncated data == full-season build
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from nfl.sim.usage import (
    PARAMS_PATH,
    OUTPUT_SEASONS,
    SKILL_POS,
    load_pbp,
    load_roster_data,
    build_player_game_aggs,
    build_position_map,
    compute_position_priors,
    compute_season_share_data,
    build_active_universe,
    build_player_usage,
    derive_starting_qbs,
)

PBP_DIR = ROOT / "nfl" / "data" / "pbp"


# ─── shared fixtures ────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def data_bundle():
    """Load all data once for the entire module."""
    plays = load_pbp()
    scrimmage = plays[plays["play_type"].isin(["pass", "run"])].copy()
    del plays

    rosters, depth, injuries = load_roster_data()
    starting_qbs = derive_starting_qbs(depth, scrimmage)

    rec, team_tgt, car, team_car = build_player_game_aggs(scrimmage)
    del scrimmage

    pos_map = build_position_map(rosters)
    rate_priors = compute_position_priors(rec, car, pos_map)
    roster_uni = rosters[rosters["position"].isin(SKILL_POS)][
        ["season", "week", "gsis_id", "team", "position", "full_name"]
    ].rename(columns={"gsis_id": "player_id"}).drop_duplicates(
        ["season", "week", "player_id"]
    )
    active = build_active_universe(rosters, injuries, depth)
    dop, pss = compute_season_share_data(active, rec, team_tgt, car, team_car)

    params = json.load(open(PARAMS_PATH))

    return {
        "rec": rec, "team_tgt": team_tgt, "car": car, "team_car": team_car,
        "pos_map": pos_map, "rate_priors": rate_priors,
        "roster_uni": roster_uni, "active": active,
        "dop": dop, "pss": pss, "params": params,
        "starting_qbs": starting_qbs, "depth": depth,
    }


@pytest.fixture(scope="module")
def usage_df(data_bundle):
    """Build full usage once."""
    d = data_bundle
    return build_player_usage(
        d["rec"], d["team_tgt"], d["car"], d["team_car"],
        d["pos_map"], d["rate_priors"], d["params"],
        d["roster_uni"], d["active"], d["dop"], d["pss"],
        starting_qbs=d["starting_qbs"],
    )


# ─── (a) params block present and read ──────────────────────────────────────

def test_params_block_present_and_read(data_bundle):
    """Usage block must exist; perturbing k_share changes shares."""
    d = data_bundle
    params = d["params"]
    assert "usage" in params, "params_v1.json missing 'usage' block"
    assert params["usage"]["share_half_life"] == 4
    assert params["usage"]["k_share"] == 20

    # Build with default k_share=20
    usage_20 = build_player_usage(
        d["rec"], d["team_tgt"], d["car"], d["team_car"],
        d["pos_map"], d["rate_priors"], params,
        d["roster_uni"], d["active"], d["dop"], d["pss"],
        output_seasons=[2024],
        starting_qbs=d["starting_qbs"],
    )

    # Build with perturbed k_share=100
    params2 = json.loads(json.dumps(params, default=str))
    params2["usage"]["k_share"] = 100
    usage_100 = build_player_usage(
        d["rec"], d["team_tgt"], d["car"], d["team_car"],
        d["pos_map"], d["rate_priors"], params2,
        d["roster_uni"], d["active"], d["dop"], d["pss"],
        output_seasons=[2024],
        starting_qbs=d["starting_qbs"],
    )

    # Shares must differ
    merged = usage_20.merge(
        usage_100, on=["season", "week", "team", "player_id"],
        suffixes=("_20", "_100"),
    )
    diff = (merged["target_share_20"] - merged["target_share_100"]).abs()
    assert diff.max() > 0.001, (
        f"Perturbing k_share did not change target_share (max diff {diff.max():.6f})"
    )

    # Missing block must raise
    params_no_usage = {k: v for k, v in params.items() if k != "usage"}
    with pytest.raises(ValueError, match="missing required 'usage' block"):
        build_player_usage(
            d["rec"], d["team_tgt"], d["car"], d["team_car"],
            d["pos_map"], d["rate_priors"], params_no_usage,
            d["roster_uni"], d["active"], d["dop"], d["pss"],
            output_seasons=[2024],
        )


# ─── (b) share sums ─────────────────────────────────────────────────────────

def test_share_sums(usage_df):
    """Shares per team-week sum to 1.00 +/- 0.001."""
    share_cols = ["target_share", "carry_share", "rz_target_share", "gl_carry_share"]
    failures = []
    for (s, w, t), grp in usage_df.groupby(["season", "week", "team"]):
        for sc in share_cols:
            total = grp[sc].sum()
            if total > 0 and abs(total - 1.0) > 0.001:
                failures.append(f"{s} wk{w} {t} {sc}={total:.6f}")
    assert not failures, f"Share sum failures:\n" + "\n".join(failures[:20])


# ─── (c) KC 2025 wk17 top-3 target share vs observed ────────────────────────

def test_kc_2025_wk17_target_shares(data_bundle, usage_df):
    """Top-3 model target shares within 0.05 of observed PBP shares."""
    # Observed shares from PBP
    pbp = pd.read_parquet(PBP_DIR / "pbp_2025.parquet")
    kc17 = pbp[(pbp["posteam"] == "KC") & (pbp["week"] == 17) & (pbp["play_type"] == "pass")]
    tgt = kc17[kc17["receiver_player_id"].notna()]
    team_total = len(tgt)
    assert team_total > 0, "No KC wk17 targets in PBP"
    actual = (
        tgt.groupby("receiver_player_id").size()
        .reset_index(name="n")
        .assign(actual_share=lambda x: x["n"] / team_total)
    ).rename(columns={"receiver_player_id": "player_id"})

    # Model shares
    model = usage_df[
        (usage_df["season"] == 2025) & (usage_df["week"] == 17)
        & (usage_df["team"] == "KC")
    ].copy()
    top3 = model.nlargest(3, "target_share")

    for _, row in top3.iterrows():
        pid = row["player_id"]
        model_share = row["target_share"]
        act_row = actual[actual["player_id"] == pid]
        if act_row.empty:
            actual_share = 0.0
        else:
            actual_share = float(act_row["actual_share"].iloc[0])
        diff = abs(model_share - actual_share)
        assert diff <= 0.05, (
            f"KC wk17 {row['player_name']}: model={model_share:.4f} "
            f"actual={actual_share:.4f} diff={diff:.4f} > 0.05"
        )


# ─── (d) starting-QB identity ───────────────────────────────────────────────

def test_starting_qb_identity_2026(data_bundle, usage_df):
    """Starting-QB for every 2026 team-week matches depth chart or prev-game passer.
    100% match, no tolerance."""
    starting_qbs = data_bundle["starting_qbs"]
    depth = data_bundle["depth"]

    # Get the latest depth-chart QB1 per team (new schema)
    if "pos_rank" in depth.columns:
        new_qb = depth[
            (depth.get("pos_abb", pd.Series(dtype=str)) == "QB")
            & depth["pos_rank"].notna()
        ].copy()
        new_qb["pos_rank"] = pd.to_numeric(new_qb["pos_rank"], errors="coerce")
        dc_qb1 = (
            new_qb[new_qb["pos_rank"] == 1]
            .sort_values("dt", ascending=False, na_position="last")
            .drop_duplicates("team", keep="first")
        )
        dc_qb1_map = {r["team"]: r["gsis_id"] for _, r in dc_qb1.iterrows()}
    else:
        dc_qb1_map = {}

    # Get prev-game leading passer for 2026 from PBP
    pbp_2026_path = PBP_DIR / "pbp_2026.parquet"
    pbp_passers = {}
    if pbp_2026_path.exists():
        pbp26 = pd.read_parquet(pbp_2026_path)
        passes = pbp26[
            (pbp26["play_type"] == "pass") & pbp26["passer_player_id"].notna()
        ]
        if not passes.empty:
            leader = (
                passes.groupby(["week", "posteam", "passer_player_id"])
                .size().reset_index(name="att")
            )
            leader = leader.sort_values("att", ascending=False).drop_duplicates(
                ["week", "posteam"]
            )
            for _, r in leader.iterrows():
                pbp_passers[(int(r["week"]) + 1, r["posteam"])] = r["passer_player_id"]

    # Check every 2026 team-week in usage
    u26 = usage_df[usage_df["season"] == 2026]
    failures = []
    for (w, team), grp in u26.groupby(["week", "team"]):
        starters = grp[grp["is_starting_qb"]]
        if starters.empty:
            failures.append(f"wk{w} {team}: no starting QB identified")
            continue
        if len(starters) > 1:
            failures.append(f"wk{w} {team}: multiple starting QBs: {starters['player_name'].tolist()}")
            continue
        starter_id = starters.iloc[0]["player_id"]

        # What we expect: prev-game passer if available, else depth chart
        expected = pbp_passers.get((w, team), dc_qb1_map.get(team))
        if expected is None:
            failures.append(f"wk{w} {team}: no expected QB (no depth chart or PBP)")
            continue
        if starter_id != expected:
            failures.append(
                f"wk{w} {team}: starter={starter_id} expected={expected}"
            )

    assert not failures, "Starting-QB identity failures:\n" + "\n".join(failures)


# ─── (e) CAR case: zero-opp players below D14 prior ─────────────────────────

def test_car_zero_opp_below_prior(data_bundle, usage_df):
    """No player with zero 2026 opportunities above the D14 prior."""
    dop = data_bundle["dop"]

    # Get depth-order priors from 2025 (s-1 for 2026)
    dop_2025 = dop.get(2025, dop.get(max(dop.keys()), {}))

    u26 = usage_df[usage_df["season"] == 2026].copy()
    zero_opp = u26[(u26["n_targets"] == 0) & (u26["n_carries"] == 0)]

    failures = []
    for _, row in zero_opp.iterrows():
        # Skip starting QBs — they retain their prior by design
        if row.get("is_starting_qb", False):
            continue

        pos = row["position"]
        for share_col, share_type in [
            ("target_share", "target_share"),
            ("carry_share", "carry_share"),
        ]:
            player_share = row[share_col]
            # Find the maximum depth-order prior for this position
            max_prior = 0.0
            for dg, vals in dop_2025.items():
                if dg.startswith(pos[:2]):
                    max_prior = max(max_prior, vals.get(share_type, 0))
            if max_prior == 0:
                max_prior = 1 / 10  # fallback
            if player_share > max_prior + 0.001:
                failures.append(
                    f"{row['team']} {row['player_name']} ({pos}): "
                    f"{share_col}={player_share:.4f} > prior={max_prior:.4f}"
                )

    # Specific Dotson/Zaccheaus check: must NOT appear on CAR
    car_pids = set(u26[u26["team"] == "CAR"]["player_id"].unique())
    # Check known Dotson/Zaccheaus gsis_ids
    dotson_id = "00-0037741"  # Jahan Dotson
    zaccheaus_id = "00-0035208"  # Olamide Zaccheaus
    assert dotson_id not in car_pids, "Jahan Dotson erroneously on CAR"
    assert zaccheaus_id not in car_pids, "Olamide Zaccheaus erroneously on CAR"

    assert not failures, (
        f"Zero-opp players above D14 prior ({len(failures)}):\n"
        + "\n".join(failures[:20])
    )


# ─── (f) PIT byte-identity ──────────────────────────────────────────────────

def test_pit_byte_identity_2024_wk10(data_bundle):
    """2024 wk10 shares from truncated data == full-season build."""
    d = data_bundle

    # Full build for 2024
    full = build_player_usage(
        d["rec"], d["team_tgt"], d["car"], d["team_car"],
        d["pos_map"], d["rate_priors"], d["params"],
        d["roster_uni"], d["active"], d["dop"], d["pss"],
        output_seasons=[2024],
        starting_qbs=d["starting_qbs"],
    )
    full_wk10 = full[
        (full["season"] == 2024) & (full["week"] == 10)
    ].sort_values(["team", "player_id"]).reset_index(drop=True)

    # Truncated build: only PBP data < 2024 wk10 (rec/car/team aggregates).
    # Active universe and roster universe are NOT truncated — they control which
    # players appear, and the PIT guarantee is about share VALUES, not player set.
    def trunc(df, s_col="season", w_col="week"):
        return df[~((df[s_col] > 2024) | ((df[s_col] == 2024) & (df[w_col] >= 10)))]

    trunc_rec = trunc(d["rec"])
    trunc_tt = trunc(d["team_tgt"])
    trunc_car = trunc(d["car"])
    trunc_tc = trunc(d["team_car"])

    # Depth-order priors for s-1 (2023) are the same either way, but compute
    # from truncated data to prove PIT holds end-to-end.
    trunc_rate_priors = compute_position_priors(trunc_rec, trunc_car, d["pos_map"])
    trunc_dop, trunc_pss = compute_season_share_data(
        d["active"], trunc_rec, trunc_tt, trunc_car, trunc_tc
    )

    trunc_usage = build_player_usage(
        trunc_rec, trunc_tt, trunc_car, trunc_tc,
        d["pos_map"], trunc_rate_priors, d["params"],
        d["roster_uni"], d["active"], trunc_dop, trunc_pss,
        output_seasons=[2024],
        starting_qbs=d["starting_qbs"],
    )
    trunc_wk10 = trunc_usage[
        (trunc_usage["season"] == 2024) & (trunc_usage["week"] == 10)
    ].sort_values(["team", "player_id"]).reset_index(drop=True)

    # Byte-identity: same player set, same values
    assert len(full_wk10) == len(trunc_wk10), (
        f"Row count mismatch: full={len(full_wk10)} trunc={len(trunc_wk10)}"
    )
    assert list(full_wk10["player_id"]) == list(trunc_wk10["player_id"]), (
        "Player ID mismatch between full and truncated builds"
    )

    float_cols = [
        "target_share", "carry_share", "rz_target_share", "gl_carry_share",
        "adot", "catch_rate", "yac_per_rec", "yards_per_target", "yards_per_carry",
        "explosive_rec_rate", "explosive_rush_rate",
    ]
    int_cols = ["n_targets", "n_carries"]

    for col in float_cols + int_cols:
        if col not in full_wk10.columns:
            continue
        full_vals = full_wk10[col].values
        trunc_vals = trunc_wk10[col].values
        if not np.array_equal(full_vals, trunc_vals):
            max_diff = np.max(np.abs(full_vals - trunc_vals))
            idx = np.argmax(np.abs(full_vals - trunc_vals))
            pid = full_wk10.iloc[idx]["player_id"]
            pytest.fail(
                f"PIT FAIL {col}: max diff {max_diff:.2e} at {pid} "
                f"(full={full_vals[idx]:.8f} trunc={trunc_vals[idx]:.8f})"
            )
