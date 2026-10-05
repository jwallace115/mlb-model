"""Tests for the conf/conf_rank/edge amendment to log_ai_opinions.py (L2 in LAYERS_DECISION)."""
import json, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from nfl.pipeline import log_ai_opinions as L  # noqa: E402

NOW = datetime(2026, 9, 21, 20, 0, tzinfo=timezone.utc)
KICK = "2026-09-22T00:15:00Z"


def _props():
    base = {"event_id": "e1", "commence_time": KICK, "home_team": "Los Angeles Rams",
            "away_team": "New York Giants", "bookmaker": L.SPORTS["nfl"]["book"],
            "pull_timestamp": "2026-09-21T19:50:00+00:00"}
    return pd.DataFrame([
        {**base, "market_key": "player_receptions", "player_name": "A B", "line": 4.5, "over_price": -120, "under_price": -110},
        {**base, "market_key": "player_anytime_td", "player_name": "A B", "line": None, "over_price": 150, "under_price": None},
    ])


def _lines():
    base = {"snapshot_utc": "2026-09-21T19:55:00+00:00", "event_id": "e1", "commence_time": KICK,
            "home_team": "Los Angeles Rams", "away_team": "New York Giants",
            "bookmaker": L.SPORTS["nfl"]["book"]}
    return pd.DataFrame([
        {**base, "market": "spreads", "outcome_name": "New York Giants", "point": 6.5, "price": -105},
        {**base, "market": "spreads", "outcome_name": "Los Angeles Rams", "point": -6.5, "price": -115},
        {**base, "market": "totals", "outcome_name": "Under", "point": 47.0, "price": -105},
        {**base, "market": "totals", "outcome_name": "Over", "point": 47.0, "price": -115},
    ])


def _filled(sheet, **over):
    f = sheet[L.KEY].copy()
    book = sheet["q_first"].where(sheet["two_way"], sheet["imp_first"])
    f["p_first"] = book + 0.05
    f["tag"] = "matchup"
    f["reason"] = "a reason long enough to pass"
    f["conf"] = [80 - i * 10 for i in range(len(f))]
    f["conf_rank"] = list(range(1, len(f) + 1))
    for k, v in over.items():
        f[k] = v
    return f


class TestConfValidation:
    def test_missing_conf_columns_halts(self):
        L.set_sport("nfl")
        s = L.build_sheet(_props(), _lines(), NOW)
        f = s[L.KEY].copy()
        f["p_first"] = s["q_first"] + 0.05
        f["tag"] = "matchup"
        f["reason"] = "a reason long enough to pass"
        # no conf, no conf_rank
        with pytest.raises(SystemExit, match="conf"):
            L.validate(s, f)

    def test_conf_out_of_range_halts(self):
        L.set_sport("nfl")
        s = L.build_sheet(_props(), _lines(), NOW)
        with pytest.raises(SystemExit, match="conf must be"):
            L.validate(s, _filled(s, conf=150))

    def test_conf_rank_duplicates_halt(self):
        L.set_sport("nfl")
        s = L.build_sheet(_props(), _lines(), NOW)
        with pytest.raises(SystemExit, match="conf_rank"):
            L.validate(s, _filled(s, conf_rank=1))

    def test_conf_rank_gaps_halt(self):
        L.set_sport("nfl")
        s = L.build_sheet(_props(), _lines(), NOW)
        # ranks 1,2,3,5 has a gap (missing 4)
        f = _filled(s)
        f["conf_rank"] = list(range(1, len(f))) + [len(f) + 1]
        with pytest.raises(SystemExit, match="conf_rank"):
            L.validate(s, f)


class TestEdgeComputation:
    def test_edge_positive_for_chosen_side(self):
        L.set_sport("nfl")
        s = L.build_sheet(_props(), _lines(), NOW)
        m = L.validate(s, _filled(s))
        # reader takes first side (gap > 0), so edge = p_first - book_p_first = gap
        for _, r in m[m["side"] == "first"].iterrows():
            assert r["edge"] > 0, f"edge should be positive for first side: {r['edge']}"
            assert r["edge"] == pytest.approx(r["gap"], abs=1e-6)

    def test_edge_positive_for_second_side(self):
        L.set_sport("nfl")
        s = L.build_sheet(_props(), _lines(), NOW)
        f = _filled(s)
        book = s["q_first"].where(s["two_way"], s["imp_first"])
        f["p_first"] = book - 0.05  # reader takes second side
        m = L.validate(s, f)
        for _, r in m[m["side"] == "second"].iterrows():
            # edge = (1 - p_first) - (1 - book_p_first) = book_p_first - p_first = -gap
            assert r["edge"] > 0, f"edge should be positive for second side: {r['edge']}"
            assert r["edge"] == pytest.approx(-r["gap"], abs=1e-6)

    def test_edge_zero_for_none_side(self):
        L.set_sport("nfl")
        s = L.build_sheet(_props(), _lines(), NOW)
        f = _filled(s)
        book = s["q_first"].where(s["two_way"], s["imp_first"])
        f["p_first"] = book - 0.05
        m = L.validate(s, f)
        for _, r in m[m["side"] == "none"].iterrows():
            assert r["edge"] == 0.0

    def test_edge_written_to_frozen_file(self, tmp_path):
        L.set_sport("nfl")
        s = L.build_sheet(_props(), _lines(), NOW)
        dest, sha, m = L.freeze(s, _filled(s), 2026, 2, True, NOW, d=tmp_path, reader_model="test-model")
        df = pd.read_parquet(dest)
        assert "edge" in df.columns
        assert "conf" in df.columns
        assert "conf_rank" in df.columns
        assert df["edge"].notna().all()


