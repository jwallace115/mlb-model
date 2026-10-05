"""Synthetic slips, legs and pick rows for the bet-ledger tests. No real slip data."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pick_sources as ps  # noqa: E402

SLIP_COLS = ["slip_id", "placed_local", "status", "league", "match", "bet_type", "market", "price_dec",
             "wager", "winnings", "payout", "potential_payout", "result_time_local"]
LEG_COLS = ["slip_id", "leg_status", "league", "match", "market", "selection", "price_dec", "start_local", "leg_no"]


def slip(sid, placed_local, legs, league="NFL", wager=10.0, status="Lost", payout=0.0):
    """legs: list of (match, market, selection, start_local)."""
    S = dict(slip_id=sid, placed_local=pd.Timestamp(placed_local), status=status, league=league, match="",
             bet_type="MULTIPLE", market="", price_dec=10.0, wager=wager, winnings=0.0, payout=payout,
             potential_payout=100.0, result_time_local=pd.NaT)
    L = [dict(slip_id=sid, leg_status="Win", league=league, match=m, market=mk, selection=sel, price_dec=1.9,
              start_local=pd.Timestamp(st), leg_no=i + 1) for i, (m, mk, sel, st) in enumerate(legs)]
    return S, L


def frames(*slips):
    S = pd.DataFrame([s for s, _ in slips], columns=SLIP_COLS)
    L = pd.DataFrame([l for _, ls in slips for l in ls], columns=LEG_COLS)
    return S, L


def pick(ticket_id, build_utc, game, market, subject, side, point=None, league="NFL", kind="card",
         commence_utc=None, leg_type="pick"):
    return dict(ticket_id=ticket_id, lane=league.lower(), kind=kind, build_time=pd.Timestamp(build_utc, tz="UTC"),
                league=league, game=game, teams=tuple(ps.split_game(game)), market=market, subject=subject,
                side=side, point=point, price=-110, book=None, reason=None, leg_type=leg_type, stake=None,
                commence_utc=pd.Timestamp(commence_utc, tz="UTC") if commence_utc else pd.NaT,
                source_file="test", source_set="test", raw="")


def picks(*rows):
    return pd.DataFrame(list(rows), columns=ps.COLS)


# Bears vs Eagles, Mon 2026-09-28 20:15 ET = 2026-09-29 00:15Z
MNF = "Bears vs Eagles"
MNF_KICK_ET = "2026-09-28 20:15"
MNF_KICK_Z = "2026-09-29T00:15:00"


def mnf_card(tid="nfl_card_A", build="2026-09-28T19:30:00"):
    return [pick(tid, build, "PHI @ CHI", "prop:rush_att", "D'Andre Swift", "over", 14.5),
            pick(tid, build, "PHI @ CHI", "prop:rush_att", "Saquon Barkley", "under", 17.5),
            pick(tid, build, "PHI @ CHI", "total", "", "under", 41.5),
            pick(tid, build, "PHI @ CHI", "prop:rush_yds", "Case Keenum", "under", 4.5)]


def mnf_slip(sid, placed="2026-09-28 15:40", points=("14.5", "17.5", "43.5", "3.5")):
    return slip(sid, placed, [
        (MNF, "D'Andre Swift - Rushing Attempts", f"Over {points[0]}", MNF_KICK_ET),
        (MNF, "Saquon Barkley - Rushing Attempts", f"Under {points[1]}", MNF_KICK_ET),
        (MNF, "Total Points", f"Under {points[2]}", MNF_KICK_ET),
        (MNF, "Case Keenum - Rushing Yards", f"Under {points[3]}", MNF_KICK_ET)])
