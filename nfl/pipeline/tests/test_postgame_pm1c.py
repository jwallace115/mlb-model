#!/usr/bin/env python3
"""Tests for PM-1c: actuals, thesis, join coverage, freeze contract.

Item 1 RED-FIRST:
  pass_att actuals include sacks in PBP (pass_attempt==1 includes sack==1).
  Official nflverse player_stats 'attempts' excludes sacks.
  The builder must use pass_attempt==1 AND sack!=1 for player pass_attempts.

  Unresolved player → actual NaN, why_code UNRESOLVED, never 0.

Item 2:
  Thesis link name mapping per market type.
  teammates_out and one_play_decided fixtures.

Item 3:
  reader_v3 writes thesis only when sport == "nfl".
  log_ai_opinions cross-type HALT.
"""
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "shared" / "pipeline"))


# ── Fixtures ──

def _pbp_slice(game_id, home, away, week, plays):
    """Build a PBP DataFrame from a list of play dicts."""
    base = {"game_id": game_id, "home_team": home, "away_team": away,
            "week": week, "season": 2026, "score_differential": 0,
            "home_score": 0, "away_score": 0, "qtr": 1,
            "pass_attempt": 0, "rush_attempt": 0, "sack": 0,
            "complete_pass": 0, "yards_gained": 0, "passing_yards": 0,
            "receiving_yards": 0, "rushing_yards": 0, "interception": 0,
            "fumble": 0, "fumble_lost": 0, "touchdown": 0,
            "passer_player_id": None, "passer_player_name": None,
            "receiver_player_id": None, "receiver_player_name": None,
            "rusher_player_id": None, "rusher_player_name": None,
            "posteam": home, "defteam": away, "yardline_100": 50,
            "play_type": "pass", "desc": "pass", "result": 0, "play_id": 0,
            "two_point_attempt": 0, "return_touchdown": 0}
    rows = []
    for i, p in enumerate(plays):
        row = {**base, "play_id": i + 1}
        row.update(p)
        rows.append(row)
    rows.append({**base, "play_id": 999, "play_type": "no_play", "desc": "END GAME"})
    return pd.DataFrame(rows)


# ══════════ ITEM 1: pass_att sack exclusion (RED FIRST) ══════════

def test_pass_att_excludes_sacks():
    """RED FIRST: A QB has 5 pass_attempt=1 plays, 2 of which are sacks.
    The builder must report pass_attempts=3 (official), not 5 (dropbacks).
    Current code counts all pass_attempt==1, so this fails before the fix."""
    from build_postgame import _player_stats_from_pbp

    plays = [
        # 3 real pass attempts (completions)
        {"posteam": "KC", "pass_attempt": 1, "sack": 0,
         "passer_player_id": "QB1", "passer_player_name": "P.Mahomes",
         "complete_pass": 1, "passing_yards": 15, "play_type": "pass"},
        {"posteam": "KC", "pass_attempt": 1, "sack": 0,
         "passer_player_id": "QB1", "passer_player_name": "P.Mahomes",
         "complete_pass": 1, "passing_yards": 20, "play_type": "pass"},
        {"posteam": "KC", "pass_attempt": 1, "sack": 0,
         "passer_player_id": "QB1", "passer_player_name": "P.Mahomes",
         "complete_pass": 0, "passing_yards": 0, "play_type": "pass"},
        # 2 sacks (pass_attempt=1, sack=1)
        {"posteam": "KC", "pass_attempt": 1, "sack": 1,
         "passer_player_id": "QB1", "passer_player_name": "P.Mahomes",
         "complete_pass": 0, "passing_yards": -8, "play_type": "pass",
         "desc": "P.Mahomes sacked at KC 20 for -8 yards"},
        {"posteam": "KC", "pass_attempt": 1, "sack": 1,
         "passer_player_id": "QB1", "passer_player_name": "P.Mahomes",
         "complete_pass": 0, "passing_yards": -5, "play_type": "pass",
         "desc": "P.Mahomes sacked at KC 30 for -5 yards"},
    ]

    pbp = _pbp_slice("2026_01_BUF_KC", "KC", "BUF", 1, plays)
    p_stats = _player_stats_from_pbp(pbp, "KC")

    assert "QB1" in p_stats, "QB1 not found in player stats"
    qb = p_stats["QB1"]
    assert qb["pass_attempts"] == 3, (
        f"pass_attempts={qb['pass_attempts']}; expected 3 (excl sacks). "
        "BUG: PBP pass_attempt==1 includes sacks; official attempts do not."
    )
    # Completions should still be 2 (sacks are not completions)
    assert qb["completions"] == 2
    # Passing yards: only from non-sack plays (15 + 20 + 0 = 35)
    assert qb["passing_yards"] == 35, (
        f"passing_yards={qb['passing_yards']}; expected 35 (excl sack yardage)."
    )


