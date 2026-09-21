#!/usr/bin/env python3
"""
N46: a SLATE of NFL prop tickets dealt by rule from one candidate table, with no player on two
tickets — so one miss cannot sink more than one ticket.

Jeff's slate (2026-09-20): a 1pm 5-leg, a 4pm 5-leg, an all-day 5-leg, an all-day 10-leg and an
all-day 20-leg. No edge is claimed; q is Hard Rock's own de-vigged probability.

  * Windows are hours after the slate's first kickoff: early [0,1), late [2.5,4.5), all [0,9).
  * Pools: `role_overs` (Overs the book favours on a team's lead roles — the 5-leg tickets) and
    `top_q` (any eligible leg by q — the long tickets need every point of hit probability).
  * DEAL: tickets take turns, in SPEC order, one leg per round, each taking its best remaining leg
    that keeps the ticket legal: at most `max_per_game` legs in a game, a second leg in a game
    only on the OTHER team, and no player already used anywhere on the slate.
  * The dealt ticket is logged as `<ID>_RULE`. The reader's version is logged as `<ID>_FINAL`;
    every leg it drops or adds against the RULE ticket is derived by code and needs a reason and
    a source; every final leg needs its own availability confirmation AND a one-line `ai_reason`
    (N50); fewer legs is valid.
  * A later ticket (the 4pm one, built from a later pull) is dealt from the NEW candidate table
    with every player already logged on the slate's tickets excluded.

Outputs: appended to nfl/data/board/nfl_prop_tickets_<season>.json (same log as N43/N44), and
nfl/data/board/week=<season>_<ww>/nfl_slate_<UTC>.md
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from nfl.pipeline import build_nfl_candidates as C  # noqa: E402

SLATE_SPECS = [
    {"ticket_id": "ALLDAY_20", "legs": 20, "max_per_game": 2, "window": "all", "pool": "top_q"},
    {"ticket_id": "ALLDAY_10", "legs": 10, "max_per_game": 1, "window": "all", "pool": "top_q"},
    {"ticket_id": "EARLY_5", "legs": 5, "max_per_game": 1, "window": "early", "pool": "role_overs"},
    {"ticket_id": "ALLDAY_5", "legs": 5, "max_per_game": 1, "window": "all", "pool": "role_overs"},
    {"ticket_id": "LATE_5", "legs": 5, "max_per_game": 1, "window": "late", "pool": "role_overs"},
    # N47 (Jeff, 2026-09-20 14:15Z): "give the 5 leg our most promising, then the 10 and then the 20".
    {"ticket_id": "BEST_5", "legs": 5, "max_per_game": 1, "window": "all", "pool": "top_q"},
    # N48: lead-role Overs (top-2 target share / lead back / starting QB) across all Sunday games.
    {"ticket_id": "LEAD_5", "legs": 5, "max_per_game": 1, "window": "all", "pool": "role_overs"},
    {"ticket_id": "LEAD_10", "legs": 10, "max_per_game": 1, "window": "all", "pool": "role_overs"},
]
WINDOWS = {"early": (0.0, 1.0), "late": (2.5, 4.5), "all": (0.0, 9.0)}
# N48: ranking every family on one q scale picks ONLY receptions. Reception lines are small integers
# (1.5, 2.5) the book cannot balance, so their prices are lopsided (-160 to -250, q up to 0.66), while
# attempts/completions lines sit at the median (-115 to -145, q <= 0.55): on the 2026-09-20 14:07Z
# pull the top 60 legs by q were all receptions and 35 of 35 dealt legs were. A lopsided price is
# not a better bet, and 35 legs of one kind is one bet made 35 times. With `balance_families` a
# ticket takes its legs from the three groups in turn, best q WITHIN the group.
FAMILY_GROUP = {"player_receptions": "REC", "player_rush_attempts": "RUSH",
                "player_pass_attempts": "QB", "player_pass_completions": "QB"}
FAMILY_CYCLE = ("REC", "RUSH", "QB")


def _player(row):
    return (row["team"], row["player_name"])


def slate_first_kick(cand):
    return cand["commence_time"].map(C._utc).min()


def pool_rows(cand, spec, first_kick):
    lo, hi = WINDOWS[spec["window"]]
    hours = (cand["commence_time"].map(C._utc) - first_kick).dt.total_seconds() / 3600
    e = cand[cand["eligible"] & (hours >= lo) & (hours < hi)]
    if spec["pool"] == "role_overs":
        lead = (((e["market_key"] == "player_receptions") & (e["target_rank"] <= 2))
                | ((e["market_key"] == "player_rush_attempts") & (e["carry_rank"] == 1))
                | (e["market_key"].isin(["player_pass_attempts", "player_pass_completions"])
                   & (e["is_starting_qb"] == True)))  # noqa: E712
        e = e[lead & (e["pick_side"] == "Over")]
    return e.sort_values(["q_pick", "pick_price", "player_name", "market_key"],
        ascending=[False, False, True, True])


def deal_slate(cand, specs=SLATE_SPECS, used_players=(), first_kick=None, sequential=False,
               balance_families=False):
    """Deterministic deal. Returns {ticket_id: [candidate row dicts]}.

    Round-robin by default (tickets share the strong legs evenly). `sequential=True` fills each
    ticket COMPLETELY in spec order, so the first ticket gets the strongest legs outright."""
    if sequential:
        hands, used = {}, set(used_players)
        for s in specs:
            hands.update(deal_slate(cand, [s], used, first_kick or slate_first_kick(cand),
                                    balance_families=balance_families))
            used |= {_player(r) for r in hands[s["ticket_id"]]}
        return hands
    first_kick = first_kick or slate_first_kick(cand)
    used = set(used_players)
    pools = {s["ticket_id"]: pool_rows(cand, s, first_kick).to_dict("records") for s in specs}
    hands = {s["ticket_id"]: [] for s in specs}
    for _ in range(max(s["legs"] for s in specs)):
        for s in specs:
            hand = hands[s["ticket_id"]]
            if len(hand) >= s["legs"]:
                continue
            # A game the ticket is not in yet comes first: a second leg in a game is what the
            # book prices down, so it is taken only when no legal leg in a NEW game is left.
            k = len(hand) % len(FAMILY_CYCLE)
            turn = FAMILY_CYCLE[k:] + FAMILY_CYCLE[:k] if balance_families else (None,)
            for group, allow_second in [(g, a) for a in (False, True) for g in turn]:
                pick = None
                for row in pools[s["ticket_id"]]:
                    if group is not None and FAMILY_GROUP[row["market_key"]] != group:
                        continue
                    in_game = [h for h in hand if h["event_id"] == row["event_id"]]
                    if (_player(row) in used or len(in_game) >= s["max_per_game"]
                            or (in_game and not allow_second)
                            or any(h["team"] == row["team"] for h in in_game)):
                        continue
                    pick = row
                    break
                if pick is not None:
                    hand.append(pick)
                    used.add(_player(pick))
                    break
    return hands


def slate_players_in_log(log_path, slate):
    """Players already on any ticket of this slate, from the log (RULE and FINAL entries)."""
    log_path = Path(log_path)
    if not log_path.exists():
        return set()
    used = set()
    for e in json.loads(log_path.read_text()):
        if e.get("slate") == slate:
            used |= {(leg["team"], leg["player_name"]) for leg in e["legs"]}
    return used


def log_rule_tickets(log_path, cand, meta, slate, specs=SLATE_SPECS, used_players=(), first_kick=None,
                     sequential=False, balance_families=False):
    hands = deal_slate(cand, specs, used_players, first_kick, sequential, balance_families)
    for s in specs:
        legs = [C.leg_record(r) for r in hands[s["ticket_id"]]]
        C.log_ticket(log_path, {
            "build_time": meta["build_time"], "ticket_id": f"{s['ticket_id']}_RULE",
            "kind": "slate_rule", "slate": slate, "spec": s, "deal": ("sequential" if sequential else "round_robin") + ("+balanced_families" if balance_families else ""),
            "manifest": meta, "legs": legs,
            "short_of_spec": s["legs"] - len(legs),
            "price": C.ticket_price(legs) if legs else None, "placed": None, "graded": False,
        }, cand, max_per_game=s["max_per_game"])
    return hands


def log_final_slate_ticket(log_path, cand, meta, slate, spec, final_keys, reasons, confirmations,
                           reader, revision=None, revision_reason=None):
    """The reader's version of ONE slate ticket, checked against its RULE ticket in the log.

    The log is append-only, so a mistake in a FINAL ticket is not edited: a REVISION is appended
    as `<ID>_FINAL_r<n>` with `supersedes` and a stated reason; the earlier entry stays."""
    if revision is not None and not revision_reason:
        raise RuntimeError("HALT: a revision needs a revision_reason")
    final_id = f"{spec['ticket_id']}_FINAL" + (f"_r{revision}" if revision is not None else "")
    final_keys = [tuple(k) for k in final_keys]
    if len(final_keys) > spec["legs"] or len(set(final_keys)) != len(final_keys):
        raise RuntimeError(f"HALT: {spec['ticket_id']}: too many or duplicate legs")
    for field in ("model", "inputs", "raw_output"):
        if not reader.get(field):
            raise RuntimeError(f"HALT: reader record missing {field}")
    log = json.loads(Path(log_path).read_text())
    rule = [e for e in log if e.get("slate") == slate and e["ticket_id"] == f"{spec['ticket_id']}_RULE"
            and e["build_time"] == meta["build_time"]]
    if len(rule) != 1:
        raise RuntimeError(f"HALT: no RULE ticket logged for {spec['ticket_id']} at {meta['build_time']}")
    rule_keys = {C._key(leg) for leg in rule[0]["legs"]}
    legs = []
    for k in final_keys:
        m = cand[(cand["event_id"] == k[0]) & (cand["player_name"] == k[1]) & (cand["market_key"] == k[2])]
        if len(m) != 1:
            raise RuntimeError(f"HALT: {k} is not exactly one candidate row")
        legs.append(C.leg_record(m.iloc[0].to_dict()))
    # no player on two FINAL tickets of the slate
    others = set()
    for e in log:
        if (e.get("slate") == slate and e.get("kind") == "slate_final"
                and not e["ticket_id"].startswith(f"{spec['ticket_id']}_FINAL")):
            others |= {(leg["team"], leg["player_name"]) for leg in e["legs"]}
    clash = [leg["player_name"] for leg in legs if (leg["team"], leg["player_name"]) in others]
    if clash:
        raise RuntimeError(f"HALT: already on another final ticket of this slate: {clash}")
    removed, added = sorted(rule_keys - set(final_keys)), sorted(set(final_keys) - rule_keys)
    reasons = {tuple(k): v for k, v in reasons.items()}
    confirmations = {tuple(k): v for k, v in confirmations.items()}
    for k in removed + added:
        r = reasons.get(k) or {}
        if not r.get("reason") or not r.get("source"):
            raise RuntimeError(f"HALT: {'removed' if k in removed else 'added'} leg {k} needs a reason AND a source")
    for k in final_keys:
        c = confirmations.get(k) or {}
        if not c.get("availability_source") or not c.get("checked_at"):
            raise RuntimeError(f"HALT: final leg {k} has no availability confirmation")
    leg_notes = check_ai_reasons(final_keys, confirmations)
    entry = {
        "build_time": meta["build_time"], "ticket_id": final_id,
        "supersedes": (f"{spec['ticket_id']}_FINAL" + (f"_r{revision - 1}" if revision and revision > 1 else "")
                       if revision is not None else None),
        "revision_reason": revision_reason,
        "kind": "slate_final", "slate": slate, "spec": spec, "manifest": meta, "legs": legs,
        "price": C.ticket_price(legs) if legs else None,
        "departures": {"removed_from_rule": [list(k) for k in removed],
                       "added_outside_rule": [list(k) for k in added]},
        "reasons": [{"leg": list(k), **v} for k, v in reasons.items()],
        "confirmations": [{"leg": list(k), **v} for k, v in confirmations.items()],
        "leg_notes": leg_notes,
        "reader": reader, "placed": None, "graded": False,
    }
    return C.log_ticket(log_path, entry, cand, max_per_game=spec["max_per_game"]), entry


AI_REASON_MIN, AI_REASON_MAX, AI_REASON_MAX_REUSE = 20, 200, 2
AI_REASON_BANNED = ("lock", "guaranteed", "sure thing", "can't lose", "cant lose", "free money")


def check_ai_reasons(final_keys, confirmations):
    """N50: every FINAL leg carries the reader's own one-line reason (`ai_reason`, in the leg's
    confirmation record), so the ticket shows leg / game / why-the-AI-kept-it. It is a NOTE, not
    evidence of an edge: it is logged so that kept-vs-dealt can be compared later, and so a ticket
    is never 'AI-picked' in name only. Refused: missing, under 20 or over 200 characters, the same
    sentence on more than two legs (boilerplate), or sure-thing language."""
    notes, seen = [], {}
    for k in final_keys:
        r = str((confirmations.get(k) or {}).get("ai_reason") or "").strip()
        if not (AI_REASON_MIN <= len(r) <= AI_REASON_MAX):
            raise RuntimeError(f"HALT: final leg {k} needs an ai_reason of {AI_REASON_MIN}-{AI_REASON_MAX} "
                               f"characters (got {len(r)})")
        low = r.lower()
        bad = [w for w in AI_REASON_BANNED if w in low]
        if bad:
            raise RuntimeError(f"HALT: ai_reason for {k} uses sure-thing language: {bad}")
        seen[low] = seen.get(low, 0) + 1
        if seen[low] > AI_REASON_MAX_REUSE:
            raise RuntimeError(f"HALT: the same ai_reason is on more than {AI_REASON_MAX_REUSE} legs - "
                               f"write one per leg: {r!r}")
        notes.append({"leg": list(k), "ai_reason": r})
    return notes


def final_ticket_markdown(entry):
    """What Jeff is sent: leg, game, kickoff, the book's number, and the AI's reason."""
    why = {tuple(n["leg"]): n["ai_reason"] for n in entry.get("leg_notes", [])}
    out = [f"### {entry['ticket_id']} - {len(entry['legs'])} legs"
           + (f", product price {entry['price']['decimal']}" if entry.get("price") else ""), "",
           "| Leg | Game | Kick (UTC) | Price | Book q | AI reason |", "|---|---|---|---|---|---|"]
    for leg in sorted(entry["legs"], key=lambda x: (x["commence_time"], x["home_team"])):
        k = (leg["event_id"], leg["player_name"], leg["market_key"])
        out.append(f"| {leg['player_name']} ({leg['team']}) {leg['market_key'].replace('player_', '')} "
                   f"{leg['pick_side']} {leg['line']} | {leg['away_team']} @ {leg['home_team']} | "
                   f"{str(leg['commence_time'])[11:16]} | {leg['pick_price']:+.0f} | {leg['q_pick']:.3f} | "
                   f"{why.get(k, 'NO REASON LOGGED')} |")
    out += ["", "The reason is the reader's note on why the leg stayed on the ticket. It is not a claim of edge."]
    return "\n".join(out)


def log_placement(log_path, slate, ticket_id, refers_to, stake, quoted_american, legs_placed,
                  source, dropped=(), same_game_quotes=(), note=None):
    """N49: what was ACTUALLY placed, from the book's own slip. Appended, never merged into the
    FINAL entry: the accepted contract can differ from the recommendation (a leg skipped, a price
    moved), and the difference is the record. `legs_placed` = [{player_name, market_key, side, line,
    american (None when the slip shows only the pair's price)}]."""
    log_path = Path(log_path)
    log = json.loads(log_path.read_text())
    ref = [e for e in log if e.get("slate") == slate and e["ticket_id"] == refers_to]
    if len(ref) != 1:
        raise RuntimeError(f"HALT: {refers_to} is not exactly one entry of slate {slate}")
    if any(e["ticket_id"] == ticket_id and e.get("slate") == slate for e in log):
        raise RuntimeError(f"HALT: {ticket_id} already logged — append-only")
    if not source or stake is None or quoted_american is None or not legs_placed:
        raise RuntimeError("HALT: a placement needs a source, a stake, the quoted odds and its legs")
    rec = {(l["player_name"], l["market_key"]): l for l in ref[0]["legs"]}
    placed = {(l["player_name"], l["market_key"]) for l in legs_placed}
    unknown = sorted(placed - set(rec))
    if unknown:
        raise RuntimeError(f"HALT: placed legs that were never recommended on {refers_to}: {unknown}")
    not_placed = sorted(set(rec) - placed)
    explained = {(d["player_name"], d["market_key"]) for d in dropped if d.get("reason")}
    if set(not_placed) - explained:
        raise RuntimeError(f"HALT: recommended legs not placed and not explained: {sorted(set(not_placed) - explained)}")
    moved = []
    for l in legs_placed:
        r = rec[(l["player_name"], l["market_key"])]
        if float(l["line"]) != float(r["line"]) or l["side"] != r["pick_side"]:
            raise RuntimeError(f"HALT: {l['player_name']} placed at {l['side']} {l['line']}, recommended "
                               f"{r['pick_side']} {r['line']} — a different contract is a new leg, not this one")
        if l.get("american") is not None and float(l["american"]) != float(r["pick_price"]):
            moved.append({"player_name": l["player_name"], "recommended": r["pick_price"], "accepted": l["american"]})
    dec = C.american_to_decimal(quoted_american)
    entry = {"build_time": ref[0]["build_time"], "ticket_id": ticket_id, "kind": "placement",
             "slate": slate, "refers_to": refers_to, "stake": stake, "quoted_american": quoted_american,
             "quoted_decimal": round(dec, 3), "legs_placed": list(legs_placed), "dropped": list(dropped),
             "price_moved": moved, "same_game_quotes": list(same_game_quotes), "source": source,
             "note": note, "legs": [], "graded": False,
             "logged_at": datetime.now(timezone.utc).isoformat()}
    log.append(entry)
    log_path.write_text(json.dumps(log, indent=2, default=str))
    return len(log), entry


def slate_markdown(hands, specs, meta):
    out = [f"# NFL slate — built {meta['build_time']} from the Hard Rock pull "
           f"{meta['props_pull_timestamp']} ({meta['props_pull_age_hours']} h old)", "",
           "RULE tickets, dealt by code. No edge is claimed; q is the book's own de-vigged number.",
           "Same-game legs on the 20-leg are on opposing teams; Hard Rock may still price them down.", ""]
    for s in specs:
        legs = [C.leg_record(r) for r in hands[s["ticket_id"]]]
        if not legs:
            out += [f"## {s['ticket_id']} — no legs in this window", ""]
            continue
        p = C.ticket_price(legs)
        out += [f"## {s['ticket_id']} — {len(legs)}/{s['legs']} legs, product price "
                f"{p['decimal']} (before any same-game charge), calculated return per $1 "
                f"{p['expected_return_per_1_at_book_q']}", ""]
        for leg in sorted(legs, key=lambda x: (x["commence_time"], x["home_team"])):
            share = leg["carry_share"] if leg["market_key"] == "player_rush_attempts" else leg["target_share"]
            flags = "".join([" [no ESPN status]" if leg.get("feed_status_missing") else "",
                             f" [{leg['injury_status']}]" if leg.get("injury_status") not in (None, "Active") else "",
                             " MOVED-AGAINST" if leg.get("moved_against") is True else ""])
            out.append(f"- {leg['player_name']} ({leg['team']}) {leg['market_key'].replace('player_', '')} "
                       f"{leg['pick_side']} {leg['line']} @ {leg['pick_price']:+.0f}  q={leg['q_pick']:.3f}  "
                       f"share={share:.2f} wk1 tgt/car={leg['n_targets']}/{leg['n_carries']}{flags}")
        out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--build-time")
    ap.add_argument("--tickets", default="ALLDAY_20,ALLDAY_10,EARLY_5,ALLDAY_5",
                    help="comma list of ticket ids to deal from THIS pull, in deal order")
    ap.add_argument("--slate", help="slate label; default = UTC date of the first kickoff")
    ap.add_argument("--first-kick", help="ISO time of the slate's first kickoff (needed for a late build)")
    ap.add_argument("--balance-families", action="store_true",
                    help="take legs from receptions / rush attempts / QB volume in turn (N48)")
    ap.add_argument("--sequential", action="store_true",
                    help="fill each ticket completely in the order given (first ticket gets the strongest legs)")
    args = ap.parse_args()
    bt = args.build_time or datetime.now(timezone.utc).isoformat()
    cand, meta = C.build_candidates(season=args.season, build_time=bt)
    first_kick = C._utc(args.first_kick) if args.first_kick else slate_first_kick(cand)
    slate = args.slate or first_kick.strftime("%Y-%m-%d")
    wanted = args.tickets.split(",")
    specs = [s for t in wanted for s in SLATE_SPECS if s["ticket_id"] == t]
    if len(specs) != len(wanted):
        raise RuntimeError(f"HALT: unknown ticket id in {wanted}")
    stamp = C._utc(bt).strftime("%Y%m%dT%H%MZ")
    out_dir = C.BOARD_DIR / f"week={args.season}_{meta['week']:02d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    pq = out_dir / f"nfl_prop_candidates_{stamp}.parquet"
    if pq.exists():
        raise RuntimeError(f"HALT: {pq} exists — refusing to overwrite")
    cand.to_parquet(pq, index=False)
    meta["candidates_file"] = str(pq.relative_to(C.ROOT))
    meta["candidates_sha256"] = hashlib.sha256(pq.read_bytes()).hexdigest()
    meta["first_kick"] = first_kick.isoformat()
    log_path = C.BOARD_DIR / f"nfl_prop_tickets_{args.season}.json"
    used = slate_players_in_log(log_path, slate)
    # deal with the slate's true first kickoff so "late" means late even after the early games kicked
    hands = log_rule_tickets(log_path, cand, meta, slate, specs, used, first_kick, args.sequential,
                             args.balance_families)
    md = slate_markdown(hands, specs, meta)
    (out_dir / f"nfl_slate_{stamp}.md").write_text(md)
    print(md)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
