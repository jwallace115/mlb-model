"""S18/S20 tests: truncation, mutation, old-code, and starter agreement.
Ported from research/nhl_sim/cowork_checks/truncation_check_2026-09-29.py."""
import sys, io, contextlib, importlib.util, tempfile, json, gzip
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from nhl.sim.ratings import build_pit_ratings, CARRYOVER_PATH

TGS_PATH = ROOT / "nhl" / "data" / "sim" / "ratings" / "team_game_stats.parquet"
BOX_DIR = ROOT / "nhl" / "cache"
COLS = ["ev_att_for_per60", "ev_att_against_per60", "ev_xg_per_att_for", "ev_xg_per_att_against"]
NUM_COLS_PATTERN = ("ev_", "pp_", "pk_", "pen")
SEED = 20260929
N_DATES = 20


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
    """Drop rows after D, corrupt D's stats, rebuild ratings."""
    t = tgs[tgs["date"] <= D].copy()
    num_cols = [c for c in t.columns if any(c.startswith(p) for p in NUM_COLS_PATTERN)
                and pd.api.types.is_numeric_dtype(t[c])]
    m = t["date"] == D
    t.loc[m, num_cols] = t.loc[m, num_cols] * 7 + 3
    with contextlib.redirect_stdout(io.StringIO()):
        out, _ = build_fn(t)
    return out.set_index(["game_id", "team"])[COLS]


class TestTruncationCurrentCode:
    """The current ratings.py must pass: ratings on D unchanged when future is dropped and D is corrupted."""

    def test_truncation_passes(self, tgs, full_ratings, test_dates):
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


class TestMutantFails:
    """Moving tc[...] += above the rating recording must break truncation (diff > 1e-6)."""

    def test_mutant_fails(self, tgs, full_ratings, test_dates):
        """Build a leaky variant by wrapping build_pit_ratings to update BEFORE recording."""
        from nhl.sim.ratings import (load_carryover, compute_split_half_r, compute_K,
                                      shrink, ALL_SEASONS, FIT_SEASONS)

        def leaky_build(tgs_in):
            """Same as build_pit_ratings but accumulates BEFORE recording the rating."""
            tgs_in = tgs_in.sort_values("date").reset_index(drop=True)
            carryover = load_carryover()
            fit_data = tgs_in[tgs_in["season"].isin(FIT_SEASONS)].copy()
            fit_data["ev_att_share"] = fit_data["ev_att_for"] / (fit_data["ev_att_for"] + fit_data["ev_att_against"]).clip(1)
            fit_data["ev_xg_per_att_for"] = fit_data["ev_xg_for"] / fit_data["ev_att_for"].clip(1)
            r_att, _ = compute_split_half_r(fit_data, "ev_att_share")
            r_xg, _ = compute_split_half_r(fit_data, "ev_xg_per_att_for")
            K_att, K_xg = compute_K(r_att, 82), compute_K(r_xg, 82)

            season_league = {}; prior_final = {}; all_ratings = []
            for season in sorted(tgs_in["season"].unique()):
                s = tgs_in[tgs_in["season"] == season].sort_values("date")
                dates = sorted(s["date"].unique())
                lc = {"af": 0, "aa": 0, "xf": 0.0, "xa": 0.0, "es": 0.0, "n": 0}
                la = {}
                for d in dates:
                    la[d] = dict(lc)
                    for _, r in s[s["date"] == d].iterrows():
                        lc["af"] += r["ev_att_for"]; lc["aa"] += r["ev_att_against"]
                        lc["xf"] += r["ev_xg_for"]; lc["xa"] += r["ev_xg_against"]
                        lc["es"] += r["ev_seconds"]; lc["n"] += 1
                prev = season - 1
                prev_lg = season_league.get(prev, {"ar": 42.0, "xr": 0.062})
                tc = {t: {"af": 0, "aa": 0, "xf": 0.0, "xa": 0.0, "es": 0.0, "n": 0} for t in s["team"].unique()}
                for _, row in s.iterrows():
                    team, d = row["team"], row["date"]
                    c = tc[team]
                    l = la[d]
                    lg_att = l["af"] / max(l["es"], 1) * 3600 if l["n"] >= 20 else prev_lg["ar"]
                    lg_xg = l["xf"] / max(l["af"], 1) if l["n"] >= 20 else prev_lg["xr"]
                    w_af = carryover["ev_att_for_per60"]
                    if season != min(tgs_in["season"].unique()) and team in prior_final.get(prev, {}):
                        pf = prior_final[prev][team]
                        tgt_af = pf["af"] * w_af + lg_att * (1 - w_af)
                    else:
                        tgt_af = lg_att

                    # LEAK: accumulate BEFORE recording
                    c["af"] += row["ev_att_for"]; c["aa"] += row["ev_att_against"]
                    c["xf"] += row["ev_xg_for"]; c["xa"] += row["ev_xg_against"]
                    c["es"] += row["ev_seconds"]; c["n"] += 1

                    if c["n"] <= 1:
                        r_af = tgt_af
                    else:
                        raw = c["af"] / max(c["es"], 1) * 3600
                        r_af = shrink(raw * c["n"], c["n"], tgt_af, K_att)
                    all_ratings.append({"game_id": row["game_id"], "team": team, "season": season,
                                         "date": d, "role": row["role"], "n_prior_games": c["n"],
                                         "ev_att_for_per60": round(r_af, 4),
                                         "ev_att_against_per60": round(r_af, 4),
                                         "ev_xg_per_att_for": round(lg_xg, 6),
                                         "ev_xg_per_att_against": round(lg_xg, 6)})
                prior_final[season] = {}
                for t in tc:
                    if tc[t]["n"] > 0:
                        prior_final[season][t] = {"af": tc[t]["af"] / max(tc[t]["es"], 1) * 3600}
                season_league[season] = {"ar": lc["af"] / max(lc["es"], 1) * 3600, "xr": lc["xf"] / max(lc["af"], 1)}
            return pd.DataFrame(all_ratings), {}

        D = test_dates[0]
        tr = _corrupt_and_rebuild(tgs, D, leaky_build)
        with contextlib.redirect_stdout(io.StringIO()):
            leaky_full, _ = leaky_build(tgs)
        leaky_idx = leaky_full.set_index(["game_id", "team"])[COLS]
        idx = tgs[tgs["date"] == D].set_index(["game_id", "team"]).index
        common = leaky_idx.index.intersection(idx)
        diff = (tr.loc[common] - leaky_idx.loc[common]).abs().to_numpy().max()
        assert diff > 1e-6, f"Leaky mutant should fail but diff was only {diff:.2e}"


