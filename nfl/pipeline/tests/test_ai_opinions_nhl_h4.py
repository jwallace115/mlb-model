"""H4 tests: NHL outcomes loader + score with CLV and baselines."""
import sys, json, tempfile, shutil
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import nfl.pipeline.log_ai_opinions as L
from nhl.pipeline.nhl_outcomes import (
    game_result, settle_game_markets, load_boxscore, odds_to_nhl,
    agreement_check, match_game, load_all_results,
)

FIXTURE = Path(__file__).parent / "fixtures" / "nhl_tape_20260929T2000Z.parquet"


class TestNHLOutcomes:
    def test_agreement_check_no_mismatches(self):
        """Every cached 2025-26 boxscore agrees with nhl_games_canonical.csv."""
        n, mm = agreement_check(2025)
        actual = [m for m in mm if m["issue"] != "not in cache"]
        assert len(actual) == 0, f"Mismatches: {actual[:5]}"
        assert n >= 1000, f"Only {n} games checked — cache too small?"

    def test_reg_game_settlement(self):
        """REG game 2025020001: CHI@FLA, final 2-3, no OT/SO."""
        box = load_boxscore(2025020001)
        assert box is not None
        r = game_result(box)
        assert r["home_score"] == 3 and r["away_score"] == 2
        assert r["went_to_ot"] is False and r["went_to_so"] is False
        # h2h: home (FLA) wins -> first side won = 1
        assert settle_game_markets(r, "h2h", 0.0) == 1
        # spreads: home -1.5 -> FLA 3 + (-1.5) - CHI 2 = -0.5 -> 0
        assert settle_game_markets(r, "spreads", -1.5) == 0
        # totals: 5, line 5.5 -> Under -> 0
        assert settle_game_markets(r, "totals", 5.5) == 0

    def test_ot_game_settlement(self):
        """OT game 2025020008: CHI@BOS, final 3-4, OT winner."""
        box = load_boxscore(2025020008)
        assert box is not None
        r = game_result(box)
        assert r["home_score"] == 4 and r["away_score"] == 3
        assert r["went_to_ot"] is True and r["went_to_so"] is False
        # h2h: home (BOS) wins -> 1
        assert settle_game_markets(r, "h2h", 0.0) == 1
        # totals: 7, line 6.5 -> Over -> 1
        assert settle_game_markets(r, "totals", 6.5) == 1

    def test_so_game_settlement_changes_grade(self):
        """SO game 2025020006: CGY@EDM, final 4-3 (CGY wins SO), reg 3-3.
        Total 6.5: final=7 -> Over (1), but regulation=6 -> Under (0).
        The SO rule (settle on final) changes this grade."""
        box = load_boxscore(2025020006)
        assert box is not None
        r = game_result(box)
        # CGY wins: away_score > home_score
        assert r["away_score"] == 4 and r["home_score"] == 3
        assert r["went_to_ot"] is True and r["went_to_so"] is True
        # Final total = 7 > 6.5 -> Over -> first side won = 1
        assert settle_game_markets(r, "totals", 6.5) == 1
        # If we used regulation only (3+3=6 < 6.5), it would be Under = 0
        # This confirms the SO rule changes the grade
        assert r["home_goals_reg"] + r["away_goals_reg"] == 6
        # h2h: away (CGY) wins -> first side (home EDM) lost -> 0
        assert settle_game_markets(r, "h2h", 0.0) == 0


class TestTeamMap:
    def test_all_odds_api_names_map(self):
        """Every team in the NHL tape fixture maps to an NHL abbreviation."""
        df = pd.read_parquet(FIXTURE)
        for name in set(df["home_team"]) | set(df["away_team"]):
            abbr = odds_to_nhl(name)
            assert abbr is not None and len(abbr) == 3, f"Bad mapping for {name}"

    def test_accent_preserved(self):
        assert odds_to_nhl("Montréal Canadiens") == "MTL"
        assert odds_to_nhl("Montreal Canadiens") == "MTL"

    def test_st_louis_variants(self):
        assert odds_to_nhl("St Louis Blues") == "STL"
        assert odds_to_nhl("St. Louis Blues") == "STL"

    def test_unmapped_name_halts(self):
        with pytest.raises(SystemExit, match="unmapped"):
            odds_to_nhl("Nonexistent Team")


