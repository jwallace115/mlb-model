"""Phase 5A-11 tests — overtime audit: first-possession completion and the second
possession coming up empty (D38), OT's last minutes as late-game (D39), sudden-death
in-range behaviour (D40).

Tolerances are the acceptance spec; a failing test is reported red, never widened.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import nfl.sim.engine as E  # noqa: E402
from nfl.sim.engine import simulate_game, _load_tables, _load_ratings  # noqa: E402
from nfl.sim.seed_util import stable_seed  # noqa: E402

TABLES = ROOT / "nfl" / "data" / "sim" / "tables"

# Measured 2021-2024 regular season, 70 OT games (phase5a11 report)
ACT_P_TIE_GIVEN_OT = 3 / 70          # 0.043; the 70-game sample's own 95% interval is ~1-12%
ACT_OT_DRIVES = 2.51
ACT_OT_FIRST = {"TD": 0.19, "FG": 0.17, "punt": 0.46}   # first OT drive result mix
ACT_MATCHED_FG_CONTINUES = 1.0        # 2 of 2 real matched-FG overtimes went on (sudden death)

SAMPLE_GAMES = [("KC", "BUF", 2023, 6), ("PHI", "DAL", 2022, 10), ("SF", "SEA", 2024, 12),
                ("DET", "GB", 2023, 4), ("BAL", "CIN", 2022, 14), ("MIA", "NYJ", 2024, 8),
                ("LA", "ARI", 2023, 12), ("MIN", "CHI", 2022, 6), ("TB", "ATL", 2024, 15),
                ("DEN", "LV", 2023, 17), ("CLE", "PIT", 2022, 2), ("HOU", "IND", 2024, 5)]


@pytest.fixture(scope="module")
def ratings():
    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()
    return dict(team_r=team_r, tend=tend, sit=sit, kicker=kicker, league=league)


def _td(r):
    return r[0] if isinstance(r, tuple) else r


@pytest.fixture(scope="module")
def ot_sample(ratings):
    """OT drive sequences from 12 games x 2000 sims (~1,200 overtimes)."""
    rows = []
    for home, away, season, week in SAMPLE_GAMES:
        r = _td(simulate_game(home, away, season, week, n_sims=2000, seed=stable_seed(f"ot_{season}_{week}_{away}_{home}"),
                              drive_log=True, **ratings))
        dl = r.attrs["drive_log"]
        ot = dl[dl.start_quarter >= 5].sort_values(["sim_id", "drive_no"])
        tie = (r.home_score == r.away_score).to_numpy()
        for sid, g in ot.groupby("sim_id"):
            rows.append({"seq": list(g.result), "tie": bool(tie[sid]), "n": len(g)})
    return pd.DataFrame(rows)


def test_t1_table_has_the_ot_sudden_death_cell():
    t = pd.read_parquet(TABLES / "fg_setup.parquet")
    r = t[t.state == "ot_sd"]
    assert len(r) == 1 and r.n.iloc[0] >= 100
    assert 0.1 <= r.p_fg.iloc[0] <= 0.3 and 0.2 <= r.pass_rate.iloc[0] <= 0.4


def test_t2_ot_rules(ot_sample):
    s = ot_sample
    # a matched field goal never ends the game as a tie (sudden death continues)
    ff = s[s.seq.apply(lambda q: q[:2] == ["FG_made", "FG_made"])]
    assert len(ff) > 0 and (ff.n > 2).mean() >= ACT_MATCHED_FG_CONTINUES - 1e-9, "matched FGs ended games"
    # after a first-drive FG, the second team's empty possession ends the game (2 drives)
    fd = s[s.seq.apply(lambda q: len(q) >= 2 and q[0] == "FG_made" and q[1] in ("punt", "downs", "turnover_int", "turnover_fumble", "FG_missed"))]
    assert len(fd) > 0 and (fd.n == 2).all(), "first-drive FG + empty second possession did not end the game"
    # after a first-drive punt, the second team's FG ends the game (sudden death)
    pf = s[s.seq.apply(lambda q: len(q) >= 2 and q[0] == "punt" and q[1] == "FG_made")]
    assert len(pf) > 0 and (pf.n == 2).all(), "a FG after both possessed did not end the game"
    # a first-possession TD ends it at once
    assert (s[s.seq.apply(lambda q: q[0] == "TD")].n == 1).all()


def test_t3_ot_structure(ot_sample):
    s = ot_sample
    first = s.seq.str[0].map({"TD": "TD", "FG_made": "FG", "punt": "punt"}).fillna("other")
    for k, v in ACT_OT_FIRST.items():
        assert abs(float((first == k).mean()) - v) <= 0.06, f"first OT drive {k}: {float((first == k).mean()):.3f} vs {v}"
    assert abs(float(s.n.mean()) - ACT_OT_DRIVES) <= 0.35, f"drives per OT {s.n.mean():.2f} vs {ACT_OT_DRIVES}"
    tie = float(s.tie.mean())
    assert tie <= ACT_P_TIE_GIVEN_OT + 0.08, f"P(tie | OT) {tie:.3f} vs {ACT_P_TIE_GIVEN_OT:.3f} (was 0.19 before 5A-11)"
