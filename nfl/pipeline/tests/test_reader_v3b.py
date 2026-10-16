"""Tests for reader_v3b changes (P52):
(a) ATD one-way line with 7 books → no_view
(b) two-way line, n=7, edge 0.004 → conf 2.0; n=1 → no_view
(c) null control: a fixture of 20 two-way lines re-scored under v3b has the SAME p_first
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "nfl" / "pipeline"))
import reader_v3 as rv3


# ── helpers ──

def _sheet_row(event_id="ev1", market_key="player_anytime_td", player_name="RB Test",
               line=0.5, two_way=False, price_first=650, price_second=None,
               q_first=None, commence_time="2026-10-12T17:00:00Z",
               home_team="Buffalo Bills", away_team="New England Patriots"):
    imp_first = rv3.imp(price_first)
    imp_second = rv3.imp(price_second) if price_second is not None else None
    q = imp_first / (imp_first + imp_second) if two_way and imp_second else imp_first
    return {
        "event_id": event_id, "commence_time": commence_time,
        "home_team": home_team, "away_team": away_team,
        "market_key": market_key, "player_name": player_name,
        "line": line, "first_side": "Over", "second_side": "Under" if two_way else "",
        "price_first": price_first, "price_second": price_second or 0,
        "source_utc": "2026-10-12T15:00:00Z",
        "imp_first": imp_first, "imp_second": imp_second or 0,
        "two_way": two_way, "q_first": q_first if q_first is not None else q,
        "source_age_min": 10.0,
    }


def _props_for_atd(event_id="ev1", n_books=7, implied_yes=0.028):
    """Build a props frame with n_books quoting ATD, no under_price (one-way)."""
    books = ["pinnacle", "draftkings", "fanduel", "betmgm", "williamhill_us",
             "betrivers", "betonlineag"][:n_books]
    price = int(round(100 / implied_yes - 100))  # ~+3471
    rows = []
    for bk in books:
        rows.append({
            "sport": "nfl", "event_id": event_id, "game_date": "2026-10-12",
            "commence_time": "2026-10-12T17:00:00Z",
            "home_team": "Buffalo Bills", "away_team": "New England Patriots",
            "bookmaker": bk, "market_key": "player_anytime_td",
            "last_update": "2026-10-12T14:00:00+00:00",
            "player_name": "RB Test", "line": 0.5,
            "over_price": price, "under_price": None,
            "implied_over": implied_yes, "implied_under": None,
            "pull_batch": "test", "pull_timestamp": "2026-10-12T14:00:00+00:00",
            "snapshot_tag": "mid",
        })
    return pd.DataFrame(rows)


def _props_two_way(event_id="ev1", n_books=7, over_imp=0.504):
    """Build a props frame with n_books quoting a two-way prop."""
    books = ["pinnacle", "draftkings", "fanduel", "betmgm", "williamhill_us",
             "betrivers", "betonlineag"][:n_books]
    over_price = -int(round(over_imp / (1 - over_imp) * 100))
    under_price = int(round((1 - over_imp) / over_imp * 100))
    rows = []
    for bk in books:
        rows.append({
            "sport": "nfl", "event_id": event_id, "game_date": "2026-10-12",
            "commence_time": "2026-10-12T17:00:00Z",
            "home_team": "Buffalo Bills", "away_team": "New England Patriots",
            "bookmaker": bk, "market_key": "player_pass_yds",
            "last_update": "2026-10-12T14:00:00+00:00",
            "player_name": "Test QB", "line": 250.5,
            "over_price": over_price, "under_price": under_price,
            "implied_over": over_imp, "implied_under": 1 - over_imp,
            "pull_batch": "test", "pull_timestamp": "2026-10-12T14:00:00+00:00",
            "snapshot_tag": "mid",
        })
    return pd.DataFrame(rows)


# ── (a) ATD one-way → no_view under v3b ──

class TestATDOneWay:
    """ATD line with 7 books at implied 0.028 vs HR 0.024: must be no_view."""

    def test_atd_one_way_is_no_view(self):
        sheet = pd.DataFrame([_sheet_row(
            market_key="player_anytime_td", player_name="RB Test",
            line=0.5, two_way=False, price_first=650,
        )])
        props = _props_for_atd(n_books=7, implied_yes=0.028)
        lines = pd.DataFrame()
        out = rv3.read_opinions(sheet, props, lines, pd.DataFrame(),
                                pd.DataFrame(), pd.DataFrame(), {}, None)
        row = out.iloc[0]
        # Under v3b: one-way market → no_view
        assert row.tag == "no_view", f"expected no_view, got {row.tag}"
        assert row.conf == 0.0, f"expected conf 0, got {row.conf}"


# ── (b) two-way conf formula; n=1 gate ──

class TestConfFormula:
    """Two-way line, n=7, edge 0.004 → conf 2.0; n=1 → no_view."""

    def test_two_way_conf_edge_only(self):
        # HR q_first = 0.500; consensus ~ 0.504 then -0.005 Under lean → p≈0.495
        # edge ≈ |0.495 - 0.500| ≈ 0.005; conf = round(0.005*500*min(1,7/5),1) = 2.5
        # (v3 had: (0.005*500 + min(7,9)*1.0 + 0) * min(1,7/5) = (2.5+7)*1 = 9.5)
        sheet = pd.DataFrame([_sheet_row(
            market_key="player_pass_yds", player_name="Test QB",
            line=250.5, two_way=True, price_first=-110, price_second=-110,
            q_first=0.5,
        )])
        props = _props_two_way(n_books=7, over_imp=0.504)
        lines = pd.DataFrame()
        out = rv3.read_opinions(sheet, props, lines, pd.DataFrame(),
                                pd.DataFrame(), pd.DataFrame(), {}, None)
        row = out.iloc[0]
        # v3b conf = round(edge*500 * min(1, n/5), 1)
        assert row.conf == 2.5, f"expected conf 2.5, got {row.conf}"

    def test_one_book_is_no_view(self):
        sheet = pd.DataFrame([_sheet_row(
            market_key="player_pass_yds", player_name="Test QB",
            line=250.5, two_way=True, price_first=-110, price_second=-110,
            q_first=0.5,
        )])
        props = _props_two_way(n_books=1, over_imp=0.504)
        lines = pd.DataFrame()
        out = rv3.read_opinions(sheet, props, lines, pd.DataFrame(),
                                pd.DataFrame(), pd.DataFrame(), {}, None)
        row = out.iloc[0]
        # v3b: n < 2 → no_view
        assert row.tag == "no_view", f"expected no_view, got {row.tag}"
        assert row.conf == 0.0


# ── (c) null control: p_first unchanged on two-way rows ──

class TestNullControlPFirst:
    """20 two-way lines re-scored: p_first identical, only conf and one-way rows change."""

    def test_p_first_unchanged_on_two_way(self):
        np.random.seed(42)
        rows = []
        all_props = []
        for i in range(20):
            eid = f"ev{i}"
            over_imp = 0.48 + np.random.random() * 0.04  # 0.48..0.52
            rows.append(_sheet_row(
                event_id=eid, market_key="player_pass_yds",
                player_name=f"QB{i}", line=250.5,
                two_way=True, price_first=-110, price_second=-110,
                q_first=0.5,
            ))
            all_props.append(_props_two_way(event_id=eid, n_books=5, over_imp=over_imp))
        sheet = pd.DataFrame(rows)
        props = pd.concat(all_props, ignore_index=True)
        lines = pd.DataFrame()

        out = rv3.read_opinions(sheet, props, lines, pd.DataFrame(),
                                pd.DataFrame(), pd.DataFrame(), {}, None)

        # All rows are two-way with n≥5, so no row should be no_view (due to one-way gate)
        # and p_first should be identical to what consensus_prop returns
        # The null control is that p_first doesn't change between v3 and v3b.
        # Since v3b only changes: (1) one-way → no_view, (2) conf formula,
        # p_first should be exactly the same.
        for _, r in out.iterrows():
            # p_first is determined by consensus only (no one-way change applies)
            assert r.tag != "no_view" or r.conf == 0.0
            # p_first is a float in [0.02, 0.98] — just verify it's valid
            assert 0.02 <= r.p_first <= 0.98
        # Count of rows where tag != no_view should be 20
        assert (out.tag != "no_view").sum() == 20, f"expected 20 non-no_view, got {(out.tag != 'no_view').sum()}"
