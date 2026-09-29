"""S13 tests: ratings must be per-season, point-in-time, no holdout leakage.
Each test must FAIL on e17ace021 (the S10 code)."""
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


class TestNoHoldoutLeakage:
    """A 2022-23 rating must not change when 2024-25 and 2025-26 games are deleted.
    FAILS on e17ace021: the old code computed league_means from ALL seasons."""

    def test_rating_unchanged_without_holdout(self):
        """Build ratings with and without holdout seasons; 2022-23 values must match."""
        from nhl.sim.ratings import (get_game_info, build_game_stats_vectorised as build_game_stats, build_pit_ratings,
                                      load_xg_model, ALL_SEASONS, EVENTS_DIR, FIT_SEASONS)

        # Use cached team_game_stats instead of rebuilding (takes 90s)
        tgs_full = pd.read_parquet(ROOT / "nhl" / "data" / "sim" / "ratings" / "team_game_stats.parquet")
        import io, contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            ratings_full, _ = build_pit_ratings(tgs_full)

        # Now without holdout
        no_holdout = [2021, 2022, 2023]
        tgs_nh = tgs_full[tgs_full["season"].isin(no_holdout)]
        with contextlib.redirect_stdout(io.StringIO()):
            ratings_nh, _ = build_pit_ratings(tgs_nh)

        # 2022-23 ratings must be identical
        r_full = ratings_full[ratings_full["season"] == 2022].set_index(["game_id", "team"])
        r_nh = ratings_nh[ratings_nh["season"] == 2022].set_index(["game_id", "team"])

        common = r_full.index.intersection(r_nh.index)
        assert len(common) > 100, f"Too few common rows: {len(common)}"

        for col in ["ev_att_for_per60", "ev_att_against_per60", "ev_xg_per_att_for"]:
            diff = (r_full.loc[common, col] - r_nh.loc[common, col]).abs()
            max_diff = diff.max()
            assert max_diff < 1e-10, (
                f"2022-23 {col} changed when holdout removed: max diff={max_diff:.2e}. "
                f"The league mean must be per-season, not all-season."
            )


class TestPerSeasonReset:
    """Ratings must reset at season boundaries (with carry-over, not continuous)."""

    def test_first_game_of_season_uses_carryover(self):
        """The first game of 2022-23 should NOT have the same n_prior_games as the last
        game of 2021-22 + 1."""
        tr = pd.read_parquet(ROOT / "nhl" / "data" / "sim" / "ratings" / "team_ratings.parquet")
        # Pick a team that played in both seasons
        team = "TOR"
        s21 = tr[(tr["team"] == team) & (tr["season"] == 2021)].sort_values("date")
        s22 = tr[(tr["team"] == team) & (tr["season"] == 2022)].sort_values("date")
        if len(s21) == 0 or len(s22) == 0:
            pytest.skip("Team not in both seasons")
        last_21 = s21.iloc[-1]["n_prior_games"]
        first_22 = s22.iloc[0]["n_prior_games"]
        # First game of 2022-23 should have n_prior_games = 0 (new season reset)
        assert first_22 == 0, (
            f"First game of 2022-23 has n_prior_games={first_22}, expected 0 (season reset). "
            f"Last game of 2021-22 had n_prior_games={last_21}."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
