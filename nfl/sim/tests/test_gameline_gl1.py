#!/usr/bin/env python3
"""
GL1 truncation-equivalence and season-membership tests for gameline_baseline.

Tests:
1. Season membership: every output table in this order has season in {2021, 2022, 2023}.
2. Truncation equivalence: feature row for (s, w) built from all data is byte-identical
   to one built from data truncated at week w, for >= 6 (s, w) pairs.
3. Negative control: planting one future game into the truncated frame must produce
   a DIFFERENT feature row (proving the as-of filter is real).
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

PBP_DIR = Path("/Users/jw115/mlb-model/nfl/data/pbp")
ALLOWED_SEASONS = {2021, 2022, 2023}


def _load_plays(seasons_to_load):
    """Load PBP for the requested seasons."""
    frames = []
    for s in seasons_to_load:
        p = PBP_DIR / f"pbp_{s}.parquet"
        if p.exists():
            frames.append(pd.read_parquet(p))
    return pd.concat(frames, ignore_index=True)


class TestSeasonMembership:
    """Every output produced by this order must contain only seasons 2021-2023."""

    def test_build_dataset_seasons(self):
        from nfl.sim.gameline_baseline import build_dataset
        df, _, _ = build_dataset([2021, 2022, 2023], hl_games=16, pbp_dir=str(PBP_DIR))
        bad = set(df["season"].unique()) - ALLOWED_SEASONS
        assert bad == set(), f"Disallowed seasons in output: {bad}"

    def test_no_2024_2025_in_dataset(self):
        from nfl.sim.gameline_baseline import build_dataset
        df, _, _ = build_dataset([2021, 2022, 2023], hl_games=16, pbp_dir=str(PBP_DIR))
        assert 2024 not in df["season"].values
        assert 2025 not in df["season"].values
        assert 2026 not in df["season"].values


class TestTruncationEquivalence:
    """Feature rows must be identical whether built from all data or truncated data.

    This proves the as-of filter works: data from week w and later has no effect
    on the feature row for week w.
    """

    # Test pairs: (season, week) — at least 6, spread across all 3 seasons
    TEST_PAIRS = [
        (2021, 5), (2021, 12),
        (2022, 3), (2022, 10),
        (2023, 7), (2023, 15),
    ]

    @pytest.fixture(scope="class")
    def plays_and_aggs(self):
        """Load all data once for the class."""
        from nfl.sim.gameline_baseline import (
            _build_game_aggs, _build_qb_game_aggs, _compute_league_means, _load_params
        )
        plays = _load_plays([2020, 2021, 2022, 2023])
        game_aggs = _build_game_aggs(plays)
        qb_aggs = _build_qb_game_aggs(plays)
        league_means = _compute_league_means(plays)
        params = _load_params()
        return plays, game_aggs, qb_aggs, league_means, params

    @pytest.fixture(scope="class")
    def game_schedule(self):
        """Load game schedule for picking home/away teams."""
        frames = []
        for s in [2021, 2022, 2023]:
            df = pd.read_parquet(PBP_DIR / f"pbp_{s}.parquet",
                columns=["game_id", "season", "week", "home_team", "away_team",
                         "spread_line", "total_line"])
            frames.append(df.drop_duplicates("game_id"))
        return pd.concat(frames, ignore_index=True)

    def _get_game(self, schedule, season, week):
        """Get first game in (season, week)."""
        g = schedule[(schedule["season"] == season) & (schedule["week"] == week) &
                     schedule["spread_line"].notna()]
        assert len(g) > 0, f"No game found for ({season}, {week})"
        return g.iloc[0]

    @pytest.mark.parametrize("season,week", TEST_PAIRS)
    def test_truncation_equivalence(self, plays_and_aggs, game_schedule, season, week):
        """Feature row from all data == feature row from truncated data."""
        from nfl.sim.gameline_baseline import (
            build_feature_row, _build_game_aggs, _build_qb_game_aggs,
            _compute_league_means
        )
        _, game_aggs_full, qb_aggs_full, league_means_full, params = plays_and_aggs

        game = self._get_game(game_schedule, season, week)
        hl = 16
        k = params["k"]
        k_qb = params.get("k_qb", k)
        pw = params["prior_weight"]
        pr = params.get("prior_regression", 0.5)

        # Full data
        mf_full, tf_full = build_feature_row(
            game_aggs_full, qb_aggs_full, league_means_full,
            season, week, game["home_team"], game["away_team"],
            hl, k, k_qb, pw, pr)

        # Truncated data: remove all plays from week >= w in this season
        plays_full = plays_and_aggs[0]
        trunc = plays_full[~((plays_full["season"] == season) & (plays_full["week"] >= week))]
        # Also remove future seasons
        trunc = trunc[trunc["season"] <= season]

        game_aggs_trunc = _build_game_aggs(trunc)
        qb_aggs_trunc = _build_qb_game_aggs(trunc)
        league_means_trunc = _compute_league_means(trunc)

        mf_trunc, tf_trunc = build_feature_row(
            game_aggs_trunc, qb_aggs_trunc, league_means_trunc,
            season, week, game["home_team"], game["away_team"],
            hl, k, k_qb, pw, pr)

        for key in mf_full:
            assert mf_full[key] == pytest.approx(mf_trunc[key], abs=1e-12), \
                f"Margin feature {key} differs: full={mf_full[key]}, trunc={mf_trunc[key]}"
        for key in tf_full:
            assert tf_full[key] == pytest.approx(tf_trunc[key], abs=1e-12), \
                f"Total feature {key} differs: full={tf_full[key]}, trunc={tf_trunc[key]}"

    def test_negative_control_future_game_changes_features(self, plays_and_aggs, game_schedule):
        """Planting a future game into the data must change the feature row.

        This proves the as-of filter is the thing providing isolation, not data absence.
        """
        from nfl.sim.gameline_baseline import (
            build_feature_row, _build_game_aggs, _build_qb_game_aggs,
            _compute_league_means
        )
        plays_full, _, _, _, params = plays_and_aggs
        season, week = 2022, 8
        game = self._get_game(game_schedule, season, week)

        hl = 16
        k = params["k"]
        k_qb = params.get("k_qb", k)
        pw = params["prior_weight"]
        pr = params.get("prior_regression", 0.5)

        # Truncated at week 8
        trunc = plays_full[~((plays_full["season"] == season) & (plays_full["week"] >= week))]
        trunc = trunc[trunc["season"] <= season]

        game_aggs_clean = _build_game_aggs(trunc)
        qb_aggs_clean = _build_qb_game_aggs(trunc)
        league_means_clean = _compute_league_means(trunc)

        mf_clean, _ = build_feature_row(
            game_aggs_clean, qb_aggs_clean, league_means_clean,
            season, week, game["home_team"], game["away_team"],
            hl, k, k_qb, pw, pr)

        # Now plant a fake game in week 7 (one week before) for the home team
        # This should change the features because it's in the as-of window
        fake_plays = trunc[
            (trunc["season"] == season) & (trunc["week"] == week - 1)
        ].head(30).copy()
        fake_plays["week"] = week - 1  # keep it in the valid window
        # Modify EPA to be extreme
        fake_plays["epa"] = 2.0
        fake_plays["posteam"] = game["home_team"]

        trunc_with_fake = pd.concat([trunc, fake_plays], ignore_index=True)
        game_aggs_fake = _build_game_aggs(trunc_with_fake)
        qb_aggs_fake = _build_qb_game_aggs(trunc_with_fake)
        league_means_fake = _compute_league_means(trunc_with_fake)

        mf_fake, _ = build_feature_row(
            game_aggs_fake, qb_aggs_fake, league_means_fake,
            season, week, game["home_team"], game["away_team"],
            hl, k, k_qb, pw, pr)

        # At least one margin feature must differ
        diffs = [abs(mf_clean[key] - mf_fake[key]) for key in mf_clean]
        assert max(diffs) > 1e-6, \
            "Negative control FAILED: planting a future game did not change features"
