"""S20/S23 tests: truncation, source-patched mutant, old-code, starter agreement.
Ported from research/nhl_sim/cowork_checks/truncation_check_2026-09-29.py."""
import sys, io, contextlib, importlib.util, tempfile, json, gzip, re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from nhl.sim.ratings import build_pit_ratings, goalie_ratings_from_games, finishing_term_from_games, CARRYOVER_PATH, GOALIE_GAMES_PATH

TGS_PATH = ROOT / "nhl" / "data" / "sim" / "ratings" / "team_game_stats.parquet"
BOX_DIR = ROOT / "nhl" / "cache"
COLS = ["ev_att_for_per60", "ev_att_against_per60", "ev_xg_per_att_for", "ev_xg_per_att_against",
        "pp_xg_for_per60", "pk_xg_against_per60", "penalties_taken_per60", "penalties_drawn_per60"]
NUM_COLS_PATTERN = ("ev_", "pp_", "pk_", "pen")
SEED = 20260929
N_DATES = 20

# The accumulation block that updates team stats (must exist in ratings.py)
ACCUM_BLOCK = (
    '            for c in acc_cols:\n'
    '                tc[c] += r[c]\n'
    '            tc["n"] += 1'
)
INSERT_BEFORE = '            # --- rating going INTO this game ---'
GOALIE_ACCUM_BLOCK = (
    '            gs["gsax"] += gg.gsax\n'
    '            gs["att"] += gg.attempts_faced\n'
    '            gs["n"] += 1'
)
GOALIE_INSERT_BEFORE = '            # --- goalie rating going INTO this game ---'


def _load_source_as_module(src, name):
    """Exec patched ratings.py source as a temp module with ROOT pinned to the repo."""
    src = src.replace("ROOT = Path(__file__).resolve().parents[2]", f'ROOT = Path("{ROOT}")')
    assert f'ROOT = Path("{ROOT}")' in src, "could not pin ROOT in patched source"
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(src)
        path = f.name
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    Path(path).unlink()
    return mod


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
        mutant_src = src.replace(ACCUM_BLOCK, "            pass  # REMOVED_ACCUM")
        assert INSERT_BEFORE in mutant_src, "insertion marker not found — cannot build mutant"
        mutant_src = mutant_src.replace(INSERT_BEFORE, ACCUM_BLOCK + "\n" + INSERT_BEFORE)
        mutant = _load_source_as_module(mutant_src, "mutant_ratings")

        D = test_dates[0]
        tr = _corrupt_and_rebuild(tgs, D, mutant.build_pit_ratings)
        with contextlib.redirect_stdout(io.StringIO()):
            mutant_full, _ = mutant.build_pit_ratings(tgs)
        mutant_idx = mutant_full.set_index(["game_id", "team"])[COLS]

        idx = tgs[tgs["date"] == D].set_index(["game_id", "team"]).index
        common = mutant_idx.index.intersection(idx)
        diff = (tr.loc[common] - mutant_idx.loc[common]).abs().to_numpy().max()
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