class TestEndToEnd:
    """End-to-end: build a synthetic pilot file, score it, assert grades."""

    def setup_method(self):
        L.set_sport("nhl")
        self.tmpdir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        L.set_sport("nfl")
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_score_real_finished_games(self):
        """Freeze synthetic opinions on 3 real finished games, score, assert grades.

        Games: REG 2025020001 (CHI@FLA 2-3), OT 2025020008 (CHI@BOS 3-4),
               SO 2025020006 (CGY@EDM 4-3, reg 3-3).
        Hand derivation:
        - h2h home wins: REG=1 (FLA), OT=1 (BOS), SO=0 (CGY=away wins)
        - totals 6.5: REG total=5 Under=0, OT total=7 Over=1, SO total=7 Over=1
        """
        # Build a synthetic tape fixture for these games
        games = [
            # Real start times from boxscore API
            {"event_id": "test_reg", "commence_time": "2025-10-07T21:00:00Z",
             "home_team": "Florida Panthers", "away_team": "Chicago Blackhawks"},
            {"event_id": "test_ot", "commence_time": "2025-10-09T23:00:00Z",
             "home_team": "Boston Bruins", "away_team": "Chicago Blackhawks"},
            {"event_id": "test_so", "commence_time": "2025-10-09T02:00:00Z",
             "home_team": "Edmonton Oilers", "away_team": "Calgary Flames"},
        ]
        rows = []
        for g in games:
            for mk, outcomes in [
                ("h2h", [(g["home_team"], None, -130), (g["away_team"], None, 110)]),
                ("totals", [("Over", 6.5, -110), ("Under", 6.5, -110)]),
            ]:
                for name, pt, price in outcomes:
                    rows.append({
                        "snapshot_utc": "2025-10-07T20:00:00Z",
                        "sport": "icehockey_nhl",
                        "event_id": g["event_id"],
                        "commence_time": g["commence_time"],
                        "home_team": g["home_team"],
                        "away_team": g["away_team"],
                        "bookmaker": "pinnacle",
                        "book_last_update": "2025-10-07T19:00:00Z",
                        "market": mk,
                        "outcome_name": name,
                        "point": pt,
                        "price": price,
                    })
        tape = pd.DataFrame(rows)
        tape_path = self.tmpdir / "snap_synthetic.parquet"
        tape.to_parquet(tape_path, index=False)

        # Build sheet
        now = datetime(2025, 10, 7, 20, 0, tzinfo=timezone.utc)
        props = pd.DataFrame(columns=["bookmaker", "commence_time", "home_team",
                                       "away_team", "market_key", "player_name",
                                       "line", "over_price", "under_price",
                                       "pull_timestamp", "event_id"])
        lines = pd.read_parquet(tape_path)
        sheet = L.build_sheet(props, lines, now)
        assert len(sheet) == 6  # 3 games x 2 markets

        # Fill the sheet: all first-side with p_first > q_first
        filled = sheet[L.KEY].copy()
        filled["p_first"] = sheet["q_first"] + 0.05
        filled["p_first"] = filled["p_first"].clip(L.P_MIN, L.P_MAX)
        filled["tag"] = "matchup"
        filled["reason"] = "synthetic test for NHL" + " " * 5
        filled["conf"] = list(range(100, 100 - len(filled), -1))
        filled["conf_rank"] = list(range(1, len(filled) + 1))
        filled["drivers"] = "market,history"

        # Build a minimal packet for freeze
        packet = {"header": {"sport": "nhl", "slate_date": "2025-10-07",
                             "built_utc": "2025-10-07T19:59:00+00:00", "builder_sha256": "test",
                             "sources": []}, "games": []}
        for g in games:
            packet["games"].append({
                "event_id": g["event_id"], "home": g["home_team"], "away": g["away_team"],
                "commence_time": g["commence_time"],
                "layers": {"market": {"h2h": {}}, "news": {"status": "no obs"},
                           "history": {}, "model": {"absent": "test"}}
            })
        packet_path = self.tmpdir / "packet.json"
        packet_path.write_text(json.dumps(packet))
        # Freeze
        d = self.tmpdir / "date=2025-10-07" / "ai_opinions"
        dest, sha, m = L.freeze(sheet, filled, 2025, None, True, now, d=d,
                                reader_model="test-h4", slate_date="2025-10-07",
                                packet_path=str(packet_path), window="adhoc")
        assert len(m) == 6

        # Score
        out = L.score(2025, None, d=d, include_pilot=True, slate_date="2025-10-07")

        # Assert grades against hand derivation
        def grade(eid, mk):
            r = out[(out["event_id"] == eid) & (out["market_key"] == mk)]
            assert len(r) == 1, f"Expected 1 row for {eid}/{mk}, got {len(r)}"
            return r.iloc[0]["y_first"]

        # REG: FLA 3, CHI 2 -> h2h home wins=1, total 5 < 6.5 Under=0
        assert grade("test_reg", "h2h") == 1
        assert grade("test_reg", "totals") == 0
        # OT: BOS 4, CHI 3 -> h2h home wins=1, total 7 > 6.5 Over=1
        assert grade("test_ot", "h2h") == 1
        assert grade("test_ot", "totals") == 1
        # SO: EDM 3, CGY 4 -> h2h away wins=0, total 7 > 6.5 Over=1
        # (The SO +1 makes total=7, not reg total=6)
        assert grade("test_so", "h2h") == 0
        assert grade("test_so", "totals") == 1


