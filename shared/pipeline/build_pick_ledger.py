#!/usr/bin/env python3
"""
Item 3 of claude/ops_workorder_bet_ledger_2026-10-03.md: one pick ledger.

  run     python3 shared/pipeline/build_pick_ledger.py
  writes  bets/ledger/picks.parquet   (gitignored; rebuilt from scratch every run)

One row per pick-leg from every source in pick_sources.SOURCES, with the common schema
  ticket_id, lane, build_time, league, game, market, side, point, price, book, reason,
  leg_type, stake, source_file
plus kind, subject, source_set and the join columns
  slip_id, join_method (ticket_id | leg_rule), leg_outcome, slip_leg_price_dec.

Join order: bets/placements.csv on ticket_id first (no fuzzy matching); for picks logged before
ticket_id existed, the item-1 rule (link_picks_to_slips: leg agreement, uncontested tickets only).
Inside a joined ticket each pick-leg takes the outcome of the slip leg it agrees with; a leg Jeff
swapped out keeps the slip id and gets no outcome.

HALTS (non-zero, nothing written) when a source file cannot be parsed or the bet ledger is missing.
Prints no slip id.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pick_sources as ps            # noqa: E402
import link_picks_to_slips as lk     # noqa: E402
import ticket_id as tk               # noqa: E402

ROOT = ps.ROOT
OUT_COLS = ["ticket_id", "lane", "build_time", "league", "game", "market", "side", "point", "price", "book",
            "reason", "leg_type", "stake", "source_file", "kind", "subject", "source_set",
            "slip_id", "join_method", "leg_outcome", "slip_leg_price_dec"]


def join_slips(P, S, L, placements):
    """P: pick legs. placements: rows of bets/placements.csv. Returns P with join columns."""
    P = P.copy()
    for c in ("slip_id", "join_method", "leg_outcome", "slip_leg_price_dec"):
        P[c] = None
    P = tk.attach_slips(P, placements)                       # exact: ticket_id (item 2)
    links = {t: (sid, "ticket_id") for t, sid in
             P[P.join_method == "ticket_id"].groupby("ticket_id").slip_id.first().items()}
    if len(S):
        M = lk.match_all(S, L, P)
        for _, m in M[M.matched].iterrows():                 # fallback: item-1 rule
            if m.ticket_id not in links and m.slip_id not in {v[0] for v in links.values()}:
                links[m.ticket_id] = (m.slip_id, "leg_rule")
    if not links:
        return P
    SL = lk.slip_table(S[S.slip_id.isin({v[0] for v in links.values()})], L)
    for tid, (sid, how) in links.items():
        idx = P.index[P.ticket_id == tid]
        P.loc[idx, "slip_id"], P.loc[idx, "join_method"] = sid, how
        legs, used = SL[SL.slip_id == sid], set()
        for i in idx:
            pk = P.loc[i]
            if pk.market is None or pd.isna(pk.build_time):
                continue
            for j, sl in legs.iterrows():
                if j not in used and lk.legs_agree(sl, pk):
                    used.add(j)
                    P.loc[i, "leg_outcome"] = sl.leg_status
                    P.loc[i, "slip_leg_price_dec"] = sl.leg_price_dec
                    break
    return P


def build(root=None):
    root = Path(root or ROOT)
    led = root / "bets" / "ledger"
    if not (led / "slips.parquet").exists() or not (led / "legs.parquet").exists():
        raise ps.Halt(f"bet ledger missing under {led} (Mac-only; run ingest_hardrock_bets.py first)")
    P, F = ps.load_picks(root)
    S, L = pd.read_parquet(led / "slips.parquet"), pd.read_parquet(led / "legs.parquet")
    J = join_slips(P, S, L, tk.read_placements(root / "bets" / "placements.csv"))
    return J[OUT_COLS], F


def main():
    J, F = build()
    out = ROOT / "bets" / "ledger" / "picks.parquet"
    tmp = out.with_suffix(".tmp.parquet")
    J.to_parquet(tmp, index=False)
    tmp.replace(out)
    print(f"{len(F)} source files -> {len(J)} pick-leg rows, {J.ticket_id.nunique()} tickets -> {out.relative_to(ROOT)}")
    t = J.groupby("ticket_id").agg(lane=("lane", "first"), leg_type=("leg_type", "first"), kind=("kind", "first"),
                                   joined=("slip_id", lambda s: s.notna().any()), how=("join_method", "first"))
    by = J.groupby("lane").agg(rows=("ticket_id", "size"), tickets=("ticket_id", "nunique"),
                               rows_joined=("slip_id", lambda s: int(s.notna().sum())),
                               rows_with_outcome=("leg_outcome", lambda s: int(s.notna().sum())))
    by["tickets_joined"] = t.groupby("lane").joined.sum()
    print(by.to_string())
    print("\njoin method (tickets):", t[t.joined].how.value_counts().to_dict())
    nb = t[~t.joined].groupby(["lane", "leg_type", "kind"]).size()
    print("\ntickets that never became a bet, by lane and kind of pick:")
    print(nb.to_string())
    print("('pick' = a ticket or card offered, INCLUDING drafts later superseded (sun_cards v1, mnf_sgp v1-v4, "
          "slate_rule before slate_final), so it over-counts what Jeff passed on; 'placed' = a logged placement the "
          "rule could not tie to one slip, usually because the same ticket was placed twice; 'view' = an AI opinion "
          "row, not a ticket)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ps.Halt as e:
        print(f"HALT: {e}"); sys.exit(1)
