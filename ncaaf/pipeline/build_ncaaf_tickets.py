#!/usr/bin/env python3
"""
N04: NCAAF ticket writer with AI reasoning layer.

One Anthropic call per game. The AI layer's permitted outputs:
  1. Structured flags with headline source
  2. Short prose rationale
  3. Binary veto with reason
It MAY NOT output a number that enters pricing.
"""

import argparse, hashlib, json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=True)

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
KEY_FP = hashlib.sha256(ANTHROPIC_KEY.strip().encode()).hexdigest()[:8] if ANTHROPIC_KEY else "UNSET"
TICKET_LOG = ROOT / "ncaaf" / "logs" / "ncaaf_board_tickets_2026.json"


def _call_ai_layer(game_board_rows, news_articles, home, away):
    """Call Anthropic for one game. Returns (flags, rationale, veto, veto_reason)."""
    if not ANTHROPIC_KEY:
        raise RuntimeError("HALT: ANTHROPIC_API_KEY not set — AI layer cannot run")

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    except ImportError:
        raise RuntimeError("HALT: anthropic package not installed")

    # Build prompt
    board_text = "\n".join(
        f"  {r.get('market','?')} {r.get('outcome_name','?')}: point={r.get('consensus_point','?')}, "
        f"implied={r.get('consensus_implied','?'):.3f}, books={r.get('n_books','?')}, "
        f"disp={r.get('dispersion','?')}, move={r.get('movement','?')}"
        for r in game_board_rows
    ) if game_board_rows else "  (no board data)"

    news_text = "\n".join(
        f"  [{a.get('published','?')}] {a.get('headline','?')}"
        for a in news_articles[:10]
    ) if news_articles else "  (no recent news)"

    prompt = f"""You are analyzing an NCAAF game: {away} @ {home}.

MARKET DATA (stated facts from the odds archive):
{board_text}

RECENT NEWS:
{news_text}

YOUR TASK: Analyze this game for a parlay board. You must output EXACTLY:
1. STRUCTURED FLAGS — any of: qb_status_uncertain, weather_mentioned, travel_note,
   key_injury, coaching_change, rivalry_game. Each must cite the headline and published
   timestamp it came from. If none apply, output an empty list.
2. RATIONALE — 2-3 sentences explaining the market setup.
3. VETO — true/false. True means "do not include this game on the board" with a reason.

CRITICAL: You may NOT output any number that enters pricing — no probability,
no projected total, no "fair line". If you produce one it will be discarded.

Respond in JSON: {{"flags": [...], "rationale": "...", "veto": false, "veto_reason": null}}
"""

    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",  # N13: verified 2026-09-19
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        # Parse JSON from response
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        result = json.loads(text)

        # ENFORCE: discard any numeric pricing field
        for key in list(result.keys()):
            if key not in ("flags", "rationale", "veto", "veto_reason"):
                print(f"  AI output discarded field: {key}={result[key]}")
                del result[key]

        flags = result.get("flags", [])
        rationale = result.get("rationale", "")
        veto = result.get("veto", False)
        veto_reason = result.get("veto_reason")
        return flags, rationale, veto, veto_reason

    except Exception as e:
        raise RuntimeError(f"HALT: AI layer failed for {away} @ {home}: {str(e)[:200]}")


def build_tickets(board_df, news_articles, build_time):
    """Build tickets from board data + AI analysis."""
    tickets = []

    for eid in board_df["event_id"].unique():
        ev = board_df[board_df["event_id"] == eid]
        home = ev.iloc[0]["home_team"]
        away = ev.iloc[0]["away_team"]
        commence = ev.iloc[0]["commence_time"]

        # Get news for this game's teams
        game_news = [a for a in news_articles
                     if a.get("team_name") in (home, away)]

        # AI layer
        game_rows = ev.to_dict("records")
        flags, rationale, veto, veto_reason = _call_ai_layer(game_rows, game_news, home, away)

        if veto:
            print(f"  {away} @ {home}: VETOED — {veto_reason}")
            continue

        # Build a ticket from the game's markets
        legs = []
        for _, r in ev.iterrows():
            if r["market"] in ("spreads", "totals") and pd.notna(r["consensus_point"]):
                legs.append({
                    "market": r["market"],
                    "side": r["outcome_name"],
                    "point": r["consensus_point"],
                    "price": r["best_price"],
                    "book": r["best_book"],
                    "implied": r["consensus_implied"],
                })

        if len(legs) < 2:
            continue

        ticket = {
            "event_id": eid,
            "home_team": home,
            "away_team": away,
            "commence_time": commence,
            "legs": legs,
            "ai_flags": flags,
            "ai_rationale": rationale,
            "build_time": build_time,
            "reference_only": True,  # N01: hardrockbet_fl absent
            "close_price": None,  # filled by grader
            "clv": None,  # filled by grader
            "graded": False,
        }
        tickets.append(ticket)

    return tickets


def write_ticket_log(new_tickets):
    """N16: Append tickets to the log with monotonicity guard.

    - ticket count must never decrease
    - no (event_id, build_time) key on disk may vanish
    Halts on either violation.
    """
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
        raise RuntimeError(
            f"HALT: append-only violation — {len(lost)} tickets would vanish: "
            f"{list(lost)[:5]}")
    if len(merged) < before_count:
        raise RuntimeError(
            f"HALT: ticket count would decrease from {before_count} to {len(merged)}")

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

    # Load board
    from ncaaf.pipeline.build_ncaaf_board import build_board
    board_df, _ = build_board(args.season, build_time=bt)
    if board_df.empty:
        print("No board data"); sys.exit(0)

    # Load news
    news_dir = ROOT / "data" / "news_archive" / "ncaaf" / f"season={args.season}"
    news_articles = []
    if news_dir.exists():
        for f in sorted(news_dir.glob("*.json")):
            with open(f) as fh:
                news_articles.extend(json.load(fh))

    print(f"Board: {board_df['event_id'].nunique()} events, News: {len(news_articles)} articles")

    if args.dry_run:
        print("--dry-run: stopping before AI calls")
        return

    tickets = build_tickets(board_df, news_articles, bt)
    print(f"Tickets built: {len(tickets)}")

    # N16: append-only with monotonicity guard
    write_ticket_log(tickets)
    print(f"Ticket log: {len(existing)} total tickets -> {TICKET_LOG}")


if __name__ == "__main__":
    main()
