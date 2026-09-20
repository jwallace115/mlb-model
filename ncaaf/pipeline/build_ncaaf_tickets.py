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


def select_best_quote(quotes, market, side):
    """N37: select the best quote for a leg from real per-book quotes.

    Rule: best point for the side, ties broken by best price, then book name.
      spreads: most positive point (max)
      Over:    lowest point (min)
      Under:   HIGHEST point (max)
    Best price = highest American odds (less juice / more payout).
    """
    valid = [q for q in quotes
             if q.get("point") is not None and q.get("price") is not None]
    if not valid:
        return None

    if market == "spreads" or (market == "totals" and "Under" in str(side)):
        valid.sort(key=lambda q: (-q["point"], -q["price"], q.get("book", "")))
    else:  # Over, h2h
        valid.sort(key=lambda q: (q["point"], -q["price"], q.get("book", "")))

    return valid[0]


def validate_leg_against_tape(leg, tape_df):
    """N37 1d: assert that a leg's (book, market, side, point, price) exists in the tape."""
    match = tape_df[
        (tape_df["bookmaker"] == leg["book"])
        & (tape_df["market"] == leg["market"])
        & (tape_df["outcome_name"] == leg["side"])
        & (tape_df["point"] == leg["point"])
        & (tape_df["price"] == leg["price"])
    ]
    if match.empty:
        raise RuntimeError(
            f"HALT: leg not in tape — ({leg['book']}, {leg['market']}, "
            f"{leg['side']}, {leg['point']}, {leg['price']})")


NEWS_PER_GAME = 10
NEWS_RECENCY_DAYS = 14


def _article_key(article):
    """Stable key for an article: id if present, else sha1(team+published+headline)."""
    aid = str(article.get("id", "")).strip()
    if aid:
        return aid
    team = article.get("_team_name", article.get("team_name", ""))
    pub = article.get("published", "")
    hl = article.get("headline", "")
    return hashlib.sha1(f"{team}|{pub}|{hl}".encode()).hexdigest()


def _article_pull_time(article):
    """Return pull time as ISO string, accepting both _pull_time and pull_time."""
    return article.get("_pull_time", article.get("pull_time", ""))


def load_news(news_dir, build_time):
    """N39: Load and de-dup news articles, respecting build_time.

    Accepts both `_team_name` (new puller) and `team_name` (legacy).
    Legacy articles with empty id get sha1(team+published+headline) as key.
    De-dup keeps the latest version WITH pull time <= build_time.
    """
    import gzip as _gzip, re as _re
    from pathlib import Path

    news_dir = Path(news_dir)
    if not news_dir.exists():
        return []

    build_dt = datetime.fromisoformat(
        build_time.replace("Z", "+00:00") if "Z" in build_time else build_time)
    if build_dt.tzinfo is None:
        build_dt = build_dt.replace(tzinfo=timezone.utc)

    all_articles = []
    for f in sorted(news_dir.iterdir()):
        if f.name.startswith("_") or f.name.startswith("index_"):
            continue
        if f.suffix == ".json":
            with open(f) as fh:
                all_articles.extend(json.load(fh))
        elif f.name.endswith(".json.gz") and f.name.startswith("news_"):
            with _gzip.open(f, "rt", encoding="utf-8") as fh:
                all_articles.extend(json.load(fh))

    # De-duplicate: key by article id (or sha1 for legacy no-id),
    # keep latest version with pull_time <= build_time
    seen = {}  # key -> (lastModified, article)
    for a in all_articles:
        key = _article_key(a)
        pull_str = _article_pull_time(a)

        # Enforce build_time cutoff if pull_time is present
        if pull_str:
            try:
                pull_dt = datetime.fromisoformat(
                    pull_str.replace("Z", "+00:00") if "Z" in pull_str else pull_str)
                if pull_dt.tzinfo is None:
                    pull_dt = pull_dt.replace(tzinfo=timezone.utc)
                if pull_dt > build_dt:
                    continue  # pulled after build — must not enter
            except (ValueError, TypeError):
                pass

        lm = a.get("lastModified", a.get("published", ""))
        prev_lm = seen.get(key, ("", None))[0] if key in seen else ""
        if lm >= prev_lm:
            seen[key] = (lm, a)

    return [v[1] for v in seen.values()]


