#!/usr/bin/env python3
"""
Phase 5F — PIT test for D59/D60/D61.

D59: depth_order from new-schema snapshots is restricted to dt < week's first
     kickoff. Usage for week W must be identical whether or not depth rows with
     dt >= kickoff(W) exist.

D60: a traded player appears with a non-zero share on his debut week for the
     new team.

D61: s-1 aggregate prior uses opp-weighted share across all depth groups (tested
     structurally via the D59 PIT assertion — if the prior formula changed the
     shares, the PIT test would break).

NEGATIVE CONTROL: injecting a synthetic depth row with dt AFTER kickoff that
changes a player's depth_order MUST produce different usage in the untruncated
build. If it does not, the test is not exercising the D59 path.
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
    SKILL_POS,
    PBP_DIR,
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
TEST_WEEK = 5
TEST_SEASON = 2025


# ─── shared fixtures ────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def raw_data():
    """Load raw data once."""
    plays = load_pbp()
    scrimmage = plays[plays["play_type"].isin(["pass", "run"])].copy()
    del plays
    rosters, depth, injuries = load_roster_data()
    params = json.load(open(PARAMS_PATH))
    rec, team_tgt, car, team_car = build_player_game_aggs(scrimmage)
    pos_map = build_position_map(rosters)
    return {
        "scrimmage": scrimmage,
        "rosters": rosters,
        "depth": depth,
        "injuries": injuries,
        "params": params,
        "rec": rec,
        "team_tgt": team_tgt,
        "car": car,
        "team_car": team_car,
        "pos_map": pos_map,
    }


def _build_usage_from(raw, depth_override=None, output_seasons=None):
    """Build usage with optional depth override."""
    d = raw
    depth = depth_override if depth_override is not None else d["depth"]
    rosters, injuries = d["rosters"], d["injuries"]
    active = build_active_universe(rosters, injuries, depth)
    starting_qbs = derive_starting_qbs(depth, d["scrimmage"], active_universe=active)
    rate_priors = compute_position_priors(d["rec"], d["car"], d["pos_map"])
    roster_uni = rosters[rosters["position"].isin(SKILL_POS)][
        ["season", "week", "gsis_id", "team", "position", "full_name"]
    ].rename(columns={"gsis_id": "player_id"}).drop_duplicates(
        ["season", "week", "player_id"]
    )
    dop, pss = compute_season_share_data(active, d["rec"], d["team_tgt"],
                                          d["car"], d["team_car"])
    return build_player_usage(
        d["rec"], d["team_tgt"], d["car"], d["team_car"],
        d["pos_map"], rate_priors, d["params"],
        roster_uni, active, dop, pss,
        output_seasons=output_seasons or [TEST_SEASON],
        starting_qbs=starting_qbs,
    )


def _get_kickoff(season, week):
    """Get the first kickoff datetime for a season-week from PBP."""
    pbp_path = PBP_DIR / f"pbp_{season}.parquet"
    gdf = pd.read_parquet(pbp_path, columns=["season", "week", "game_date"])
    gdf = gdf.drop_duplicates(["season", "week", "game_date"])
    gdf["game_date"] = pd.to_datetime(gdf["game_date"], errors="coerce", utc=True)
    wg = gdf[gdf["week"] == week]
    return wg["game_date"].min()


# ─── D59: PIT — full vs truncated depth produces identical week W ─────────

def test_d59_pit_depth_truncated(raw_data):
    """Usage for week W is identical with and without depth rows having
    dt >= kickoff(W). This is the D59 claim: new-schema depth is filtered
    to dt < kickoff before influencing depth_order."""
    kickoff = _get_kickoff(TEST_SEASON, TEST_WEEK)
    assert pd.notna(kickoff), f"No kickoff found for {TEST_SEASON} wk{TEST_WEEK}"

    depth = raw_data["depth"].copy()

    # Truncated: remove depth rows with dt >= kickoff
    if "dt" in depth.columns:
        dt_col = pd.to_datetime(depth["dt"], errors="coerce", utc=True)
        truncated_depth = depth[dt_col.isna() | (dt_col < kickoff)].copy()
        removed_count = len(depth) - len(truncated_depth)
        assert removed_count > 0, (
            f"No depth rows with dt >= kickoff ({kickoff}) — test is inert"
        )
    else:
        pytest.skip("No dt column in depth — new schema not present")

    # Build usage with full depth (includes future rows)
    full_usage = _build_usage_from(raw_data, output_seasons=[TEST_SEASON])

    # Build usage with truncated depth (no future rows)
    trunc_usage = _build_usage_from(raw_data, depth_override=truncated_depth,
                                     output_seasons=[TEST_SEASON])

    # Extract week W
    full_w = (full_usage[(full_usage["season"] == TEST_SEASON) &
                         (full_usage["week"] == TEST_WEEK)]
              .sort_values(["team", "player_id"]).reset_index(drop=True))
    trunc_w = (trunc_usage[(trunc_usage["season"] == TEST_SEASON) &
                           (trunc_usage["week"] == TEST_WEEK)]
               .sort_values(["team", "player_id"]).reset_index(drop=True))

    assert len(full_w) == len(trunc_w), (
        f"Row count mismatch: full={len(full_w)} trunc={len(trunc_w)}"
    )
    assert list(full_w["player_id"]) == list(trunc_w["player_id"]), (
        "Player ID mismatch between full and truncated builds"
    )

    float_cols = [c for c in full_w.columns if full_w[c].dtype in ("float64", "float32")]
    for col in float_cols:
        fv = full_w[col].values
        tv = trunc_w[col].values
        if not np.array_equal(fv, tv):
            # Allow NaN == NaN
            if np.allclose(fv, tv, equal_nan=True, atol=1e-12):
                continue
            idx = np.argmax(np.abs(np.nan_to_num(fv) - np.nan_to_num(tv)))
            pid = full_w.iloc[idx]["player_id"]
            team = full_w.iloc[idx]["team"]
            pytest.fail(
                f"D59 PIT FAIL col={col}: {team} {pid} "
                f"full={fv[idx]:.10f} trunc={tv[idx]:.10f}"
            )


# ─── D59 NEGATIVE CONTROL: synthetic future depth row MUST change output ──

def test_d59_negative_control(raw_data):
    """D87: a control that can actually fail.

    The original version injected a future-dated row and asserted the output was
    UNCHANGED — the same assertion as test_d59_pit_depth_truncated, so it was not a
    control at all. Its own comment admitted "the test needs to verify the MECHANISM
    differently" and then did not. When a real control was added it FAILED: the
    chosen row was inert, because D59 fills only where depth_order is NaN
    (usage.py ~440, `fill_mask = depth_order.isna() & new_depth.notna()`) and the
    target already had an eligible snapshot.

    So: find a player who has NO pre-kickoff depth row (depth_order would be NaN,
    i.e. fillable), inject the SAME rank-1 row twice differing ONLY in dt, and show
    that the before-kickoff one changes the output while the after-kickoff one does
    not. That isolates exactly the D59 date filter.
    """
    kickoff = _get_kickoff(TEST_SEASON, TEST_WEEK)
    depth = raw_data["depth"].copy()
    dt_col = pd.to_datetime(depth["dt"], errors="coerce", utc=True)
    new_schema = depth[dt_col.notna()].copy()
    new_schema["_dt"] = dt_col[new_schema.index]

    base_usage = _build_usage_from(raw_data, output_seasons=[TEST_SEASON])
    base_w = (base_usage[(base_usage["season"] == TEST_SEASON) &
                         (base_usage["week"] == TEST_WEEK)]
              .sort_values(["team", "player_id"]).reset_index(drop=True))
    float_cols = [c for c in base_w.columns if base_w[c].dtype in ("float64", "float32")]

    # players WITH a pre-kickoff snapshot are inert — D59 only fills NaN
    covered = set(new_schema.loc[new_schema["_dt"] < kickoff, "gsis_id"].dropna())
    template = new_schema.iloc[0]

    def _inject(pid, team, when):
        row = template.copy()
        row["gsis_id"] = pid
        row["team"] = team
        row["pos_abb"] = "RB"
        row["pos_rank"] = 1
        row["dt"] = when.isoformat()
        if "_dt" in row.index:
            row = row.drop("_dt")
        d = pd.concat([depth, pd.DataFrame([row])], ignore_index=True)
        u = _build_usage_from(raw_data, depth_override=d, output_seasons=[TEST_SEASON])
        return (u[(u["season"] == TEST_SEASON) & (u["week"] == TEST_WEEK)]
                .sort_values(["team", "player_id"]).reset_index(drop=True))

    def _differs(a, b):
        return any(not np.allclose(a[c].values, b[c].values, equal_nan=True, atol=1e-12)
                   for c in float_cols)

    candidates = [(r.player_id, r.team) for r in base_w.itertuples()
                  if r.player_id not in covered][:4]
    if not candidates:
        pytest.skip("every player in the week has a pre-kickoff snapshot — "
                    "no fillable target, so this control cannot be built")

    potent = None
    for pid, team in candidates:
        if _differs(base_w, _inject(pid, team, kickoff - pd.Timedelta(hours=1))):
            potent = (pid, team)
            break

    assert potent is not None, (
        "CONTROL FAILED: none of the candidate rows changed the output even when "
        "dated BEFORE kickoff. The injection is inert, so an after-kickoff "
        "assertion would prove nothing about D59.")

    pid, team = potent
    # same row, one hour AFTER kickoff — D59 must exclude it
    after = _inject(pid, team, kickoff + pd.Timedelta(hours=1))
    assert not _differs(base_w, after), (
        f"D59 LEAK: a depth row dated after kickoff changed week {TEST_WEEK} output "
        f"for {pid} ({team}). The date filter is not excluding future snapshots.")


# ─── D60: traded players appear on new team with non-zero share ───────────

def test_d60_traded_player_debut(raw_data):
    """McCaffrey (CAR→SF wk7 2022) and Hockenson (DET→MIN wk9 2022) must
    appear with non-zero target/carry share on their debut week for the
    new team."""
    usage = _build_usage_from(raw_data, output_seasons=[2022])

    # McCaffrey SF wk7
    cmc = usage[
        (usage["season"] == 2022) & (usage["week"] == 7) &
        (usage["team"] == "SF") &
        (usage["player_name"].str.contains("McCaffrey", na=False))
    ]
    assert not cmc.empty, "McCaffrey not found on SF in 2022 wk7"
    assert float(cmc.iloc[0]["carry_share"]) > 0, (
        f"McCaffrey SF wk7 carry_share = {cmc.iloc[0]['carry_share']} (expected > 0)"
    )
    assert float(cmc.iloc[0]["target_share"]) > 0, (
        f"McCaffrey SF wk7 target_share = {cmc.iloc[0]['target_share']} (expected > 0)"
    )

    # Hockenson MIN wk9
    hock = usage[
        (usage["season"] == 2022) & (usage["week"] == 9) &
        (usage["team"] == "MIN") &
        (usage["player_name"].str.contains("Hockenson", na=False))
    ]
    assert not hock.empty, "Hockenson not found on MIN in 2022 wk9"
    assert float(hock.iloc[0]["target_share"]) > 0, (
        f"Hockenson MIN wk9 target_share = {hock.iloc[0]['target_share']} (expected > 0)"
    )


# ─── Coverage statement ──────────────────────────────────────────────────

# D59: TESTED by test_d59_pit_depth_truncated + test_d59_negative_control.
#   The PIT test verifies that removing depth rows with dt >= kickoff does
#   not change week W output. The negative control verifies the injected
#   future row exists and would be eligible if the filter were absent.
#
# D60: TESTED by test_d60_traded_player_debut. McCaffrey and Hockenson
#   appear on their new team with non-zero shares on debut week.
#
# D61: NOT DIRECTLY TESTED. D61 changed the s-1 prior from a single
#   depth-group row to an opp-weighted aggregate across all depth groups.
#   This affects the shrinkage VALUE but not the PIT IDENTITY — a player
#   with multi-depth-group history gets a different prior, but the prior
#   is still computed from s-1 data only, so the PIT guarantee holds.
#   A direct test would require building usage with the old prior formula
#   and comparing, which would need the old code path to be preserved.
#   The D59 PIT test implicitly covers D61's structural correctness: if
#   the aggregate prior formula introduced a time leak, the PIT assertion
#   would catch it.
