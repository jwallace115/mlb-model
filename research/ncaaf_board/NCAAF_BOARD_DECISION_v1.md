# NCAAF Parlay Board — DECISION LOG v1

Numbered `N01…`, deliberately separate from the `D…` series in
`research/nfl_sim/NFL_SIM_DECISION_v1.md` so the two never collide.

**Contract (from `CLAUDE.md` § WORK ORDERS):** any work-order item that makes a decision
writes its `### NNN — title (date)` entry here **in that same commit**. A decision that
exists only in a commit message does not exist. This has already gone wrong twice on the NFL
side (D59–D61, then D62–D65).

Governing spec: `research/ncaaf_board/NCAAF_BOARD_SPEC_v1.md`.

---

<!-- entries begin -->

### N01 — Book and market universe for NCAAF (2026-09-18)
Probe: 10-book request against americanfootball_ncaaf. hardrockbet_fl absent
from all 90 events. Null control PASS: hardrockbet_fl present on NFL (15/29).

Available books (9 of 10): DK (89), FD (85), BetRivers (75), BetOnline (73),
Bovada (73), BetMGM (72), Pinnacle (72), LowVig (71), Caesars (32).
Cost: 3 credits/call (h2h+spreads+totals in the existing tape).

Per-event probe: team_totals (6 books), alt spreads/totals (7), 1H markets (7).
Player props not tested.

REFERENCE_ONLY: every NCAAF price is from a book Jeff cannot bet.
Pre-registered predictions A (HR absent) and B (team_totals available): both HELD.

### N02 — Pre-kick eligibility rule and board field set (2026-09-18)
A row is eligible only if snapshot_utc < commence_time AND snapshot_utc <=
build_time. Never read files[-1] — the tape contains in-play odds.

Regression test: Pitt vs Cuse event f06e90b4, the pre-kick filter returns
point=-10.5/price=-112 (T-30min), not point=-14.5/price=+970 (T+210min
in-play). The naive files[-1] implementation returns the in-play line,
confirming the test can fail. Null control: unstarted games have identical
row counts with and without the filter.

Per game × market × side: consensus point (median), consensus no-vig implied,
best number (extreme point + book), dispersion (max-min), movement
(first-seen → latest), key-number proximity (spreads only, dist to 3/7/10/14),
n_books, newest snapshot age.

Board header: REFERENCE_ONLY from N01, book name per price.

### N03 — News, not injuries, is layer 2 for NCAAF (2026-09-18)
Re-verified: ESPN /teams/99/injuries returns {} (empty). /teams/99 has no
injuries or news key. /news?team={id}&limit=20 WORKS — returns articles with
headline, description, published (ISO8601), categories with team refs.

Team map: 191 board teams matched to ESPN IDs. 179 auto-matched (93.7%),
12 required manual correction (name variants: Hawai'i, App State, Ragin',
SE Louisiana, etc.). Map committed at ncaaf/pipeline/espn_team_map.json.

PIT rule: only articles with published < build_time are eligible. Articles
from after build_time are excluded.

### N04 — Ticket schema, AI output boundary, CLV convention (2026-09-18)
AI layer: one Anthropic call per game (claude-sonnet-4-20250514). Permitted outputs:
  (1) structured flags with headline + published source
  (2) prose rationale
  (3) binary veto with reason
Any numeric pricing field is discarded and logged. An AI-produced number
would be an unvalidated model.

Ticket schema: event_id, home_team, away_team, commence_time, legs (market,
side, point, price, book, implied), ai_flags, ai_rationale, build_time,
reference_only (True per N01), close_price (null, filled by grader),
clv (null, filled by grader), graded (bool).

CLV: no-vig scale, game identity (event_id), push = void (D64 convention).
Closing price = last snapshot strictly before commence_time.
Grader is UPDATE-ONLY: never appends, never re-grades.

Ticket log: ncaaf/logs/ncaaf_board_tickets_2026.json (append-only).
.gitignore allow-listed at line 49.

SPORT_MAP in shared/clv_utils.py updated: "NCAAF" -> "americanfootball_ncaaf".

### N05 — 2025 held-out data; spread is the close, spreadOpen is pre-game (2026-09-18)
cfbd_games_2025.parquet: 3,831 games (3,829 with scores).
cfbd_betting_lines_2025.parquet: 3,345 rows. Bovada: 934 rows, all with
spread + overUnder + both scores (comparable to ~840/yr in 2022-24).
Other providers: ESPN Bet 1,542, DraftKings 805+64.

spread vs spreadOpen: differ on 84.8% of Bovada 2025 rows. Examples show
`spread` tracks the closing line (moves with market), `spreadOpen` is the
opening line available pre-game. For any downstream build that conditions
on a line available when a bet is placed, `spreadOpen` must be used.

cfbd_games_2026.parquet: 3,679 games (757 with scores — season in progress).
Written to SEPARATE files from the 2022-24 data to preserve the audit
guarantee that 2025 was untouched during the exploratory probe.

### N06 — Blowout correlation survives OOS on 2025 (2026-09-18)
Null control PASS: P(cover)=0.524, P(over)=0.496 (both within 3pp of 0.50).
2025 Bovada, N=904 (after dropping pushes).

Pre-registered predictions:
  1. 21+ phi positive ~0.10-0.25: phi=0.280, t=3.94 — **HELD** (larger than 2022-24).
  2. 14-21 positive but smaller: phi=0.148, t=1.69 — **HELD** (positive, below 21+).
  3. 0-3, 3-7, 7-14 flat |t|<2: 0-3 t=-1.66, 3-7 t=0.92, 7-14 t=2.27 — **DID NOT HOLD**
     (7-14 has t=2.27, breaking the prediction).

The blowout correlation (|spread| >= 14) survived out of sample. The 21+
bucket is the strongest result in both windows: phi=0.196 (N=363) discovery,
phi=0.280 (N=198) validation — combined N=561.

Branch decision: **Branch A** — build the joint outcome table for |spread| >= 14.

### N07 — Joint outcome table v1, Branch A (2026-09-18)
joint_outcome_table_v1.parquet: 8 cells keyed on (spread_bucket, total_bucket),
holding empirical P(cover & over), P(cover & under), P(miss & over), P(miss & under).
Restricted to |spread| >= 14 (the buckets that survived N06).

By spread bucket (2022-2025 combined, N=1119):
  14-21: N=523, phi=0.084, t=1.93 (marginal, but consistently positive)
  21+:   N=596, phi=0.224, t=5.48 (strong, all 4 seasons positive)

By season: 2022 phi=0.135 t=2.32, 2023 phi=0.093 t=1.54,
2024 phi=0.177 t=2.62, 2025 phi=0.227 t=4.12.

Generator: ncaaf/pipeline/build_joint_table.py (committed code, reproducible).
Spec checks 1b, 2, 3 updated from N/A to REQUIRES ATTENTION — the joint table
is the first fitted object and introduces provenance requirements.

### N08 — Market microstructure layer (2026-09-18)
market_microstructure.py: reads tape only, zero credits, zero fitting.
Pre-kick eligibility enforced (snapshot_utc < commence_time).

Hold by market: spreads 3.6-5.5%, totals 4.1-5.7%, h2h 3.5-5.4%.
Pinnacle and LowVig lowest (3.6-4.1%); BetRivers highest (5.4-5.7%).

Stale-book: williamhill_us flagged 28 times (mean lag 121h); betmgm 2 flags.
Null control PASS: 0 stale flags in the most recent 1-hour window.

Move origination: betmgm leads (3,956 changes), pinnacle fewest (1,166).
N01 found no parlay/SGP market keys for NCAAF, so the parlay pricing
audit (4a) computes hold from single-leg overround only.

None of this is fitted. Nothing is selected or tuned on outcomes.

### N09 — Bin-convention defect; Prediction 3 HELD (2026-09-18)
The OOS test used left-closed bins [lo,hi) while the probe used right-closed
(lo,hi] from pd.cut. The LABELS matched; the EDGES did not. In football
3/7/14/21 are modal spreads, so the convention reallocates a large mass.

7-14 t=2.27 was 1 of 8 configurations that cleared |t|>2 — the one the
script happened to use. Under the probe's own bins: t=1.25. **Prediction 3
HELD.** The "extends further toward the middle" interpretation is withdrawn.

Requirement: any bucketed test MUST report both conventions side by side.
test_joint_correlation.py now requires --bins (left|right, no default) and
always prints both. Bin edges are recorded in the output.

### N10 — Joint table v2: spreadOpen, |spread| >= 21 only (2026-09-18)
Rebuilt on spreadOpen (the line available at bet time, N05). |spread| 14-21
excluded: t=1.32-1.64 on spreadOpen under both conventions (neither clears 2).

v2: 4 cells (v1 had 8), all |spreadOpen| >= 21, keyed on total quartiles.
N=565 total (v1 had 1119 with the 14-21 rows).
21+ on spreadOpen: phi=0.220-0.247, t=5.23-5.62 under both conventions.

Cell counts: OU<50 n=137, OU_50-54 n=129, OU_54-58 n=145, OU>58 n=154.
All cells n >= 129. delta ranges +0.026 to +0.097.

v1 preserved on disk. The table is a fitted object — Checks 1b, 2, 3 apply.
Discovery (2022-24) and validation (2025) are pooled; cell values have no
clean OOS estimate.

### N11 — First end-to-end run (2026-09-18)
build_ncaaf_board: 90 games covered, 96 dropped by pre-kick filter.
pull_ncaaf_news: 30 teams pulled, 0 returned zero articles.
build_ncaaf_tickets: 3 games tested, 3 tickets built.
  REFERENCE_ONLY=True on all (N01).
  AI no-pricing-number guard: 0 discards. Guard was never triggered
  (model followed instructions) — untested, not proven.
grade_ncaaf_tickets: first run changed 3 tickets, second run changed 0.
  UPDATE-ONLY null control: PASS.

Odds API credits: unchanged at 8976 (this order used zero Odds API credits).

### N12 — Premature-grading defect: recovery + two guards (2026-09-19)
Three unplayed tickets were graded with CLV=0.0 on all 12 legs. For a game
that has not kicked off, every snapshot satisfies snapshot < commence, so
"closing price" resolved to the current line = the decision price.
UPDATE-ONLY then made them permanently ungradeable.

Recovery: graded set back to False, close_price and clv cleared to null
on all 12 legs. Decision prices (price, point, book, side) untouched.

Guard 1: grade_ncaaf_tickets.py skips any ticket whose commence_time is
in the future (compared to now UTC). Grading is undefined before kickoff.

Guard 2: if all graded CLVs in a run are identically 0.0, the grader halts
with a RuntimeError. Twelve legs at exactly 0.000 is a symptom, not data.

Test: test_grader_5d4.py — future-kickoff ticket must not be graded.

### N13 — AI layer: verified model id, fail-closed, guard tested (2026-09-19)
Model: claude-haiku-4-5-20251001. Verified 2026-09-19 — the only model the
key can reach. claude-sonnet-4-20250514, claude-3-5-sonnet-20241022, and
claude-sonnet-4-6-20250929 all return 404 not_found.

Fail-closed: an API error now raises RuntimeError, not writes to ai_rationale.
Missing ANTHROPIC_API_KEY also raises.

No-pricing-number guard: tested with a canned response containing
fair_spread=-21.5 and projected_total=52.0. Both discarded. Guard
exercised and proven to work — no longer untested.

### N14 — Board artifact as single source of truth for layer 2 (2026-09-19)
pull_ncaaf_news.py now reads its team list from the board artifact
(ncaaf/data/board/week=*/ncaaf_board.parquet), not from the latest tape
snapshot. This is why N11 covered only 30 of 146 teams.

Full run: 146 teams queried, 146 with news, 0 zero-article teams.
2,920 articles. Board-news coverage: 146/146 = 100%.
Runtime: ~146s (146 teams × 1s sleep).