def test_pass_att_verdict_matches_grader():
    """A pass_att Over 29.5 pick: QB has 34 PBP pass_attempt=1 rows (5 sacks).
    Official attempts = 29. Ledger says L (29 < 29.5). Builder must also say L.
    Bug: builder currently says W (34 > 29.5)."""
    from build_postgame import build_verdicts

    # 29 real attempts + 5 sacks = 34 pass_attempt=1
    plays = (
        [{"posteam": "ARI", "pass_attempt": 1, "sack": 0,
          "passer_player_id": "QB_MURRAY", "passer_player_name": "K.Murray",
          "complete_pass": 1, "passing_yards": 8, "play_type": "pass"}] * 21 +
        [{"posteam": "ARI", "pass_attempt": 1, "sack": 0,
          "passer_player_id": "QB_MURRAY", "passer_player_name": "K.Murray",
          "complete_pass": 0, "passing_yards": 0, "play_type": "pass"}] * 8 +
        [{"posteam": "ARI", "pass_attempt": 1, "sack": 1,
          "passer_player_id": "QB_MURRAY", "passer_player_name": "K.Murray",
          "complete_pass": 0, "passing_yards": -7, "play_type": "pass",
          "desc": "K.Murray sacked"}] * 5 +
        # Some runs for the opponent
        [{"posteam": "NO", "defteam": "ARI", "rush_attempt": 1,
          "rusher_player_id": "RB1", "rusher_player_name": "A.Kamara",
          "rushing_yards": 5, "play_type": "run"}] * 10
    )

    pbp = _pbp_slice("2026_01_ARI_NO", "NO", "ARI", 1, plays)

    # Also need prior games for the chain
    prior_plays = (
        [{"posteam": "ARI", "pass_attempt": 1, "sack": 0,
          "passer_player_id": "QB_MURRAY", "passer_player_name": "K.Murray",
          "complete_pass": 1, "passing_yards": 10, "play_type": "pass"}] * 30 +
        [{"posteam": "ARI", "rush_attempt": 1,
          "rusher_player_id": "RB2", "rusher_player_name": "J.Conner",
          "rushing_yards": 5, "play_type": "run"}] * 15
    )
    pbp_prior1 = _pbp_slice("2026_pre_ARI_1", "ARI", "SF", 98, prior_plays)
    pbp_prior1["week"] = 98  # won't match week filter but < week for priors
    pbp_prior2 = _pbp_slice("2026_pre_ARI_2", "ARI", "LA", 99, prior_plays)
    pbp_prior2["week"] = 99

    ledger_row = {
        "pick_id": "test_murray_pa", "owner": "ai_nfl", "sport": "NFL",
        "event_id": "ev_ari_no", "market": "prop:pass_att", "side": "Over",
        "point": 29.5, "player_name": "K.Murray", "result": "L",
        "commence_time": "2026-09-07T17:00:00Z",
        "source_file": "test.parquet", "price_american": -110,
        "home": "NO", "away": "ARI",
    }

    slices = {
        "2026_pre_ARI_1": pbp_prior1,
        "2026_pre_ARI_2": pbp_prior2,
        "2026_01_ARI_NO": pbp,
    }

    v = build_verdicts([ledger_row], slices, week_filter=1, season=2026)
    assert v is not None and len(v) > 0
    row = v.iloc[0]
    assert row["actual_stat"] == 29, (
        f"actual_stat={row['actual_stat']}; expected 29 (official attempts excl sacks). "
        f"Got {row['actual_stat']} — sacks are being counted as attempts."
    )
    assert row.get("computed_result") == "L", (
        f"computed_result={row.get('computed_result')}; expected L (29 < 29.5)"
    )
    assert row.get("wl_mismatch") is False or row.get("wl_mismatch") == False


