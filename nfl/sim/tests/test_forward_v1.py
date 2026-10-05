"""FWD1/FWD1b (D211/D215): tests for the forward-test harness.
All tests call the real functions from run_forward_v1.py."""
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from nfl.sim.run_forward_v1 import fill_sheet, anchor_sidecar, FAMILY_TO_MARKET


# ── D215(a) fill_sheet tests ─────────────────────────────────────────────────

def _sheet_row(player, market_key, line, q_first=0.50, two_way=True):
    return {"event_id": "e1", "market_key": market_key, "player_name": player,
            "line": line, "price_first": -110, "price_second": -110,
            "q_first": q_first, "two_way": two_way, "home_team": "KC", "away_team": "BUF",
            "commence_time": "2026-10-05T17:00:00Z", "source_age_min": 10,
            "source_utc": "2026-10-05T16:50:00Z"}


def _picks_row(player, family, line, cal_p, side="over", tier="TRUSTED",
               game_id="BUF@KC"):
    return {"player_name": player, "family": family, "line": line,
            "cal_p": cal_p, "side": side, "tier": tier, "game_id": game_id}


def test_fill_matches_on_market_not_just_line():
    """D215(a): a player with rush_attempts 9.5 AND player_reception_yds 9.5 on the
    sheet, and a rush_attempts 9.5 picks_log row: only the rush-attempts sheet row
    gets the sim's p; the reception_yds row stays no_view."""
    sheet = pd.DataFrame([
        _sheet_row("J.Doe", "player_rush_attempts", 9.5),
        _sheet_row("J.Doe", "player_reception_yds", 9.5),
    ])
    picks = pd.DataFrame([_picks_row("J.Doe", "rush_attempts", 9.5, 0.55)])
    filled, n = fill_sheet(sheet, picks)
    rush_row = filled[filled["market_key"] == "player_rush_attempts"].iloc[0]
    rec_row = filled[filled["market_key"] == "player_reception_yds"].iloc[0]
    assert rush_row["tag"] == "sim_v1"
    assert abs(rush_row["p_first"] - 0.55) < 0.001
    assert rec_row["tag"] == "no_view"
    assert n == 1


def test_fill_unmapped_family_stays_no_view():
    """D215(a): a QB pass_tds 1.5 row (family not in FAMILY_TO_MARKET) stays no_view."""
    sheet = pd.DataFrame([_sheet_row("P.Mahomes", "player_pass_tds", 1.5)])
    picks = pd.DataFrame([_picks_row("P.Mahomes", "anytime_td", 0.5, 0.30)])
    filled, n = fill_sheet(sheet, picks)
    assert filled.iloc[0]["tag"] == "no_view"
    assert n == 0


def test_fill_under_side_gives_complement():
    """D215(a): an 'under' picks_log row gives p_first = 1 - cal_p."""
    sheet = pd.DataFrame([_sheet_row("T.Kelce", "player_receptions", 5.5)])
    picks = pd.DataFrame([_picks_row("T.Kelce", "receptions", 5.5, 0.612, side="under")])
    filled, n = fill_sheet(sheet, picks)
    assert abs(filled.iloc[0]["p_first"] - (1.0 - 0.612)) < 0.001
    assert n == 1


def test_fill_game_line_always_no_view():
    """A game-line row is always no_view with p_first == q_first."""
    sheet = pd.DataFrame([_sheet_row("", "spreads", -3.5)])
    picks = pd.DataFrame(columns=["player_name", "family", "line", "cal_p", "side", "tier"])
    filled, n = fill_sheet(sheet, picks)
    assert filled.iloc[0]["tag"] == "no_view"
    assert abs(filled.iloc[0]["p_first"] - filled.iloc[0]["q_first"]) < 0.001


def test_fill_unmatched_prop_no_view():
    """An unmatched prop row is no_view."""
    sheet = pd.DataFrame([_sheet_row("X.Nobody", "player_receptions", 3.5)])
    picks = pd.DataFrame([_picks_row("T.Kelce", "receptions", 5.5, 0.612)])
    filled, n = fill_sheet(sheet, picks)
    assert filled.iloc[0]["tag"] == "no_view"
    assert n == 0


# ── D215(b) anchor_sidecar tests ─────────────────────────────────────────────

def test_anchor_sidecar_week2():
    """D215(b)/D226: the committed week-2 anchoring log -> 15 games, all anchored, max |miss| <= 0.35.
    D229: now passes actual lines dict (D226 requires it)."""
    al = pd.read_parquet(ROOT / "nfl" / "data" / "sim" / "outputs" / "week=2026_02" / "anchoring_log.parquet")
    # Build lines dict from the anchoring log's best iterations
    lines = {}
    for gname in al["game"].unique():
        g = al[al["game"] == gname]
        best = g.loc[(abs(g["err_m"]) + abs(g["err_t"])).idxmin()]
        # Reconstruct market targets from best iteration: spread ≈ margin - err_m
        lines[gname] = {
            "spread": round(float(best["margin"]) - float(best["err_m"]), 4),
            "total": round(float(best["total"]) - float(best["err_t"]), 4),
        }
    sidecar = anchor_sidecar(al, lines)
    assert len(sidecar) == 15, f"Expected 15 games, got {len(sidecar)}"
    assert sidecar["anchored"].all(), f"Unanchored games: {sidecar[~sidecar['anchored']]}"
    max_miss = max(sidecar["miss_m"].max(), sidecar["miss_t"].max())
    assert max_miss <= 0.35, f"max |miss| {max_miss:.2f} > 0.35"


def test_anchor_sidecar_missing_column():
    """D215(b): a missing column raises KeyError."""
    df = pd.DataFrame({"game": ["A"], "iter": [0], "margin": [0]})
    with pytest.raises(KeyError, match="missing"):
        anchor_sidecar(df, {})


# ── D215(e) freeze halt test ─────────────────────────────────────────────────

def test_harness_halts_on_freeze_mismatch():
    """The harness halts when FREEZE_v1.json has a wrong hash."""
    freeze_path = ROOT / "research" / "nfl_sim" / "FREEZE_v1.json"
    freeze = json.loads(freeze_path.read_text())
    modified = dict(freeze)
    modified["table_hashes"] = dict(freeze["table_hashes"])
    first_key = next(iter(modified["table_hashes"]))
    modified["table_hashes"][first_key] = "0000000000000000"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(modified, f)
        tmp_path = f.name
    import nfl.sim.tests.test_freeze_v1 as ft
    old_path = ft.FREEZE_PATH
    try:
        ft.FREEZE_PATH = Path(tmp_path)
        with pytest.raises(AssertionError, match="frozen"):
            ft.test_table_hashes()
    finally:
        ft.FREEZE_PATH = old_path
        Path(tmp_path).unlink()
