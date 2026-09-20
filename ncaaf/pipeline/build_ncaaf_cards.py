#!/usr/bin/env python3
"""
N22-N23: NCAAF card assembler — two separate parlay cards from AI tickets.

Card A: 5-leg conviction-only card. At most one leg per game.
Card B: 10+ leg longshot. Conviction legs first, then FILLER legs clearly marked.
        At most one leg per game unless joint-table cover+over pair (|spread|>=21).

No overlap between cards. Assert and raise on violation.
Prints real hold from actual leg prices.
Logs both cards to the ticket log with card_id and leg_type tags.
"""

import argparse, json, math, sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from ncaaf.pipeline.build_ncaaf_tickets import (select_best_quote, complement_quote,
                                                event_newest_snapshot)

TICKET_LOG = ROOT / "ncaaf" / "logs" / "ncaaf_board_tickets_2026.json"
BOARD_DIR = ROOT / "ncaaf" / "data" / "board"
JOINT_TABLE = ROOT / "research" / "ncaaf_board" / "joint_outcome_table_v2.parquet"


def american_to_decimal(odds):
    """American odds -> decimal payout (includes stake)."""
    if odds is None or (isinstance(odds, float) and np.isnan(odds)):
        return np.nan
    if odds > 0:
        return 1 + odds / 100
    return 1 + 100 / abs(odds)


def american_to_implied(odds):
    """American odds -> implied probability (vig-included)."""
    if odds is None or (isinstance(odds, float) and np.isnan(odds)):
        return np.nan
    if odds > 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)


def no_vig_prob_pair(odds_a, odds_b):
    """Devig a two-outcome market using multiplicative method.

    Returns the no-vig probability for side A.
    """
    imp_a = american_to_implied(odds_a)
    imp_b = american_to_implied(odds_b)
    if np.isnan(imp_a) or np.isnan(imp_b):
        # Fallback: assume ~4.55% total overround
        return imp_a / 1.04545 if not np.isnan(imp_a) else np.nan
    total = imp_a + imp_b
    return imp_a / total


def load_conviction_tickets(build_date):
    """Load tickets from the log that were built today and have legs."""
    if not TICKET_LOG.exists():
        return []
    with open(TICKET_LOG) as f:
        all_tickets = json.load(f)

    today_tickets = []
    for t in all_tickets:
        bt = t.get("build_time", "")
        if t.get("pre_repair") or t.get("abstain") or t.get("card_id"):
            continue
        if bt.startswith(build_date) and t.get("legs"):
            today_tickets.append(t)
    return today_tickets


def load_board(build_date):
    """Load the board parquet for today's events."""
    # Find the right week directory
    board_dirs = sorted(BOARD_DIR.glob("week=2026_*"))
    if not board_dirs:
        return pd.DataFrame()
    # Use the most recent board
    latest = board_dirs[-1]
    pq = latest / "ncaaf_board.parquet"
    if not pq.exists():
        return pd.DataFrame()
    df = pd.read_parquet(pq)
    # Filter to today's events
    today = df[df["commence_time"].str.startswith(build_date)]
    return today


def _total_bucket(total_line):
    """Map total line to joint table bucket."""
    if total_line is None or np.isnan(total_line):
        return None
    if total_line < 50:
        return "OU<50"
    if total_line < 54:
        return "OU_50-54"
    if total_line < 58:
        return "OU_54-58"
    return "OU>58"


