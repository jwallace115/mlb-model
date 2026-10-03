"""D276 (FWD7f): ChatGPT audit #18 — play-level admission checks on every raw PBP row, numeric
identity dtypes, and the week-zero survivor. No parametrize (CLAUDE.md)."""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def _plays():
    """A valid miniature season: an administrative row, a completed pass, an incomplete pass
    without a receiver, a sack (pass play, no receiver), a run, a no-play penalty."""
    base = {"season": 2025, "week": 1, "game_id": "g1", "game_date": "2025-09-04"}
    rows = [
        dict(play_id=1, play_type=None, posteam=None, defteam=None, complete_pass=0, pass_attempt=0,
             rush_attempt=0, receiver_player_id=None, passer_player_id=None, rusher_player_id=None),
        dict(play_id=2, play_type="pass", posteam="KC", defteam="CAR", complete_pass=1, pass_attempt=1,
             rush_attempt=0, receiver_player_id="00-1", passer_player_id="00-q", rusher_player_id=None),
        dict(play_id=3, play_type="pass", posteam="KC", defteam="CAR", complete_pass=0, pass_attempt=1,
             rush_attempt=0, receiver_player_id=None, passer_player_id="00-q", rusher_player_id=None),
        dict(play_id=4, play_type="pass", posteam="KC", defteam="CAR", complete_pass=0, pass_attempt=1,
             rush_attempt=0, receiver_player_id=None, passer_player_id="00-q", rusher_player_id=None),
        dict(play_id=5, play_type="run", posteam="KC", defteam="CAR", complete_pass=0, pass_attempt=0,
             rush_attempt=1, receiver_player_id=None, passer_player_id=None, rusher_player_id="00-3"),
        dict(play_id=6, play_type="no_play", posteam="KC", defteam="CAR", complete_pass=0, pass_attempt=1,
             rush_attempt=0, receiver_player_id=None, passer_player_id="00-q", rusher_player_id=None),
    ]
    return pd.DataFrame([{**base, **r} for r in rows])


def _check(tmp_path, monkeypatch, df, season=2025):
    import nfl.sim.usage as U
    monkeypatch.setattr(U, "PBP_DIR", tmp_path)
    df.to_parquet(tmp_path / f"pbp_{season}.parquet", index=False)
    return U._pbp_game_dates(season)


def test_valid_plays_including_keyless_legitimate_rows_are_admitted(tmp_path, monkeypatch):
    g = _check(tmp_path, monkeypatch, _plays())
    assert g["game_id"].tolist() == ["g1"]


def _bad(tmp_path, monkeypatch, i, col, val, match):
    p = _plays()
    p.loc[i, col] = val
    with pytest.raises(RuntimeError, match=match):
        _check(tmp_path, monkeypatch, p)


def test_a_completed_pass_without_posteam_halts(tmp_path, monkeypatch):
    """Audit #18 A1: posteam=None on one completed pass passed every check; the usage groupby
    dropped the target and 17 real-worker probabilities moved."""
    _bad(tmp_path, monkeypatch, 1, "posteam", None, "inadmissible plays — 1 rows: pass/run play without posteam")


def test_a_run_without_defteam_halts(tmp_path, monkeypatch):
    _bad(tmp_path, monkeypatch, 4, "defteam", None, "pass/run play without defteam")


def test_a_flagged_play_without_play_type_halts(tmp_path, monkeypatch):
    _bad(tmp_path, monkeypatch, 1, "play_type", None, "pass/rush flag without play_type")
    _bad(tmp_path, monkeypatch, 4, "play_type", None, "pass/rush flag without play_type")


def test_a_completed_pass_without_receiver_or_as_a_run_halts(tmp_path, monkeypatch):
    _bad(tmp_path, monkeypatch, 1, "receiver_player_id", None, "completed pass without receiver")
    _bad(tmp_path, monkeypatch, 1, "play_type", "run", "completed pass that is not a pass play")


def test_a_pass_without_passer_or_run_without_rusher_halts(tmp_path, monkeypatch):
    _bad(tmp_path, monkeypatch, 2, "passer_player_id", None, "pass play without passer")
    _bad(tmp_path, monkeypatch, 4, "rusher_player_id", None, "run play without rusher")


def test_a_file_with_play_type_but_without_an_admission_column_halts(tmp_path, monkeypatch):
    with pytest.raises(RuntimeError, match="admission columns missing \\['defteam'\\]"):
        _check(tmp_path, monkeypatch, _plays().drop(columns=["defteam"]))


def test_both_loaders_run_the_admission_check(tmp_path, monkeypatch):
    import nfl.sim.usage as U
    import nfl.sim.ratings as RT
    p = _plays()
    p.loc[1, "posteam"] = None
    p.to_parquet(tmp_path / "pbp_2025.parquet", index=False)
    monkeypatch.setattr(U, "PBP_DIR", tmp_path)
    monkeypatch.setattr(RT, "PBP_DIR", tmp_path)
    with pytest.raises(RuntimeError, match="inadmissible plays"):
        U.load_pbp()
    monkeypatch.setattr(U, "PBP_DIR", tmp_path / "elsewhere")
    with pytest.raises(RuntimeError, match="inadmissible plays"):
        RT.load_all_pbp()


def test_identity_columns_must_be_numeric(tmp_path, monkeypatch):
    """Audit #18: a season stored as strings passed the coerced row check and then matched no
    `season == s` row downstream."""
    with pytest.raises(RuntimeError, match="column season is stored as \\w+, not a number"):
        _check(tmp_path, monkeypatch, _plays().assign(season="2025"))
    with pytest.raises(RuntimeError, match="column week is stored as \\w+, not a number"):
        _check(tmp_path, monkeypatch, _plays().assign(week="1"))


def test_week_zero_halts(tmp_path, monkeypatch):
    """Survivor N1 (audit #18): `wk < 1` weakened to `wk < 0`."""
    with pytest.raises(RuntimeError, match="week missing or not an integer in 1-22"):
        _check(tmp_path, monkeypatch, _plays().assign(week=0))


# ── D278: audit #19 A1 ────────────────────────────────────────────────────────

def test_blank_or_whitespace_keys_and_unknown_teams_halt(tmp_path, monkeypatch):
    """Audit #19 A1: posteam="" on one completed pass passed (isna() misses empty strings)
    and moved 18 calibrated probabilities on the real IND@WAS worker (max 0.0452)."""
    _bad(tmp_path, monkeypatch, 1, "posteam", "", "empty or whitespace-only posteam")
    _bad(tmp_path, monkeypatch, 4, "defteam", "  ", "empty or whitespace-only defteam")
    _bad(tmp_path, monkeypatch, 1, "receiver_player_id", " ", "empty or whitespace-only receiver_player_id")
    _bad(tmp_path, monkeypatch, 2, "passer_player_id", "", "empty or whitespace-only passer_player_id")
    _bad(tmp_path, monkeypatch, 4, "rusher_player_id", "", "empty or whitespace-only rusher_player_id")
    _bad(tmp_path, monkeypatch, 1, "play_type", "", "empty or whitespace-only play_type")
    _bad(tmp_path, monkeypatch, 1, "posteam", "XYZ", "team key outside the 32 nflverse codes")
    _bad(tmp_path, monkeypatch, 0, "defteam", "kc", "team key outside the 32 nflverse codes")


def test_y3_a_lower_case_posteam_halts(tmp_path, monkeypatch):
    """Audit #20 Y3: the team domain is case-sensitive (real PBP uses upper case)."""
    _bad(tmp_path, monkeypatch, 1, "posteam", "kc", "team key outside the 32 nflverse codes")
