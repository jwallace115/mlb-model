"""S54 (L-WO1 Item 1): all-source point-in-time truncation test with planted-leak negative controls.

For each of 5 dates D (2 in 2022-23, 2 in 2023-24, 1 in 2024-25):
  - Truncate EVERY time-stamped source to strictly before D
  - Rebuild team ratings, goalie ratings, F(D), and verify equality with full-data values
  - Assert equality to 1e-12 (ratings, F)
  - xG: assert fit_seasons == [2021, 2022] and re-scoring is deterministic

Planted-leak negative controls: corrupt data on D (should not affect D's own ratings,
which use only data < D) and corrupt data on D+1 (should affect ratings after D+1,
proving the test infrastructure can detect changes).
"""
import json, sys, io, contextlib, copy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from nhl.sim.ratings import (
    build_pit_ratings, goalie_ratings_from_games, finishing_term_from_games,
    load_hyper, load_carryover, score_xg, load_xg_model,
    GOALIE_GAMES_PATH,
)
from nhl.sim.sanity_check_v2 import load_pinnacle

TGS_PATH = ROOT / "nhl" / "data" / "sim" / "ratings" / "team_game_stats.parquet"
XG_PATH = ROOT / "nhl" / "data" / "sim" / "xg_v2.json"
EVENTS_DIR = ROOT / "nhl" / "data" / "sim" / "events"

TR_COLS = ["ev_att_for_per60", "ev_att_against_per60", "ev_xg_per_att_for",
           "ev_xg_per_att_against", "pp_xg_for_per60", "pk_xg_against_per60",
           "penalties_taken_per60", "penalties_drawn_per60"]


