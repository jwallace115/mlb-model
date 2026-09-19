# NCAAF Parlay Board — SPEC v1

Created 2026-09-18 (Cowork session). Governing doc for `ncaaf/pipeline/build_ncaaf_board.py`
and siblings. Decisions live in `research/ncaaf_board/NCAAF_BOARD_DECISION_v1.md` as `N01…`.

---

## 0. What this is, and what it is explicitly not

Three layers, no sim: **lines → news → AI reasoning → ticket**.

It is **entertainment infrastructure with a free measurement side-effect**. It makes no
edge claim, has no backtest, and no signal in it has been validated. Every ticket logs its
decision price and its pre-kick closing price, so CLV accumulates at zero marginal cost. If
CLV turns out positive over a real sample, that is a finding nobody paid for. Until then the
board is a way to build correlated tickets from the market's own numbers.

**Relationship to the standing football rule.** `CLAUDE.md` demotes football to one boxed
prospective experiment and forbids new feature searches. This build does not search for
features. It fits nothing, tunes nothing, and selects nothing on outcomes. It reports market
quantities and logs CLV. If a future session adds a threshold fitted on results, that is a
new system and the standing rule applies to it.

---

## 1. Assets that already exist (verified 2026-09-18)

| Asset | Path | State |
|---|---|---|
| NCAAF line tape | `data/odds_archive/ncaaf/line_history/season=2026/` | **LIVE.** 657 snapshots, 2026-09-06 → present, ~30 min cadence, 186 events |
| Capture script | `shared/pipeline/multi_book_open_capture.py` | `americanfootball_ncaaf` already in `SPORTS`. 3 credits/call |
| Books in tape | — | draftkings, fanduel, betrivers, betmgm, bovada, pinnacle, betonlineag, lowvig, williamhill_us |
| Markets in tape | — | `h2h`, `spreads`, `totals` only |
| CFBD history | `research/ncaaf/*.parquet` | games, drives, advanced stats, SP+ ratings, venues, weather, betting lines, 2022–2025 |
| Canonical + model | `ncaaf/data/ncaaf_canonical_2022_2025.parquet`, `ncaaf/models/base_ridge_v1.pkl` | present, not used by this build |
| CLV helpers | `shared/clv_utils.py` | `american_to_implied`, `implied_to_american`, `compute_clv` reusable. `SPORT_MAP` has **no NCAAF key** |

Lead time: a game first appears in the tape a median of **6.2 days** before kickoff
(25th pct 5.6d, 75th pct 6.5d). A week-ahead board is possible from existing data.

---

## 2. Two defects found during spec work — both must be handled

### 2.1 `hardrockbet_fl` is absent from 100% of NCAAF snapshots

Sampled 66 of 657 snapshots: `hardrockbet_fl` present in **0**. The same script, same run,
same 10-book request returns it on **33 of 33** sampled NFL snapshots. Hard Rock does take
college football in Florida, so this is an Odds API coverage question, not a legal one.

**Consequence.** Until resolved, every price on an NCAAF board is a reference price at a book
Jeff cannot bet. That is a Check-4 failure for deployment purposes and it must be stated on
the board itself, not buried. Resolution is one live API call — item 1 of the work order.

**Rule: do not substitute.** If Hard Rock is genuinely unavailable on this sport, the board
labels its prices `REFERENCE_ONLY` and names the book. It does not quietly price off
DraftKings and call it a number Jeff can bet.

**RESOLVED 2026-09-18 (N01).** The probe ran. `hardrockbet_fl` was absent from **all 90**
NCAAF events, while the same request against NFL returned it on 15 of 29 — so the null control
passed and this is NCAAF coverage, not the key or the request. **Every NCAAF price on this
board is `REFERENCE_ONLY`.** Check 4 is therefore FAILING by design, not pending, and the board
header must say so on every output.

### 2.2 The line tape contains in-play odds — "last snapshot" is not the close

The capture runs every 30 minutes regardless of game state, and the Odds API keeps returning
an event after kickoff. Worked example, Pittsburgh vs Syracuse, `event_id`
`f06e90b4212fb514f3564ded9f190107`, kickoff 2026-09-17T23:30:00Z, DraftKings, Pittsburgh side
of `spreads`:

```
T-30 min   point -10.5   price -112     <- the actual close
T+30 min   point -13.5   price -120
T+60 min   point -18.5   price -112
T+210 min  point -14.5   price  +970    <- what "last snapshot" returns
```

**Consequence for this build.** Two hard requirements, enforced by test:
- the board may read only snapshots with `snapshot_utc < commence_time` **and**
  `snapshot_utc <= build_time`;
- the CLV grader's closing price is the last snapshot **strictly before** `commence_time`,
  never `files[-1]`.

