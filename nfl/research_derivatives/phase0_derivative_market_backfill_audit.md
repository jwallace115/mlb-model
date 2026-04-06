# NFL Derivative Market Backfill Audit

**Date:** 2026-04-06
**Season:** 2025 NFL (Sep 2025 – Feb 2026)

---

## What Was Pulled

Historical Q1 and H1 odds for all 284 available 2025 NFL season games from
The Odds API `/historical/sports/americanfootball_nfl/events/{id}/odds` endpoint.

**Markets pulled:**
- `totals_q1`, `spreads_q1`, `h2h_q1`
- `totals_h1`, `spreads_h1`, `h2h_h1`

**Total derivative rows:** 15,407
**API credits used:** ~600 (from 4.99M balance)

## What Was Built

### Derivative Canonical Table
**Path:** `nfl/data/nfl_derivative_canonical_2025.parquet`
**Rows:** 284 (one per game)
**Columns:** 36

**Close selection method:** For each game + market, take the latest snapshot per
bookmaker, then use the median line across books as the "close." This matches
the existing repo convention for MLB/NHL closing lines.

### Actuals
Derived from `nflreadpy.load_pbp([2025])` — play-by-play running score at end
of Q1 and Q2. 100% coverage (285 games in PBP, 284 matched to odds events).

---

## Coverage Tables

### Market Coverage

| Market | Games | % of 284 | Avg Books | Notes |
|--------|-------|----------|-----------|-------|
| **h1_h2h** | **266** | **94%** | 2.5 | Best coverage |
| h1_spread | 236 | 83% | 1.8 | Strong |
| **h1_total** | **221** | **78%** | 1.7 | Primary research target |
| q1_h2h | 253 | 89% | 1.8 | Good |
| q1_spread | 190 | 67% | 1.4 | Moderate |
| q1_total | 177 | 62% | 1.4 | Moderate |

### Actuals Coverage

| Field | Games | % |
|-------|-------|---|
| total_points_q1 | 284 | 100% |
| total_points_h1 | 284 | 100% |
| home/away points Q1 | 284 | 100% |
| home/away points H1 | 284 | 100% |

### Score Distributions

| Market | Mean Close | Median | Min | Max |
|--------|-----------|--------|-----|-----|
| Q1 total | 8.2 | 7.5 | 6.5 | 10.5 |
| H1 total | 23.1 | 23.0 | 16.5 | 31.5 |

---

## Data Quality Issues

1. **Snapshot depth is thin:** Average 1.4-2.5 books per game per market. The
   historical endpoint returns a single snapshot (the close), not intraday
   multi-snapshot history. No opener/close comparison possible without forward
   collection in 2026.

2. **Q1 totals coverage (62%)** is the weakest market. Some books don't offer
   Q1 totals for all games. Research using Q1 totals should expect ~60% of
   games to have usable closing lines.

3. **1 game missing from odds archive** (285 in PBP vs 284 in odds). Likely a
   very early or very late-season game that expired from the historical endpoint.

4. **No team name mapping issues** after fuzzy ±1 day date matching (UTC
   commence_time vs US game date offset for night games).

---

## GO / PARTIAL GO / BLOCKED

### Verdict: PARTIAL GO

**H1 totals:** GO NOW — 221 games (78%) with closing lines, 100% actuals. This
is the strongest derivative market and should be the first research target.

**H1 spreads:** GO NOW — 236 games (83%). Can support H1 spread research
alongside totals.

**Q1 totals:** CONDITIONAL — 177 games (62%). Usable for exploratory analysis
but sample may be tight for robust archetype testing. Better suited as a
secondary branch after H1 results are known.

**Q1 spreads:** CONDITIONAL — same as Q1 totals, moderate coverage.

**H2H markets:** GO for descriptive analysis (89-94% coverage) but less useful
for totals/scoring research.

### Recommended First Market: H1 TOTALS

Why:
1. Best totals coverage (221 games, 78%)
2. H1 total line (mean 23.1) provides enough range for meaningful over/under analysis
3. Directly supports the project brief's "opening-script archetype" hypothesis
4. H1 scoring captures both Q1 and Q2, giving the model more outcome variance to work with
5. nflverse PBP provides 100% actuals for residual analysis

### Recommended Build Order

1. **H1 totals residual analysis** — does the market misprice first-half scoring
   for specific team/matchup archetypes?
2. **Q1 totals** — if H1 shows promise, drill into Q1 to test whether opening
   script effects are concentrated in Q1 specifically
3. **H1/Q1 spreads** — side-level analysis if totals branch produces usable
   structural archetypes
4. **Forward collection** — add `totals_q1,spreads_q1,h2h_q1,totals_h1,spreads_h1,h2h_h1`
   to the 2026 NFL season odds collection config before September

---

## Files Created

| File | Purpose |
|------|---------|
| `nfl/data/nfl_derivative_canonical_2025.parquet` | Derivative canonical (284 games, 36 cols) |
| `nfl/research_derivatives/pull_derivative_odds.py` | Backfill script (resumable, cached) |
| `nfl/research_derivatives/cache/` | 738 cached API responses |
| `nfl/research_derivatives/phase0_derivative_market_backfill_audit.md` | This report |

No existing files were modified.