### N15 — First genuine end-to-end run (2026-09-19)
Board: 90 games covered, 96 dropped by pre-kick filter.
News: 3,520 articles, 146/146 board teams (100% coverage).
AI: 5 calls made (claude-haiku-4-5-20251001), 5 succeeded, 0 discards.
  Pricing-number guard: not triggered (model followed instructions).
  Guard is tested (N13 proved it with a canned response).
Tickets: 5 built, all reference_only=True, all graded=False.
Stopped before grading — games not yet played.

Odds API credits: unchanged at 8976. Zero used in this order.

### N16 — Append-only ticket log enforced by assertion (2026-09-19)
write_ticket_log: before every write, asserts (1) ticket count does not
decrease, (2) no (event_id, build_time) key on disk vanishes from the
merged output. Halts on either violation.

Deletion path found: the N15 session used an inline `python3 -c` block
with `existing = [t for t in existing if t['event_id'] not in old_eids]`,
which filtered out the 3 original tickets. This was not in the committed
writer. No cron/launchd touches this file.

Test: append of 2 to a log of 3 gives 5. Guard prevents count decrease.

### N17 — No-pricing-number guard demonstrated (2026-09-19)
_call_ai_layer now returns a 5th value: discarded (dict of fields removed).
Test feeds canned response with fair_spread=-21.5, projected_total=52.0,
win_probability=0.78. Asserts all three are in discarded dict and NOT in
the returned flags/rationale/veto.

RED shown: without the guard, fair_spread stays in the parsed result.
GREEN: guard removes it and returns it in discarded.

This is the guard's first real demonstration. It was reported as handled
in N04 (prose), N11 ("never triggered"), N13 ("discards work" but the
test only checked types). It is now established.

### N18 — Grading deferred: games not yet played (2026-09-19)
Current time: 2026-09-19T01:09Z. The four Saturday games kick between
16:00Z and 23:30Z on 2026-09-19 and will settle around 03:00Z on 2026-09-20.
Nebraska @ Michigan State is 2026-09-26T21:00Z — a week out.

Grading cannot run in this session. The N12 future-kickoff guard will
correctly skip all 5 tickets. Grading happens in a later session after
the games settle, with N12/N16/N17 guards in place.

5 tickets: all graded=False, all reference_only=True. Decision prices
intact. No CLV data yet — the measurement asset begins accumulating
when the first game settles.