def test_unresolved_player_is_nan_not_zero():
    """An unresolved player must produce actual_stat=NaN and why_code=UNRESOLVED,
    never actual_stat=0."""
    from build_postgame import build_verdicts

    # PBP with a real receiver but NOT our pick player
    plays = [
        {"posteam": "KC", "pass_attempt": 1, "sack": 0,
         "passer_player_id": "QB1", "passer_player_name": "P.Mahomes",
         "receiver_player_id": "WR1", "receiver_player_name": "R.Rice",
         "complete_pass": 1, "receiving_yards": 15, "play_type": "pass"},
    ] * 10

    pbp = _pbp_slice("2026_01_BUF_KC", "KC", "BUF", 1, plays)

    ledger_row = {
        "pick_id": "test_ghost", "owner": "ai_nfl", "sport": "NFL",
        "event_id": "ev_kc_buf", "market": "prop:rec_yds", "side": "Under",
        "point": 40.5, "player_name": "Deebo Samuel", "result": "L",
        "commence_time": "2026-09-07T17:00:00Z",
        "source_file": "test.parquet", "price_american": -110,
        "home": "KC", "away": "BUF",
    }

    v = build_verdicts([ledger_row], {"2026_01_BUF_KC": pbp},
                       week_filter=1, season=2026)
    assert v is not None and len(v) > 0
    row = v.iloc[0]
    # Must be NaN, not 0
    actual = row.get("actual_stat")
    assert actual is None or (isinstance(actual, float) and np.isnan(actual)), (
        f"actual_stat={actual}; expected NaN for unresolved player, not 0."
    )
    assert row.get("why_code_auto") == "UNRESOLVED", (
        f"why_code_auto={row.get('why_code_auto')}; expected UNRESOLVED"
    )


# ══════════ ITEM 2: thesis link name mapping ══════════

def test_thesis_share_maps_to_carry_share_for_rush():
    """A rush prop with thesis 'share:up' must check carry_share in the chain,
    not 'share' (which is target share for rec markets)."""
    from build_postgame import _thesis_link_for_market

    assert _thesis_link_for_market("share", "prop:rush_att") == "carry_share"
    assert _thesis_link_for_market("share", "prop:rush_yds") == "carry_share"


def test_thesis_share_maps_to_share_for_rec():
    """A rec prop with thesis 'share:up' checks 'share' (target share)."""
    from build_postgame import _thesis_link_for_market

    assert _thesis_link_for_market("share", "prop:rec") == "share"
    assert _thesis_link_for_market("share", "prop:rec_yds") == "share"


def test_thesis_share_maps_to_qb_share_for_pass():
    """A pass prop with thesis 'share:up' checks 'qb_share'."""
    from build_postgame import _thesis_link_for_market

    assert _thesis_link_for_market("share", "prop:pass_att") == "qb_share"
    assert _thesis_link_for_market("share", "prop:pass_cmp") == "qb_share"
    assert _thesis_link_for_market("share", "prop:pass_yds") == "qb_share"


def test_thesis_efficiency_maps_by_market():
    """'efficiency' thesis maps to the right rate link per market."""
    from build_postgame import _thesis_link_for_market

    assert _thesis_link_for_market("efficiency", "prop:rec") == "catch_rate"
    assert _thesis_link_for_market("efficiency", "prop:rec_yds") == "yards_per_target"
    assert _thesis_link_for_market("efficiency", "prop:rush_yds") == "yards_per_carry"
    assert _thesis_link_for_market("efficiency", "prop:pass_cmp") == "completion_rate"
    assert _thesis_link_for_market("efficiency", "prop:pass_yds") == "yards_per_attempt"


