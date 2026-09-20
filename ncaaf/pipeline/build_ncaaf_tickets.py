#!/usr/bin/env python3
"""
N19-N20: NCAAF ticket writer — AI selects sides.

The AI picks market + side per game. It never emits a pricing number.
Favourite/underdog derived in CODE from the spread sign, not by the AI.
"""

import argparse, hashlib, json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=True)

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
KEY_FP = hashlib.sha256(ANTHROPIC_KEY.strip().encode()).hexdigest()[:8] if ANTHROPIC_KEY else "UNSET"
TICKET_LOG = ROOT / "ncaaf" / "logs" / "ncaaf_board_tickets_2026.json"


def _derive_matchup(board_rows):
    """N19: derive favourite/underdog from the spread sign in CODE."""
    spreads = [r for r in board_rows if r.get("market") == "spreads"]
    totals = [r for r in board_rows if r.get("market") == "totals"]
    if not spreads:
        return None

    # The side with negative consensus_point is the favourite
    fav_row = min(spreads, key=lambda r: r.get("consensus_point", 0))
    dog_row = max(spreads, key=lambda r: r.get("consensus_point", 0))
    fav = fav_row["outcome_name"]
    dog = dog_row["outcome_name"]
    spread_mag = abs(fav_row["consensus_point"])

    over_row = next((r for r in totals if "Over" in str(r.get("outcome_name", ""))), None)
    total_line = over_row["consensus_point"] if over_row else None

    return {
        "favourite": fav, "underdog": dog, "spread_magnitude": spread_mag,
        "total_line": total_line, "spreads": spreads, "totals": totals,
        "fav_row": fav_row, "dog_row": dog_row, "over_row": over_row,
    }


def _call_ai_layer(matchup, news_articles, home, away):
    """Call Anthropic for one game. Returns (pick, discarded).

    pick = {"legs": [...], "abstain": bool, "abstain_reason": str|None,
            "flags": [...], "rationale": str}
    """
    if not ANTHROPIC_KEY:
        raise RuntimeError("HALT: ANTHROPIC_API_KEY not set")

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    except ImportError:
        raise RuntimeError("HALT: anthropic package not installed")

    fav = matchup["favourite"]
    dog = matchup["underdog"]
    spread = matchup["spread_magnitude"]
    total = matchup["total_line"]

    # Build spread options text
    spread_text = f"{fav} is favoured by {spread}. {dog} is the underdog receiving {spread}."
    total_text = f"Total line is {total}." if total else ""

    news_text = "\n".join(
        f"  [{a.get('published', '?')}] {a.get('headline', '?')}"
        for a in news_articles[:10]
    ) if news_articles else "  (no recent news)"

    # Available sides for the AI to pick from
    spread_sides = [f'"{matchup["fav_row"]["outcome_name"]}" (favourite, point={matchup["fav_row"]["consensus_point"]})',
                    f'"{matchup["dog_row"]["outcome_name"]}" (underdog, point={matchup["dog_row"]["consensus_point"]})']
    total_sides = []
    for r in matchup["totals"]:
        total_sides.append(f'"{r["outcome_name"]}" (point={r["consensus_point"]})')

    prompt = f"""You are picking sides for an NCAAF parlay ticket: {away} @ {home}.

MATCHUP FACTS (derived from the odds archive):
  {spread_text}
  {total_text}
  Dispersion: spreads {matchup['fav_row'].get('dispersion', 0):.1f}, totals {matchup.get('over_row', {}).get('dispersion', 0) if matchup.get('over_row') else 0:.1f}

AVAILABLE SPREAD SIDES:
  {chr(10).join('  ' + s for s in spread_sides)}

AVAILABLE TOTAL SIDES:
  {chr(10).join('  ' + s for s in total_sides)}

RECENT NEWS:
{news_text}

YOUR TASK: Pick at most ONE side for spreads and at most ONE side for totals.
You may ABSTAIN from this game entirely if neither side has a clear edge from
the market setup or news. A picker that picks every game picks noise — abstain
when appropriate.

RESPOND IN JSON:
{{
  "legs": [
    {{"market": "spreads", "side": "<exact outcome_name>", "point": <number>, "reason": "<one sentence>"}},
    {{"market": "totals", "side": "<exact outcome_name>", "point": <number>, "reason": "<one sentence>"}}
  ],
  "abstain": false,
  "abstain_reason": null,
  "flags": [],
  "rationale": "<2-3 sentences>"
}}

If abstaining: {{"legs": [], "abstain": true, "abstain_reason": "<why>", "flags": [], "rationale": "<brief>"}}

CRITICAL: You may NOT output any number that enters pricing — no probability,
no projected total, no "fair line", no "fair spread", no "win probability".
If you produce one it will be discarded.
"""

    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        result = json.loads(text)

        # N17: discard any field not in the allowed set
        _ALLOWED = {"legs", "abstain", "abstain_reason", "flags", "rationale"}
        discarded = {}
        for key in list(result.keys()):
            if key not in _ALLOWED:
                discarded[key] = result.pop(key)
                print(f"  AI output discarded field: {key}={discarded[key]}")

        return result, discarded

    except Exception as e:
        raise RuntimeError(f"HALT: AI layer failed for {away} @ {home}: {str(e)[:200]}")


