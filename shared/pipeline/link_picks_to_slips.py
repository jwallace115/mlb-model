#!/usr/bin/env python3
"""
Item 1 of claude/ops_workorder_bet_ledger_2026-10-03.md: propose tags for untagged Hard Rock
slips by matching them to logged picks. Conservative by design: a wrong tag reads as settled,
so anything that does not clear the bar stays `?`.

  run     python3 shared/pipeline/link_picks_to_slips.py
  reads   bets/ledger/slips.parquet, bets/ledger/legs.parquet, bets/tags.csv,
          every pick source in shared/pipeline/pick_sources.py
  writes  bets/tags_proposed.csv  (gitignored; Jeff reviews, then copies accepted rows into
          bets/tags.csv). bets/tags.csv is never written by this script.

THE RULE (a time window alone is never a match)
  A slip is proposed `ours` only if ONE logged pick ticket satisfies all of:
    1. same league;
    2. slip placed between WINDOW_BEFORE_H hours before and WINDOW_AFTER_H hours after the
       ticket's build time (a pick file is sometimes written a few minutes after Jeff places
       the slip it came from: the MNF 09-28 v3/v4 files were written 12-27 min after);
    3. at least NEED(n) = max(ceil(n/2), min(n, 2)) of the slip's n legs agree with distinct legs
       of that ticket on (game, market, subject, side). Point and price may differ (Jeff buys
       points; Hard Rock prices are not the card's). The min(n,2) floor stops one popular leg
       from tagging a 2-leg slip.
  Game agreement: both teams when the pick names its game; the named team when the pick only
  names a side; a player-prop leg with no game needs the player's first and last name.
  If a leg has a kickoff on both sides, they must be within 12 h; if the pick has none (free-text
  cards), the slip leg must kick off between 6 h before and 30 h after the pick was written.

The rule is measured on the already-tagged slips: how many `ours` it recovers and how many
`other` it would wrongly claim. Both numbers are printed.

No slip id is printed. Rows are referred to by placed time and league.
"""
import math, os, re, sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pick_sources as ps  # noqa: E402

ROOT = ps.ROOT
BETS = ROOT / "bets"
WINDOW_BEFORE_H = 2.0      # slip may be placed up to 2 h BEFORE the pick file's timestamp
WINDOW_AFTER_H = 48.0      # ... and up to 48 h after it
KICK_TOL_H = 12.0
NOKICK_BEFORE_H, NOKICK_AFTER_H = 6.0, 30.0
LEAGUE = {"NFL": "NFL", "NCAA, Regular": "NCAAF", "NCAAF": "NCAAF"}
# tie-break between tickets with equal agreement: a logged placement beats a card, a card beats an AI view
KIND_RANK = {"placement": 3, "slate_final": 2, "card": 2, "sgp_card": 2, "game_ticket": 2, "slate_rule": 1,
             "game_view": 0, "ai_opinion": 0}


def need(n):
    return max(math.ceil(n / 2), min(n, 2))


# ------------------------------------------------------------------ slip legs
def hr_leg(league, match, market, selection, start_local):
    lg = LEAGUE.get(league)
    mk, subject, side = None, "", ""
    m, sel = str(market or ""), str(selection or "").strip()
    ml = m.lower()
    ou = re.match(r"^(over|under)\b", sel, re.I)
    if ml == "spread" or ml.endswith("spread") and " - " not in m:
        mk, subject = "spread", re.sub(r"\s*[-+]\d+(\.\d+)?\s*$", "", sel)
        side = subject
    elif ml in ("total points", "total", "totals"):
        mk, side = "total", (ou.group(1).lower() if ou else "")
    elif ml in ("to win", "moneyline", "money line"):
        mk, subject, side = "moneyline", sel, sel
    elif "1st half total" in ml:
        mk, side = "h1_total", (ou.group(1).lower() if ou else "")
    elif " - " in m:
        player, stat = m.split(" - ", 1)
        sk = ps.stat_key(stat)
        if sk:
            mk, subject, side = "prop:" + sk, player.strip(), (ou.group(1).lower() if ou else "over")
    start = pd.Timestamp(start_local).tz_localize("America/New_York").tz_convert("UTC") \
        if pd.notna(start_local) else pd.NaT
    return dict(league=lg, game=match, teams=tuple(ps.split_game(match)), market=mk, subject=subject,
                side=side, start_utc=start)


