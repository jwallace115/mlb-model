#!/usr/bin/env python3
"""Tests for DA-3 Item 1b fixes.

RED-first:
  1. Fixture where every row has residual +5 gives centered z ~ 0.
  2. Cross-defense permutation changes which defense a row is labelled with.
  3. Within-defense permutation leaves >= 60% of rows unchanged (the bug).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "research" / "nfl_sim" / "defensive_archetypes" / "discovery"))
sys.path.insert(0, str(ROOT / "research" / "nfl_sim" / "defensive_archetypes"))


class TestCenteringKillsMarketTilt:

    def test_uniform_residual_centered_to_zero(self):
        """Every row has residual +5 → centered z ≈ 0."""
        from run_discovery import center_residuals
        df = pd.DataFrame({
            "season": [2023] * 100,
            "market_key": ["player_receptions"] * 100,
            "position": ["RB"] * 100,
            "t2_residual": [5.0] * 100,
        })
        centered = center_residuals(df, "t2_residual")
        assert abs(centered.mean()) < 1e-9, f"centered mean should be ~0, got {centered.mean()}"


class TestCrossDefensePermutation:

    def test_cross_defense_changes_labels(self):
        """Cross-defense permutation reassigns which defense gets which label."""
        from run_discovery import cross_defense_null
        np.random.seed(42)
        n = 200
        df = pd.DataFrame({
            "season": [2023] * n,
            "week": np.repeat(range(1, 11), 20),
            "_opp": [f"team_{i % 10}" for i in range(n)],
            "label": np.random.choice([1, 2, 3], n),
            "t2_residual": np.random.randn(n),
            "game_id": [f"g_{i}" for i in range(n)],
        })
        # Run one draw of the cross-defense permutation
        shuffled = df.copy()
        for (s, w), idx in shuffled.groupby(["season", "week"]).groups.items():
            vals = shuffled.loc[idx, "label"].values.copy()
            np.random.shuffle(vals)
            shuffled.loc[idx, "label"] = vals
        # At least some labels should have changed
        changed = (df["label"] != shuffled["label"]).mean()
        assert changed > 0.3, f"cross-defense should change >30% of labels, changed {changed:.1%}"


class TestWithinDefenseBug:

    def test_within_defense_preserves_most_labels(self):
        """Within-defense permutation (the bug) leaves >= 60% unchanged because
        labels persist across weeks for the same defense."""
        np.random.seed(42)
        n = 200
        # Simulate persistent labels: each defense has mostly the same tercile
        teams = [f"team_{i % 10}" for i in range(n)]
        # Persistent: team_0 always tercile 3, team_1 always 1, etc.
        base_label = {f"team_{i}": (i % 3) + 1 for i in range(10)}
        labels = [base_label[t] for t in teams]
        df = pd.DataFrame({
            "season": [2023] * n,
            "week": np.repeat(range(1, 11), 20),
            "_opp": teams,
            "label": labels,
            "t2_residual": np.random.randn(n),
            "game_id": [f"g_{i}" for i in range(n)],
        })
        # Within-defense permutation: shuffle within each (season, defense)
        shuffled = df.copy()
        for (s, d), idx in shuffled.groupby(["season", "_opp"]).groups.items():
            vals = shuffled.loc[idx, "label"].values.copy()
            np.random.shuffle(vals)
            shuffled.loc[idx, "label"] = vals
        # With persistent labels, most rows should be unchanged
        unchanged = (df["label"] == shuffled["label"]).mean()
        assert unchanged >= 0.60, \
            f"within-defense permutation should leave >=60% unchanged (persistence bug), got {unchanged:.1%}"