def _validate_ticket(ticket, board_rows):
    """N19: assert invariants before writing."""
    legs = ticket.get("legs", [])

    # 1b: no both-sides of the same market
    markets_seen = {}
    for leg in legs:
        mkt = leg["market"]
        if mkt in markets_seen:
            raise RuntimeError(
                f"HALT: both-sides violation — {mkt} has sides "
                f"{markets_seen[mkt]} and {leg['side']} in the same ticket")
        markets_seen[mkt] = leg["side"]

    # 1c: every leg exists on the board
    board_set = set()
    for r in board_rows:
        board_set.add((r["market"], r["outcome_name"], r.get("consensus_point")))
    for leg in legs:
        key = (leg["market"], leg["side"], leg["point"])
        if key not in board_set:
            raise RuntimeError(
                f"HALT: leg not on board — {key} not in board rows")


def build_tickets(board_df, news_articles, build_time):
    """Build tickets — AI selects sides."""
    tickets = []
    abstain_count = 0

    for eid in board_df["event_id"].unique():
        ev = board_df[board_df["event_id"] == eid]
        home = ev.iloc[0]["home_team"]
        away = ev.iloc[0]["away_team"]
        commence = ev.iloc[0]["commence_time"]

        game_rows = ev.to_dict("records")
        matchup = _derive_matchup(game_rows)
        if matchup is None:
            continue

        game_news = [a for a in news_articles if a.get("team_name") in (home, away)]

        result, discarded = _call_ai_layer(matchup, game_news, home, away)

        if result.get("abstain"):
            abstain_count += 1
            print(f"  {away} @ {home}: ABSTAIN — {result.get('abstain_reason', '?')}")
            continue

        ai_legs = result.get("legs", [])
        if not ai_legs:
            abstain_count += 1
            print(f"  {away} @ {home}: no legs returned (implicit abstain)")
            continue

        # Build legs with best price from the board
        final_legs = []
        for al in ai_legs:
            mkt = al.get("market")
            side = al.get("side")
            point = al.get("point")
            if not mkt or not side:
                continue
            # Find the best price on the board for this side
            board_match = ev[(ev["market"] == mkt) & (ev["outcome_name"] == side)]
            if board_match.empty:
                print(f"  WARNING: AI picked {mkt}/{side} but not on board — skipping")
                continue
            br = board_match.iloc[0]
            final_legs.append({
                "market": mkt, "side": side,
                "point": br["consensus_point"],
                "price": br["best_price"],
                "book": br["best_book"],
                "implied": br["consensus_implied"],
                "ai_reason": al.get("reason", ""),
            })

        if not final_legs:
            continue

        ticket = {
            "event_id": eid,
            "home_team": home, "away_team": away,
            "commence_time": commence,
            "favourite": matchup["favourite"],
            "underdog": matchup["underdog"],
            "spread_magnitude": matchup["spread_magnitude"],
            "legs": final_legs,
            "ai_flags": result.get("flags", []),
            "ai_rationale": result.get("rationale", ""),
            "ai_discarded": discarded,
            "build_time": build_time,
            "reference_only": True,
            "close_price": None, "clv": None,
            "graded": False,
        }

        # Validate before adding
        _validate_ticket(ticket, game_rows)
        tickets.append(ticket)

        sides = ", ".join(f"{l['market']}:{l['side']}" for l in final_legs)
        print(f"  {away} @ {home}: {len(final_legs)} legs [{sides}]")

    print(f"\nTickets: {len(tickets)}, Abstains: {abstain_count}")
    return tickets