def build_cards(conviction_tickets, board_df, build_time):
    """Build Card A (5-leg conviction) and Card B (10+ longshot)."""

    # Load joint table for cover+over pair detection
    joint_table = None
    if JOINT_TABLE.exists():
        joint_table = pd.read_parquet(JOINT_TABLE)

    # Deduplicate conviction tickets: keep latest build per event
    by_event = {}
    for t in conviction_tickets:
        eid = t["event_id"]
        if eid not in by_event or t["build_time"] > by_event[eid]["build_time"]:
            by_event[eid] = t

    # Drop tickets where AI picked both sides of the same market (WO7 bug)
    clean_events = {}
    for eid, t in by_event.items():
        markets_seen = {}
        bad = False
        for leg in t["legs"]:
            mkt = leg["market"]
            if mkt in markets_seen:
                print(f"  DROP both-sides ticket: {t['away_team']} @ {t['home_team']} "
                      f"({mkt}: {markets_seen[mkt]} AND {leg['side']})")
                bad = True
                break
            markets_seen[mkt] = leg["side"]
        if not bad:
            clean_events[eid] = t
    by_event = clean_events

    # Flatten conviction legs — one spread + one total per event max
    conviction_legs = []
    for eid, t in by_event.items():
        for leg in t["legs"]:
            conviction_legs.append({
                "event_id": eid,
                "home_team": t["home_team"],
                "away_team": t["away_team"],
                "commence_time": t["commence_time"],
                "spread_magnitude": t.get("spread_magnitude", 0),
                "favourite": t.get("favourite", ""),
                "underdog": t.get("underdog", ""),
                "market": leg["market"],
                "side": leg["side"],
                "point": leg["point"],
                "price": leg["price"],
                "book": leg["book"],
                # N42: a card leg keeps the quote's identity and its entry complement; they
                # were dropped here, so no card leg could ever get a probability CLV.
                "snapshot_utc": leg.get("snapshot_utc"),
                "complement_side": leg.get("complement_side"),
                "complement_point": leg.get("complement_point"),
                "complement_price": leg.get("complement_price"),
                "implied": leg.get("implied", american_to_implied(leg["price"])),
                "ai_reason": leg.get("ai_reason", ""),
                "leg_type": "CONVICTION",
                "rationale": t.get("ai_rationale", ""),
            })

    print(f"Conviction legs available: {len(conviction_legs)} from {len(by_event)} events")

    # --- CARD A: 5-leg conviction only, ONE LEG per game ---
    # Sort: spreads first (more decisive pick), then by spread magnitude
    ranked = sorted(conviction_legs,
                    key=lambda l: (l["market"] == "spreads", l["spread_magnitude"]),
                    reverse=True)

    card_a_legs = []
    card_a_events = set()
    for leg in ranked:
        if leg["event_id"] in card_a_events:
            continue
        card_a_legs.append(leg)
        card_a_events.add(leg["event_id"])
        if len(card_a_legs) >= 5:
            break

    print(f"Card A: {len(card_a_legs)} conviction legs")

    # --- CARD B: 10+ legs, conviction first (NOT on Card A), then FILLER ---
    # Rule: at most ONE leg per game UNLESS joint-table cover+over pair (|spread|>=21)
    card_a_leg_keys = {_leg_key(l) for l in card_a_legs}

    # Remaining conviction legs not on Card A
    remaining = [l for l in conviction_legs if _leg_key(l) not in card_a_leg_keys]

    # Group remaining by event: pick best single leg per event,
    # or allow spread+total pair if |spread| >= 21
    remaining_by_event = {}
    for l in remaining:
        remaining_by_event.setdefault(l["event_id"], []).append(l)

    card_b_legs = []
    card_b_events = set()

    # Sort events by spread magnitude descending
    event_order = sorted(remaining_by_event.keys(),
                         key=lambda eid: max(l["spread_magnitude"]
                                             for l in remaining_by_event[eid]),
                         reverse=True)

    for eid in event_order:
        legs = remaining_by_event[eid]
        spread_mag = max(l["spread_magnitude"] for l in legs)
        spread_legs = [l for l in legs if l["market"] == "spreads"]
        total_legs = [l for l in legs if l["market"] == "totals"]

        # Joint-table pair: both spread + total, |spread| >= 21
        if spread_mag >= 21 and spread_legs and total_legs:
            # Add both as a pair — cite the joint table cell
            sl = spread_legs[0]
            tl = total_legs[0]
            tb = _total_bucket(tl["point"])
            jt_row = None
            if joint_table is not None and tb is not None:
                match = joint_table[joint_table["total_bucket"] == tb]
                if not match.empty:
                    jt_row = match.iloc[0]
            note = ""
            if jt_row is not None:
                note = (f" [joint-table pair: 21+/{tb}, n={int(jt_row['n'])}, "
                        f"delta={jt_row['delta']:.3f}]")
            sl["ai_reason"] = (sl["ai_reason"] or "") + note
            card_b_legs.extend([sl, tl])
            card_b_events.add(eid)
        else:
            # One leg per game: prefer spreads
            pick = spread_legs[0] if spread_legs else (total_legs[0] if total_legs else None)
            if pick:
                card_b_legs.append(pick)
                card_b_events.add(eid)

    conviction_in_b = len(card_b_legs)
    print(f"Card B conviction legs: {conviction_in_b}")

    # FILLER: if Card B < 10, add filler from board events not on either card
    filler_count = 0
    if len(card_b_legs) < 10 and not board_df.empty:
        used_events = card_a_events | card_b_events
        filler_candidates = []

        for eid in board_df["event_id"].unique():
            if eid in used_events:
                continue
            ev = board_df[board_df["event_id"] == eid]
            spreads = ev[ev["market"] == "spreads"]
            if spreads.empty:
                continue

            fav_row = spreads.loc[spreads["consensus_point"].idxmin()]
            spread_mag = abs(fav_row["consensus_point"])
            # N42: a FILLER leg is one row of one book too. This wrote consensus_point with
            # best_price/best_book — the audit #4 defect, which WO11 fixed in the ticket
            # builder and left here.
            fq = fav_row.get("quotes")
            best_q = select_best_quote(
                list(fq), "spreads", fav_row["outcome_name"],
                newest_snapshot=event_newest_snapshot(ev.to_dict("records"))) \
                if fq is not None and len(fq) else None
            if best_q is None:
                continue
            comp_side, comp = complement_quote(
                spreads[spreads["outcome_name"] != fav_row["outcome_name"]].to_dict("records"),
                best_q)
            filler_candidates.append({
                "event_id": eid,
                "home_team": ev.iloc[0]["home_team"],
                "away_team": ev.iloc[0]["away_team"],
                "commence_time": ev.iloc[0]["commence_time"],
                "spread_magnitude": spread_mag,
                "favourite": fav_row["outcome_name"],
                "underdog": "",
                "market": "spreads",
                "side": fav_row["outcome_name"],
                "point": best_q["point"],
                "price": best_q["price"],
                "book": best_q["book"],
                "snapshot_utc": best_q["snapshot_utc"],
                "complement_side": comp_side,
                "complement_point": comp["point"] if comp else None,
                "complement_price": comp["price"] if comp else None,
                "implied": fav_row["consensus_implied"],
                "ai_reason": "FILLER -- favourite at posted spread",
                "leg_type": "FILLER",
                "rationale": "",
            })

        # Sort fillers: larger spreads first
        filler_candidates.sort(key=lambda l: l["spread_magnitude"], reverse=True)
        for filler in filler_candidates:
            if len(card_b_legs) >= 12:
                break
            card_b_legs.append(filler)
            card_b_events.add(filler["event_id"])
            filler_count += 1

    print(f"Card B filler legs: {filler_count}")
    print(f"Card B total legs: {len(card_b_legs)}")

    # --- OVERLAP CHECK ---
    a_keys = {_leg_key(l) for l in card_a_legs}
    b_keys = {_leg_key(l) for l in card_b_legs}
    overlap = a_keys & b_keys
    if overlap:
        raise RuntimeError(f"HALT: Card A/B overlap: {overlap}")

    return card_a_legs, card_b_legs, conviction_in_b, filler_count


