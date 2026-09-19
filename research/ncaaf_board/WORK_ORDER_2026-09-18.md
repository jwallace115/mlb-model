NCAAF PARLAY BOARD — WORK ORDER, 2026-09-18

Governing spec: research/ncaaf_board/NCAAF_BOARD_SPEC_v1.md — READ IT FIRST. It records two
verified defects and one false premise that this order is built around. Decisions go in
research/ncaaf_board/NCAAF_BOARD_DECISION_v1.md as N01..N04, each in the SAME COMMIT as its
item. The WORK ORDERS section of CLAUDE.md binds this session whether or not it is repeated
here.

Framing, so no item drifts: this is entertainment infrastructure that logs CLV as a free
side-effect. It makes no edge claim. Nothing in it is fitted, tuned, or selected on outcomes.
If an item tempts you to add a threshold derived from results, stop and report instead.

Commit AND push after each item before starting the next. Use:
    git pull --rebase --autostash && git push
logs/ is gitignored — use git add -f for logs/agent_sessions.md.

--------------------------------------------------------------------------------
ITEM 1 — PROBE: what books and markets does the Odds API actually serve for NCAAF?

No build. This is discovery, and its result changes item 4's design.

PRE-REGISTER, in research/ncaaf_board/probe_2026-09-18.md, BEFORE making any call:
  - Prediction A: hardrockbet_fl will NOT be returned for americanfootball_ncaaf.
    Basis: 0 of 66 sampled snapshots in the existing tape contain it.
  - Prediction B: team_totals WILL be available for americanfootball_ncaaf.
    Basis: Jeff's read of the market; untested.
  Then run the calls and state plainly whether each held. Do not tune anything to rescue a
  prediction that did not hold.

NULL CONTROL — this is the point of the item, do not skip it:
  Make the SAME 10-book request against americanfootball_nfl in the same run.
  hardrockbet_fl MUST come back there. If it does not, the finding is about the key or the
  request, not about NCAAF coverage, and every conclusion below is void. Report which.

CALLS (state x-requests-remaining before and after):
  1a. GET /v4/sports/americanfootball_ncaaf/odds
      bookmakers = the exact 10-book list in shared/pipeline/multi_book_open_capture.py
      markets = h2h,spreads,totals          -> 3 credits
      Report: which of the 10 books returned, and on how many events each.
  1b. Same request, sport = americanfootball_nfl  -> 3 credits   [null control]
  1c. GET /v4/sports/americanfootball_ncaaf/events/{one_event_id}/odds
      ONE event only. Probe candidate markets in a single call:
      team_totals, alternate_spreads, alternate_totals, spreads_h1, totals_h1, h2h_h1,
      and whichever player-prop keys the API documents for this sport.
      -> <= ~10 credits. Do NOT loop over events. Do NOT exceed 10 bookmakers.
      Report which market keys return outcomes and which return nothing.

BUDGET: ~13 credits total, one time. Most recent capture log shows remaining=2198311.
If the run would exceed 25 credits, stop and report the arithmetic instead.

HALT CONDITIONS:
  - Null control fails (no hardrockbet_fl on NFL either) -> HALT. Report, do not proceed.
  - hardrockbet_fl absent on NCAAF but present on NFL -> do NOT substitute another book as
    the pricing reference. Record it and continue; item 2 will label prices REFERENCE_ONLY.

DECISION N01: the book and market universe actually available for NCAAF, with the credit
cost of each market family, and the REFERENCE_ONLY determination. Same commit.

--------------------------------------------------------------------------------
ITEM 2 — BOARD BUILDER + THE PRE-KICK GUARD

New file: ncaaf/pipeline/build_ncaaf_board.py
Output:   ncaaf/data/board/week=2026_NN/ncaaf_board.md and .parquet

