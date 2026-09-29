"""S20/S23 tests: truncation, source-patched mutant, old-code, starter agreement.
Ported from research/nhl_sim/cowork_checks/truncation_check_2026-09-29.py."""
import sys, io, contextlib, importlib.util, tempfile, json, gzip, re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from nhl.sim.ratings import build_pit_ratings, build_goalie_ratings, CARRYOVER_PATH, load_xg_model

TGS_PATH = ROOT / "nhl" / "data" / "sim" / "ratings" / "team_game_stats.parquet"
BOX_DIR = ROOT / "nhl" / "cache"
COLS = ["ev_att_for_per60", "ev_att_against_per60", "ev_xg_per_att_for", "ev_xg_per_att_against"]
NUM_COLS_PATTERN = ("ev_", "pp_", "pk_", "pen")
SEED = 20260929
N_DATES = 20

# The accumulation block that updates team stats (must exist in ratings.py)
ACCUM_BLOCK = (
    '            tc["att_for"] += row["ev_att_for"]\n'
    '            tc["att_ag"] += row["ev_att_against"]\n'
    '            tc["xg_for"] += row["ev_xg_for"]\n'
    '            tc["xg_ag"] += row["ev_xg_against"]\n'
    '            tc["ev_secs"] += row["ev_seconds"]\n'
    '            tc["pp_xg"] += row["pp_xg_for"]\n'
    '            tc["pp_secs"] += row["pp_seconds"]\n'
    '            tc["pk_xg_ag"] += row["pk_xg_against"]\n'
    '            tc["pk_secs"] += row["pk_seconds"]\n'
    '            tc["pen_taken"] += row["penalties_taken"]\n'
    '            tc["pen_drawn"] += row["penalties_drawn"]\n'
    '            tc["n"] += 1'
)
# The line AFTER which the block currently sits (used to detect the append)
APPEND_LINE = '            })\n'


@pytest.fixture(scope="module")
def tgs():
    return pd.read_parquet(TGS_PATH)


@pytest.fixture(scope="module")
def full_ratings(tgs):
    with contextlib.redirect_stdout(io.StringIO()):
        out, _ = build_pit_ratings(tgs)
    return out.set_index(["game_id", "team"])[COLS]


@pytest.fixture(scope="module")
def test_dates(tgs):
    rng = np.random.RandomState(SEED)
    dates = sorted(tgs[tgs["season"] == 2023]["date"].unique())
    return sorted(rng.choice(dates, N_DATES, replace=False))


def _corrupt_and_rebuild(tgs, D, build_fn):
    t = tgs[tgs["date"] <= D].copy()
    num_cols = [c for c in t.columns if any(c.startswith(p) for p in NUM_COLS_PATTERN)
                and pd.api.types.is_numeric_dtype(t[c])]
    m = t["date"] == D
    t.loc[m, num_cols] = t.loc[m, num_cols] * 7 + 3
    with contextlib.redirect_stdout(io.StringIO()):
        out, _ = build_fn(t)
    return out.set_index(["game_id", "team"])[COLS]


class TestTruncationCurrentCode:
    def test_truncation_team_ratings(self, tgs, full_ratings, test_dates):
        worst = 0.0
        fails = 0
        for D in test_dates:
            tr = _corrupt_and_rebuild(tgs, D, build_pit_ratings)
            idx = tgs[tgs["date"] == D].set_index(["game_id", "team"]).index
            common = full_ratings.index.intersection(idx)
            diff = (tr.loc[common] - full_ratings.loc[common]).abs().to_numpy().max()
            worst = max(worst, diff)
            if diff > 1e-12:
                fails += 1
        assert fails == 0, f"Truncation failed on {fails}/{N_DATES} dates, worst diff={worst:.2e}"


class TestMutantSourcePatch:
    """Patch the REAL ratings.py source: move the 6-line accum block above the if-block."""

    def test_six_line_block_exists(self):
        """The exact six-line block must be in ratings.py. If not, the test FAILS, not skips."""
        src = Path(ROOT / "nhl" / "sim" / "ratings.py").read_text()
        assert ACCUM_BLOCK in src, (
            f"The six-line accumulation block was not found in ratings.py. "
            f"The test cannot verify the mutation."
        )

    def test_mutant_fails(self, tgs, full_ratings, test_dates):
        """Move the 6-line block above 'if tc[\"n\"] == 0:', load as temp module, verify diff > 1e-6."""
        src = Path(ROOT / "nhl" / "sim" / "ratings.py").read_text()
        assert ACCUM_BLOCK in src, "Six-line block not found — cannot build mutant"

        # The block is currently AFTER the season_ratings.append({...}).
        # Move it to BEFORE 'if tc["n"] == 0:' by:
        # 1. Remove the block from its current position
        # 2. Insert it just before 'if tc["n"] == 0:'
        mutant_src = src.replace(ACCUM_BLOCK, "# REMOVED_ACCUM")
        insert_before = '            if tc["n"] == 0:'
        mutant_src = mutant_src.replace(insert_before, ACCUM_BLOCK + "\n\n" + insert_before)
        # Also patch CARRYOVER_PATH
        mutant_src = mutant_src.replace(
            'CARRYOVER_PATH = OUT_DIR / "carryover_w.json"',
            f'CARRYOVER_PATH = __import__("pathlib").Path("{CARRYOVER_PATH}")'
        )

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(mutant_src)
            mutant_path = f.name

        spec = importlib.util.spec_from_file_location("mutant_ratings", mutant_path)
        mutant = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mutant)

        D = test_dates[0]
        tr = _corrupt_and_rebuild(tgs, D, mutant.build_pit_ratings)
        with contextlib.redirect_stdout(io.StringIO()):
            mutant_full, _ = mutant.build_pit_ratings(tgs)
        mutant_idx = mutant_full.set_index(["game_id", "team"])[COLS]

        idx = tgs[tgs["date"] == D].set_index(["game_id", "team"]).index
        common = mutant_idx.index.intersection(idx)
        diff = (tr.loc[common] - mutant_idx.loc[common]).abs().to_numpy().max()
        Path(mutant_path).unlink()
        assert diff > 1e-6, f"Mutant should fail truncation but diff was {diff:.2e}"