def _leg_key(leg):
    return (leg["event_id"], leg["market"], leg["side"], leg["point"])


def _can_pair(leg, existing_legs, joint_table):
    """Check if a leg can be paired with an existing leg on the same game
    via the joint table (|spread| >= 21, cover+over)."""
    if joint_table is None:
        return False
    if leg["spread_magnitude"] < 21:
        return False
    same_game = [l for l in existing_legs if l["event_id"] == leg["event_id"]]
    if not same_game:
        return False
    existing_markets = {l["market"] for l in same_game}
    if leg["market"] in existing_markets:
        return False
    # One is spreads, the other is totals -> joint-table pair
    if {leg["market"]} | existing_markets == {"spreads", "totals"}:
        return True
    return False


def compute_card_math(legs, board_df=None):
    """Compute parlay math from actual leg prices.

    If board_df is provided, uses proper two-sided devig. Otherwise falls
    back to the crude 4.55% overround assumption.
    """
    if not legs:
        return {}

    decimals = [american_to_decimal(l["price"]) for l in legs]
    implieds = [american_to_implied(l["price"]) for l in legs]

    # Compute no-vig probs using proper devig from the board
    no_vig_probs = []
    for l in legs:
        nv = _devig_from_board(l, board_df)
        no_vig_probs.append(nv)

    combined_decimal = 1.0
    for d in decimals:
        if not np.isnan(d):
            combined_decimal *= d

    implied_product = 1.0
    for p in implieds:
        if not np.isnan(p):
            implied_product *= p

    fair_product = 1.0
    for p in no_vig_probs:
        if not np.isnan(p):
            fair_product *= p

    fair_payout = 1.0 / fair_product if fair_product > 0 else float('inf')
    effective_hold = 1 - (combined_decimal / fair_payout) if fair_payout > 0 else float('nan')

    return {
        "n_legs": len(legs),
        "combined_decimal_payout": combined_decimal,
        "implied_prob_at_price": implied_product,
        "fair_prob_no_vig": fair_product,
        "fair_payout": fair_payout,
        "effective_hold": effective_hold,
    }