**Consequence beyond this build (NFL, not fixed here).**
`nfl/sim/run_week.py::get_lines_from_history()` reads `files[-1]` and applies no
`commence_time` filter at all. For a board built while any game is in progress it will take
an in-play line and report it as the market line. `nfl/sim/anchor.py::get_market_lines()`
documents the pre-kickoff intent for 2026 but its live branch is an unimplemented
placeholder returning `(None, None)`. Flagged, not touched — separate order.

### 2.3 ESPN has no college-football injury table

Verified 2026-09-18:

- `…/college-football/teams/99/injuries` → `{}` (empty). No injury data. The NFL equivalent
  of this endpoint does return data; the college one does not.
- `…/college-football/teams/99` → no `injuries` and no `news` key.
- `…/college-football/news?team={id}&limit=N` → **works.** Returns `articles[]` with
  `headline`, `description`, `published` (ISO8601), `links`, and a `categories[]` carrying
  structured team references (`{"id":1098,"type":"team","uid":"s:20~l:23~t:99",
  "description":"LSU Tigers"}`).
- `…/college-football/teams?limit=900` → team list with `id`, `displayName`, `abbreviation`,
  `location`, `slug`. Includes non-FBS schools, so the map must be built against the teams
  actually on the board, not assumed.

**Consequence.** Layer 2 is **team-tagged news headlines with timestamps**, not a structured
injury feed. The AI layer reads those headlines. This is weaker than the NFL equivalent and
the board must say so rather than implying an injury check happened.

---

## 3. Layer design

### Layer 1 — Lines (deterministic, zero credits)
Reads the existing tape. Per game, per market, per side:
- **consensus**: median `point` and median no-vig implied probability across books present;
- **best number**: extreme `point` (and price at that point) + the book holding it;
- **dispersion**: max−min `point` across books — the repo's own NFL work found the open is
  where dispersion lives (1.213 pts open vs 0.711 close);
- **movement**: first-seen `point` → latest pre-kick `point`, and elapsed hours;
- **key-number proximity**: distance to 3, 7, 10, 14 on spreads.

No probabilities are invented. Every number is a market quantity or an arithmetic transform
of one.

### Layer 2 — News (deterministic, zero credits, no key)
`GET site.api.espn.com/apis/site/v2/sports/football/college-football/news?team={espn_id}&limit=20`
for each team on the board. Raw JSON stored append-only under
`data/news_archive/ncaaf/season=2026/`. Only articles with `published < build_time` reach the
AI layer. The Odds-API-name ↔ ESPN-id map is built once from the teams endpoint and its match
rate is **measured and reported**; anything under 100% of teams on the current board is a
HALT, not a partial run. Team-code normalization has silently destroyed a result in this repo
before (ops v9 §10, 2026-04-22).

### Layer 3 — AI selection (Anthropic API, `ANTHROPIC_API_KEY` in `.env`)
One call per game. Input: that game's Layer 1 rows and Layer 2 headlines, as stated facts,
with the favourite/underdog derived in code from the spread sign (N19).

**N20: The AI layer is the selection mechanism.** It picks at most one side per market per
game. Its selections are **unvalidated** — no backtest exists for them, and prospective CLV
(which needs ~125 observations) is the only thing that will ever grade them.

**The AI layer's permitted outputs:**
1. structured pick: `legs` with market, side (exact board outcome_name), point, and reason;
2. structured flags, each citing a headline + timestamp;
3. a short prose rationale;
4. `abstain` (bool) with reason — **genuinely available**; a picker that never declines picks noise;
5. ~~a binary `veto` with a reason~~ superseded by abstain (N20).

**Selection and pricing are SEPARATE.** The AI picks market and side; the code takes the best
number across the nine books. The AI never chooses the book or the price.

**It may not output a number that enters pricing.** No probability, no projected total, no
"fair line". If it emits one it is discarded. This boundary is the whole reason the build has
no leakage surface: an AI-produced number would be an unvalidated model wearing a signal's
clothes, and nothing in this repo would be able to audit it.

### Layer 4 — Ticket + CLV log
Correlated legs within one game from the game-market universe (whatever item 1 finds actually
exists — at minimum `h2h`, `spreads`, `totals`). Ticket written to
`ncaaf/logs/ncaaf_board_tickets_2026.json`, append-only, never re-graded, recording decision
price, book, snapshot timestamp, and null closing fields. The grader fills closing from the
last **pre-kick** snapshot and computes CLV on the no-vig scale, matching D64's NFL
convention (game identity required, push = void).