### N19 — Favourite/underdog in code; both-sides + on-board invariants (2026-09-19)
_derive_matchup: favourite = team with negative spread point, underdog = other.
Passed to the AI in words ("X is favoured by N at Y. Y is the underdog
receiving N."). The AI never derives the sign — the inversion was an input defect.

Invariant 1b: a ticket may not contain both sides of the same market. Raises.
Invariant 1c: every leg must exist on the board (market, side, point). Raises.

Tests: 4/4. both_sides_raises, single_side_passes, not_on_board_raises,
favourite_derivation. RED shown: old code allowed both sides silently.

### N20 — AI is the selection mechanism; abstain path (2026-09-19)
The AI picks at most one side per market per game. Abstain is genuinely
available. Selection and pricing are separate — the AI never chooses the
book or the price.

Spec updated: Layer 3 is "AI selection" not "AI reasoning". Unvalidated.
No backtest. Prospective CLV (~125 obs needed) is the only grade.

N17 guard UNCHANGED and confirmed passing (3/3) — protects a model that
now has real influence over what gets bet.

### N21 — First bettable slate: 3 tickets, 7 abstains, inversion fixed (2026-09-19)
10 games tested. 3 tickets built, 7 abstains (70% abstain rate — the picker
declines when it has no edge, as designed).

Tickets:
  Georgia -24.5 + Under 54.5 (fav: Georgia, correct)
  Colorado +3.5 + Over 48.0  (fav: Northwestern, correct)
  James Madison +1.5 + Over 46.5 (fav: San Diego State, correct)

SPOT-CHECK:
  Colorado @ Northwestern: favourite = Northwestern (-3.5). CORRECT.
  Nebraska @ Michigan State: favourite = Nebraska (-5.5). CORRECT.
  No inversions. Fix works.

0 both-sides violations, 0 legs not on board, 0 pricing numbers discarded.
All reference_only=True, all graded=False.
Ticket log: 5 → 8 (+3). Append-only guard passed.

### N22 — Card assembler: conviction-vs-filler, no-overlap invariant (2026-09-19)
`ncaaf/pipeline/build_ncaaf_cards.py` — reads today's tickets, emits two cards.

CARD A (5-leg conviction): one leg per game, spreads preferred, ranked by spread
magnitude. All CONVICTION — never weakened to reach 5.

CARD B (10+ longshot): conviction legs first (not on Card A), then FILLER legs
clearly marked with `leg_type="FILLER"`. At most one leg per game UNLESS the
pair is a joint-table cover+over pairing (|spread| >= 21), citing the cell and n.

No-overlap invariant: `_leg_key(l) = (event_id, market, side, point)`. Card A
keys and Card B keys must be disjoint. Assert + raise on violation.

Both-sides tickets from WO7 (which had both spread sides in a single ticket)
are dropped before card assembly.

Hold computed from actual leg prices with proper two-sided devig from the board
(multiplicative method), not from assumed -110.

First run: Card A = 5 legs (24.2% hold), Card B = 19 legs (68.1% hold, all
conviction — no filler needed). AI abstained on 70/89 events (78.7%).

### N23 — Card logging with conviction/filler tagging (2026-09-19)
Both cards logged to `ncaaf/logs/ncaaf_board_tickets_2026.json` as entries with:
- `card_id`: "A_5LEG" or "B_LONGSHOT"
- `graded`: False
- `reference_only`: True
- Each leg carries `leg_type` ("CONVICTION" or "FILLER"), `price`, `book`,
  `snapshot_time`, enabling later CLV breakdown by conviction vs filler.

N16 append-only guard applies: ticket count must not decrease.
Grading deferred to Sunday 13:00Z scheduled task.

### N28 — NFL Hard Rock props schedule, measured cost, plan arithmetic (2026-09-20)

**D84 entries status.** Installed 2026-09-18T02:50 UTC (Friday). No Tue 10:00 or
Thu 22:00 slot occurred between then and now (Sat 02:09 UTC). The first scheduled
slot is Sun 15:00 UTC today. Syslog shows zero scheduled firings; the two entries
on Sep 19 (15:06 and 15:11) were one-off test entries from D84 verification, since
removed. The three D84 entries are correctly formed and retained.

**Schedule (UTC), 8 entries total (3 existing + 5 new):**
```
0 10 * * 2      --window-hours 168 --tag open     Tue 6am ET    (existing)
0 16 * * 3-6    --window-hours 168 --tag mid      Wed-Sat noon ET (NEW)
0 22 * * 4      --window-hours 12  --tag close    Thu 6pm ET    (existing)
0 15 * * 0      --window-hours 12  --tag close    Sun 11am ET   (existing)
30 16 * * 0     --window-hours 2   --tag close    Sun 12:30 ET  (NEW)
45 19 * * 0     --window-hours 2   --tag close    Sun 3:45 ET   (NEW)
50 23 * * 0     --window-hours 2   --tag close    Sun 7:50 ET   (NEW)
45 23 * * 1     --window-hours 2   --tag close    Mon 7:45 ET   (NEW)
```

**Measured cost:** 16 events = 241 credits (168h window dry-run, 2026-09-20).
~15.1 credits/event (15 per event + 1 for events list).
Estimated weekly: ~1,090 credits. Combined with existing line cron (~290/day):
~446/day = ~13,400/month.

**Plan arithmetic:** x-requests-remaining = 8,250 as of 2026-09-20T02:09Z.
x-requests-used not reported separately by the dry-run headers. 13,400/month
fits the 20K plan with ~6,600 spare. The account plan is not visible from
the API headers; stated as UNKNOWN. Do not upgrade.

**What the fixed UTC slots miss:** Holiday games (Thanksgiving, Christmas),
Saturday flex games, international games, and flexed Sunday/Monday times.
The Wed-Sat mid pulls (168h window) and the Sunday 11am close (12h window)
will still capture these games' props at non-optimal timing — just not
their final pre-kick price. No schedule-aware dispatcher built in this order.

**In-play filter (1c):** The events filter `now <= ct_dt` already excludes
started games. Added explicit post-normalization filter: rows with
`pull_timestamp >= commence_time` are dropped. The filter is a string
comparison on ISO timestamps (both UTC, same format), which is correct
because ISO8601 sorts lexicographically.

**DST note:** After 2026-11-01, the same UTC slots land 1 hour earlier
relative to kickoff. All 2-hour windows still contain their kickoffs
(verified: 1pm ET = 18:00 UTC is inside 16:30+2h = 18:30 UTC). Not missed,
just earlier capture (~90 min pre-kick instead of ~30).

### N29 — ESPN news/injuries/depth, nflverse schedule, what college lacks (2026-09-20)

**Sources verified from VM (root@142.93.242.4, 2026-09-20T02:17Z):**
- `nfl/news?team={id}&limit=20`: 200 OK, articles with `published` timestamps
- `college-football/news?team={id}&limit=20`: 200 OK (existing puller)
- `nfl/injuries` (league endpoint): 200 OK, **32 teams in one response**
  (no per-team looping needed), athlete-level: status, date, type, detail
- `nfl/teams/{id}/depthcharts`: 200 OK, `depthchart` key (list of formations)
- `college-football/teams/{id}/injuries`: returns `{}` (empty) — confirmed N03
- `college-football/teams/{id}/depthcharts`: returns no `depthchart` key — confirmed

**What college does NOT have:** ESPN provides no structured injury feed and no
depth chart feed for NCAAF. For college football, news IS the injury layer (N03).
CFBD has rosters and player game stats but no injuries and no depth charts.

**Scripts:**
- `shared/pipeline/pull_espn_news.py --sport nfl|ncaaf`: generalized puller,
  72h freshness check, gzipped output (NCAAF is 67 MB uncompressed per pull)
- `ncaaf/pipeline/pull_ncaaf_news.py`: thin wrapper calling the shared puller
- `shared/pipeline/pull_espn_nfl_status.py`: injuries + depth charts, asserts
  32 teams each
- `shared/pipeline/run_nflverse_with_archive.sh`: runs pull_nflverse_inputs.py
  then copies timestamped parquets to data/depth_archive/nfl/season=2026/

**Paths:**
```
data/news_archive/nfl/season=2026/news_<UTC>.json.gz
data/news_archive/ncaaf/season=2026/news_<UTC>.json.gz
data/injury_archive/nfl/season=2026/injuries_<UTC>.json
data/depth_archive/nfl/season=2026/depth_<UTC>.json
data/depth_archive/nfl/season=2026/nflverse_<name>_<UTC>.parquet
```

**Measured sizes (one pull each, 2026-09-20):**
| Feed           | Size      | Articles/Teams | Runtime |
|----------------|-----------|----------------|---------|
| NFL news (gz)  | ~1,100 KB | 640 / 32       | 21.4s   |
| NCAAF news (gz)| 10,032 KB | 2,920 / 146    | 113.3s  |
| NFL injuries   | 9,156 KB  | 800 / 32       | ~2s     |
| NFL depth      | 6,970 KB  | 32 teams       | 23.2s   |
| nflverse arch  | 12.0 MB   | 3 files        | ~15s    |

**Storage projection:** News gzipped: NFL ~66 MB/mo + NCAAF ~1.2 GB/mo.
Injuries + depth: ~480 MB/mo. Total ~1.7 GB/month in git. Large but the
work order says gzip, not drop fields.

**Freshness checks:**
- News: newest article within 72h, else HALT. Measured: NFL 2.4h, NCAAF 1.6h.
- Depth charts: ESPN timestamps may be stale (Cowork saw 2026-07-26 on KC);
  capturing anyway — nflverse is primary, ESPN is cross-check.
- Every file: valid JSON/parquet, non-empty, expected team count (32 for NFL).

**Schedule (UTC):**
```
10 0,6,12,18 * * *    pull_espn_news.py --sport nfl
20 0,6,12,18 * * *    pull_espn_news.py --sport ncaaf
30 0,6,12,18 * * *    pull_espn_nfl_status.py
40 16 * * 0            pull_espn_nfl_status.py (Sun 12:40 ET, after inactives)
0 9 * * *              run_nflverse_with_archive.sh
```

**nflverse was NOT in any crontab.** This is how the feed died for 4.5 days.
Now scheduled daily at 09:00 UTC (5am ET).

**Depth chart staleness:** ESPN's KC depth chart `timestamp` field was
2026-07-26 when Cowork checked. The depth chart IS populated (3 formations,
30 positions), but the metadata timestamp is stale. This is an ESPN artifact,
not an indication of empty data. Capturing anyway; nflverse is the primary
source and this is the cross-check. The staleness is noted, not suppressed.

### N30 — Kalshi football markets: series, fields, price scale, pre-game filtering (2026-09-20)

**Series captured (6):**
| Series         | Open Markets | Zero Vol | Notes                  |
|----------------|-------------|----------|------------------------|
| KXNFLGAME      | 62          | 5%       | Active trading         |
| KXNFLSPREAD    | 417         | 5%       | Active trading         |
| KXNFLTOTAL     | 304         | 5%       | Active trading         |
| KXNCAAFGAME    | 548         | 16%      | Mostly empty books     |
| KXNCAAFSPREAD  | 1,089       | 16%      | Mostly empty books     |
| KXNCAAFTOTAL   | 835         | 16%      | Mostly empty books     |

**Player-prop series flagged, NOT captured:** KXNFLTD, KXNFLPASSTDS, etc.
(see `kalshi_football_series_2026-09-20.md`). 0-1 open markets each,
impractical to capture (hundreds of API calls for near-zero data).

**Fields stored:** pull_timestamp, series_ticker, ticker, event_ticker, title,
yes_sub_title, no_sub_title, yes_bid_dollars, yes_ask_dollars, no_bid_dollars,
no_ask_dollars, last_price_dollars, previous_price_dollars, volume_fp,
volume_24h_fp, open_interest_fp, liquidity_dollars, open_time, close_time,
expected_expiration_time, occurrence_datetime, status, market_type.

**Price scale: DOLLARS** (0.00 to 1.00). Field names include `_dollars` suffix.
Consistent with WebSocket data in `kalshi_parse_to_parquet.py` (bid/ask 0-1).
No scale conversion applied. Any comparison of Kalshi prices to sportsbook
prices must convert (Kalshi 0.47 = implied 47% = about -113 American).

**Pre-game filtering:** The API field `occurrence_datetime` appears to be a
kickoff proxy (e.g. 2026-10-04T03:00Z). It is NOT explicitly labelled as
kickoff. `close_time` and `expected_expiration_time` are also stored.
Kalshi markets stay open during games (confirmed by work order).
**Pre-game filtering will need the schedule joined on later.** The puller
stores all three time fields to enable this. No kickoff is guessed.

**Measured (VM, 2026-09-20):**
- NFL: 3 series, 1 page each, 783 rows, 55 KB, 0.4-1.5s
- NCAAF: 3 series (1 needed 2 pages), 2,472 rows, 140 KB, 0.8s
- Total per cycle: ~6 requests, <2s
- Storage: 32 snapshots/day × 195 KB = ~6 MB/day = ~180 MB/month

**Schedule (UTC), aligned 5 min after line tape:**
```
5,35 0-5,14-23 * * *   pull_kalshi_football.py --sport nfl
7,37 0-5,14-23 * * *   pull_kalshi_football.py --sport ncaaf
```

**Cron proof:** one-off entry at 02:30 UTC 2026-09-20. Syslog:
`2026-09-20T02:30:01 CRON ... pull_kalshi_football.py --sport nfl`.
Produced snap_20260920T0230Z.parquet, 783 rows, 55 KB. Removed after.

### N31 — Health check thresholds and observed-firing table (2026-09-20)

**Health check:** `shared/pipeline/capture_health.py` — reads files only, no
network. For each feed, finds newest file by mtime, computes age, compares
with max age. Exits non-zero if ANY feed is stale, naming it.

**Thresholds (capture_health.py):**
| Feed             | Max Age (in capture window) | Max Age (outside) |
|------------------|----------------------------|-------------------|
| NFL/NCAAF lines  | 45 min                     | 9 h               |
| Kalshi NFL/NCAAF | 45 min                     | 9 h               |
| NFL props        | 26 h (Wed-Sun)             | 168 h (Mon-Tue)   |
| NFL/NCAAF news   | 7 h                        | 7 h               |
| NFL injuries     | 7 h                        | 7 h               |
| NFL depth        | 7 h                        | 7 h               |
| nflverse inputs  | 26 h                       | 26 h              |

Capture window: 14:00-05:30 UTC (matching the line tape schedule).

**Failure test:** Pointed at a fixture directory with one stale file. Exit 1,
named all 10 feeds as stale (fixture had only the stale file). On the real
repo, exit 1 naming nfl_props (4,225.8h old — D84 entries haven't fired a
scheduled pull yet; first slot is Sun 15:00 UTC).

**Observed scheduled firings (syslog, 2026-09-20):**
| Feed          | Time (UTC)   | Output                                  |
|---------------|-------------|------------------------------------------|
| Kalshi NFL    | 02:35:01    | snap_20260920T0235Z.parquet, 783 rows    |
| Kalshi NCAAF  | 02:37:01    | snap_20260920T0237Z.parquet, 2,382 rows  |
| Health check  | 02:45:01    | 9/10 OK, 1 STALE (nfl_props)             |

Not yet observed (scheduled but slot not reached):
- NFL props (first: Sun 15:00 UTC)
- NFL news (first: Sun 06:10 UTC)
- NCAAF news (first: Sun 06:20 UTC)
- NFL injuries/depth (first: Sun 06:30 UTC)
- nflverse inputs (first: Sun 09:00 UTC)

### N32 — Bleed stopped: ESPN/nflverse paused, already-pushed data quantified (2026-09-20)

**Paused (commented out with `#WO10b_PAUSED#`, not deleted):**
1. `10 0,6,12,18 * * *` — pull_espn_news.py --sport nfl (4x/day)
2. `20 0,6,12,18 * * *` — pull_espn_news.py --sport ncaaf (4x/day)
3. `30 0,6,12,18 * * *` — pull_espn_nfl_status.py (4x/day)
4. `40 16 * * 0` — pull_espn_nfl_status.py (Sun extra)
5. `0 9 * * *` — run_nflverse_with_archive.sh (daily)

**Already pushed to origin (cannot delete without history rewrite):**
| File | Size |
|------|------|
| news_20260920T0218Z.json (NCAAF, uncompressed) | 68 MB |
| news_20260920T0221Z.json.gz (NCAAF, gzipped) | 10 MB |
| news_20260920T0217Z.json (NFL, uncompressed) | 6 MB |
| injuries_20260920T0220Z.json | 9 MB |
| depth_20260920T0220Z.json | 7 MB |
| nflverse_depth_charts_20260920T0221Z.parquet | 7 MB |
| nflverse_rosters_weekly_20260920T0221Z.parquet | 4 MB |
| **Total already on origin** | **~111 MB** |

All were committed by push_daemon at 02:30Z before this order ran.
At the installed cadence (~110 MB/day), one more day of unchecked capture would
have added another ~110 MB permanently. The bleeding is stopped.

**Removed:** Nothing. Every oversized file was already tracked and pushed.

**Not paused (left running):** props (3 D84 + 5 WO10 entries), Kalshi NFL/NCAAF
(every 30 min in capture window), capture_health.py (hourly), all pre-existing
entries (line tape, push_daemon, etc.).

**nfl/data/pbp/depth_charts.parquet:** 7.5 MB, tracked, now written by VM via
run_nflverse_with_archive.sh. This is a dual-writer violation (Mac also writes it
via pull_nflverse_inputs.py). Resolved in N33.

### N33 — Storage: de-dup, gzip, hash-skip, single depth-chart writer (2026-09-20)

**News de-duplication (2a).** ESPN articles carry `id` (int) and `lastModified`
(ISO8601, present on 2920/2920 NCAAF articles). De-dup key: `str(id)` ->
`lastModified`. State file `_seen.json` maps article id to lastModified. Each pull
writes:
- `news_<UTC>.json.gz` — only articles that are new or whose lastModified changed
  (complete and unmodified, no field dropped)
- `index_<UTC>.json.gz` — every (team_id, article_id) present in this pull

First run writes everything (empty state). Subsequent runs write only deltas.
Freshness halt unchanged (newest article within 72h).

**Injuries and depth charts gzip + hash-skip (2b).** Output changed from `.json`
to `.json.gz`. Content hash: SHA-256 of JSON with `timestamp` and `_pull_time`
fields excluded (both are volatile). When the hash equals the previous capture's,
no file is written; instead one line `{utc, sha256, "unchanged"}` is appended to
`_pulls.jsonl`, proving the pull happened and what it saw.

**nflverse hash-skip (2c).** SHA-256 of each archived parquet; skip the copy when
it matches the last archived copy. Same `_pulls.jsonl` logging for skipped writes.

**Single depth-chart writer:** VM is the sole writer of
`nfl/data/pbp/depth_charts.parquet` via `run_nflverse_with_archive.sh` (daily
09:00 UTC). The Mac does NOT run `pull_nflverse_inputs.py`. The Mac receives the
updated file via `git pull` (push_daemon pushes every 30 min, the Mac's morning
pipeline pulls before reading). This resolves the dual-writer violation from N32.

**Kalshi NCAAF schedule (2d).** Changed from every-30-min-every-day to:
- Fri 14:00 - Sun 05:30 UTC: every 30 min (game window, same as NFL)
- Otherwise: every 3h
16% of NCAAF markets are empty books; the slate is Saturday. Off-window pulls
still capture any mid-week line moves but at 1/6th the frequency.

**Measured MB/month (second runs, steady state):**
| Feed | Steady-state KB/pull | Pulls/day | MB/month |
|------|---------------------|-----------|----------|
| NFL news (de-duped) | 6 KB | 4 | 0.7 |
| NCAAF news (de-duped) | 16 KB | 4 | 1.9 |
| NFL injuries (hash-skip) | 0 (353 KB when changed) | 4.14 | ~1.4 |
| NFL depth (hash-skip) | 0 (386 KB when changed) | 4.14 | ~1.2 |
| nflverse (hash-skip) | 0 (11.5 MB when changed) | 1 | ~46-92 |
| Kalshi NFL | 55 KB | 32 | 53 |
| Kalshi NCAAF (new sched) | 95 KB | ~17.4 avg | 50 |
| **Total** | | | **~154-200** |

Under the 300 MB/month target. Nflverse dominates and depends on how often
rosters/depth actually change (1-2x/week typical in-season). NFL news de-dup
achieved 100% skip on the second run (0 new articles). NCAAF news: 3 new
articles out of 2900 (99.9% skip). Injuries: 100% hash-skip. Depth: 100%
hash-skip after recursive timestamp strip (the first two runs hashed differently
due to per-team `timestamp` fields; fixed with recursive strip).

### N34 — Reader contract and health check clock (2026-09-20)

**Ticket builder reader (3a).** `build_ncaaf_tickets.py` now reads:
- Legacy `*.json` files (3 existing from pre-WO10b)
- New `news_*.json.gz` files (de-duplicated output from WO10b)
- Ignores `index_*` and `_seen.json`
- De-duplicates by article `id`, keeping the version with the latest `lastModified`
- Reports newest pull's UTC timestamp and article count
- HALT if newest pull is >24h older than build_time

**Health check clock (3b).** `capture_health.py` rewritten:
1. **Filename timestamps, not st_mtime.** Ages come from the UTC timestamp
   embedded in the filename (regex `\d{8}T\d{4}Z`). This is immune to clone,
   rebase, and checkout — the same file reports the same age on any host.
2. **_pulls.jsonl for hash-skipped feeds.** For injuries, depth, and nflverse,
   the newest evidence of a pull is whichever is more recent: the newest file's
   filename timestamp OR the last line of `_pulls.jsonl` (which records
   hash-skipped pulls that wrote no file).
3. **tz-aware UTC throughout.** Props: `pd.to_datetime(..., utc=True)` forces
   UTC on every partition. The C(1) bug was: month=02 had tz-naive timestamps,
   month=09 had tz-aware; comparison threw TypeError, swallowed by bare except,
   silently skipping the September file. Now: every timestamp is tz-aware before
   comparison, and there is no bare except.
4. **No bare `except Exception: continue`.** An unreadable file is a failure:
   the file is named and the check exits non-zero.

### N35 — Test inventory and correction of order #10 report (2026-09-20)

**Test inventory (20 tests, all passing):**

`nfl/pipeline/tests/test_props_inplay_filter.py` (6 tests):
- pre_game_row_kept, in_play_row_dropped, exact_kickoff_dropped, mixed_rows,
  filter_removed_fails (proves test can fail without filter), tz_format_comparison

`shared/pipeline/tests/test_espn_news_halt.py` (4 tests):
- stale_news_halts (100h-old article -> SystemExit(1), no file written)
- fresh_news_passes (1h-old article -> no halt)
- 31_teams_halts (31 teams -> SystemExit(1))
- 32_teams_passes

`shared/pipeline/tests/test_kalshi_halt.py` (2 tests):
- non200_halts (HTTP 429 -> SystemExit(1))
- empty_markets_no_file (all series return 0 -> SystemExit(1), no file)

`shared/pipeline/tests/test_news_dedup.py` (1 test):
- second pull with 1 changed + 1 new -> writes exactly those 2; index lists all 3

`shared/pipeline/tests/test_capture_health.py` (4 tests):
- stale_nfl_news_detected (one stale feed -> detected, only that one)
- all_fresh_returns_empty
- REGRESSION C(1): mixed_tz_props (tz-naive month=02 + tz-aware month=09 -> reports
  month=09 age, not 4,226h)
- REGRESSION C(2): mtime_does_not_affect_age (all files touched to now -> ages
  unchanged from filename, not near 0)

`shared/pipeline/tests/test_ticket_reader.py` (3 tests):
- union_deduplication (1 .json + 1 .json.gz -> 3 unique articles, updated version kept)
- stale_30h_halts (30h-old newest pull -> SystemExit)
- fresh_does_not_halt

**Explicit correction of order #10's report:**
1. The 4,226h `nfl_props` reading was NOT "correctly identifies props feed dead."
   It was a swallowed `except Exception: continue` in `_newest_props_age`: month=02
   had tz-naive timestamps, month=09 had tz-aware; comparison threw TypeError,
   September was silently skipped, and the check fell back to March's date. The
   actual props age was ~12h. The bare except has been removed.
2. The tests were listed as neither DONE nor NOT DONE in the report. They were not
   written. `git diff --name-only 0529f52..3f42eb1` contains zero test files.

### N36 — Order #10b verified; nflverse depth archive becomes a delta; in-play filter tested for real (2026-09-20)
Cowork, verified from a fresh clone of origin at 74223d6, then fixed directly (order "10c").

**What held up in #10b.** Health check in a fresh clone: all 10 feeds OK, nfl_props 12.5 h —
it agrees with the VM and no longer uses st_mtime or a bare except. De-dup works: second
pulls wrote 6 KB (NFL) and 16 KB (NCAAF). Status feeds gzip to ~0.35-0.39 MB. 20 tests pass.
The tests for the health check, ESPN halts, Kalshi halts and news de-dup import the real
modules. Already on origin and permanent: ~115 MB from #10's one-off pulls (the 66.6 MB raw
NCAAF news file is most of it).