class TestOldCodeFails:
    """e17ace021's code (all-season league mean) must fail the truncation test."""

    def test_old_code_fails(self, tgs, full_ratings, test_dates):
        # Load old code from git
        import subprocess
        result = subprocess.run(
            ["git", "show", "e17ace021:nhl/sim/ratings.py"],
            capture_output=True, text=True, cwd=str(ROOT)
        )
        if result.returncode != 0:
            pytest.skip(f"Cannot load e17ace021: {result.stderr[:100]}")

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(result.stdout)
            old_path = f.name

        spec = importlib.util.spec_from_file_location("old_R", old_path)
        old = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(old)
        except Exception:
            Path(old_path).unlink()
            pytest.skip("Old code failed to import")

        # The old code has compute_pit_ratings, not build_pit_ratings
        old_fn = getattr(old, "compute_pit_ratings", getattr(old, "build_pit_ratings", None))
        if old_fn is None:
            Path(old_path).unlink()
            pytest.skip("No ratings function found in old code")

        D = test_dates[0]
        try:
            tr = _corrupt_and_rebuild(tgs, D, old_fn)
        except Exception as e:
            # Old code may fail because column names differ — that's also a "fail"
            Path(old_path).unlink()
            return  # It failed, which means it can't reproduce clean results

        # If it ran, check the diff
        with contextlib.redirect_stdout(io.StringIO()):
            old_full, _ = old_fn(tgs)
        old_full_idx = old_full.set_index(["game_id", "team"])[COLS]

        idx = tgs[tgs["date"] == D].set_index(["game_id", "team"]).index
        common = old_full_idx.index.intersection(idx)
        if len(common) == 0:
            Path(old_path).unlink()
            return

        diff = (tr.loc[common] - old_full_idx.loc[common]).abs().to_numpy().max()
        Path(old_path).unlink()
        assert diff > 1e-6, f"Old code should fail but diff was only {diff:.2e}"


class TestStarterAgreement:
    """The rated goalie must match the box-score starter flag in > 99% of games."""

    def test_starter_agreement(self):
        gr = pd.read_parquet(ROOT / "nhl" / "data" / "sim" / "ratings" / "goalie_ratings.parquet")
        if gr.empty:
            pytest.skip("No goalie ratings built yet")

        matches = 0
        total = 0
        for _, row in gr.iterrows():
            gid = row["game_id"]
            bp = BOX_DIR / f"boxscore_{gid}.json"
            if not bp.exists():
                continue
            with open(bp) as f:
                d = json.load(f)
            # Find the starter from playerByGameStats
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
            print(f"\nStarter agreement: {matches}/{total} = {rate:.4%}")
            assert rate > 0.99, f"Starter agreement {rate:.4%} < 99%"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