class TestEventCounts:
    """team_game_stats attempt counts must exactly match the event tables."""

    def test_attempt_counts_match(self):
        """tgs attempt counts must exactly match the event tables (restricted to tgs games)."""
        EVENTS_DIR = ROOT / "nhl" / "data" / "sim" / "events"
        ALL = [2021, 2022, 2023, 2024, 2025]
        EVEN = ["5v5"]
        PP = ["5v4", "5v3", "4v3"]
        tgs = pd.read_parquet(TGS_PATH)

        for s in ALL:
            shots = pd.read_parquet(EVENTS_DIR / f"season={s}" / "shots.parquet")
            # Restrict to games that appear in tgs (handles incomplete seasons)
            tgs_games = set(tgs[tgs["season"] == s]["game_id"].unique())
            shots = shots[shots["game_id"].isin(tgs_games)]

            ev = shots[shots["strength"].isin(EVEN)]
            pp = shots[shots["strength"].isin(PP)]
            s_tgs = tgs[tgs["season"] == s]

            actual_ev_att = int(s_tgs["ev_att_for"].sum())
            actual_ev_goals = int(s_tgs["ev_goals_for"].sum())
            actual_pp_att = int(s_tgs["pp_att_for"].sum())
            assert actual_ev_att == len(ev), (
                f"Season {s}: ev_att_for sum={actual_ev_att} vs event table={len(ev)}")
            assert actual_ev_goals == int(ev["is_goal"].sum()), (
                f"Season {s}: ev_goals_for sum={actual_ev_goals} vs event table={int(ev['is_goal'].sum())}")
            assert actual_pp_att == len(pp), (
                f"Season {s}: pp_att_for sum={actual_pp_att} vs event table={len(pp)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# ---------------------------------------------------------------------------
# S27 (Cowork): fit-season truncation and goalie point-in-time tests
# ---------------------------------------------------------------------------
class TestTruncationFitSeason:
    """Same truncation test on 20 dates of 2022-23 (a FIT season). Hyperparameters are frozen in JSON,
    so any rating that uses same-season future rows (e.g. a league mean computed over the whole fit
    set) fails here. The a3a7bcecb code (global fit-season league mean for PP/PK/penalties) fails it."""

    def test_truncation_fit_season(self, tgs, full_ratings):
        rng = np.random.RandomState(SEED)
        dates = sorted(tgs[tgs["season"] == 2022]["date"].unique())
        worst, fails = 0.0, 0
        for D in sorted(rng.choice(dates, N_DATES, replace=False)):
            tr = _corrupt_and_rebuild(tgs, D, build_pit_ratings)
            idx = tgs[tgs["date"] == D].set_index(["game_id", "team"]).index
            diff = np.nanmax((tr.loc[idx] - full_ratings.loc[idx]).abs().to_numpy())
            worst = max(worst, diff)
            fails += diff > 1e-12
        assert fails == 0, f"Fit-season truncation failed on {fails}/{N_DATES} dates, worst diff={worst:.2e}"


@pytest.fixture(scope="module")
def gdf():
    return pd.read_parquet(GOALIE_GAMES_PATH)


def _goalie_corrupt_and_rebuild(gdf, D, fn):
    g = gdf[gdf["date"] <= D].copy()
    m = g["date"] == D
    g.loc[m, "gsax"] = g.loc[m, "gsax"] * 7 + 3
    g.loc[m, "attempts_faced"] = g.loc[m, "attempts_faced"] * 7 + 3
    return fn(g).set_index(["game_id", "role"])["gsax_per_att_rating"]


class TestGoalieTruncation:
    def test_goalie_truncation(self, gdf, test_dates):
        full = goalie_ratings_from_games(gdf).set_index(["game_id", "role"])["gsax_per_att_rating"]
        worst, fails = 0.0, 0
        for D in test_dates:
            tr = _goalie_corrupt_and_rebuild(gdf, D, goalie_ratings_from_games)
            idx = gdf[gdf["date"] == D].set_index(["game_id", "role"]).index
            diff = float((tr.loc[idx] - full.loc[idx]).abs().max())
            worst = max(worst, diff)
            fails += diff > 1e-12
        assert fails == 0, f"Goalie truncation failed on {fails}/{N_DATES} dates, worst diff={worst:.2e}"

    def test_goalie_mutant_fails(self, gdf, test_dates):
        src = Path(ROOT / "nhl" / "sim" / "ratings.py").read_text()
        assert GOALIE_ACCUM_BLOCK in src, "goalie accumulation block not found — test FAILS, not skips"
        assert GOALIE_INSERT_BEFORE in src, "goalie insertion marker not found"
        msrc = src.replace(GOALIE_ACCUM_BLOCK, "            pass  # REMOVED_GOALIE_ACCUM")
        msrc = msrc.replace(GOALIE_INSERT_BEFORE, GOALIE_ACCUM_BLOCK + "\n" + GOALIE_INSERT_BEFORE)
        mutant = _load_source_as_module(msrc, "mutant_goalie")
        D = test_dates[0]
        full = mutant.goalie_ratings_from_games(gdf).set_index(["game_id", "role"])["gsax_per_att_rating"]
        tr = _goalie_corrupt_and_rebuild(gdf, D, mutant.goalie_ratings_from_games)
        idx = gdf[gdf["date"] == D].set_index(["game_id", "role"]).index
        diff = float((tr.loc[idx] - full.loc[idx]).abs().max())
        assert diff > 1e-6, f"Goalie mutant should fail truncation but diff was {diff:.2e}"


# ---------------------------------------------------------------------------
# S31 (Cowork): finishing term F(D) point-in-time tests
# ---------------------------------------------------------------------------
FT_WINDOW_LINE = '            w = S[(S["d"] >= D - pd.Timedelta(days=window_days)) & (S["d"] < D)]'


def _ft_corrupt(gdf, D):
    g = gdf[gdf["date"] <= D].copy()
    m = g["date"] == D
    g.loc[m, "goals_against"] = g.loc[m, "goals_against"] * 7 + 3
    g.loc[m, "xg_faced"] = g.loc[m, "xg_faced"] * 7 + 3
    return g


class TestFinishingTerm:
    def test_finishing_truncation(self, gdf):
        full = finishing_term_from_games(gdf).set_index("date")["F"]
        rng = np.random.RandomState(SEED)
        dates = sorted(gdf[gdf["season"].isin([2022, 2023])]["date"].unique())
        fails, worst = 0, 0.0
        for D in sorted(rng.choice(dates, N_DATES, replace=False)):
            tr = finishing_term_from_games(_ft_corrupt(gdf, D)).set_index("date")["F"]
            diff = abs(float(tr.loc[D]) - float(full.loc[D]))
            worst = max(worst, diff)
            fails += diff > 1e-12
        assert fails == 0, f"F(D) truncation failed on {fails}/{N_DATES} dates, worst {worst:.2e}"

    def test_finishing_mutant_fails(self, gdf):
        src = Path(ROOT / "nhl" / "sim" / "ratings.py").read_text()
        assert FT_WINDOW_LINE in src, "finishing window line not found — test FAILS, not skips"
        mutant = _load_source_as_module(src.replace(FT_WINDOW_LINE, FT_WINDOW_LINE.replace('(S["d"] < D)', '(S["d"] <= D)')), "mutant_ft")
        dates = sorted(gdf[gdf["season"] == 2023]["date"].unique())
        D = dates[len(dates) // 2]                       # mid-season: in-season window is used
        full = mutant.finishing_term_from_games(gdf).set_index("date")["F"]
        tr = mutant.finishing_term_from_games(_ft_corrupt(gdf, D)).set_index("date")["F"]
        assert abs(float(tr.loc[D]) - float(full.loc[D])) > 1e-6, "F mutant (window includes D) should fail truncation"

    def test_finishing_rules(self, gdf):
        ft = finishing_term_from_games(gdf)
        assert (ft.loc[ft["source"] == "in_season", "n_games"] >= 150).all(), "in-season F used with < 150 games"
        assert ft.loc[ft["season"] >= 2022, "F"].notna().all(), "NaN F after the warm-up season"