**What did not.**
1. **N33's nflverse figure (46-92 MB/month) rests on "rosters/depth change 1-2x/week". Measured:
   `depth_charts.parquet` carries a `dt` snapshot per row and has 253 distinct snapshot dates in
   2026, one per day through 09-19.** It changes daily, so the sha256 hash-skip never skips:
   a 7.2 MB full copy every day (~216 MB/month), of rows already in the previous copy. The file
   is its own history. FIX: `shared/pipeline/archive_nflverse_depth_delta.py` archives only rows
   with `dt` newer than the newest already archived (baseline = the 02:21Z full copy), logs every
   pull with the full-file sha256 to `_pulls.jsonl`, refuses to overwrite, halts on a missing
   file or a missing `dt` column. Run against the real file: `unchanged rows=0
   max_dt=2026-09-19T11:56:08Z`. Stated limit: a retroactive nflverse edit to an archived
   snapshot is detectable (hash) but not reconstructable. Injuries/rosters keep hash-skipped
   full copies.
2. **Two of #10b's tests guarded a replica, not the code.** `test_props_inplay_filter.py` and
   `test_ticket_reader.py` each define a "Replica of…" function and test that; deleting the
   real filter left every test green. FIXED for the props filter: `drop_inplay_rows()` is now a
   function in the puller, compares parsed UTC datetimes, raises on an unparseable row, and the
   test imports it. Mutation check: with the old string comparison restored, 3 of 9 tests fail —
   including the puller's REAL timestamp shapes (`…17:00:00.000001+00:00` sorts before
   `…17:00:00Z` as text, so a row pulled in the kickoff second was kept). NOT fixed: the
   ticket-reader test is still a replica — the reader lives inline in `main()` of
   `build_ncaaf_tickets.py` and needs extracting into a function first. The reader code itself
   was read and is correct, with one nit: articles with an empty `id` collapse into one.
3. `pytest shared/pipeline/tests nfl/pipeline/tests` in ONE command fails at collection (both
   folders are a package named `tests`). Run them separately until one `__init__.py` goes.

**Still open — the largest remaining item.** `nfl/data/pbp/depth_charts.parquet` is tracked and
the VM now rewrites it daily: ~7.2 MB/day (~216 MB/month) of git history by itself. The clean fix
is for `run_week.py` to refresh its own inputs so the file can be untracked like the rest of
`nfl/data/pbp/`; that is in `nfl/sim/`, which Phase 5I has open — do it after `eng/5i` merges.
Until then the measured total is roughly: Kalshi ~103 + news ~3 + ESPN status ~3 + nflverse
rosters/injuries ~20 + tracked depth file ~216 = **~345 MB/month**, not the 154-200 reported.

**Not verified:** any ESPN/nflverse/props SCHEDULED firing (first slots 06:10Z, 09:00Z,
Sun 15:00Z); the delta script on the VM (it reaches the VM on the next push_daemon pull).

### N37 — A leg is one row of one book; pre_repair flag (2026-09-20)
ChatGPT audit #4, adjudicated by Cowork. Item 1 of WO11.

**Defect.** `build_ncaaf_tickets.py:226-228` wrote `point=consensus_point` (median of
all books), `price=best_price` (from the book with the best point), `book=best_book`.
The resulting triple (book, point, price) did not exist in the tape 17 of 30 times in
the 2026-09-19T11 build. The Under/h2h branch in `build_ncaaf_board.py` was worse:
median point plus the FIRST book's price.

**Pre-registration.** Reproduction will show 17 of 30. It showed 17 of 30.

**Fix.**
1. `build_ncaaf_board.py`: each board row now carries a `quotes` list — one entry per
   book with `{book, point, price, snapshot_utc}`, each a single tape row.
2. `build_ncaaf_tickets.py`: new `select_best_quote(quotes, market, side)`:
   - spreads: most positive point (max), ties -> best price (max), ties -> book name
   - Over: lowest point (min), ties -> best price, ties -> book name
   - Under: HIGHEST point (max), ties -> best price, ties -> book name
3. Each leg stores `snapshot_utc` and the complement row from the same book/snapshot
   (needed for entry de-vigging).
4. `validate_leg_against_tape(leg, tape_df)`: asserts every leg's (book, market, side,
   point, price) exists in the tape. Called at write time; raises on failure.
5. `_validate_ticket` now checks against real book quotes, not consensus_point.
6. News filter accepts both `_team_name` (new puller) and `team_name` (legacy).

**Pre_repair flag.** All 31 existing ticket-log entries marked `pre_repair: true`.
Entries with this flag are excluded from any future grade or count. No existing entry
was deleted or otherwise modified.

**Tests (5 new, 4 updated):**
- `test_board_carries_quotes`: board_df must have a `quotes` column with per-book data
- `test_select_best_quote_spreads/over/under`: selection rule produces the correct
  (book, point, price) triple for each market type
- `test_validate_leg_against_tape`: consensus-mixed leg raises; real tape row passes

**Null control.** `_validate_ticket`'s both-sides invariant still passes (unchanged).
The 4 existing test_ticket_invariants tests still pass with updated fixtures.

### N38 — A grader that runs, measures point_clv and prob_clv separately, 30-min close rule, CFBD outcomes (2026-09-20)
ChatGPT audit #4, adjudicated by Cowork. Item 2 of WO11.

**Defect.** `grade_tickets(2026)` crashed with `KeyError: 'event_id'` because 4 card
entries carry event_id on their legs. Also: close had no maximum age (any pre-kick
row accepted), `graded=True` was unconditional after the leg loop, CLV was a single
no-vig-scale number that de-vigged the pick with the CLOSING complement, and the grader
had no outcome source.

**Pre-registration.** KeyError on the committed log. It raised `KeyError: 'event_id'`,
0 of 31 graded. Matches.

**CLV definitions (verbatim from the adjudication):**
- `point_clv`: spread (same team): `entry_point - close_point`; Over: `close_point -
  entry_point`; Under: `entry_point - close_point`.
- `prob_clv`: ONLY if the close quotes the leg's ORIGINAL point at that book. `q_c` =
  close price de-vigged with its own same-snapshot complement; `q_0` = entry price
  de-vigged with the ENTRY complement stored in item 1c. Stores `q_c - q_0` and
  `C = d_0 * q_c - 1`. Otherwise null with reason `line_moved_no_alt_quote`. Never
  the new main line.

**30-minute rule.** Close = last pre-kick row within 30 min of commence_time for the
leg's book/market/outcome. Older: stored as `last_observed_*` with age. A leg with no
close within 30 min stays `graded: false` with `grade_status: close_unavailable`.

**Outcomes.** CFBD refresh: 4 HTTP calls to collegefootballdata.com (rate-limited, zero
Odds API credits). 1,045 completed games. Outcome join on teams + date: **89/95 legs
matched** (93.7%). Unmatched legs: `outcome_unavailable` with reason, never a loss.

**Fix.** Full rewrite of `grade_ncaaf_tickets.py`. Legs graded wherever they live
(event tickets or card entries). `pre_repair` entries skipped. Team-name mapping via
strip-mascot with 2 overrides (San Jose State -> San José State, UMass -> Massachusetts).

**Tests (3 new):**
- `test_grader_handles_cards_and_events`: event + card + pre_repair fixture; 2 graded, pre_repair skipped
- `test_30min_close_rule`: 60-min-old snapshot leaves ticket ungraded with `grade_status: close_unavailable`
- `test_point_clv_spread`: entry -7.0, close -7.5 -> point_clv = +0.5

**N12 all-zero-CLV assertion retained.**

### N39 — News reader extracted, field-name fix, build-time cutoff, coverage gate (2026-09-20)
ChatGPT audit #4, adjudicated by Cowork. Item 3 of WO11.

**Defect.** The new puller writes `_team_name`; the selector at line 195 filtered on
`team_name` (no underscore). Of 1,381 de-duped articles, only 1 (a December 2025
Wyoming article with legacy `team_name`) ever reached the AI. All 3,820 legacy articles
with empty `id` collapsed onto one key. `news_articles[:10]` was unsorted.