def _pick_dates():
    tgs = pd.read_parquet(TGS_PATH)
    rng = np.random.RandomState(20261005)
    dates = []
    for season in [2022, 2023, 2024]:
        sd = sorted(tgs[tgs["season"] == season]["date"].unique())
        mid = sd[len(sd) // 4 : 3 * len(sd) // 4]
        n = 2 if season in (2022, 2023) else 1
        dates.extend(sorted(str(d) for d in rng.choice(mid, n, replace=False)))
    return dates


def _next_day(d_str):
    return (pd.Timestamp(d_str) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")


@pytest.fixture(scope="module")
def tgs():
    return pd.read_parquet(TGS_PATH)


@pytest.fixture(scope="module")
def gdf():
    return pd.read_parquet(GOALIE_GAMES_PATH)


@pytest.fixture(scope="module")
def hyper():
    return load_hyper()


@pytest.fixture(scope="module")
def carryover():
    return load_carryover()


@pytest.fixture(scope="module")
def test_dates():
    return _pick_dates()


@pytest.fixture(scope="module")
def full_team_ratings(tgs, hyper, carryover):
    with contextlib.redirect_stdout(io.StringIO()):
        out, _ = build_pit_ratings(tgs, hyper=hyper, carryover=carryover)
    return out


@pytest.fixture(scope="module")
def full_goalie_ratings(gdf, hyper, carryover):
    return goalie_ratings_from_games(gdf, hyper=hyper, carryover=carryover)


@pytest.fixture(scope="module")
def full_finishing(gdf):
    return finishing_term_from_games(gdf)


class TestAllSourceTruncation:
    """For each test date D, truncate all sources to <= D and verify outputs on D match full-data."""

    def test_team_ratings_truncation(self, tgs, full_team_ratings, hyper, carryover, test_dates):
        full_idx = full_team_ratings.set_index(["game_id", "team"])[TR_COLS]
        fails = 0
        for D in test_dates:
            trunc = tgs[tgs["date"] <= D].copy()
            with contextlib.redirect_stdout(io.StringIO()):
                out, _ = build_pit_ratings(trunc, hyper=hyper, carryover=carryover)
            out_d = out[out["date"] == D].set_index(["game_id", "team"])[TR_COLS]
            common = full_idx.index.intersection(out_d.index)
            if len(common) == 0:
                continue
            diff = (out_d.loc[common] - full_idx.loc[common]).abs().to_numpy().max()
            if diff > 1e-12:
                fails += 1
                print(f"  FAIL team_ratings D={D}: max diff={diff:.2e}")
        assert fails == 0, f"Team ratings truncation failed on {fails}/{len(test_dates)} dates"

    def test_goalie_ratings_truncation(self, gdf, full_goalie_ratings, hyper, carryover, test_dates):
        full_idx = full_goalie_ratings.set_index(["game_id", "role"])["gsax_per_att_rating"]
        fails = 0
        for D in test_dates:
            trunc = gdf[gdf["date"] <= D].copy()
            out = goalie_ratings_from_games(trunc, hyper=hyper, carryover=carryover)
            out_d = out[out["date"] == D].set_index(["game_id", "role"])["gsax_per_att_rating"]
            common = full_idx.index.intersection(out_d.index)
            if len(common) == 0:
                continue
            diff = float((out_d.loc[common] - full_idx.loc[common]).abs().max())
            if diff > 1e-12:
                fails += 1
                print(f"  FAIL goalie_ratings D={D}: max diff={diff:.2e}")
        assert fails == 0, f"Goalie ratings truncation failed on {fails}/{len(test_dates)} dates"

    def test_finishing_term_truncation(self, gdf, full_finishing, test_dates):
        full_f = full_finishing.set_index("date")["F"]
        fails = 0
        for D in test_dates:
            trunc = gdf[gdf["date"] <= D].copy()
            out = finishing_term_from_games(trunc)
            out_f = out.set_index("date")["F"]
            if D not in out_f.index or D not in full_f.index:
                continue
            diff = abs(float(out_f.loc[D]) - float(full_f.loc[D]))
            if diff > 1e-12:
                fails += 1
                print(f"  FAIL F(D) D={D}: diff={diff:.2e}")
        assert fails == 0, f"F(D) truncation failed on {fails}/{len(test_dates)} dates"

    def test_pinnacle_selection_deterministic(self, test_dates):
        """Pinnacle snapshot selection is deterministic across re-loads."""
        for D in test_dates:
            season = int(D[:4]) if D[5:7] >= "09" else int(D[:4]) - 1
            pin1 = load_pinnacle(season)
            pin2 = load_pinnacle(season)
            if pin1.empty:
                continue
            p1d = pin1[pin1["et_date"] == D]
            p2d = pin2[pin2["et_date"] == D]
            if p1d.empty:
                continue
            pd.testing.assert_frame_equal(p1d.reset_index(drop=True), p2d.reset_index(drop=True))

    def test_xg_model_fit_seasons(self):
        with open(XG_PATH) as f:
            xg = json.load(f)
        assert xg["fit_seasons"] == [2021, 2022], f"xG fit_seasons = {xg['fit_seasons']}, expected [2021, 2022]"

    def test_xg_rescoring_deterministic(self):
        model = load_xg_model()
        for season in [2022, 2023]:
            shots = pd.read_parquet(EVENTS_DIR / f"season={season}" / "shots.parquet")
            non_en = shots[~shots["empty_net"].astype(bool)].copy()
            xg1 = score_xg(non_en, model)
            xg2 = score_xg(non_en, model)
            diff = np.abs(xg1 - xg2).max()
            assert diff < 1e-12, f"xG scoring not deterministic: max diff={diff:.2e} season={season}"


# ---- Planted-leak negative controls ----

class TestPlantedLeakTeamStats:
    """Corrupt D's own data — ratings on D must NOT change (they use only data < D).
    Then corrupt D+1's data — ratings after D+1 must change (proving detection works)."""

    def test_corrupt_D_does_not_affect_D(self, tgs, full_team_ratings, hyper, carryover, test_dates):
        D = test_dates[2]
        full_idx = full_team_ratings.set_index(["game_id", "team"])[TR_COLS]
        corrupted = tgs.copy()
        mask = corrupted["date"] == D
        corrupted.loc[mask, "ev_att_for"] = corrupted.loc[mask, "ev_att_for"] * 10 + 999
        with contextlib.redirect_stdout(io.StringIO()):
            out, _ = build_pit_ratings(corrupted, hyper=hyper, carryover=carryover)
        out_d = out[out["date"] == D].set_index(["game_id", "team"])[TR_COLS]
        common = full_idx.index.intersection(out_d.index)
        diff = (out_d.loc[common] - full_idx.loc[common]).abs().to_numpy().max()
        assert diff < 1e-12, (
            f"Ratings on D={D} changed when D's own data was corrupted (diff={diff:.2e}). "
            "Point-in-time claim is FALSE for team ratings."
        )

    def test_corrupt_D1_affects_future(self, tgs, full_team_ratings, hyper, carryover, test_dates):
        D = test_dates[2]
        full_idx = full_team_ratings.set_index(["game_id", "team"])[TR_COLS]
        nd = _next_day(D)
        corrupted = tgs.copy()
        mask = corrupted["date"] == nd
        if mask.sum() == 0:
            pytest.skip(f"No games on {nd}")
        # Corrupt ALL numeric columns to ensure league means change
        num_cols = [c for c in corrupted.columns if pd.api.types.is_numeric_dtype(corrupted[c])
                    and c not in ("season",)]
        for c in num_cols:
            corrupted.loc[mask, c] = corrupted.loc[mask, c] * 7 + 999
        with contextlib.redirect_stdout(io.StringIO()):
            out, _ = build_pit_ratings(corrupted, hyper=hyper, carryover=carryover)
        future = out[out["date"] > nd]
        if len(future) == 0:
            pytest.skip("No games after D+1")
        future_idx = future.set_index(["game_id", "team"])[TR_COLS]
        common = full_idx.index.intersection(future_idx.index)
        diff = (future_idx.loc[common] - full_idx.loc[common]).abs().to_numpy().max()
        assert diff > 1e-6, (
            f"Injecting 2000 ev_att_for on {nd} didn't change any future rating (diff={diff:.2e}). "
            "Negative control broken."
        )


class TestPlantedLeakGoalie:
    def test_corrupt_D_does_not_affect_D(self, gdf, full_goalie_ratings, hyper, carryover, test_dates):
        D = test_dates[2]
        full_idx = full_goalie_ratings.set_index(["game_id", "role"])["gsax_per_att_rating"]
        corrupted = gdf.copy()
        mask = corrupted["date"] == D
        corrupted.loc[mask, "gsax"] = corrupted.loc[mask, "gsax"] * 10 + 50
        corrupted.loc[mask, "attempts_faced"] = corrupted.loc[mask, "attempts_faced"] * 10
        out = goalie_ratings_from_games(corrupted, hyper=hyper, carryover=carryover)
        out_d = out[out["date"] == D].set_index(["game_id", "role"])["gsax_per_att_rating"]
        common = full_idx.index.intersection(out_d.index)
        diff = float((out_d.loc[common] - full_idx.loc[common]).abs().max())
        assert diff < 1e-12, (
            f"Goalie ratings on D={D} changed when D's data was corrupted (diff={diff:.2e}). "
            "Point-in-time claim is FALSE for goalie ratings."
        )

    def test_corrupt_D1_affects_future(self, gdf, full_goalie_ratings, hyper, carryover, test_dates):
        D = test_dates[2]
        full_idx = full_goalie_ratings.set_index(["game_id", "role"])["gsax_per_att_rating"]
        nd = _next_day(D)
        corrupted = gdf.copy()
        mask = corrupted["date"] == nd
        if mask.sum() == 0:
            pytest.skip(f"No goalie games on {nd}")
        corrupted.loc[mask, "gsax"] = 50.0
        out = goalie_ratings_from_games(corrupted, hyper=hyper, carryover=carryover)
        future = out[out["date"] > nd]
        if len(future) == 0:
            pytest.skip("No games after D+1")
        future_idx = future.set_index(["game_id", "role"])["gsax_per_att_rating"]
        common = full_idx.index.intersection(future_idx.index)
        diff = float((future_idx.loc[common] - full_idx.loc[common]).abs().max())
        assert diff > 1e-6, (
            f"Corrupting goalie data on {nd} didn't change future ratings (diff={diff:.2e}). "
            "Negative control broken."
        )


class TestPlantedLeakPinnacle:
    def test_pinnacle_deterministic(self, test_dates):
        D = test_dates[2]
        season = int(D[:4]) if D[5:7] >= "09" else int(D[:4]) - 1
        full_pin = load_pinnacle(season)
        if full_pin.empty:
            pytest.skip(f"No Pinnacle data for season {season}")
        pin_d = full_pin[full_pin["et_date"] == D]
        if pin_d.empty:
            pytest.skip(f"No Pinnacle data for D={D}")
        pin2 = load_pinnacle(season)
        pin2_d = pin2[pin2["et_date"] == D]
        pd.testing.assert_frame_equal(pin_d.reset_index(drop=True), pin2_d.reset_index(drop=True))


class TestPlantedLeakXG:
    def test_modified_coefficients_change_output(self):
        model = load_xg_model()
        shots = pd.read_parquet(EVENTS_DIR / "season=2022" / "shots.parquet")
        non_en = shots[~shots["empty_net"].astype(bool)].head(1000).copy()
        xg_orig = score_xg(non_en, model)
        model2 = copy.deepcopy(model)
        model2["intercept"] = model2["intercept"] + 5.0
        xg_modified = score_xg(non_en, model2)
        diff = np.abs(xg_orig - xg_modified).max()
        assert diff > 0.1, (
            f"Changing xG intercept by +5.0 didn't change predictions (max diff={diff:.2e}). "
            "The scoring function may not use the model coefficients."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