def write_ticket_log(new_tickets):
    """N16: Append tickets to the log with monotonicity guard."""
    TICKET_LOG.parent.mkdir(parents=True, exist_ok=True)
    existing = []
    if TICKET_LOG.exists() and TICKET_LOG.stat().st_size > 0:
        with open(TICKET_LOG) as f:
            existing = json.load(f)

    before_count = len(existing)
    before_keys = set((t["event_id"], t["build_time"]) for t in existing)

    merged = existing + list(new_tickets)
    after_keys = set((t["event_id"], t["build_time"]) for t in merged)
    lost = before_keys - after_keys
    if lost:
        raise RuntimeError(f"HALT: append-only violation — {len(lost)} tickets vanish")
    if len(merged) < before_count:
        raise RuntimeError(f"HALT: ticket count decrease {before_count} -> {len(merged)}")

    with open(TICKET_LOG, "w") as f:
        json.dump(merged, f, indent=2)
    print(f"Ticket log: {before_count} -> {len(merged)} (+{len(new_tickets)})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--build-time", help="ISO8601 UTC")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    bt = args.build_time or datetime.now(timezone.utc).isoformat()
    print(f"ANTHROPIC_API_KEY fingerprint: {KEY_FP}")
    print(f"Build time: {bt}")

    from ncaaf.pipeline.build_ncaaf_board import build_board
    board_df, _ = build_board(args.season, build_time=bt)
    if board_df.empty:
        print("No board data"); sys.exit(0)

    news_dir = ROOT / "data" / "news_archive" / "ncaaf" / f"season={args.season}"
    news_articles = []
    newest_pull_utc = None
    if news_dir.exists():
        # Read both legacy .json and new .json.gz; ignore index_* and _seen.json
        import gzip as _gzip, re as _re
        for f in sorted(news_dir.iterdir()):
            if f.name.startswith("_") or f.name.startswith("index_"):
                continue
            if f.suffix == ".json":
                with open(f) as fh:
                    news_articles.extend(json.load(fh))
            elif f.name.endswith(".json.gz") and f.name.startswith("news_"):
                with _gzip.open(f, "rt", encoding="utf-8") as fh:
                    news_articles.extend(json.load(fh))
            else:
                continue
            # Extract UTC timestamp from filename for freshness
            m = _re.search(r"(\d{8}T\d{4}Z)", f.name)
            if m:
                ts_str = m.group(1)
                ts = datetime.strptime(ts_str, "%Y%m%dT%H%MZ").replace(tzinfo=timezone.utc)
                if newest_pull_utc is None or ts > newest_pull_utc:
                    newest_pull_utc = ts

        # De-duplicate by article id, keeping latest version
        seen = {}
        for a in news_articles:
            aid = str(a.get("id", ""))
            lm = a.get("lastModified", a.get("published", ""))
            prev_lm = seen.get(aid, ("", None))[0] if aid in seen else ""
            if not aid or lm >= prev_lm:
                seen[aid] = (lm, a)
        news_articles = [v[1] for v in seen.values()]

    if newest_pull_utc:
        build_dt = datetime.fromisoformat(bt.replace("Z", "+00:00")) if "Z" in bt else datetime.fromisoformat(bt)
        if build_dt.tzinfo is None:
            build_dt = build_dt.replace(tzinfo=timezone.utc)
        pull_age_h = (build_dt - newest_pull_utc).total_seconds() / 3600
        print(f"  newest news pull: {newest_pull_utc.isoformat()} (age: {pull_age_h:.1f}h)")
        if pull_age_h > 24:
            print(f"HALT: newest news pull is {pull_age_h:.1f}h old (>24h) — stale news")
            sys.exit(1)
    else:
        print("WARNING: no news files found with parseable timestamps")

    print(f"Board: {board_df['event_id'].nunique()} events, News: {len(news_articles)} articles (de-duped)")

    if args.dry_run:
        print("--dry-run: stopping before AI calls")
        return

    tickets = build_tickets(board_df, news_articles, bt)
    write_ticket_log(tickets)


if __name__ == "__main__":
    main()