`ncaaf/logs/` is caught by the bare `logs/` rule at `.gitignore:12`. The directory is
un-ignored at lines 46–47 but **only `portal_2026_shadow.json` is allow-listed** (line 48). A
new log file there will be silently ignored — `git add -A` will not error and `push_daemon`
will report a clean exit. Ops v9 §16 procedure applies: add the `!` line, then verify with
`git check-ignore -v`.

---

## 4. The five research checks, stated

| Check | Verdict | Basis |
|---|---|---|
| **1a — same-day pipeline cleanliness** | **SPECIFIED, enforced by test** | Board reads only `snapshot_utc < commence_time` and `<= build_time`; news only `published < build_time`. The analogous NFL function currently fails this (§2.2) |
| **1b — historical feature provenance** | **REQUIRES ATTENTION (N07)** | The joint outcome table (joint_outcome_table_v1.parquet) is fitted on 2022-2025 historical data. Its spread/overUnder inputs are closing lines, not opening lines. Downstream use must condition on spreadOpen (the pre-game value), not spread (the close). The table itself is a historical aggregate |
| **2 — discovery-validation leakage** | **ADDRESSED for the joint table (N06)** | The |spread| buckets were chosen on 2022-24 (discovery). 2025 served as the OOS validation (N06). The table uses 2022-2025 combined. Any re-cutting of buckets after seeing 2025 would void this |
| **3 — research object vs live object** | **REQUIRES ATTENTION (N07)** | The joint table's spread column is the closing line. Live use must condition on spreadOpen. If the table is applied at game time using a spread that has moved from the open, the conditioning variable differs from the table's |
| **4 — economic reality** | **FAILING pending item 1** | Prices are real book prices, not synthetic −110 — but not from a book Jeff can bet. Until `hardrockbet_fl` resolves, every price is `REFERENCE_ONLY` |
| **5 — aggregate hiding** | **SPECIFIED** | CLV log breaks out by market, book, week, and lead-time bucket. A board that only ever fires on one market or one lead time is broken, not working |

**Standing posture:** no ticket from this board is evidence of anything until a CLV sample
exists, and CLV needs roughly 125 observations to say anything at all.

---

## 5. Cost

| Step | Credits |
|---|---|
| Item 1 probe — sport odds call | 3 (3 markets × 1 region-equivalent) |
| Item 1 probe — one event, candidate market enumeration | ≤ ~10 (≤10 markets × 1 region-equivalent, **one event only**) |
| Layers 1, 2, 4 — board, news, tickets, CLV | **0** — read the existing tape and a keyless public endpoint |
| Anthropic | ~1 call per game, ~15 games/week |

**CORRECTED 2026-09-18, after the probe ran.** This section originally quoted
`remaining=2198311`. That figure was wrong: it came from `logs/run_model_2026-03-28.log`,
**six months stale** and from a different plan. The live probe reported
`x-requests-remaining: 8976`.

Actual probe cost: **12 credits** (3 NCAAF + 3 NFL null control + 6 per-event market probe).

**The balance is the binding constraint now, not the probe.** At ~290 credits/day from the
30-minute three-sport snapshots, 8,976 is roughly **31 days of runway**, and `CLAUDE.md` sets
the alert threshold at 3,000. Consequences:

- Layers 1–4 of this build remain **zero** — they read the existing tape.
- The Tier-2 markets the probe found (`team_totals`, `alternate_spreads`, `alternate_totals`,
  `h2h_h1`, `spreads_h1`, `totals_h1`) are **not** free: ~6 credits/event × ~90 events ≈ **540
  credits per full-slate pull**. That is ~16 pulls against the current balance. Any decision to
  add them to the capture needs the arithmetic done against the live balance first, not
  against this document.
- Log `x-requests-remaining` on every run and state it in the session log.

The 10-book list must stay at 10 — an 11th silently doubles every call.

---

## 6. Paths

| Thing | Path | New? |
|---|---|---|
| Board builder | `ncaaf/pipeline/build_ncaaf_board.py` | new, matches `<sport>/pipeline/` |
| News puller | `ncaaf/pipeline/pull_ncaaf_news.py` | new |
| Ticket writer | `ncaaf/pipeline/build_ncaaf_tickets.py` | new |
| CLV grader | `ncaaf/pipeline/grade_ncaaf_tickets.py` | new |
| Board output | `ncaaf/data/board/week=2026_NN/` | new, mirrors `nfl/data/sim/outputs/week=2026_02/` |
| News archive | `data/news_archive/ncaaf/season=2026/` | new, mirrors `data/odds_archive/`, `data/weather_archive/` |
| Ticket log | `ncaaf/logs/ncaaf_board_tickets_2026.json` | new — **needs `.gitignore` allow-list** |
| Spec / decisions | `research/ncaaf_board/` | this file |