def _devig_from_board(leg, board_df):
    """Devig one leg using the counterpart side from the board."""
    if board_df is None or board_df.empty:
        imp = american_to_implied(leg["price"])
        return imp / 1.04545 if not np.isnan(imp) else np.nan

    eid = leg["event_id"]
    mkt = leg["market"]
    side = leg["side"]

    ev = board_df[(board_df["event_id"] == eid) & (board_df["market"] == mkt)]
    if ev.empty:
        imp = american_to_implied(leg["price"])
        return imp / 1.04545 if not np.isnan(imp) else np.nan

    # Find the counterpart (other side of same market)
    other = ev[ev["outcome_name"] != side]
    if other.empty:
        imp = american_to_implied(leg["price"])
        return imp / 1.04545 if not np.isnan(imp) else np.nan

    other_price = other.iloc[0]["best_price"]
    return no_vig_prob_pair(leg["price"], other_price)


def format_cards_md(card_a, card_b, math_a, math_b, conviction_in_b, filler_in_b,
                    total_events, abstain_count, build_time):
    """Format both cards as markdown."""
    lines = []
    lines.append("# NCAAF Parlay Cards — 2026 Week 3")
    lines.append(f"\nBuild time: {build_time}")
    lines.append(f"Events on board: {total_events}")
    lines.append(f"AI abstain rate: {abstain_count}/{total_events} ({abstain_count/total_events*100:.0f}%)" if total_events > 0 else "")
    lines.append("")
    lines.append("**REFERENCE_ONLY** — hardrockbet_fl absent from all NCAAF events.")
    lines.append("These are numbers to SHOP at Hard Rock, not numbers Jeff can take.")
    lines.append("")

    # Card A
    lines.append("---")
    lines.append("## CARD A — 5-Leg Conviction")
    lines.append("")
    lines.append(f"Legs: {len(card_a)} (all CONVICTION)")
    lines.append("")
    lines.append("| # | Game | Market | Side | Point | Price | Book | Reason |")
    lines.append("|---|------|--------|------|-------|-------|------|--------|")
    for i, leg in enumerate(card_a, 1):
        game = f"{leg['away_team'][:20]} @ {leg['home_team'][:20]}"
        pt = f"{leg['point']:.1f}" if leg['point'] is not None else "—"
        pr = f"{leg['price']:+.0f}" if leg['price'] is not None else "—"
        lines.append(f"| {i} | {game} | {leg['market']} | {leg['side'][:25]} | {pt} | {pr} | {leg['book']} | {leg['ai_reason'][:60]} |")

    lines.append("")
    lines.append(f"**Combined decimal payout:** {math_a['combined_decimal_payout']:.2f}x")
    lines.append(f"**Implied probability (at offered price):** {math_a['implied_prob_at_price']:.6f} ({math_a['implied_prob_at_price']*100:.4f}%)")
    lines.append(f"**Fair probability (no-vig estimate):** {math_a['fair_prob_no_vig']:.6f} ({math_a['fair_prob_no_vig']*100:.4f}%)")
    lines.append(f"**Fair payout:** {math_a['fair_payout']:.2f}x")
    lines.append(f"**Effective hold:** {math_a['effective_hold']*100:.1f}%")
    lines.append("")

    # Card B
    lines.append("---")
    lines.append("## CARD B — 10+ Leg Longshot (LOTTERY TICKET)")
    lines.append("")
    lines.append(f"Legs: {len(card_b)} ({conviction_in_b} CONVICTION + {filler_in_b} FILLER)")
    lines.append("")
    lines.append("| # | Type | Game | Market | Side | Point | Price | Book | Reason |")
    lines.append("|---|------|------|--------|------|-------|-------|------|--------|")
    for i, leg in enumerate(card_b, 1):
        game = f"{leg['away_team'][:18]} @ {leg['home_team'][:18]}"
        pt = f"{leg['point']:.1f}" if leg['point'] is not None else "—"
        pr = f"{leg['price']:+.0f}" if leg['price'] is not None else "—"
        ltype = leg["leg_type"]
        lines.append(f"| {i} | {ltype} | {game} | {leg['market']} | {leg['side'][:22]} | {pt} | {pr} | {leg['book']} | {leg['ai_reason'][:55]} |")

    lines.append("")
    lines.append(f"**Combined decimal payout:** {math_b['combined_decimal_payout']:.2f}x")
    lines.append(f"**Implied probability (at offered price):** {math_b['implied_prob_at_price']:.6f} ({math_b['implied_prob_at_price']*100:.4f}%)")
    lines.append(f"**Fair probability (no-vig estimate):** {math_b['fair_prob_no_vig']:.6f} ({math_b['fair_prob_no_vig']*100:.4f}%)")
    lines.append(f"**Fair payout:** {math_b['fair_payout']:.2f}x")
    lines.append(f"**Effective hold:** {math_b['effective_hold']*100:.1f}%")
    lines.append("")

    return "\n".join(lines)


