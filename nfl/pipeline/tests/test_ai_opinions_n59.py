"""N59: the blind opinion log. Every quoted line gets an opinion, frozen pre-kick, append-only."""
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from nfl.pipeline import log_ai_opinions as L  # noqa: E402

NOW = datetime(2026, 9, 21, 20, 0, tzinfo=timezone.utc)
KICK = "2026-09-22T00:15:00Z"


def _props():
    base = {"event_id": "e1", "commence_time": KICK, "home_team": "Los Angeles Rams",
            "away_team": "New York Giants", "bookmaker": L.BOOK, "pull_timestamp": "2026-09-21T19:50:00+00:00"}
    return pd.DataFrame([
        {**base, "market_key": "player_receptions", "player_name": "A B", "line": 4.5, "over_price": -120, "under_price": -110},
        {**base, "market_key": "player_anytime_td", "player_name": "A B", "line": None, "over_price": 150, "under_price": None},
    ])


def _lines():
    base = {"snapshot_utc": "2026-09-21T19:55:00+00:00", "event_id": "e1", "commence_time": KICK,
            "home_team": "Los Angeles Rams", "away_team": "New York Giants", "bookmaker": L.BOOK}
    return pd.DataFrame([
        {**base, "market": "spreads", "outcome_name": "New York Giants", "point": 6.5, "price": -105},
        {**base, "market": "spreads", "outcome_name": "Los Angeles Rams", "point": -6.5, "price": -115},
        {**base, "market": "totals", "outcome_name": "Under", "point": 47.0, "price": -105},
        {**base, "market": "totals", "outcome_name": "Over", "point": 47.0, "price": -115},
    ])


def _filled(sheet, **over):
    f = sheet[L.KEY].copy()
    book = sheet["q_first"].where(sheet["two_way"], sheet["imp_first"])
    f["p_first"], f["tag"], f["reason"] = book + 0.05, "matchup", "a reason long enough to pass"
    for k, v in over.items():
        f[k] = v
    return f


def test_sheet_first_side_and_devig():
    s = L.build_sheet(_props(), _lines(), NOW)
    assert len(s) == 4
    sp = s[s.market_key == "spreads"].iloc[0]
    assert sp.first_side == "Los Angeles Rams" and sp.line == -6.5 and sp.price_first == -115
    a, b = 115 / 215, 105 / 205
    assert sp.q_first == pytest.approx(a / (a + b))
    td = s[s.market_key == "player_anytime_td"].iloc[0]
    assert not td.two_way and pd.isna(td.q_first) and td.imp_first == pytest.approx(0.4)


def test_every_quoted_line_needs_an_opinion_and_no_extras():
    s = L.build_sheet(_props(), _lines(), NOW)
    with pytest.raises(SystemExit, match="no opinion"):
        L.validate(s, _filled(s).iloc[1:])
    extra = pd.concat([_filled(s), _filled(s).iloc[[0]].assign(line=9.5)])
    with pytest.raises(SystemExit, match="did not quote"):
        L.validate(s, extra)


def test_no_view_must_equal_the_book_and_a_view_needs_a_reason():
    s = L.build_sheet(_props(), _lines(), NOW)
    with pytest.raises(SystemExit, match="no_view"):
        L.validate(s, _filled(s, tag="no_view"))
    with pytest.raises(SystemExit, match="reason"):
        L.validate(s, _filled(s, reason="x"))
    with pytest.raises(SystemExit, match="unknown tag"):
        L.validate(s, _filled(s, tag="vibes"))


def test_sides_and_one_way_market():
    s = L.build_sheet(_props(), _lines(), NOW)
    f = _filled(s)
    book = s["q_first"].where(s["two_way"], s["imp_first"])
    f["p_first"] = book - 0.05                    # reader is LOWER than the book everywhere
    m = L.validate(s, f)
    td = m[m.market_key == "player_anytime_td"].iloc[0]
    assert td.side == "none"                      # cannot bet No on a one-way market
    sp = m[m.market_key == "spreads"].iloc[0]
    assert sp.side == "second" and sp.side_name == "New York Giants" and sp.side_price == -105


def test_refuses_after_kickoff(tmp_path):
    s = L.build_sheet(_props(), _lines(), NOW)
    with pytest.raises(SystemExit, match="kicked off"):
        L.freeze(s, _filled(s), 2026, 2, True, L.parse_utc(KICK) + timedelta(minutes=1), d=tmp_path)
    assert not list(tmp_path.glob("*.parquet"))
    assert L.build_sheet(_props(), _lines(), L.parse_utc(KICK) + timedelta(minutes=1)).empty


def test_append_only_revisions_and_tamper_check(tmp_path):
    s = L.build_sheet(_props(), _lines(), NOW)
    d1, sha1, m1 = L.freeze(s, _filled(s), 2026, 2, True, NOW, d=tmp_path)
    assert (m1.revision == 0).all() and m1.pilot.all()
    with pytest.raises(SystemExit, match="append-only"):
        L.freeze(s, _filled(s), 2026, 2, True, NOW, d=tmp_path)
    later = NOW + timedelta(minutes=30)
    d2, _, m2 = L.freeze(L.build_sheet(_props(), _lines(), later), _filled(s), 2026, 2, True, later, d=tmp_path)
    assert (m2.revision == 1).all() and d1.exists() and d2 != d1
    entries, bad, unlisted = L.verify(2026, 2, d=tmp_path)
    assert len(entries) == 2 and not bad and not unlisted
    df = pd.read_parquet(d1)
    df.loc[0, "p_first"] = 0.9
    df.to_parquet(d1, index=False)                # an edit after the fact
    assert L.verify(2026, 2, d=tmp_path)[1] == [d1.name]