**Pre-registration.** 14,526 loaded -> 1,381 retained -> 1 with `team_name`. Matched.

**Reader contract (`load_news(news_dir, build_time)`):**
- Reads both `.json` (legacy) and `news_*.json.gz` (new format).
- Accepts `_team_name` AND `team_name`. Both are recognized in the selector and in
  `game_news_for()`.
- Legacy articles with empty `id`: keyed on `sha1(team + published + headline)`.
- De-dup keeps the latest version with pull time <= build_time. An article version
  pulled after the build must not enter it.
- `game_news_for(articles, home, away)`: returns that game's two teams' articles only,
  sorted by `published` descending, capped at N=10 per game, within a 14-day recency
  window.

**Coverage on the next real build (at 2026-09-19T11:01:16Z):**
  3,864 de-duped articles, **191 teams** with >= 1 article (vs 1 before fix).

**Coverage gate:** HALT below 25% of board teams. Threshold is conservative — the old
layer-2 check was 146/146 but 25% accommodates early-season when only a subset of
teams appear on the board.

**`pull_espn_news.py` error guard:** exit non-zero and write nothing if > 5% of teams
fail. Measured normal failure rate: 0 of 3 observed pulls had any per-team HTTP error.

**Tests (4 new):**
- `test_load_news_accepts_both_field_names`: legacy + new-format fixture -> all 4 teams found
- `test_load_news_dedup_keeps_latest_version`: article 201 updated version kept
- `test_load_news_respects_build_time`: article pulled after build_time excluded
- `test_game_news_sorted_newest_first`: newest published first

### N40 — Feed health per-feed filtering; pytest collection fix (2026-09-20)
ChatGPT audit #4, adjudicated by Cowork. Item 4 of WO11.

**Defect.** `data/depth_archive/nfl/season=2026/_pulls.jsonl` is written by three
scripts: `pull_espn_nfl_status.py` (depth), `run_nflverse_with_archive.sh`, and
`archive_nflverse_depth_delta.py`. `_newest_pulls_age` reads the LAST line whoever
wrote it. A fresh ESPN depth write makes a stale nflverse feed read fresh.

**Pre-registration.** A fixture with a fresh ESPN depth entry and a 100h-old nflverse
entry should show nflverse_inputs as stale. Before fix: reported 0.2h (borrowed ESPN's
pulse). After fix: detected as stale. Matched.

**Fix.** New `_newest_pulls_age_by_feed(pulls_path, feed_name, now)` filters by `feed`
field. Lines without explicit `feed` get it inferred from `file` key via `_FILE_TO_FEED`
mapping (`depth_charts.parquet` -> `nflverse_depth`, etc.). Lines without both keys are
ignored (0 of 8 current lines have neither). Each feed in `check_feeds` now passes its
own `feed_name`. Thresholds unchanged.

**Completeness thresholds:**
- NFL teams: 32 (checked by ESPN status scripts)
- News index: team count vs requested list (checked by `pull_espn_news.py`)
- Kalshi/line snapshots: non-empty with >= 1 event (checked by puller halts)

**Pytest collection fix.** Removed empty `__init__.py` from `nfl/pipeline/tests/`,
`shared/pipeline/tests/`, `ncaaf/pipeline/tests/`. All three directories had the
same package name `tests`, causing `ModuleNotFoundError` on `nfl/pipeline/tests/`.
With rootdir-based discovery (no `__init__.py`), `pytest shared/pipeline/tests
nfl/pipeline/tests ncaaf/pipeline/tests` collects and runs **55 tests** in one command.

**Tests (3 new):**
- `test_espn_depth_does_not_mask_stale_nflverse`: fresh ESPN + stale nflverse -> stale detected
- `test_feed_field_filters_correctly`: two feeds in one file, checked independently
- `test_infer_feed_from_file_key`: `depth_charts.parquet` inferred as `nflverse_depth`

### N41 — Order #11 verified by Cowork: the grader never computed an outcome for an event ticket; the pull log still had no `feed` (2026-09-20)

Verified from a fresh clone of `80c675f` by RUNNING the production functions on the real tape,
the real news archive and the real CFBD file — not by reading the report.

**What held.** One-command suite: 55 passed. Contract identity on the real tape at two build
times: 356 sides, 0 legs that are not one row of one book; Under takes the highest total.
`point_clv` matched an independent formula on 263 of 263 legs. News reaches the selector:
145 of 145 board teams (2026-09-19T11Z), 40 of 40 (09-20T11Z); 0 articles pulled after the
build time entered. Health check in a fresh clone: all 10 feeds OK.

**Defect 1 — no event ticket could get an outcome.** `_compute_outcome` read
`leg["commence_time"]`. `build_tickets()` writes it on the TICKET; only card legs carry it. The
date key was `''`, so every event-ticket leg returned `outcome_unavailable`: 263 of 263 on a
real-tape run. No test read an outcome — the WO11 fixture's CFBD teams were named
"Team H CFBD"/"Team A CFBD", which the grader could never map from "Team H"/"Team A", and
nothing asserted on it. N38's "89/95 legs matched" was measured on card-shaped legs only.

**Defect 2 — ordered (home, away, date) key.** CFBD and the Odds API disagree on home/away at
neutral sites (Kansas-Arizona State, Virginia-West Virginia, 2026-09-19). Those games were
silently `no_match`. Now keyed on the unordered pair, points held BY TEAM NAME, matched within
`OUTCOME_MATCH_HOURS = 36` of kickoff (App State-Charlotte: CFBD 22:00Z, tape 01:32Z next day).
Two games for one pair inside the window -> `ambiguous_match`, never a guess.

**Defect 3 — the mascot-stripper can land on a different school.** "Southern Mississippi Golden
Eagles" shortens to "Southern" (Southern University, a real CFBD team that played that day).
The pair+date key turned it into a `no_match` rather than a wrong result, by luck of schedule.
Explicit `_TEAM_MAP` entries added for every name that failed on the 2026 tape: Southern Miss,
App State, Hawai'i, SE Louisiana. **Match rate after: 188 of 189 tape events; the one miss
(Arkansas State v South Alabama 09-12) is a game the Odds API listed and nobody played.**

**Defect 4 — `graded=True` froze a ticket before its result existed.** `graded` is terminal
(UPDATE-ONLY skips it), and it was set as soon as every leg had a close. The 13:00Z grade can run
before CFBD has the score, and nothing refreshes `cfbd_games_2026.parquet` on a schedule. Now a
game CFBD has not completed returns `pending`; `graded` needs every close AND every result;
otherwise `grade_status` = `close_unavailable` | `outcome_pending` and the ticket is re-read on
the next run. **Still open: the CFBD refresh is not scheduled — until it is, run
`ncaaf/pipeline/pull_cfbd_season.py --year 2026` before grading.**

**Defect 5 — a leg with no close got no outcome.** The `continue` on a missing close skipped the
CFBD lookup. A result does not depend on a captured close; outcome is now computed first.

**Defect 6 — kickoff drift.** The Odds API moves `commence_time`: 127 of 189 events on the 2026
tape (median 6 min, max 640). On 09-19 four games moved more than 30 min (Alabama 19:30 ->
21:15; App State 22:00 -> 01:35). Measured from the ticket's kickoff, the "close" of a delayed
game is a quote hours before kick. The grader now uses the `commence_time` on the event's last
pre-kick tape row (`_tape_kickoffs`) and stores it as `kickoff_used_utc`. A card leg whose game
has not started is `not_started` and is not closed early.

**Defect 7 — N12's all-zero guard halted on one leg.** With a single graded leg whose line did
not move (about half of them) the grader raised and wrote nothing. It now needs
`N12_MIN_LEGS = 10` legs (chance of 10 unmoved lines ~0.1%). The defect it was written for —
grading a game that has not kicked — is closed structurally by the 30-minute rule and the
`not_started` guard.

**Defect 8 — order #11 item 4b was not done.** "Every `_pulls.jsonl` line carries `feed`": no
writer emitted it (0 of 8 lines). Worse, the ESPN hash-skip read the LAST line of the shared
depth log, so after each 09:00Z nflverse run it compared ESPN's hash with a parquet's and
"unchanged" could never fire; and because bare ESPN lines were ignored by the health reader, an
unchanged ESPN pull left no pulse — a quiet Tuesday would read STALE. All three writers now emit
`feed` (`espn_depth`, `espn_injuries`, `nflverse_depth`, `nflverse_injuries`,
`nflverse_rosters`); `_last_hash(pulls_path, feed)` reads only its own feed; a legacy line with
neither `feed` nor `file` is ESPN's (every nflverse line carries `file`: 8 of 8 checked).
This reverses N40's "lines without both keys are ignored".

**End to end, real data.** Every 2026-09-19 game on the 14:30Z tape, both sides of spread and
total, best-quote rule, graded by production `grade_tickets` against the real CFBD file: 71 of 71
kicked events got a result; 284 legs (145 win / 137 loss / 2 push); an independent re-derivation
from CFBD disagreed on 0; 6 tickets `close_unavailable`.

**Tests (9 new, production functions, fixtures cut from the real tape and the real CFBD file).**
`test_grader_outcomes_n41.py` (6): event-shaped ticket; neutral-site flip; Southern Miss is not
Southern; delayed kickoff closes at the real kick; CFBD-not-completed stays ungraded; no close
still gets a result. `test_pull_log_feed_n41.py` (3): the four real log lines. All 9 fail on
`80c675f`. The WO11 grader fixture's unmatchable CFBD names were corrected and now assert `win`.

**UNVERIFIED.** Whether the VM's 13:00Z grade job exists and what it runs first (crontab not
readable from Cowork). Point CLV is measured on the BEST quote across books, which is biased
upward against any single book's close; the shadow comparison must use the same quote rule for
the AI's picks and for both baselines, and report CLV against the entry consensus as well.

### N42 — Builder: logged abstains and an input manifest; live quotes only; card legs are real rows (2026-09-20)

Order #11 item 3e (manifest; abstains logged) was not done and was not listed under NOT DONE.
Done here, with four defects found while reading the same path.

1. **Manifest + abstains.** Every game the selector saw writes one log entry: a ticket, or
   `abstain: true` with `legs: []` and the reason (`no_legs_returned` / `no_usable_legs` when the
   model did not say). Each carries `manifest` = model id, prompt sha256, raw response, the keys of
   the articles shown, the tape snapshots behind the quotes (~2 KB per entry). The grader and the
   card builder skip abstain entries. Without the abstains a selection cannot be compared with a
   baseline over the games it was offered.
2. **Stale quotes.** The board keeps each book's LAST quote however old — up to 303 h on the
   2026-09-19 14:35Z board — and "best point" seeks those out: 2.8% of quotes, **6.5% of
   best-quote picks**. A 12-day-old number cannot be bet, and its "CLV" is free. A leg is now
   chosen only from quotes in the event's newest snapshot (`event_newest_snapshot`).
3. **`validate_leg_against_tape` did not check the event or the snapshot.** A leg passed if any
   game at any time had quoted the same (book, side, point, price). Both keys added.
4. **`recency_days` was accepted and never used.** 27 of 890 articles shown on the 09-19 build
   were older than the stated 14 days. Applied when `build_time` is given; an article with no
   parseable `published` is dropped.