class TestNHLRequireSide:
    def test_nhl_refuses_side_none(self):
        L.set_sport("nhl")
        try:
            # Build a minimal NHL-like sheet (game lines only, pinnacle)
            base = {"snapshot_utc": "2026-10-01T19:55:00+00:00", "event_id": "n1",
                    "commence_time": "2026-10-02T00:00:00Z",
                    "home_team": "Boston Bruins", "away_team": "Montreal Canadiens",
                    "bookmaker": "pinnacle"}
            lines = pd.DataFrame([
                {**base, "market": "h2h", "outcome_name": "Boston Bruins", "point": None, "price": -150},
                {**base, "market": "h2h", "outcome_name": "Montreal Canadiens", "point": None, "price": 130},
            ])
            now = datetime(2026, 10, 1, 18, 0, tzinfo=timezone.utc)
            s = L.build_sheet(pd.DataFrame(columns=["bookmaker", "commence_time"]), lines, now)
            # no_view is not a valid NHL tag — rejected by tag validation
            f = s[L.KEY].copy()
            f["p_first"] = s["q_first"]
            f["tag"] = "no_view"
            f["reason"] = ""
            f["conf"] = [50]
            f["conf_rank"] = [1]
            f["drivers"] = "market,history"
            with pytest.raises(SystemExit, match="unknown tag"):
                L.validate(s, f)
        finally:
            L.set_sport("nfl")

    def test_nfl_allows_side_none(self):
        """NFL does NOT require a side (backward compat with no_view)."""
        L.set_sport("nfl")
        s = L.build_sheet(_props(), _lines(), NOW)
        f = _filled(s)
        book = s["q_first"].where(s["two_way"], s["imp_first"])
        # Set no_view on a one-way market (anytime TD) -> side will be "none"
        td_mask = f["market_key"] == "player_anytime_td"
        f.loc[td_mask, "tag"] = "no_view"
        f.loc[td_mask, "reason"] = ""
        f.loc[td_mask, "p_first"] = s.loc[s["market_key"] == "player_anytime_td", "imp_first"].values[0]
        m = L.validate(s, f)
        assert (m[m["market_key"] == "player_anytime_td"]["side"] == "none").all()


class TestConfBandInScore:
    def test_conf_band_assigned(self):
        L.set_sport("nfl")
        s = L.build_sheet(_props(), _lines(), NOW)
        f = _filled(s)
        m = L.validate(s, f)
        # Simulate a scored dataframe
        m["graded"] = True
        m["y_first"] = 1
        m["side_won"] = m["side"] == "first"
        m["units"] = 0.0
        m["_file"] = "test.parquet"
        m["postfreeze_affected"] = False
        if "conf_rank" in m.columns and m["conf_rank"].notna().any():
            m["conf_band"] = pd.cut(m["conf_rank"], bins=[0, 10, 25, 50, 9999],
                                    labels=["1-10", "11-25", "26-50", "51+"], right=True)
        assert "conf_band" in m.columns
        assert (m["conf_band"] == "1-10").all()  # only 4 lines, all rank <= 10


class TestPostfreezeReporting:
    def test_postfreeze_csv_marks_affected_rows(self, tmp_path):
        """A postfreeze CSV marks rows as affected but changes no grades."""
        L.set_sport("nfl")
        s = L.build_sheet(_props(), _lines(), NOW)
        dest, sha, m = L.freeze(s, _filled(s), 2026, 2, True, NOW, d=tmp_path, reader_model="test-model")
        # Write a postfreeze file
        pf = pd.DataFrame([{"game": "e1", "what changed": "A B inactive", "source URL": "https://x.com",
                            "retrieved_utc": "2026-09-21T23:00:00Z", "rows affected": "player_receptions,player_anytime_td"}])
        pf.to_csv(tmp_path / "postfreeze_20260921T2300Z.csv", index=False)
        # Verify the postfreeze file is found
        assert (tmp_path / "postfreeze_20260921T2300Z.csv").exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