Reads only data/odds_archive/ncaaf/line_history/season=2026/*.parquet.
Zero API calls. Zero credits.

HARD REQUIREMENT — the reason this item exists:
  A row is eligible only if  snapshot_utc < commence_time  AND  snapshot_utc <= build_time.
  Never read files[-1] as "the current line". The tape contains in-play odds: the capture
  runs every 30 minutes regardless of game state and the API keeps returning an event after
  kickoff.

REGRESSION TEST — new file ncaaf/pipeline/tests/test_ncaaf_board_prekick.py
  Use the real event already in the tape:
      event_id       f06e90b4212fb514f3564ded9f190107   (Pittsburgh vs Syracuse)
      commence_time  2026-09-17T23:30:00Z
      bookmaker      draftkings, market spreads, outcome Pittsburgh Panthers
  Assert the builder returns point = -10.5, price = -112  (the T-30min snapshot).
  Assert it does NOT return point = -14.5, price = +970   (the T+210min snapshot).
  Confirm the test CAN fail: run it against a naive files[-1] implementation and show it
  goes red. A test that passes both ways is not a test.

NULL CONTROL: for games that have NOT kicked off, the pre-kick filter must change nothing.
  Report row counts per book before and after the filter for un-started games — they must be
  identical — and separately for started games, where they must differ. State both numbers.

PER GAME, PER MARKET, PER SIDE, compute from the tape only:
  - consensus point (median across books present) and consensus no-vig implied probability
  - best number: extreme point, the price at it, and the book holding it
  - cross-book dispersion: max - min point
  - movement: first-seen point -> latest pre-kick point, and hours elapsed
  - key-number proximity on spreads: distance to 3, 7, 10, 14
  - n_books contributing, and the age in minutes of the newest eligible snapshot
No invented probabilities. Every field is a market quantity or arithmetic on one.

Board header must carry, verbatim, the REFERENCE_ONLY determination from N01 and the name of
the book each price came from.

DECISION N02: the pre-kick eligibility rule and the board's field set. Same commit.

--------------------------------------------------------------------------------
ITEM 3 — NEWS LAYER (ESPN) + TEAM MAP WITH A MEASURED MATCH RATE

New file: ncaaf/pipeline/pull_ncaaf_news.py
Output:   data/news_archive/ncaaf/season=2026/  (append-only, raw JSON, never overwritten)

No API key. Zero credits. Base: site.api.espn.com/apis/site/v2/sports/football/college-football

RE-VERIFY, do not trust the spec, and record what you actually got:
  GET /teams/99/injuries   -> expected {} (empty; college football has no injury table here)
  GET /teams/99            -> expected no injuries key and no news key
  If either now returns data, that is better than expected — say so and use it.

WHAT IS ACTUALLY AVAILABLE:
  GET /news?team={espn_id}&limit=20
      -> articles[] with headline, description, published (ISO8601), links,
         and categories[] carrying structured team refs, e.g.
         {"id":1098,"type":"team","uid":"s:20~l:23~t:99","description":"LSU Tigers"}
  GET /teams?limit=900
      -> id, displayName, abbreviation, location, slug. Includes non-FBS schools.

TEAM MAP: Odds API name ("Wake Forest Demon Deacons") -> ESPN team id.
  Build it from the teams endpoint against the teams ACTUALLY ON THE CURRENT BOARD.
  MEASURE the match rate and print it. Anything below 100% of board teams is a HALT with the
  unmatched names listed — not a partial run, not a fuzzy fallback. Silent team-code
  mismatching has already destroyed a result in this repo (ops v9 §10, 2026-04-22: 2.3%
  match rate went unnoticed).
  Commit the map as a file so it is reproducible, not rebuilt implicitly on each run.

PIT: only articles with published < build_time are eligible.
NULL CONTROL: pick a build_time earlier than the newest stored article and show that article
  is excluded, while an older one for the same team is included. State both counts.

RUNTIME: ~30 board teams x 1 call x 1s sleep = ~30s. Do not copy a sleep value from another
script. If the team count is larger, recompute before running.

DECISION N03: news, not injuries, is layer 2 for NCAAF, with the endpoint evidence. Same commit.

--------------------------------------------------------------------------------
ITEM 4 — AI LAYER, TICKET WRITER, CLV LOG

New files: ncaaf/pipeline/build_ncaaf_tickets.py, ncaaf/pipeline/grade_ncaaf_tickets.py
Log:       ncaaf/logs/ncaaf_board_tickets_2026.json   (append-only, never re-graded)

DO THIS FIRST, before writing the log file:
  ncaaf/logs/ is caught by the bare logs/ rule at .gitignore:12. The directory is un-ignored
  at lines 46-47 but ONLY portal_2026_shadow.json is allow-listed (line 48). A new file there
  is silently ignored: git add -A will not error and push_daemon reports a clean exit.
  Add:  !ncaaf/logs/ncaaf_board_tickets_2026.json
  Then verify:  git check-ignore -v ncaaf/logs/ncaaf_board_tickets_2026.json
  and paste the output showing it is NOT ignored. Commit .gitignore alone (ops v9 §16).

AI LAYER — one Anthropic call per game. ANTHROPIC_API_KEY is in .env; use
load_dotenv(path, override=True) and log sha256(key)[:8], never the key.
  Input: that game's item-2 board rows and item-3 headlines, presented as stated facts.
  PRE-REGISTERED CONSTRAINT — the permitted outputs are exactly three:
    (1) structured flags, each carrying the headline and published timestamp it came from
    (2) a short prose rationale
    (3) a binary veto with a reason
  It MAY NOT output a number that enters pricing — no probability, no projected total, no
  "fair line". Assert this in code: any numeric pricing field in the response is discarded
  and the discard is logged. An AI-produced number would be an unvalidated model that nothing
  in this repo can audit.

TICKET: correlated legs within one game, from the market universe N01 found to exist.
  Record: legs, decision price, book, the snapshot_utc the price came from, build_time,
  stake, the REFERENCE_ONLY flag, and null closing fields.

GRADER: closing price is the last snapshot STRICTLY BEFORE commence_time. Never files[-1].
  CLV on the no-vig scale, game identity required, push = void — match D64's NFL convention.
  Reuse shared/clv_utils.py; it needs "NCAAF": "americanfootball_ncaaf" added to SPORT_MAP.
  UPDATE-ONLY: never append a row, never re-grade a row already marked graded.
  Break CLV out by market, by book, by week, and by lead-time bucket. An aggregate alone is
  not a result.

NULL CONTROL: run the grader twice on the same ticket set. The second run must change zero
  rows. Report the count of rows changed on each run — expected N then 0.

EXPECTED-TO-FIRE GATE: with hardrockbet_fl likely absent, the REFERENCE_ONLY flag will be set
  on every ticket. That is the correct outcome. Do not relax it and do not substitute a book
  to make it clear.

DECISION N04: ticket schema, the AI output boundary, and the CLV convention. Same commit.

--------------------------------------------------------------------------------
CLOSING — required

Append to logs/agent_sessions.md (git add -f). Timestamp from `date -u`, not from memory.
Separate what a command RETURNED from what it MEANS. "DONE" means exit 0, not safe.
State explicitly:
  - what was NOT done
  - what remains UNVERIFIED
  - for any red test: does it fail at the parent commit with the same value, and CAN it go
    green? This suite has no xfail/skip markers, so pytest cannot exit 0 alongside real
    failures — if you see exit 0 with reds, a wrapper swallowed it. Say which.

DO NOT TOUCH in this order (known, separate):
  - nfl/sim/run_week.py::get_lines_from_history() reads files[-1] with no commence_time
    filter and will return an in-play line for any game already started.
  - nfl/sim/anchor.py::get_market_lines() 2026 branch is a placeholder returning (None, None).
  - ncaaf/logs/portal_2026_shadow.json has never been written; the Weeks 1-4 portal forward
    test has logged nothing and that window has now passed.