5. **The card builder was never repaired.** `build_ncaaf_cards.py` was untouched by order #11:
   FILLER legs still wrote `consensus_point` + `best_price` + `best_book` (audit #4's defect), and
   conviction legs dropped `snapshot_utc` and the entry complement, so no card leg could get a
   probability CLV. The saved board parquet drops `quotes`, so the card builder now builds the
   board in memory as of its build time. Fillers go through `select_best_quote` +
   `complement_quote`. `load_conviction_tickets` skips `pre_repair`, abstain and card entries
   (a second card run the same day would have raised `KeyError: 'event_id'` on the first run's cards).
6. **Coverage halt 25% -> 90%.** 25% was unjustified. Measured 145/145 and 40/40; the puller
   refuses to write above 5% team failures; under 90% means the name join broke.

**Tests (4 new, `test_builder_manifest_n42.py`):** production `build_board` -> `build_tickets` ->
`build_cards` on the real tape slice, only the Anthropic client mocked. At a 15:40Z build
FanDuel's 40-minute-old Under 54.5 -106 beats DraftKings' live -108; the leg must be
DraftKings'. All 4 fail on `80c675f`. **Real full-board run (09-19 14:35Z, 89 events, mocked
model): 89 entries, 12 abstains, 154 legs, 154 with a same-book same-snapshot complement,
0 halts; cards 5 + 12 legs, 4 fillers, all real rows.**

One command: `pytest shared/pipeline/tests nfl/pipeline/tests ncaaf/pipeline/tests` -> **68 passed**.

**Note for Saturday.** Line capture pauses 05:30-14:00Z, so an 11:00Z build prices every game off
05:30Z quotes (median quote age 5.5 h). Build after the 14:00Z pull.

### N43 — The NFL ticket gets a written half: candidate table, two rule baselines, a ticket log (2026-09-20)

Audit #4 item 4: NFL selection was "an unlogged LLM in a chat window" — nothing in the repo. Built
before the first scheduled Sunday props pull (15:00Z) and before anyone has seen it.

`nfl/pipeline/build_nfl_candidates.py` (no simulation, no model, **no edge claimed**):
1. Hard Rock props, the newest pull at or before `build_time`; pre-kick rows only (production
   `drop_inplay_rows`); games that have not kicked. Nothing pulled after `build_time` is read.
2. Two-way markets de-vigged FROM THE SAME ROW (same book, same pull). One-way markets (anytime
   TD, 385 of 973 rows on the 09-19 pull) have no complement and are never eligible.
3. Roles: `player_usage_weekly.parquet` (season, week), matched on normalised name within the
   game's two teams; `role_unmatched` is a reason, never a silent drop (0 of 263 volume legs on
   the 09-19 pull). Injury status: newest ESPN file at or before `build_time`; 32 teams or HALT.
4. ELIGIBLE = volume family (receptions, rush attempts, pass attempts, completions — the families
   whose role attribute passed the 2021-24 split-half audit, D11) AND two-way AND role matched AND
   not Out/Doubtful/IR AND the pull is at most `MAX_PULL_AGE_HOURS = 3` old. The pick side is the
   side the book favours. D58 MOVED-AGAINST (first pull of the week vs this one, same line only)
   is displayed and never acted on.
5. Two baselines, both pure rules, one leg per game, top 5 by de-vigged q:
   `BASELINE_TOPK_Q` (any eligible leg) and `BASELINE_ROLE_OVERS` (Overs on a team's top-2 target
   share / top carry share / flagged starting QB — ranks within team, no threshold to tune).
6. `nfl/data/board/nfl_prop_tickets_2026.json`, append-only: each entry stores the manifest (pull
   timestamp and age, usage sha256, injury file, candidates file + sha256), full legs (line, price,
   SAME-ROW complement, q, pull timestamp), the price, and `vetoes`. **A veto without a reason AND
   a source is refused.** The reader's final ticket is logged beside the baselines it departed from.

**What the real 09-19 15:11Z pull says (measured, not a claim of edge).** Hard Rock's two-way hold
is a flat ~6.7-7.0% in every family. The top-5-by-q ticket prices at 7.29 decimal against a
product of the book's own de-vigged probabilities of 0.0957: **expected return 0.70 per 1 staked
at the book's own numbers** — every leg costs ~6.5%, five legs ~30%, before any same-game charge.
Top-q legs are low-line Unders (TE2 receptions U1.5 -230); lead-role Overs sit at q 0.58-0.59.

**Pre-registered, for the prospective comparison (nothing tuned on 2026):** per week, hit rate and
point/probability CLV of (a) each baseline, (b) the reader's final ticket, (c) the legs the reader
vetoed. The reader layer earns its place only if (b) beats (a) on CLV and the vetoed legs do worse
than the kept ones. No count of weeks is declared sufficient in advance; the log just accumulates.

**NOT DONE.** No NFL prop grader for this log (close = last pre-kick Hard Rock pull within 30 min;
the Sunday slots give 16:30Z for 17:00Z kicks and 19:45Z for 20:05Z, but 20:25Z kicks are 40 min
out -> `close_unavailable` as the rule stands). No outcomes join (nflverse player stats). Alt lines
are not in the pull. `nfl/sim/` untouched; the sim is not a layer in this log yet.

**Tests (6, production functions, fixtures cut from the real props archive, the real week-2 usage
rows and the real ESPN injuries pull):** same-row de-vig; nothing after build_time, nothing kicked;
stale pull -> nothing eligible; an Out player is never eligible; baselines reproducible and one leg
per game; log append-only and a veto needs a source. Six mutations of the production file (raw
implied as q, no build-time cutoff, status ignored, kicked games kept, stale pull allowed, many legs
per game) each turn at least one test red. One command: **74 passed**.

### N44 — ChatGPT audit #5 adjudicated: the final ticket is enforced by code; five defects fixed (2026-09-20)

Full table: `research/cross_ai/chatgpt_audit5_adjudication_parlay_board_2026-09-20.md`. Every
probe reproduced on production functions at `73bf63f`.

1. **NFL final ticket (N43 was a description, not an enforcement).** `log_ticket(path, entry, cand)`
   now checks every leg against the candidate table: exactly one row, same line / side / both
   prices / pull, eligible, one leg per game. `log_final_ticket` builds the legs FROM candidate rows,
   derives removed/added legs against BOTH baselines and halts unless each has a reason and a
   source, requires an availability confirmation per final leg and the reader's model / inputs /
   raw output, and accepts 0..5 legs (no ticket is a valid logged outcome). `main --final file`
   reaches it and refuses a candidate table whose sha256 differs from the logged baselines'.
2. **Injury feed.** File older than `MAX_INJURY_AGE_HOURS = 7` (the feed runs 6-hourly) -> nothing
   eligible. Status is read from the player's own team only. No feed entry -> `feed_status_missing`
   (28 of 263 eligible on the 09-19 pull, all healthy starters) — eligible, never final without an
   availability source.
3. **Roles.** Rank ties take the worst rank; `n_targets` / `n_carries` shown beside the shares.
   The usage layer-3 QB fallback has no date guard (open); the committed week-2 rows were checked:
   32 of 32 flagged starters are the week-1 leading passer.
4. **NCAAF writer** keyed on `t["event_id"]` and raised KeyError on the committed log's card
   entries — no ticket build could have been persisted. Key is now event_id or `card:<id>`.
5. **NCAAF news:** coverage counts what the selector is shown (inside the 14-day window):
   143/145 on 09-19. An article without a readable pull time does not enter.
6. **`prob_clv_C`** uses the accepted decimal price: unchanged -110/-110 = -4.55%, not 0.
7. **Close capture:** Sunday props pulls at 16:50Z, 19:55Z, 20:15Z (`--window-hours 1`), ~243
   credits per Sunday, so every kickoff window has a Hard Rock quote inside 30 minutes.

**Tests:** NFL file 6 -> 11 (invented leg refused, two legs in one game, ineligible leg, old injury
file, own-team status, derived departures, no-ticket, `main()` -> `--final` end to end with a
tampered table); NCAAF `test_audit5_n44.py` 4 (writer on a copy of the REAL log, unreadable pull
time, in-window coverage, C at -110/-110). A WO11 news fixture lacked the `pull_time` every real
legacy article carries; corrected. One command: **83 passed**.

### N45 — WO5 item 3 executed: 0 rows graded. The cohort it was written for is excluded by N37 (2026-09-20)
Work order #5 item 3 ("first genuine grading run"), run at 2026-09-20T13:0xZ, one day
after N18 deferred it. Ran from the Cowork bridge VM (python 3.10.12, pandas 2.3.3).

**Decision number.** WO5 assigned this N18. N18 was already written on 2026-09-19 as
"Grading deferred: games not yet played". The number is occupied by a real decision and
is not reused; overwriting it would delete the deferral record. This entry continues the
series at N45 and supersedes the *intent* of N18, not its text.

**RETURNED.**
  Run 1: `Graded: 0 tickets changed` / `No graded tickets (excluding pre_repair)`. exit 0.
  Run 2: identical. exit 0.
  Ticket log sha256 `9d982b81…a203f878` before run 1, after run 1 and after run 2 —
  byte-identical. 31 entries, 0 graded, 0 keys lost, 0 keys added.

**MEANS.** Nothing was graded, and not for the reason WO5 anticipated. Execution trace
(sys.settrace on grade_ncaaf_tickets.py, real run, not a code reading):
    line 245  `for ticket in tickets`        32 hits
    line 246  `if ticket.get("pre_repair")`  31 hits
    line 247  `continue`                     31 hits   <- all 31 exit here
    line 263  future-kickoff guard            0 hits
    line 402  `if changed > 0` (N12 gate)     1 hit, False
All 31 entries carry `pre_repair: true` from N37. The guard at line 246 fires before the
N12 future-kickoff guard is ever evaluated. Nebraska @ Michigan State did stay ungraded,
but by the pre_repair skip, not by the future-kickoff guard.

**The N12 future-kickoff guard is not defective — it is unreached.** Demonstrated on a
scratch copy with the five WO5 tickets un-flagged (repo log untouched): line 263 evaluated
5 times, line 264 skipped exactly 1 — Nebraska @ Michigan State, 2026-09-26T21:00Z. The
guard works on its own. It has still never been exercised by a production run.

**Why the cohort is not gradeable, ever.** N37 found `build_ncaaf_tickets.py` wrote
consensus_point + best_price + best_book, a triple that did not exist in the tape 17 of 30
times. Applied to these exact legs: **9 of the 16 settled-game legs exist in the tape;
7 do not.** Those 7 carry an entry price no book offered. CLV against a price that was
never available is not CLV. The pre_repair exclusion is correct and must not be lifted.

**Diagnostic only — NOT a CLV result, NOT written to the log.** With pre_repair removed on
a scratch copy the grader returns changed=4 and produces:
  - Pre-kick rule HOLDS. Minutes from close snapshot to kickoff: -4.8, -29.9, -29.9, -4.9.
    All negative. No in-play row was selected as a close on any of 16 legs.
  - point_clv spread -1.0 .. +1.0, distinct {-1.0,-0.5,0,+0.5,+1.0}, 7 of 16 exactly zero.
    Not all-zero, so the N12 assertion would not have fired.
  - By market: spreads N=8 mean -0.125; totals N=8 mean -0.125.
  - By book: bovada N=11 +0.045, betrivers N=2 -0.500, betmgm N=1 -0.500,
    fanduel N=1 -1.000, lowvig N=1 0.000.
  - **prob_clv: 0 of 16 computed.** 9 `line_moved_no_alt_quote`, 7 `entry_complement_missing`
    (pre-N37 legs carry no `complement_price`). The economically meaningful CLV is absent.
  - These are 8 mirrored both-sides pairs, not 16 observations. Per-ticket sums are 0.0,
    0.0, -0.5, -1.5 — near-mechanically zero by construction. No aggregate here is
    interpretable, and none is claimed.

**Defect found, not fixed here.** `grade_ncaaf_tickets.py` writes the ticket log directly
(`open(TICKET_LOG,"w"); json.dump`) and does not route through `build_ncaaf_tickets.
write_ticket_log`. N16's claim that append-only is "enforced by assertion, not by
convention" is not true of the grader — the one writer that now runs repeatedly. Separately
`build_ncaaf_cards.log_cards` guards with `len(merged) < before_count` where
`merged = existing + 2`, a condition that cannot be true; it is a guard that cannot fail.