def game_news_for(articles, home_team, away_team, max_per_game=NEWS_PER_GAME,
                  recency_days=NEWS_RECENCY_DAYS):
    """N39: return news for a game's two teams, newest published first, capped."""
    game_articles = []
    for a in articles:
        team = a.get("_team_name", a.get("team_name", ""))
        if team in (home_team, away_team):
            game_articles.append(a)

    # Sort by published descending
    game_articles.sort(key=lambda a: a.get("published", ""), reverse=True)
    return game_articles[:max_per_game]


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

    # 1c: every leg's (book, point, price) exists in some quote on the board
    quote_set = set()
    for r in board_rows:
        for q in r.get("quotes", []):
            quote_set.add((r["market"], r["outcome_name"],
                           q.get("book"), q.get("point"), q.get("price")))
    for leg in legs:
        key = (leg["market"], leg["side"], leg.get("book"),
               leg["point"], leg.get("price"))
        if key not in quote_set:
            raise RuntimeError(
                f"HALT: leg not in any book's quotes — {key}")


def build_tickets(board_df, news_articles, build_time, tape=None):
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

        # N39: sorted, capped, accepting both field names
        game_news = game_news_for(news_articles, home, away)

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

        # N37: Build legs from real per-book quotes, not consensus/best mix
        final_legs = []
        for al in ai_legs:
            mkt = al.get("market")
            side = al.get("side")
            if not mkt or not side:
                continue
            board_match = ev[(ev["market"] == mkt) & (ev["outcome_name"] == side)]
            if board_match.empty:
                print(f"  WARNING: AI picked {mkt}/{side} but not on board — skipping")
                continue
            br = board_match.iloc[0]
            quotes = br.get("quotes", [])
            if not quotes:
                print(f"  WARNING: no quotes for {mkt}/{side} — skipping")
                continue
            best_q = select_best_quote(quotes, mkt, side)
            if best_q is None:
                continue

            # Find complement from the other side, same book and snapshot
            comp = None
            other_rows = ev[(ev["market"] == mkt) & (ev["outcome_name"] != side)]
            if not other_rows.empty:
                for _, orow in other_rows.iterrows():
                    for oq in orow.get("quotes", []):
                        if (oq["book"] == best_q["book"]
                                and oq["snapshot_utc"] == best_q["snapshot_utc"]):
                            comp = oq
                            break
                    if comp:
                        break

            leg = {
                "market": mkt, "side": side,
                "point": best_q["point"],
                "price": best_q["price"],
                "book": best_q["book"],
                "snapshot_utc": best_q["snapshot_utc"],
                "implied": br["consensus_implied"],
                "ai_reason": al.get("reason", ""),
            }
            if comp:
                leg["complement_side"] = other_rows.iloc[0]["outcome_name"]
                leg["complement_point"] = comp["point"]
                leg["complement_price"] = comp["price"]

            # N37 1d: assert leg exists in tape
            if tape is not None:
                validate_leg_against_tape(leg, tape)

            final_legs.append(leg)

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

    from ncaaf.pipeline.build_ncaaf_board import build_board, load_tape
    board_df, _ = build_board(args.season, build_time=bt)
    if board_df.empty:
        print("No board data"); sys.exit(0)
    tape = load_tape(args.season, bt)

    news_dir = ROOT / "data" / "news_archive" / "ncaaf" / f"season={args.season}"
    news_articles = load_news(news_dir, bt)

    # Coverage check
    board_teams = set(board_df["home_team"].unique()) | set(board_df["away_team"].unique())
    teams_with_news = set()
    for a in news_articles:
        tn = a.get("_team_name", a.get("team_name", ""))
        if tn in board_teams:
            teams_with_news.add(tn)
    coverage = len(teams_with_news)
    total_teams = len(board_teams)
    print(f"  News coverage: {coverage}/{total_teams} board teams have >= 1 article")
    if total_teams > 0 and coverage / total_teams < 0.25:
        print(f"HALT: news coverage {coverage}/{total_teams} ({coverage/total_teams*100:.0f}%) "
              f"below 25% threshold")
        sys.exit(1)

    print(f"Board: {board_df['event_id'].nunique()} events, News: {len(news_articles)} articles (de-duped)")

    if args.dry_run:
        print("--dry-run: stopping before AI calls")
        return

    tickets = build_tickets(board_df, news_articles, bt, tape=tape)
    write_ticket_log(tickets)


if __name__ == "__main__":
    main()