def slip_table(S, L):
    """One row per slip leg. A straight bet has no leg rows: the slip row carries its one leg
    (Bet Type = market kind, Market = selection)."""
    out = []
    for _, s in S.iterrows():
        legs = L[L.slip_id == s.slip_id]
        if len(legs):
            for _, l in legs.iterrows():
                out.append(dict(slip_id=s.slip_id, leg_no=l.leg_no, leg_status=l.leg_status, leg_price_dec=l.price_dec,
                                selection=l.selection,
                                **hr_leg(l.league, l.match, l.market, l.selection, l.start_local)))
        else:
            out.append(dict(slip_id=s.slip_id, leg_no=1, leg_status=s.status, leg_price_dec=s.price_dec,
                            selection=s.market, **hr_leg(s.league, s.match, s.bet_type, s.market, pd.NaT)))
    return pd.DataFrame(out)


# ------------------------------------------------------------------ agreement
def _same_team(league, a, b):
    if not a or not b:
        return False
    if league == "NFL":
        ta, tb = ps.nfl_team(a), ps.nfl_team(b)
        return bool(ta) and ta == tb
    return ps.ncaaf_same(a, b)


def _team_in(league, team, teams):
    return any(_same_team(league, team, t) for t in teams)


def _game_ok(sl, pk):
    lg = sl["league"]
    if len(pk["teams"]) >= 2:
        return all(_team_in(lg, t, sl["teams"]) for t in pk["teams"][:2])
    if pk["market"] in ("spread", "moneyline"):
        return _team_in(lg, pk["subject"], sl["teams"])
    return None          # pick does not name its game


def _player_ok(a, b, game_known):
    ta, tb = ps.player_tokens(a), ps.player_tokens(b)
    if not ta or not tb:
        return False
    short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    if not set(short) <= set(long_):
        return False
    return len(short) >= 2 or game_known


def legs_agree(sl, pk):
    if sl["league"] != pk["league"] or not sl["market"] or sl["market"] != pk["market"]:
        return False
    if pd.notna(sl["start_utc"]) and pd.notna(pk["commence_utc"]):
        if abs((sl["start_utc"] - pk["commence_utc"]).total_seconds()) > KICK_TOL_H * 3600:
            return False
    elif pd.notna(sl["start_utc"]) and pd.notna(pk["build_time"]):
        # pick carries no kickoff (free-text cards): the slip's game must kick off within
        # NOKICK_AFTER_H of the card being written — cards are built for that day's games
        h = (sl["start_utc"] - pk["build_time"]).total_seconds() / 3600
        if h < -NOKICK_BEFORE_H or h > NOKICK_AFTER_H:
            return False
    g = _game_ok(sl, pk)
    if g is False:
        return False
    m = sl["market"]
    if m in ("spread", "moneyline"):
        return g is True and _same_team(sl["league"], sl["subject"], pk["subject"])
    if m in ("total", "h1_total"):
        return g is True and sl["side"] == str(pk["side"]).lower()
    if m.startswith("prop:"):
        return sl["side"] == str(pk["side"]).lower() and _player_ok(sl["subject"], pk["subject"], g is True)
    return False


def count_agree(slip_legs, ticket_legs):
    used, n = set(), 0
    for _, sl in slip_legs.iterrows():
        for j, pk in ticket_legs.iterrows():
            if j not in used and legs_agree(sl, pk):
                used.add(j); n += 1
                break
    return n


# ------------------------------------------------------------------ match
def match_all(S, L, P):
    SL = slip_table(S, L)
    P = P[P.market.notna() & P.build_time.notna()]
    tickets = {t: g for t, g in P.groupby("ticket_id")}
    tmeta = P.groupby("ticket_id").agg(build_time=("build_time", "first"), league=("league", "first"),
                                       source_file=("source_file", "first"), source_set=("source_set", "first"),
                                       kind=("kind", "first"))
    rows = []
    for _, s in S.iterrows():
        legs = SL[SL.slip_id == s.slip_id]
        lg = LEAGUE.get(s.league)
        placed = pd.Timestamp(s.placed_local).tz_localize("America/New_York").tz_convert("UTC")
        n = len(legs)
        best = dict(agreed=0, ticket_id=None, delta_min=None, rank=(0, 0, 0))
        cand = tmeta[(tmeta.league == lg)] if lg else tmeta.iloc[0:0]
        for tid, t in cand.iterrows():
            d_h = (placed - t.build_time).total_seconds() / 3600
            if d_h < -WINDOW_BEFORE_H or d_h > WINDOW_AFTER_H:
                continue
            a = count_agree(legs, tickets[tid])
            rank = (a, KIND_RANK.get(t.kind, 0), -abs(d_h))
            if a > 0 and rank > best["rank"]:
                best = dict(agreed=a, rank=rank, ticket_id=tid, delta_min=round(d_h * 60), source_file=t.source_file,
                            source_set=t.source_set, kind=t.kind)
        ok = n > 0 and best["agreed"] >= need(n)
        rows.append(dict(slip_id=s.slip_id, placed_local=s.placed_local, league=s.league, wager=s.wager,
                         payout=s.payout, status=s.status, legs_total=n, legs_parsed=int(legs.market.notna().sum()),
                         need=need(n) if n else None, legs_agreed=best["agreed"], qualified=ok,
                         ticket_id=best.get("ticket_id"), source_file=best.get("source_file"),
                         source_set=best.get("source_set"), ticket_kind=best.get("kind"),
                         minutes_after_build=best.get("delta_min"),
                         has_picks_in_window=bool(lg) and any(
                             -WINDOW_BEFORE_H <= (placed - bt).total_seconds() / 3600 <= WINDOW_AFTER_H
                             for bt in cand.build_time)))
    M = pd.DataFrame(rows)
    # One pick ticket can be the source of only one of Jeff's slips. When two or more slips clear the
    # bar on the SAME ticket (e.g. the same card placed again for a friend), leg agreement cannot say
    # which one is Jeff's, so none of them is proposed. Measured: this is what separates the three
    # tagged-`other` copies of 09-27 cards from the `ours` originals.
    claims = M[M.qualified].groupby("ticket_id").slip_id.nunique()
    M["contested"] = M.ticket_id.map(claims).fillna(0).gt(1) & M.qualified
    M["matched"] = M.qualified & ~M.contested
    return M


