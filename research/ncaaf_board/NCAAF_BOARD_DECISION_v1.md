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