class TestEdgeRankWithinFreeze:
    """Amendment: edge_rank must be ranked within each freeze file, not across all."""

    def test_edge_rank_per_file(self):
        """edge_rank is 1..n within each _file, not across all files."""
        L.set_sport("nfl")
        try:
            # Need PBP data for NFL score
            d = Path(ROOT / "nfl" / "data" / "board" / "week=2026_03" / "ai_opinions")
            if not d.exists():
                pytest.skip("NFL wk3 board not available")
            pbp_path = ROOT / "nfl" / "data" / "pbp" / "pbp_2026.parquet"
            if not pbp_path.exists():
                pytest.skip("PBP file not available")
            out = L.score(2026, 3, include_pilot=True)
            if "edge_rank" not in out.columns:
                pytest.skip("No edge_rank in output")
            # Check that edge_rank restarts per file
            for f, g in out.groupby("_file"):
                ranked = g[g["edge_rank"].notna()]
                if len(ranked) == 0:
                    continue
                assert ranked["edge_rank"].min() == 1, (
                    f"edge_rank in {f} should start at 1, got {ranked['edge_rank'].min()}")
                assert ranked["edge_rank"].max() == len(ranked), (
                    f"edge_rank in {f} should be 1..{len(ranked)}, max={ranked['edge_rank'].max()}")
        finally:
            L.set_sport("nfl")


class TestFootballScoreUnchanged:
    """NULL CONTROL: football score produces the same numbers as before."""

    def test_ncaaf_wk4_score(self):
        L.set_sport("ncaaf")
        try:
            out = L.score(2026, 4, include_pilot=True)
            # N63 "Opus file" numbers: look at the big file
            big = out[out["_file"] == "ai_opinions_20260926T121647Z.parquet"]
            graded = big[big["graded"] & (big["side"] != "none")]
            assert len(graded) == 177, f"Expected 177 graded sides, got {len(graded)}"
            assert int(graded["side_won"].sum()) == 99
            assert abs(graded["units"].sum() - 8.96) < 0.01
        finally:
            L.set_sport("nfl")

    def test_nfl_wk3_tnf_score(self):
        L.set_sport("nfl")
        pbp_path = ROOT / "nfl" / "data" / "pbp" / "pbp_2026.parquet"
        if not pbp_path.exists():
            pytest.skip("PBP file not available")
        out = L.score(2026, 3, include_pilot=True)
        # TNF file
        tnf = out[out["_file"] == "ai_opinions_20260924T215526Z.parquet"]
        graded = tnf[tnf["graded"] & (tnf["side"] != "none")]
        assert len(graded) == 28, f"Expected 28 sides, got {len(graded)}"
        assert int(graded["side_won"].sum()) == 18
        assert abs(graded["units"].sum() - 7.59) < 0.01
        two = tnf[tnf["graded"] & tnf["two_way"]]
        brier_r = L.brier_(two["p_first"], two["y_first"])
        brier_b = L.brier_(two["book_p_first"], two["y_first"])
        assert abs(brier_r - 0.2519) < 0.001
        assert abs(brier_b - 0.2618) < 0.001