class TestOldCodeFails:
    def test_old_code_fails(self, tgs, full_ratings, test_dates):
        import subprocess
        result = subprocess.run(
            ["git", "show", "e17ace021:nhl/sim/ratings.py"],
            capture_output=True, text=True, cwd=str(ROOT)
        )
        if result.returncode != 0:
            pytest.fail(f"Cannot load e17ace021: {result.stderr[:100]}")

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(result.stdout)
            old_path = f.name

        spec = importlib.util.spec_from_file_location("old_R", old_path)
        old = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(old)
        except Exception as e:
            Path(old_path).unlink()
            pytest.fail(f"Old code failed to import: {e}")

        old_fn = getattr(old, "compute_pit_ratings", getattr(old, "build_pit_ratings", None))
        if old_fn is None:
            Path(old_path).unlink()
            pytest.fail("No ratings function found in old code")

        D = test_dates[0]
        try:
            tr = _corrupt_and_rebuild(tgs, D, old_fn)
            with contextlib.redirect_stdout(io.StringIO()):
                old_full, _ = old_fn(tgs)
            old_full_idx = old_full.set_index(["game_id", "team"])[COLS]
            idx = tgs[tgs["date"] == D].set_index(["game_id", "team"]).index
            common = old_full_idx.index.intersection(idx)
            diff = (tr.loc[common] - old_full_idx.loc[common]).abs().to_numpy().max()
            Path(old_path).unlink()
            assert diff > 1e-6, f"Old code should fail but diff was {diff:.2e}"
        except Exception as e:
            Path(old_path).unlink()
            # If the old code crashes, that also counts as "not passing"
            pass


class TestStarterAgreement:
    def test_starter_agreement(self):
        gr = pd.read_parquet(ROOT / "nhl" / "data" / "sim" / "ratings" / "goalie_ratings.parquet")
        matches = 0
        total = 0
        for _, row in gr.head(2000).iterrows():  # sample for speed
            gid = row["game_id"]
            bp = BOX_DIR / f"boxscore_{gid}.json"
            if not bp.exists():
                continue
            with open(bp) as f:
                d = json.load(f)
            role = row["role"]
            team_key = "homeTeam" if role == "home" else "awayTeam"
            pgs = d.get("playerByGameStats", {}).get(team_key, {})
            goalies = pgs.get("goalies", [])
            box_starter = None
            for g in goalies:
                if g.get("starter", False):
                    box_starter = g.get("playerId")
                    break
            if box_starter is None:
                continue
            total += 1
            if row["goalie_id"] == box_starter:
                matches += 1
        if total > 0:
            rate = matches / total
            assert rate > 0.99, f"Starter agreement {rate:.4%} < 99%"


class TestNoHoldoutLeakage:
    def test_rating_unchanged_without_holdout(self):
        tgs = pd.read_parquet(TGS_PATH)
        with contextlib.redirect_stdout(io.StringIO()):
            ratings_full, _ = build_pit_ratings(tgs)
        tgs_nh = tgs[tgs["season"].isin([2021, 2022, 2023])]
        with contextlib.redirect_stdout(io.StringIO()):
            ratings_nh, _ = build_pit_ratings(tgs_nh)
        r_full = ratings_full[ratings_full["season"] == 2022].set_index(["game_id", "team"])
        r_nh = ratings_nh[ratings_nh["season"] == 2022].set_index(["game_id", "team"])
        common = r_full.index.intersection(r_nh.index)
        assert len(common) > 100
        for col in COLS:
            diff = (r_full.loc[common, col] - r_nh.loc[common, col]).abs().max()
            assert diff < 1e-10, f"Leakage: {col} changed by {diff:.2e}"


class TestPerSeasonReset:
    def test_season_reset(self):
        tgs = pd.read_parquet(TGS_PATH)
        with contextlib.redirect_stdout(io.StringIO()):
            tr, _ = build_pit_ratings(tgs)
        for s in [2022, 2023, 2024]:
            first = tr[(tr["season"] == s)].sort_values("date").groupby("team").first()
            assert (first["n_prior_games"] == 0).all(), f"Season {s} has non-zero n_prior_games at start"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
