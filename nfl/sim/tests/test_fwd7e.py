"""D275 (FWD7e): ChatGPT audit #17 — PBP identity fields validated on every raw row, in every
season any builder aggregates, and audit #17's two requirement survivors. No parametrize
(CLAUDE.md)."""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from nfl.sim.tests.test_fwd7a import _depth_world  # noqa: E402


def _world(tmp_path, tag):
    (tmp_path / tag).mkdir()
    return _depth_world(tmp_path / tag, False)


def _second_play(d, edit, season=2026):
    """Add a second, later play to an otherwise valid week-3 game g3 and corrupt one field."""
    f = d / f"pbp_{season}.parquet"
    p = pd.read_parquet(f)
    row = p[p["game_id"] == "g3"].iloc[[0]].copy()
    p = pd.concat([p, row], ignore_index=True)
    p = edit(p, len(p) - 1)
    p.to_parquet(f, index=False)


def test_one_null_week_on_a_later_row_halts(tmp_path, monkeypatch):
    """Audit #17 A1: one play's week set to null (float column) inside a valid game passed
    the grouped checks (nunique skips NaN; the deduplicated row was valid) and the usage
    groupby dropped that play: 16 target shares and 17 real-worker probabilities moved."""
    d, U, rosters, injuries, depth = _world(tmp_path, "w")
    monkeypatch.setattr(U, "PBP_DIR", d)

    def null_week(p, i):
        p["week"] = p["week"].astype("float64")
        p.loc[i, "week"] = None
        return p
    _second_play(d, null_week)
    with pytest.raises(RuntimeError, match="pbp_2026.parquet: invalid game identities — 1 rows with "
                                           "week missing or not an integer in 1-22 \\(row index \\[3\\]\\)"):
        U.build_active_universe(rosters, injuries, depth)
    with pytest.raises(RuntimeError, match="week missing"):
        U.load_pbp()


def test_nullable_int64_na_season_halts(tmp_path, monkeypatch):
    """Audit #17 A1: a nullable-Int64 <NA> season: `p["season"] != s` is <NA> and .any()
    skipped it."""
    d, U, rosters, injuries, depth = _world(tmp_path, "s")
    monkeypatch.setattr(U, "PBP_DIR", d)

    def na_season(p, i):
        p["season"] = p["season"].astype("Int64")
        p.loc[i, "season"] = pd.NA
        return p
    _second_play(d, na_season)
    with pytest.raises(RuntimeError, match="1 rows with season missing or != 2026 \\(row index \\[3\\]\\)"):
        U.build_active_universe(rosters, injuries, depth)


def test_missing_or_blank_game_id_halts_in_history(tmp_path, monkeypatch):
    """Audit #17 A1, historical form: a null game_id in a season with no snapshot was skipped
    by groupby("game_id") and the play dropped from the priors. Also a blank game_id and a
    non-integer or out-of-range week."""
    for i, edit in enumerate((lambda v: v.assign(game_id=[None] + list(v["game_id"][1:])),
                              lambda v: v.assign(game_id=["  "] + list(v["game_id"][1:])),
                              lambda v: v.assign(week=[2.5] + list(v["week"][1:])),
                              lambda v: v.assign(week=[23] + list(v["week"][1:])))):
        d, U, rosters, injuries, depth = _world(tmp_path, f"h{i}")
        monkeypatch.setattr(U, "PBP_DIR", d)
        h = pd.DataFrame([{"season": 2025, "week": w, "game_id": f"h{w}", "game_date": dd}
                          for w, dd in ((1, "2025-09-04"), (2, "2025-09-11"), (3, "2025-09-18"))])
        edit(h).to_parquet(d / "pbp_2025.parquet", index=False)
        with pytest.raises(RuntimeError, match="pbp_2025.parquet: invalid game identities"):
            U.load_pbp()


def test_every_aggregated_season_is_validated_even_outside_the_built_seasons(tmp_path, monkeypatch):
    """load_pbp validates each season file it reads (2020-2026), not only the seasons the
    active universe is built for; ratings.load_all_pbp does the same."""
    import nfl.sim.ratings as RT
    d, U, *_ = _world(tmp_path, "x")
    monkeypatch.setattr(U, "PBP_DIR", d)
    monkeypatch.setattr(RT, "PBP_DIR", d)
    pd.DataFrame([{"season": 2020, "week": None, "game_id": "o1", "game_date": "2020-09-10"}]
                 ).to_parquet(d / "pbp_2020.parquet", index=False)
    with pytest.raises(RuntimeError, match="pbp_2020.parquet: invalid game identities"):
        U.load_pbp()
    # ratings validates ITS OWN PBP_DIR (survivor: validating usage's directory instead)
    monkeypatch.setattr(U, "PBP_DIR", tmp_path / "x" / "elsewhere")
    with pytest.raises(RuntimeError, match="pbp_2020.parquet: invalid game identities"):
        RT.load_all_pbp()


def test_clean_rows_pass_and_the_validated_week_is_integral(tmp_path, monkeypatch):
    d, U, *_ = _world(tmp_path, "c")
    monkeypatch.setattr(U, "PBP_DIR", d)
    p = pd.read_parquet(d / "pbp_2026.parquet")
    p.assign(week=p["week"].astype("float64"), season=p["season"].astype("Int64")
             ).to_parquet(d / "pbp_2026.parquet", index=False)
    g = U._pbp_game_dates(2026)
    assert g["week"].dtype == "int64" and sorted(g["week"]) == [1, 2, 3]


# ── audit #17 requirement survivors ───────────────────────────────────────────

def _rostered(rosters, season, week):
    return pd.concat([rosters, rosters[rosters["week"] == 1].assign(season=season, week=week)],
                     ignore_index=True)


def test_a_rostered_postseason_week_without_pbp_halts(tmp_path, monkeypatch):
    """Survivor: cutoffs required only for weeks <= 18."""
    d, U, rosters, injuries, depth = _world(tmp_path, "p")
    monkeypatch.setattr(U, "PBP_DIR", d)
    pd.DataFrame([{"season": 2025, "week": w, "game_id": f"h{w}", "game_date": f"2025-09-{3 + w:02d}"}
                  for w in (1, 2)]).to_parquet(d / "pbp_2025.parquet", index=False)
    r = _rostered(_rostered(_rostered(rosters, 2025, 1), 2025, 2), 2025, 19)
    with pytest.raises(RuntimeError, match="no valid week cutoff for season 2025 weeks \\[19\\]"):
        U.build_active_universe(r, injuries, depth)


def test_an_older_rostered_season_without_pbp_halts(tmp_path, monkeypatch):
    """Survivor: the requirement skipped seasons before 2025."""
    d, U, rosters, injuries, depth = _world(tmp_path, "o")
    monkeypatch.setattr(U, "PBP_DIR", d)
    pd.DataFrame([{"season": 2023, "week": 1, "game_id": "o1", "game_date": "2023-09-07"}]
                 ).to_parquet(d / "pbp_2023.parquet", index=False)
    r = _rostered(_rostered(rosters, 2023, 1), 2023, 2)
    with pytest.raises(RuntimeError, match="no valid week cutoff for season 2023 weeks \\[2\\]"):
        U.build_active_universe(r, injuries, depth)
