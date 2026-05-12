# P09 PIT Verification and Open-Question Resolution V1

**Date:** 2026-05-12
**Inputs:** P09 spec v1, P09 spec review, MLB registry v2, repo evidence
**Purpose:** Resolve PIT hard stops and Section 12 open questions before implementation prompt

---

## A. PIT Verification — The Seven Hard Stops

### A1. Starter identity is knowable pregame

**VERIFIED**

Evidence: `modules.schedule.fetch_schedule()` returns `home_probable_pitcher` and `away_probable_pitcher` with `id` and `name` fields. Tested on 2026-05-12: 13/15 games had starter IDs available. The 2 missing are expected (TBD starters announced late). The spec's `STARTER_UNAVAILABLE` skip-and-note behavior handles the gap.

### A2. Rolling hard-hit feature uses only prior starts

**VERIFIED**

Evidence: The daily aggregate `pitcher_statcast_per_start.parquet` stores per-start `hard_hit_rate`. The rolling feature is computed at runtime using `shift(1).rolling(5, min_periods=3).mean()` (confirmed in `daily_signal_generator.py` lines 330–340). `shift(1)` excludes the current row. The parquet contains only completed starts (game_date < today because the daily rebuild runs at 4:45am from yesterday's data). No same-game data is possible.

### A3. shift(1) can be preserved at runtime

**VERIFIED**

Evidence: The standalone runner will sort by `(pitcher_id, game_date)` and apply `shift(1)` identically to the V1 pipeline. The parquet is sorted by these columns. The `shift(1)` operation is a pandas standard that excludes the current row from the rolling window. No implementation-specific barrier exists.

### A4. rolling(5, min_periods=3) can be preserved at runtime

**VERIFIED**

Evidence: Same mechanism as A3. `rolling(5, min_periods=3)` is a pandas standard applied after `shift(1)`. The standalone runner replicates the same groupby-transform chain. No barrier.

### A5. No same-game Statcast data is used

**VERIFIED**

Evidence: The daily Statcast rebuild (`rebuild_statcast_aggregates.py`) runs at 4:45am and includes data through the prior day's completed games. The `shift(1)` further excludes the most recent completed start. Today's games have not been played when the runner fires. No same-game leakage path exists.

### A6. Daily runtime feature output matches the research formula

**NOT VERIFIABLE WITHOUT IMPLEMENTATION**

The implementation must verify this by computing `hh_r5` for a sample of ~20 pitchers using the standalone runner's data path and comparing against the V1 pipeline's `_hh_cache` values for the same pitchers on the same date. The values must match within floating-point tolerance (< 0.001).

**Gating check:** Before writing any runner output, the implementation must run a verification function that:
1. Loads the daily parquet
2. Filters to starters (using the chosen starter identification approach)
3. Computes shift(1) rolling(5, min_periods=3) hard_hit_rate
4. Compares output against V1's `_hh_cache` on the same date for ≥10 overlapping pitchers
5. Passes if all values match within 0.001
6. Hard-stops if any value diverges by > 0.001

### A7. P09 scores match p09_overlay.py output on sample games

**VERIFIED** (formula-level)

Evidence: Manually computed `avg(home_hh, away_hh) * park_rf` for 3 games on 2026-05-12 using the same data sources the standalone runner would use. All 3 matched `compute_p09()` output exactly (< 0.001 tolerance). Sample: LAA@CLE p09=33.152, WSN@CIN p09=48.284, COL@PIT p09=44.710.

**Note:** Full match verification (A6 + A7 combined) requires implementation-time testing with the chosen starter filter. The formula matches, but starter identity differences could cause input divergence.

---

## B. Open Question Resolution

### B1. Host placement — Mac or VM?

**RESOLVED: VM**

Reasoning:
- The Statcast parquet is rebuilt on Mac at 4:45am and pushed via `git_push.sh`. The VM receives it via `push_daemon.sh` (every 30 minutes). By 7:30am ET, the VM has the current parquet.
- YRFI shadow tracker already runs on VM cron at 7:05/7:30am ET and reads the Statcast aggregate successfully.
- P09 uses the same parquet. Same host, same timing pattern.
- Ops v9 §15: VM is the default host. Mac exceptions require justification (e.g., Statcast rebuild itself). P09 only reads the parquet, it doesn't rebuild it.

### B2. Cadence — daily pre-game

**RESOLVED: Daily at 11:30 UTC (7:30am ET)**

Reasoning:
- Matches YRFI shadow tracker timing.
- Starters are generally posted by 7am ET for day games, earlier for night games.
- The 7:30am window is after the Mac's 4:45am Statcast rebuild + push cycle.
- No per-snapshot cadence needed — P09 is a pregame-only signal.

### B3. Canonical sportsbook — DraftKings

**RESOLVED PENDING JEFF CONFIRMATION: DraftKings**

Reasoning:
- `line_snapshots_2026.json` already captures DraftKings and FanDuel totals lines at multiple snapshot times (OPEN, 2AM, 5PM, CLOSING).
- DraftKings has the widest 2026 historical coverage in the existing line snapshot infrastructure.
- Hard Rock is not currently captured by any API pipeline and would require a new data source.
- Pinnacle is useful for CLV but is not the user's betting book.
- DraftKings total line is already available in `line_snapshots_2026.json` — no new API call needed.

**Pending Jeff:** Confirm DraftKings as canonical book for P09 shadow tracking. If Hard Rock is preferred, a new price-capture pipeline would be needed first.

### B4. Alt-book capture?

**RESOLVED: Yes, FanDuel as alt-book**

Reasoning:
- FanDuel totals are already captured alongside DraftKings in `line_snapshots_2026.json`.
- No additional API cost.
- Provides cross-book validation without schema complexity (single alt-book, not N books).

### B5. Starter identification approach

**RESOLVED: Use probable starter ID from MLB Stats API schedule, then look up rolling feature by pitcher_id**

Reasoning:
- The schedule API provides `home_probable_pitcher.id` and `away_probable_pitcher.id` pregame.
- The Statcast aggregate parquet has `pitcher_id` as the key column.
- Direct lookup: `parquet[parquet.pitcher_id == starter_id]` → sort by game_date → shift(1).rolling(5, min_periods=3).
- No need to filter the aggregate parquet to "starters only" — we look up by specific pitcher_id, so reliever rows for other pitchers are irrelevant.
- The only concern is whether the lookup pitcher's rows in the aggregate include reliever appearances for that specific pitcher. Since `pitcher_statcast_per_start.parquet` requires ≥30 pitches per appearance, most reliever appearances are excluded. A pitcher who starts most games but occasionally relieves would have those relief appearances included — but `shift(1)` ensures only prior appearances are used, and the rolling average smooths over occasional relief outings.
- This approach matches the V1 pipeline's `_hh_cache` construction exactly.

### B6. Market total source

**RESOLVED: Use existing `line_snapshots_2026.json`**

Reasoning:
- `line_snapshots_2026.json` already contains `total_line`, `over_price`, `under_price`, `book`, and `snapshot_label` for DraftKings and FanDuel at multiple daily snapshots.
- The P09 runner reads the most recent snapshot for each game (preferring CLOSING if available, else 5PM, else OPEN).
- No new API call needed.
- The `game_id` in line_snapshots is the Odds API event ID. The P09 runner matches by `home_team + away_team + game_date`.
- Grading uses `actual_total` from MLB Stats API (same as YRFI grader pattern).

---

## C. Implementation Hard Stops, Restated

For the one PIT item marked NOT VERIFIABLE WITHOUT IMPLEMENTATION (A6):

**Gating check before any runner output:**

The implementation prompt must include a verification function as the first executable step. This function:
1. Loads `pitcher_statcast_per_start.parquet`
2. For each pitcher with `probable_starter` status today, computes `shift(1).rolling(5, min_periods=3).mean()` on `hard_hit_rate`
3. Loads V1's cached values from `daily_signal_generator.py`'s `_hh_cache` (by importing and calling the cache-building code, or by reading a recent signal log entry that recorded `p09_value`)
4. Compares ≥10 overlapping pitchers
5. Passes if all match within 0.001
6. Hard-stops with diagnostic output if any diverge

If this gating check fails, no P09 runner code should be written until the divergence is diagnosed.

---

## D. Resolved-vs-Pending Summary Table

| Item | Status | Decision | Notes |
|---|---|---|---|
| A1. Starter pregame | VERIFIED | — | Schedule API provides starter IDs |
| A2. Prior-starts-only | VERIFIED | — | shift(1) on sorted per-start parquet |
| A3. shift(1) preserved | VERIFIED | — | Pandas standard, no barrier |
| A4. rolling(5,3) preserved | VERIFIED | — | Pandas standard, no barrier |
| A5. No same-game data | VERIFIED | — | Rebuild timing + shift(1) |
| A6. Runtime matches research | NOT VERIFIABLE | Gating check required | Implementation-time test |
| A7. Formula match | VERIFIED | — | 3 sample games matched exactly |
| B1. Host | RESOLVED | VM | Matches YRFI pattern |
| B2. Cadence | RESOLVED | Daily 7:30am ET | Matches YRFI pattern |
| B3. Canonical book | RESOLVED PENDING JEFF | DraftKings | Already captured; Hard Rock not in API |
| B4. Alt-book | RESOLVED | FanDuel as alt | Already captured, no extra cost |
| B5. Starter ID approach | RESOLVED | Schedule API pitcher_id lookup | Matches V1 pattern exactly |
| B6. Market total source | RESOLVED | line_snapshots_2026.json | Already captured, no new pull |

---

## E. Recommendations for Implementation Prompt Structure

**Split into two phases:**

**Phase 1: Verification-first (gating check)**
- Load Statcast parquet
- Compute rolling hard-hit for today's starters
- Compare against V1's `_hh_cache` or recent signal log `p09_value` entries
- Pass/fail gate — if fail, hard-stop with diagnostic

**Phase 2: Runner build (only if Phase 1 passes)**
- Build `mlb/pipeline/p09_shadow_daily.py`
- Read schedule → starters → Statcast rolling → park factor → compute P09 → read line_snapshots → write output → grade prior entries
- Add VM cron entry at 11:30 UTC (7:30am ET)
- Add to dashboard tracker section

**Pre-runner checks that must execute before any file is written:**
1. Statcast parquet exists and is current (max_date ≥ yesterday)
2. Schedule API returns starters for today
3. Gating check (A6) passes
4. line_snapshots_2026.json has entries for today's games
5. Park factors exist for all home teams in today's slate

**Failure mode for each gate:**
- Statcast stale → hard-stop, report
- No starters → hard-stop, report
- A6 divergence → hard-stop, report divergent pitchers
- No line snapshots → proceed but mark all prices null, log warning
- Missing park factor → use 100 (neutral) with note

---

## F. Open Issues for Jeff Before Implementation Prompt

1. **Canonical sportsbook confirmation:** DraftKings is proposed as canonical for P09 shadow tracking because it's already captured in `line_snapshots_2026.json`. Hard Rock is not in any current API pipeline. Confirm DraftKings or specify alternative.

That is the only item requiring Jeff confirmation. All other decisions are resolved with repo evidence.

---

## G. Final Decision: Canonical Sportsbook

**Decision date:** 2026-05-12

**Decision:** DraftKings is the canonical sportsbook for standalone P09 shadow tracking.

**Reason:** DraftKings provides the cleanest and most consistent API/odds-history coverage for full-game MLB totals shadow tracking. DraftKings totals are already captured in `line_snapshots_2026.json` at multiple daily snapshots (OPEN, 2AM, 5PM, CLOSING). No new API pipeline is required.

**Alt-book capture policy:** Allowed and preferred if available without blocking the first implementation. Alt-book capture is forensic only unless later promoted by a separate decision.

**Permitted alt books:**
- Hard Rock
- Pinnacle
- Bovada
- BetOnline
- Bookmaker
- Bet365

**Reporting rules:**
- Canonical ROI and hit-rate reporting uses DraftKings only.
- Alt-book prices are forensic only unless later promoted by separate decision.
- Alt-book capture must not block the first implementation.

**Live betting authorization:** NO

**Promotion authorization:** NO

**Section F resolution:** This decision resolves Section F item 1 ("B3: Canonical sportsbook confirmation"). Jeff confirms DraftKings as canonical.

**Section 12 open questions status:** All Section 12 open questions from the P09 standalone shadow spec v1 are now resolved or explicitly carried into implementation gates. No pending Jeff decisions remain. The implementation prompt may be drafted.