def net(df):
    return float(df.payout.fillna(0).sum() - df.wager.sum())


def main():
    S = pd.read_parquet(BETS / "ledger" / "slips.parquet")
    L = pd.read_parquet(BETS / "ledger" / "legs.parquet")
    T = pd.read_csv(BETS / "tags.csv", dtype=str)
    P, F = ps.load_picks()
    S = S.merge(T[["slip_id", "source"]], on="slip_id", how="left")
    S["source"] = S.source.fillna("?")
    M = match_all(S, L, P).merge(S[["slip_id", "source"]], on="slip_id")

    # measured hit rate on slips Jeff already tagged
    ours, other = M[M.source == "ours"], M[M.source == "other"]
    print(f"RULE: window -{WINDOW_BEFORE_H:g}h/+{WINDOW_AFTER_H:g}h of the pick's build time; "
          f"legs agreed >= max(ceil(n/2), min(n,2)) on (game, market, subject, side); kickoffs within {KICK_TOL_H:g}h")
    print(f"pick sources: {len(F)} files, {len(P)} pick-leg rows, {P.ticket_id.nunique()} tickets, "
          f"{int(P.market.isna().sum())} legs unparsed")
    print(f"hit rate on tagged `ours`: {int(ours.matched.sum())}/{len(ours)} recovered "
          f"({int(ours.has_picks_in_window.sum())} of them have any logged pick in the window)")
    print(f"false claims on tagged `other`: {int(other.matched.sum())}/{len(other)} "
          f"({int(other.qualified.sum())} cleared the leg bar but sit on a ticket another slip also claims)")

    U = M[M.source == "?"].copy()
    U["proposed_source"] = U.matched.map({True: "ours", False: "?"})
    U["current_source"] = "?"
    cols = ["slip_id", "current_source", "proposed_source", "placed_local", "league", "wager", "status", "payout",
            "legs_total", "legs_parsed", "need", "legs_agreed", "ticket_id", "ticket_kind", "source_file", "source_set",
            "minutes_after_build", "qualified", "contested", "has_picks_in_window"]
    U.sort_values("placed_local")[cols].to_csv(BETS / "tags_proposed.csv", index=False)

    hit = U[U.matched]
    old = net(S[S.source == "ours"])
    new = old + net(hit)
    print(f"untagged: {len(U)} | proposed ours: {len(hit)} | stay ?: {len(U) - len(hit)} "
          f"(of which {int((~U.has_picks_in_window).sum())} have no logged pick of their league in the window)")
    for _, r in hit.iterrows():
        print(f"  proposed ours: {r.placed_local:%Y-%m-%d %H:%M} {r.league} ${r.wager:g} {r.status} | "
              f"{r.legs_agreed}/{r.legs_total} legs agree with {r.ticket_id} ({r.source_set}: {r.source_file}), "
              f"placed {r.minutes_after_build} min after build")
    word = "worse" if new < old else ("better" if new > old else "unchanged")
    print(f"`ours` net: ${new:,.2f} if the proposals are accepted, vs ${old:,.2f} before — {word} by "
          f"${abs(new - old):,.2f}.")
    print(f"wrote {(BETS / 'tags_proposed.csv').relative_to(ROOT)} ({len(U)} rows). bets/tags.csv untouched.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ps.Halt as e:
        print(f"HALT: {e}"); sys.exit(1)
