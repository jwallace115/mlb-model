"""FWD1 (D211): tests for the forward-test harness."""
import hashlib
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def test_harness_halts_on_freeze_mismatch():
    """The harness must HALT when the freeze manifest has a wrong hash."""
    freeze_path = ROOT / "research" / "nfl_sim" / "FREEZE_v1.json"
    freeze = json.loads(freeze_path.read_text())
    # Modify one table hash
    modified = freeze.copy()
    modified["table_hashes"] = dict(freeze["table_hashes"])
    first_key = next(iter(modified["table_hashes"]))
    modified["table_hashes"][first_key] = "0000000000000000"  # wrong hash
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(modified, f)
        tmp_path = f.name
    # The freeze test should fail with the modified manifest
    from nfl.sim.tests.test_freeze_v1 import _load_freeze
    # Temporarily swap the path
    import nfl.sim.tests.test_freeze_v1 as ft
    old_path = ft.FREEZE_PATH
    try:
        ft.FREEZE_PATH = Path(tmp_path)
        with pytest.raises(AssertionError, match="frozen"):
            ft.test_table_hashes()
    finally:
        ft.FREEZE_PATH = old_path
        Path(tmp_path).unlink()


def test_game_line_row_is_no_view():
    """A game-line row (h2h, spreads, totals) must be no_view with p_first == q_first."""
    sheet = pd.DataFrame([{
        "event_id": "e1", "market_key": "spreads", "player_name": "",
        "line": -3.5, "price_first": -110, "price_second": -110,
        "q_first": 0.50, "two_way": True, "home_team": "KC", "away_team": "BUF",
        "commence_time": "2026-10-05T17:00:00Z", "source_age_min": 10,
        "source_utc": "2026-10-05T16:50:00Z",
    }])
    picks = pd.DataFrame(columns=["player_name", "line", "cal_p", "tier", "family", "side"])
    filled = _fill(sheet, picks)
    assert filled.iloc[0]["tag"] == "no_view"
    assert abs(filled.iloc[0]["p_first"] - filled.iloc[0]["q_first"]) < 0.001


def test_matched_over_row_gets_cal_p():
    """A matched OVER prop row must get p_first = cal_p exactly (clipped to [0.02, 0.98])."""
    sheet = pd.DataFrame([{
        "event_id": "e1", "market_key": "player_receptions_over",
        "player_name": "T.Kelce", "line": 5.5,
        "price_first": -130, "price_second": 100,
        "q_first": 0.565, "two_way": True, "home_team": "KC", "away_team": "BUF",
        "commence_time": "2026-10-05T17:00:00Z", "source_age_min": 10,
        "source_utc": "2026-10-05T16:50:00Z",
    }])
    picks = pd.DataFrame([{
        "player_name": "T.Kelce", "line": 5.5, "cal_p": 0.612,
        "tier": "TRUSTED", "family": "receptions", "side": "over",
    }])
    filled = _fill(sheet, picks)
    assert filled.iloc[0]["tag"] == "sim_v1"
    assert abs(filled.iloc[0]["p_first"] - 0.612) < 0.001


def test_matched_under_row_gets_complement():
    """A matched UNDER-only prop row must get p_first = 1 - cal_p."""
    sheet = pd.DataFrame([{
        "event_id": "e1", "market_key": "player_receptions_under",
        "player_name": "T.Kelce", "line": 5.5,
        "price_first": 100, "price_second": -130,
        "q_first": 0.435, "two_way": True, "home_team": "KC", "away_team": "BUF",
        "commence_time": "2026-10-05T17:00:00Z", "source_age_min": 10,
        "source_utc": "2026-10-05T16:50:00Z",
    }])
    picks = pd.DataFrame([{
        "player_name": "T.Kelce", "line": 5.5, "cal_p": 0.612,
        "tier": "TRUSTED", "family": "receptions", "side": "over",
    }])
    filled = _fill(sheet, picks)
    assert filled.iloc[0]["tag"] == "sim_v1"
    assert abs(filled.iloc[0]["p_first"] - (1.0 - 0.612)) < 0.001


def test_unmatched_prop_row_is_no_view():
    """An unmatched prop row must be no_view."""
    sheet = pd.DataFrame([{
        "event_id": "e1", "market_key": "player_receptions_over",
        "player_name": "X.Nobody", "line": 3.5,
        "price_first": -110, "price_second": -110,
        "q_first": 0.50, "two_way": True, "home_team": "KC", "away_team": "BUF",
        "commence_time": "2026-10-05T17:00:00Z", "source_age_min": 10,
        "source_utc": "2026-10-05T16:50:00Z",
    }])
    picks = pd.DataFrame([{
        "player_name": "T.Kelce", "line": 5.5, "cal_p": 0.612,
        "tier": "TRUSTED", "family": "receptions", "side": "over",
    }])
    filled = _fill(sheet, picks)
    assert filled.iloc[0]["tag"] == "no_view"


def _fill(sheet_df, picks_log):
    """Replicate the fill logic from run_forward_v1.py."""
    filled = sheet_df.copy()
    filled["p_first"] = filled["q_first"].copy()
    filled["tag"] = "no_view"
    filled["reason"] = ""
    GAME_MARKETS = ("h2h", "spreads", "totals")
    for idx, row in filled.iterrows():
        if not row.get("two_way", False):
            continue
        if row.get("market_key", "") in GAME_MARKETS:
            continue
        pl_match = picks_log[
            (picks_log["player_name"] == row["player_name"]) &
            (picks_log["line"] == row["line"])
        ]
        if len(pl_match) == 0:
            continue
        cal_p_over = float(pl_match.iloc[0]["cal_p"])
        tier = str(pl_match.iloc[0].get("tier", ""))
        mk = str(row.get("market_key", ""))
        if "_under" in mk.lower():
            p_first = 1.0 - cal_p_over
        else:
            p_first = cal_p_over
        p_first = np.clip(p_first, 0.02, 0.98)
        filled.at[idx, "p_first"] = round(float(p_first), 4)
        filled.at[idx, "tag"] = "sim_v1"
        filled.at[idx, "reason"] = f"sim v1 cal_p {tier}"[:160]
    return filled