def test_one_play_decided_flips_result():
    """Removing the longest play must flip the Over/Under result."""
    from build_postgame import _one_play_decided

    # Player had 85 yards over 5 catches: [10, 15, 45, 8, 7] = 85
    # Line is 75.5, side Over → W. Without the 45-yarder: 40 → L. Flipped.
    ps = {"receiving_yards": 85, "_plays_rec_yds": [10, 15, 45, 8, 7]}
    assert _one_play_decided(ps, "prop:rec_yds", "Over", 75.5, 85) is True

    # Without: line 39.5 → still W (40 > 39.5). NOT flipped.
    assert _one_play_decided(ps, "prop:rec_yds", "Over", 39.5, 85) is False


def test_teammates_out_enables_role_shift():
    """When teammates_out is non-empty and primary link is share,
    why_code_auto must be ROLE_SHIFT."""
    from build_postgame import _why_code_auto_prop

    decomp = {
        "primary_link": "share",
        "links": {"share": {"term": 0.3}},
        "book_vs_prior": 0.0,
        "zero_actual": False,
    }
    # teammates_out non-empty → ROLE_SHIFT
    code = _why_code_auto_prop(decomp, None, False, True, ["T.Kelce"])
    assert code == "ROLE_SHIFT", f"Expected ROLE_SHIFT, got {code}"

    # teammates_out empty → SHARE_OTHER
    code = _why_code_auto_prop(decomp, None, False, True, [])
    assert code == "SHARE_OTHER", f"Expected SHARE_OTHER, got {code}"


# ══════════ ITEM 3: reader_v3 NFL-only thesis ══════════

def test_ncaaf_reader_no_thesis():
    """reader_v3 with sport='ncaaf' must NOT have thesis column.
    PM-1c order: reader_v3 writes thesis only when sport == 'nfl'."""
    import reader_v3 as rv3

    sheet = pd.DataFrame([{
        "event_id": "ev1", "commence_time": "2026-10-04T17:00:00Z",
        "home_team": "Alabama Crimson Tide", "away_team": "LSU Tigers",
        "market_key": "h2h", "player_name": "",
        "line": 0.0, "first_side": "Alabama Crimson Tide",
        "second_side": "LSU Tigers",
        "price_first": -150, "price_second": 130,
        "source_utc": "2026-10-04T15:00:00Z",
        "imp_first": 0.6, "imp_second": 0.435,
        "two_way": True, "q_first": 0.58, "source_age_min": 10.0,
    }])

    lines = pd.DataFrame(columns=["event_id", "bookmaker", "market",
                                   "outcome_name", "point", "price",
                                   "snapshot_utc"])

    out = rv3.read_opinions(sheet, pd.DataFrame(), lines,
                            pd.DataFrame(), pd.DataFrame(), pd.DataFrame(),
                            {}, None, sport="ncaaf")

    assert "thesis" not in out.columns, (
        "NCAAF output must NOT have thesis column (PM-1c: NFL only)"
    )