**Status of the first CLV data point: not obtained.** Zero observations, not four. The
first genuine CLV run requires a post-N37 ticket build whose legs pass
`validate_leg_against_tape`, on games that then settle. No such cohort exists yet — every
entry in the log was built 2026-09-19T14:50Z or earlier. Against the ~125 observations CLV
needs, the count is 0.

**Credits.** Zero. `grade_ncaaf_tickets.py` makes no HTTP call (no requests/urllib import;
tape and CFBD read from local parquet), so no `x-requests-remaining` header was returned by
this run. Last known balance stands at 8976, unchanged and unconfirmed by this session.

### N46 — A slate of NFL tickets dealt by rule, no player on two tickets (2026-09-20)

(N45 was taken the same morning by a parallel Cowork session's WO5 grading run; this is N46.)

**Jeff's ask (2026-09-20):** a 1pm 5-leg, a 4pm 5-leg (can run later), an all-day 5-leg, an all-day
10-leg and an all-day 20-leg, with separate legs "so 1 miss doesn't sink them all". Delivery ~12:15pm
ET off the 11am pull after inactives; he is not concerned with last-minute updates. 20-leg: two props
in some games (his choice — a 14-game Sunday cannot give 20 one-per-game legs).

`nfl/pipeline/build_nfl_slate.py`, on top of N43/N44's candidate table and log:
- Windows in hours after the slate's first kickoff: early [0,1), late [2.5,4.5), all [0,9) (Monday
  is not "all day"). Pools: `role_overs` (book-favoured Overs on a team's lead roles) for the three
  5-leg tickets, `top_q` (any eligible leg by de-vigged q) for the 10 and the 20.
- DEAL: tickets take turns in spec order (20, 10, early 5, all-day 5, late 5), one leg per round,
  each taking its best remaining legal leg. Legal = player not used ANYWHERE on the slate; at most
  `max_per_game` legs in a game; a new game before a second leg in a game; a second leg only on the
  OTHER team (the one opposing-team pair in the ledger paid 1.009 of the product; n = 1).
- Logged as `<ID>_RULE`; the reader's version as `<ID>_FINAL`, with departures derived against the
  RULE ticket (reason + source each), an availability confirmation per final leg, and a refusal if a
  player is already on another FINAL ticket of the slate. The 4pm ticket is dealt later from the
  new pull with every player already on the slate excluded.
- `check_legs_against_candidates(..., max_per_game)`: a declared cap, different teams, a player once.
- Injury-feed age now counts a hash-skipped ("unchanged") pull as a pulse; a later line with a
  different sha and no file does not.

**Measured on the real 2026-09-20 13:12Z pull (943 rows, 259 eligible):** 45 legs, 45 distinct
players. Calculated gross return per $1 at the book's own de-vigged q, independent games: early 5
0.74, all-day 5 0.73, late 5 0.73, **10-leg 0.51, 20-leg 0.27** (product price ~9,268; ~5,263 if Hard
Rock applies its measured ~0.91 per extra same-game leg to the 6 doubled games). The 5-leg tickets
cost ~27 cents on the dollar in hold; the 20-leg ~73. Stated to Jeff before placement.

**Tests (5, `test_nfl_slate_n46.py`, production functions on the N43 real-data fixtures):**
deterministic under row shuffling, disjoint players, 2-per-game on opposing teams, Monday excluded;
later ticket excludes used players; RULE/FINAL logging with derived departures and the cross-final
clash; same-team pair refused; unchanged-pull pulse. Five mutations of the dealer/logger each turn
a test red. One command: **88 passed**.

### N47 — Sequential deal: the first ticket gets the strongest legs (2026-09-20)

Jeff, 14:15Z, after the five-ticket slate was sent: one all-day 5-leg, one 10-leg, one 20-leg — "give
the 5 leg our most promising, then the 10 and then the 20"; separate 4pm tickets only if he asks later.
`deal_slate(sequential=True)` fills each ticket COMPLETELY in the order given (round-robin remains the
default); spec `BEST_5` = 5 legs, one per game, `top_q` pool. "Most promising" is defined as the
book's own de-vigged probability — nothing of ours ranks legs — so the 5-leg is low-line Unders
(backup TE/RB receptions U1.5, -195 to -250) at ~+573, return per $1 0.70; the 10-leg 0.52; the
20-leg 0.28. Logged under slate `2026-09-20b`; slate `2026-09-20` (five tickets) is superseded, not
edited. Reader-pass rules added after a caught error (a Saints RB offered as Kamara's replacement):
no replacement from a vetoed player's backfield, no Over on a player with zero week-1 targets.
FINAL tickets can be revised only by an appended `_r<n>` entry with a stated reason. Test:
`test_sequential_deal_gives_the_first_ticket_the_strongest_legs`. One command: **89 passed**.

### N48 — One q scale picks only receptions: families are dealt in turn (2026-09-20)

Jeff, 14:28Z: "why is every single leg reception based...that doesnt seem right at all." He was right.
Measured on the 14:07Z pull: receptions 153 eligible legs, q up to 0.663 (45 at or above 0.575); rush
attempts 50, max 0.554; pass attempts 28, max 0.520; completions 28, max 0.541. The top 60 legs by q
were all receptions and so were 35 of 35 dealt legs. Cause: reception lines are small integers the
book cannot balance, so they are priced lopsided (-160 to -250); attempts and completions lines sit
at the median (-125 to -135). A lopsided price is market favouritism, not a better bet — ChatGPT
audit #5 said so and N47 ranked on it anyway — and 35 legs of one kind is one bet made 35 times.

`balance_families`: a ticket takes its legs from REC / RUSH / QB (attempts or completions) in turn,
best q WITHIN the group, falling through to the next group only when none is legal. Specs `LEAD_5`
and `LEAD_10` draw from the lead-role Overs pool (top-2 target share, lead back, flagged starting QB)
— 90 legs all day: 40 QB, 28 REC, 22 RUSH. Slate `2026-09-20d`: LEAD_5 2/2/1, LEAD_10 4/3/3,
ALLDAY_20 7/7/6; return per $1 at the book's own q 0.73 / 0.53 / 0.27 (unchanged in kind: hit
probability fell, payout rose). Known residue: inside RUSH the top-q legs are QB rush-attempt Unders
at 3.5-5.5 — the same small-line artifact, plus kneel-downs count as rush attempts. A line-band rule
inside each family is the next refinement; not built today.
Test: `test_balanced_families_stops_the_all_receptions_ticket` (reproduces the defect, then the
cycle). One command: **90 passed**.

### N49 — Placed tickets are logged from the slip; opposing-team pairs ARE priced down (2026-09-20)

`log_placement`: an appended `placement` entry per ticket — stake, quoted odds, the legs actually
placed (each must be a recommended leg at the same line and side; an unplaced leg needs a reason;
an accepted price that differs is recorded), the book's same-game pair quotes, the source.

Slate `2026-09-20d` as placed (Jeff's Hard Rock slips): 5-leg $15 +1328; 10-leg $15 +26267; 19-leg
SGPMAX $10 +921621 (Wentz skipped: line moved). **Measured:**
- Cross-game = product of the legs: 10-leg 263.67 vs 263.67, 5-leg 14.28 vs 14.285. Now 18 of 18 slips.
- The six same-game pairs on the 19-leg were all OPPOSING-TEAM pairs, quoted at 0.970, 0.955,
  0.925, 0.850, 0.949, 0.917 of the product of their singles (median 0.937; the 0.850 is two
  quarterbacks' completions in one game). Singles are from the 14:07Z pull — the slip shows only the
  pair price — so each ratio carries a few minutes of price drift. SGPMAX adds ~0.4% on top.
  The whole 19-leg pays **0.631 of the straight product**.
- N46 dealt second legs "only on the other team" on the strength of ONE ledger slip at 1.009. That
  does not generalise and is withdrawn as a pricing claim; the different-team rule stays only as a
  diversification rule. **Doubling six games cost ~37% of the payout** — a 14-leg one-per-game ticket
  would have paid the full product. Next slate: offer that trade-off explicitly.
Test: `test_placement_is_appended_and_must_match_the_recommendation`. One command: **91 passed**.

### N50 — Every final leg carries the AI's one-line reason; sim-vs-book scorer written pre-kick (2026-09-20)

**Jeff (16:00Z):** "was there any AI reasoning involved in today parlays....id like for the future...
the leg, game and ai reason its apart of the parlay ... not a book just a small brief reason so we
know AI is apart of the pick." And: test the sim against today's games, NOT part of decision making.

**What the AI actually did today (slate 2026-09-20d), stated plainly.** The legs were DEALT BY CODE:
lead-role Overs (5- and 10-leg) and all eligible legs (20-leg), families in turn, best book q within
a family. The reader (Claude in the Cowork chat) only FILTERED: vetoed Kamara (Jeff's instruction;
MCL, 0 week-1 touches) and Hampton (Over 1.5 rec on 0 week-1 targets), caught its own bad Kamara
replacement (Etienne, same backfield), checked availability, and re-dealt by rule when Rodgers' line
moved (next QB leg: Shough). No leg was on a ticket because the AI argued FOR it, and no per-leg
reason was written. So today's tickets were rule-picked and AI-filtered, not AI-picked.

**Change.** `log_final_slate_ticket` refuses a FINAL ticket unless every leg's confirmation record
has an `ai_reason`: 20-200 characters, not the same sentence on more than two legs, no sure-thing
language ("lock", "guaranteed", ...). Stored as `leg_notes` on the entry. `final_ticket_markdown(entry)`
renders what Jeff is sent: Leg | Game | Kick | Price | Book q | AI reason. The reason is a NOTE, not
evidence of edge; its use is the comparison already pre-registered in N43/N44 (kept vs dealt vs
vetoed), which now has text to read. Tests: `nfl/pipeline/tests/test_ai_reason_n50.py` (2; both FAIL
on the pre-N50 logger — run). The N46 test's confirmations gained an `ai_reason`.

**Sim vs today's games (no role in any pick).** Written ~16:05Z, before the 17:00Z kickoffs:
- `nfl/pipeline/export_placed_legs.py` -> `nfl/data/board/week=2026_02/placed_legs_2026-09-20d.parquet`
  (34 legs, 34/34 player ids resolved `exact_team`) in `grade_week.py --extra` format. The sim's grader
  + `actuals.py` stay the single source of outcomes; this IS the NFL prop outcome grader for the
  ticket log (receptions, rush attempts, completions, attempts, both sides). Close/CLV still not built.
- `nfl/sim/score_week_vs_book.py`: on rows where the sim priced the book's exact line (146 today),
  Brier/log-loss of book q vs sim cal_p vs raw sim_p, game-cluster bootstrap, by family/tier/game, the
  |cal_p - q| > 0.20 rows, and W/L for every placed leg. PRE-REGISTERED: P1 book Brier < sim Brier;
  P2 on the divergent rows the outcome sides with the book more often. Tests
  (`nfl/sim/tests/test_score_vs_book.py`, 4): the scorer favours the BOOK when outcomes are drawn from
  q and the SIM when drawn from cal_p (it can go either way); placed rows never enter the universe
  (the first end-to-end run HALTED on exactly that duplicate — fixed, tested).
- Dry run end-to-end at 16:04Z: 1,271 legs, all `void-pending` (no Week 2 game in PBP yet). Outcomes
  arrive when nflverse PBP refreshes (overnight). One week: a log, not evidence.

Suite: 97 passed (shared + nfl/pipeline + ncaaf/pipeline + the new sim scorer test).
NOT DONE: close/CLV for NFL tickets; AI reasons for TODAY's legs (not written before the bet, so not
written after it). UNVERIFIED: that tonight's PBP refresh contains all 15 games by morning.

### N51 — First AI-PICKED tickets: slate 2026-09-20e, a 5 and a 10 (2026-09-20)

**Jeff (~16:13Z):** "give me your take on a 5 and 10 leg parlay....look at all the data and make your
picks independent of the 5-10-19 leg parlays already placed."

Built 16:14Z from the Hard Rock pull of 15:00:10Z (1.2 h old; candidates `..._20260920T1614Z.parquet`,
259 eligible). RULE tickets `LEAD_5_RULE` / `LEAD_10_RULE` logged first as the baseline; the reader's
tickets `LEAD_5_FINAL` and `LEAD_10_FINAL` depart from them on almost every leg, each departure with a
reason and a source, and every leg has an `ai_reason` (N50 — first production use). `LEAD_10_FINAL_r1`
supersedes `LEAD_10_FINAL`: the Hubbard reason called CAR the home favourite; the game is CAR @ ATL
(CAR -3 on the road). Legs unchanged. Log = 35 entries.

**Method, stated so it can be judged later:** game script from Hard Rock's own spread/total (15:30Z
snapshot) x week-1 volume from `pbp_2026` (team rushes, QB attempts/completions, final margin) x role
share from the candidate table; prices kept to -115..-130; one leg per game per ticket; no player on
both; NO sim input. Every leg is the side the book already favours (the candidate table offers no
other), so this is a choice AMONG book-favoured legs, not against the book.
5-leg (20.74, ~+1,974): Lamar U27.5 att, Hockenson O3.5 rec, Stroud O30.5 att, Hampton O16.5 rush,
Diggs O4.5 rec. 10-leg (393.2, ~+39,200): Hubbard O13.5, Montgomery O15.5, Rodgers O34.5 att, Lloyd
O13.5, Jeudy O2.5 rec, Lawrence O19.5 cmp, Cousins O29.5 att, Bourne O2.5 rec, Willis O26.5 att,
K. Allen O3.5 rec. Return per $1 at the book's q: 0.716 / 0.518.

**Known weaknesses, written before kickoff:** (1) one week of 2026 volume is thin evidence and the
book has it too; (2) the legs share ONE idea — favourites run, underdogs throw — so they are
positively correlated across games only through that idea failing generally, but within LV@LAC and
CIN@HOU the two tickets hold related legs; (3) Willis and Cousins also sit on the placed 19-leg in
other markets; (4) availability was checked against a list that may not be the full 90-minute
inactives; (5) 14 of 15 legs are Overs. Comparison that this enables (N43/N44): AI-picked vs the
RULE tickets of the same build vs the placed rule-dealt tickets, on hit rate and close. n = 15 legs.
NOT DONE: placement entries (waiting for Jeff's slips). UNVERIFIED: prices at bet time.

### N52 — Fresh-pull re-check of the AI tickets; first AI game-lines ticket (2026-09-20)

**Jeff (16:20Z):** the 11am numbers were stale by the time the AI tickets went out — get the newest.
CAUSE, not a fault: Sunday props pulls are 15:00Z (12 h window), 16:30Z (2 h), 16:50Z (1 h), and the VM
pushes to GitHub on the half hour, so the 16:30Z pull reaches Cowork ~17:00Z = kickoff. Jeff ran a manual
pull (16:23:40Z, 940 rows, 130 credits) + ESPN status (16:23Z, free) and scp'd both to `_cowork_patches/`.
RESULT: 14 of 15 legs identical in line AND price; Kirk Cousins pass attempts 29.5 -> 30.5 = new quote,
dropped. `LEAD_10_FINAL_r2` replaces him with Tyler Shough O34.5 att (-120), unchanged on both pulls.
No leg's player Out/Doubtful at 16:23Z; Burrow and Olave went Questionable -> Active. 9 of 240 eligible
rows moved line between 15:00Z and 16:23Z. Log = 36 entries.
STRUCTURAL GAP: for a 1pm ticket built after inactives, Cowork cannot see any pull newer than ~11am
without Jeff's manual scp. Fix candidates (not built): an extra push right after the 16:30Z pull, or
a props pull at 16:05Z so the 16:30Z push carries it.

**AI game-lines ticket (`game_ticket_ai_20260920T1635Z.json`), sent 16:34Z.** Jeff asked for 5+ legs of
spreads/totals/winners with a short reason each. Method: Hard Rock's price vs the proportional no-vig of
Pinnacle + LowVig at the same point (line_history snapshot 16:00:08Z, all books < 1 min old), and
off-market points judged against the other nine books. Legs: NYJ +3 (+100), PIT +5.5 (-105), CLE@TB
Over 41 (-110), MIA +13.5 (-105), IND +6 (-105); optional MIN +5 (-110). ~+2,740. Return per $1 at the
sharp no-vig ~0.96 (vs ~0.72 for a 5-leg prop ticket) — still below 1: NO EDGE CLAIMED. Every leg is an
underdog or an Over because Hard Rock shades favourites/Unders less generously; the prop tickets lean
on favourites controlling games — told Jeff the two do not share a story.
CHECKS: 1a all quotes pre-kick, same snapshot. 4: sharp no-vig is a proxy for fair, not truth; the
project's line-shopping result (+1.84% ex-stale) was best-of-10-books, not Hard Rock alone, so it is
NOT evidence for this ticket. No NFL game-ticket logger/grader exists (NCAAF's is college-only); this
JSON is the record. NOT DONE: placement entries for slate -20e (waiting for slips); NFL game grader.

**N52 addendum (16:46Z) — Jeff caught stale game prices; the feed itself checked out.** Jeff: "your lines
arent accurate on the hardrock site...jets plus 3 are -105 the steelers are -110 ... if your reasoning is
becasue of the lines then there off." Treated as an audit of the tape. RETURNED: a fresh capture at
16:43:52Z (3 credits) shows Hard Rock NYJ +3 -105 and PIT +5.5 -110 — identical to the app on both. MEANS:
the `hardrockbet_fl` game-line feed matched the app 2 of 2 (first time it has been checked for game lines;
n=2, not a validation); the ticket was built on a 16:00Z snapshot that was 35-40 minutes old in a moving
market (NYJ had gone 3.5/-115 -> 3.0/+100 between 15:30Z and 16:00Z). ERROR CLASS: a price-based reason
is only as good as the age of the price; the ticket message said "check each in the app" but did not
refuse to reason from a 35-minute-old quote. RULE FROM NOW: a ticket whose reasons are PRICE reasons is
built only from a snapshot < 10 minutes old (3 credits buys one), and says its age in the first line.
`game_ticket_ai_20260920T1645Z_r1.json` supersedes the first: IND +6 -105, MIA +13.5 -105, PIT +5.5 -110
(now merely fair), CLE@TB Over 41 -110, NYJ ML +150 (replaces NYJ +3); optional MIN leg gone (+5 -> +4.5).

### N53 — AI OPINION game picks (football reasoning), logged beside the price-based ticket (2026-09-20)

**Jeff (16:48Z):** asked whether the picks were "just reasoning around the lines" or news and projections.
Answer given: the game ticket was price-only; the prop tickets were judgement over script/volume/role/
news, not a numeric projection; no model here has evidence on NFL sides. **Jeff:** "yes i want those ai
opinion based wagers...giving you data to look at then with ai reasoning pick a side."

Sent 16:53Z (`game_ticket_ai_opinion_20260920T1653Z.json`), late games only (1pm games had kicked):
ARI +4 (-110), WAS +4.5 (-110), NYG +7 (-115), LV@LAC Under 43.5 (-110), JAX +2.5 (-105); optional
IND@KC Under 46 (-110). ~+2,440 for five, ~+4,750 for six. PASS on MIA@SF. Inputs: week-1 PBP
efficiency, the week's line path, team injury reports (web), NWS forecasts (wind <= 10 mph everywhere),
Hard Rock prices from the 16:43:52Z capture (9 min old when sent — inside the new < 10 min rule).

**ERROR, caught by Cowork 2 minutes after sending:** four league RANKS in the reasons were asserted
without being computed over all 32 teams (LAC offense "3rd-worst" -> 5th; LV "7th-worst" -> 13th, i.e.
mid-pack; DAL defense "worst" -> 2nd-worst; JAX offense "best" -> 3rd). Correction sent 16:54Z; the
Under 43.5 demoted from #2 to #4. Same class as the wrong-timestamp errors: a number written from
impression. RULE: every number in an `ai_reason` comes from a computed table in the same session.

**What this is for.** Three kinds of AI reasoning are now on record for slate -20e, all pre-kick, each leg
with its reason: (a) props by script/volume/role, (b) game lines by price vs sharp no-vig, (c) game lines
by football opinion. Plus the rule-dealt tickets Jeff placed. Comparison is by hit rate and close, per
kind, over weeks; n per week is 5-15 legs, so nothing here can be called evidence for a month or more.
CHECKS: 1a all inputs pre-kick; 2 n/a (no fitting); 3 the logged legs ARE the sent legs; 4 Hard Rock's
own prices, not synthetic; 5 regime: all dogs/unders again — if opinion picks only ever land on dogs and
unders, that is a bias to name, not a finding.
NOT DONE: placements (waiting on Jeff); an NFL game-ticket logger/grader (three JSON records today are
hand-built — this needs code before next Sunday). UNVERIFIED: injury statuses beyond the articles read.

### N54 — STANDING RULE: every pick is the AI's opinion; every data layer is an input to it (2026-09-20)

**Jeff (~17:10Z), verbatim:** "we need a stnading rule....all picks will always be based off your AI
opinion....all the data layers, the engine sim (when its ready), the news, the lines, the stats, there all
just there to help you form your opinion..."

**What changes.** Until today the NFL ticket was DEALT BY CODE and the reader only filtered (N43-N48); the
morning's placed tickets were rule-picked and AI-filtered (N50 said so). From now on, for every sport and
every ticket in this project:
1. THE PICK IS THE READER'S OPINION. Claude looks at everything available and chooses the side. No layer
   picks on its own: not the rule deal, not the book's q, not price-vs-sharp, not the sim.
2. EVERY LAYER IS AN INPUT, shown to the reader and recorded in the ticket's manifest: prices and their
   movement (Hard Rock + the other nine books), candidate table (roles, shares, week volume), injuries/
   inactives, news, weather, play-by-play stats, and the sim's numbers once it is ready. The sim never
   gates or ranks a ticket; it is one more thing the reader reads. (Standing sim position unchanged: D103.)
3. EVERY LEG CARRIES ITS REASON (N50), in the reader's words, brief, with the facts it rests on. Every
   number in a reason comes from a table computed in that session (N53's error), and any price quoted is
   from a snapshot < 10 minutes old or is labelled with its age (N52's error).
4. THE READER MAY PASS. Fewer legs than asked, or no ticket, is a valid answer (audit #5). A leg the reader
   does not believe in is never added to reach a count.

**What does NOT change — the opinion is the pick, the discipline is the record.**
- An opinion is not a finding. No AI pick is ever described as validated, as an edge, or as +EV. The
  ticket sentence stays: calculated return per $1 at the book's own numbers, assumptions unvalidated.
- Logged BEFORE kickoff, append-only, with inputs, model id and reasons; placements logged from the slip.
- BASELINES ARE STILL LOGGED beside every AI ticket from the same pull — the rule deal (top book-q,
  lead-role Overs) and, for game lines, the price-vs-sharp list — because "did the opinion beat the dumb
  rule?" is the only honest test of the opinion. Graded on hit rate AND close (CLV), per kind of
  reasoning, with family / side (Over-Under, dog-favourite) / week breakdowns (check 5). At 5-20 legs a
  week this says nothing for at least a month; it will be reported as a log until then.
- Known biases to watch from day one: today's opinion tickets were 14/15 Overs on props and all
  underdogs/Unders on game lines; and the reader's football knowledge ends mid-2026.

**To build before next Sunday (not built):** `kind: ai_ticket` in the NFL logger so an AI ticket is a
first-class entry with its baselines attached (today it is logged as a FINAL that "departs" from a RULE
ticket on almost every leg); an NFL game-line ticket logger + grader (today: three hand-built JSON
records); the same reader-first path for NCAAF Saturday tickets (its builder already calls a model per
game — the prompt must present ALL layers and ask for the opinion + reason, not a filter).