def log_cards(card_a, card_b, build_time):
    """Log both cards to the ticket log as card entries."""
    TICKET_LOG.parent.mkdir(parents=True, exist_ok=True)

    existing = []
    if TICKET_LOG.exists() and TICKET_LOG.stat().st_size > 0:
        with open(TICKET_LOG) as f:
            existing = json.load(f)

    before_count = len(existing)
    before_keys = set()
    for t in existing:
        before_keys.add((t.get("event_id", ""), t.get("build_time", ""),
                         t.get("card_id", "")))

    def card_entry(card_id, legs):
        return {
            "card_id": card_id,
            "build_time": build_time,
            "reference_only": True,
            "graded": False,
            "legs": [
                {
                    "event_id": l["event_id"],
                    "home_team": l["home_team"],
                    "away_team": l["away_team"],
                    "commence_time": l["commence_time"],
                    "market": l["market"],
                    "side": l["side"],
                    "point": l["point"],
                    "price": l["price"],
                    "book": l["book"],
                    "snapshot_utc": l.get("snapshot_utc"),
                    "complement_side": l.get("complement_side"),
                    "complement_point": l.get("complement_point"),
                    "complement_price": l.get("complement_price"),
                    "snapshot_time": build_time,
                    "leg_type": l["leg_type"],
                    "ai_reason": l["ai_reason"],
                }
                for l in legs
            ],
        }

    new_entries = [
        card_entry("A_5LEG", card_a),
        card_entry("B_LONGSHOT", card_b),
    ]

    merged = existing + new_entries
    # Append-only guard
    if len(merged) < before_count:
        raise RuntimeError(f"HALT: ticket count decrease {before_count} -> {len(merged)}")

    with open(TICKET_LOG, "w") as f:
        json.dump(merged, f, indent=2)
    print(f"Card log: {before_count} -> {len(merged)} (+{len(new_entries)} card entries)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-date", default=None, help="YYYY-MM-DD")
    parser.add_argument("--build-time", default=None, help="ISO8601 UTC")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    build_date = args.build_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    build_time = args.build_time or datetime.now(timezone.utc).isoformat()

    print(f"Build date: {build_date}")
    print(f"Build time: {build_time}")

    # Load conviction tickets from today's AI runs
    tickets = load_conviction_tickets(build_date)
    print(f"Today's conviction tickets: {len(tickets)}")

    if not tickets:
        print("No conviction tickets for today. Cannot build cards.")
        sys.exit(0)

    # Board for filler candidates. N42: built in memory as of build_time, because the saved
    # parquet drops the per-book `quotes` a real leg is chosen from (and "the most recent
    # board folder" need not be this build's board).
    from ncaaf.pipeline.build_ncaaf_board import build_board
    board_df, _ = build_board(2026, build_time=build_time)
    if not board_df.empty:
        board_df = board_df[board_df["commence_time"].str.startswith(build_date)]
    print(f"Board events today: {board_df['event_id'].nunique() if not board_df.empty else 0}")

    # Count total events and abstains from the ticket builder run
    total_events = board_df["event_id"].nunique() if not board_df.empty else 0
    abstain_count = total_events - len(set(t["event_id"] for t in tickets))

    card_a, card_b, conviction_in_b, filler_count = build_cards(
        tickets, board_df, build_time)

    # Load full board (not just today) for devig lookups
    full_board = pd.DataFrame()
    board_dirs = sorted(BOARD_DIR.glob("week=2026_*"))
    for bd in board_dirs:
        pq = bd / "ncaaf_board.parquet"
        if pq.exists():
            full_board = pd.concat([full_board, pd.read_parquet(pq)], ignore_index=True)

    math_a = compute_card_math(card_a, full_board)
    math_b = compute_card_math(card_b, full_board)

    print(f"\n--- CARD A MATH ---")
    for k, v in math_a.items():
        print(f"  {k}: {v}")
    print(f"\n--- CARD B MATH ---")
    for k, v in math_b.items():
        print(f"  {k}: {v}")

    # Write cards markdown
    md = format_cards_md(card_a, card_b, math_a, math_b, conviction_in_b, filler_count,
                         total_events, abstain_count, build_time)

    # Find the right output dir
    board_dirs = sorted(BOARD_DIR.glob("week=2026_*"))
    out_dir = board_dirs[-1] if board_dirs else BOARD_DIR / "week=2026_00"
    out_dir.mkdir(parents=True, exist_ok=True)
    cards_path = out_dir / "cards.md"
    with open(cards_path, "w") as f:
        f.write(md)
    print(f"\nCards written: {cards_path}")

    if args.dry_run:
        print("--dry-run: skipping log write")
        return

    # Log cards
    log_cards(card_a, card_b, build_time)

    # Print the full report
    print("\n" + "=" * 70)
    print(md)


if __name__ == "__main__":
    main()