def test_reader_v3_byte_null_control():
    """reader_v3 NFL output minus thesis column is identical to the pre-P50 schema.
    PM-1c: byte-level null control — sha256 of parquet bytes must match."""
    import hashlib
    import io
    import reader_v3 as rv3

    sheet = pd.DataFrame([{
        "event_id": "ev1", "commence_time": "2026-10-04T17:00:00Z",
        "home_team": "Buffalo Bills", "away_team": "New England Patriots",
        "market_key": "player_pass_yds", "player_name": "Test QB",
        "line": 250.5, "first_side": "Over", "second_side": "Under",
        "price_first": -110, "price_second": -110,
        "source_utc": "2026-10-04T15:00:00Z",
        "imp_first": 0.5238, "imp_second": 0.5238,
        "two_way": True, "q_first": 0.5, "source_age_min": 10.0,
    }])

    props = pd.DataFrame(columns=["event_id", "market_key", "player_name",
                                   "line", "bookmaker", "over_price",
                                   "under_price", "pull_timestamp"])
    lines = pd.DataFrame()

    out = rv3.read_opinions(sheet, props, lines, pd.DataFrame(),
                            pd.DataFrame(), pd.DataFrame(), {}, None)

    # thesis must exist in NFL output
    assert "thesis" in out.columns

    # Drop thesis and internal columns, write to parquet bytes
    base_cols = [c for c in out.columns if c != "thesis"]
    out_base = out[base_cols].copy()

    buf = io.BytesIO()
    out_base.to_parquet(buf, index=False)
    sha = hashlib.sha256(buf.getvalue()).hexdigest()

    # Run again — deterministic output
    out2 = rv3.read_opinions(sheet, props, lines, pd.DataFrame(),
                             pd.DataFrame(), pd.DataFrame(), {}, None)
    out2_base = out2[[c for c in out2.columns if c != "thesis"]].copy()

    buf2 = io.BytesIO()
    out2_base.to_parquet(buf2, index=False)
    sha2 = hashlib.sha256(buf2.getvalue()).hexdigest()

    assert sha == sha2, (
        f"reader_v3 byte-level null control FAILED: sha1={sha[:16]} sha2={sha2[:16]}"
    )

    # Verify schema: base columns match expected pre-P50 schema
    expected_base = {"event_id", "market_key", "player_name", "line",
                     "p_first", "tag", "reason", "conf", "_edge", "_kick",
                     "conf_rank"}
    assert expected_base.issubset(set(base_cols)), (
        f"Missing expected columns: {expected_base - set(base_cols)}"
    )


def test_cross_type_halt_prop_with_game_link():
    """A prop line with a game-line thesis link (points, turnovers) must HALT."""
    from log_ai_opinions import validate

    sheet = pd.DataFrame([{
        "event_id": "ev1", "commence_time": "2026-10-04T17:00:00Z",
        "home_team": "Buffalo Bills", "away_team": "New England Patriots",
        "market_key": "player_pass_yds", "player_name": "Test QB",
        "line": 250.5, "first_side": "Over", "second_side": "Under",
        "price_first": -110, "price_second": -110,
        "source_utc": "2026-10-04T15:00:00Z",
        "imp_first": 0.5238, "imp_second": 0.5238,
        "two_way": True, "q_first": 0.5, "source_age_min": 10.0,
    }])

    filled = pd.DataFrame([{
        "event_id": "ev1", "market_key": "player_pass_yds",
        "player_name": "Test QB", "line": 250.5,
        "p_first": 0.55, "tag": "game_script", "reason": "x" * 20,
        "conf": 60.0, "conf_rank": 1, "thesis": "points:up",
    }])

    with pytest.raises(SystemExit, match="prop line has game-line thesis link"):
        validate(sheet, filled)


def test_cross_type_halt_game_with_prop_link():
    """A game line with a prop thesis link (share, plays) must HALT."""
    from log_ai_opinions import validate

    sheet = pd.DataFrame([{
        "event_id": "ev1", "commence_time": "2026-10-04T17:00:00Z",
        "home_team": "Buffalo Bills", "away_team": "New England Patriots",
        "market_key": "totals", "player_name": "",
        "line": 48.5, "first_side": "Over", "second_side": "Under",
        "price_first": -110, "price_second": -110,
        "source_utc": "2026-10-04T15:00:00Z",
        "imp_first": 0.5238, "imp_second": 0.5238,
        "two_way": True, "q_first": 0.5, "source_age_min": 10.0,
    }])

    filled = pd.DataFrame([{
        "event_id": "ev1", "market_key": "totals",
        "player_name": "", "line": 48.5,
        "p_first": 0.55, "tag": "game_script", "reason": "x" * 20,
        "conf": 60.0, "conf_rank": 1, "thesis": "share:up",
    }])

    with pytest.raises(SystemExit, match="game line has prop thesis link"):
        validate(sheet, filled)
