# Phase 10 — Quick Multi-Tag Context Sweep

**Date:** 2026-04-06
**Scope:** 2024-2025, 4,361 games with first-inning actuals
**Design:** Descriptive splits + chi-square, no modeling

---

## Data Sources

| Source | File | Coverage |
|--------|------|----------|
| First-inning actuals | `research/yrfi/data/yrfi_actuals.parquet` | 4,361 games |
| Lineups | `mlb/data/lineups.parquet` | 2022-2025 |
| Pitcher game logs | `mlb/data/pitcher_game_logs.parquet` | 2022-2025 |
| Team game index | `mlb/data/team_game_index.parquet` | 2022-2025 |
| Catcher IDs | `research/statcast_enrichment/catcher_framing.parquet` | 228 catchers |
| Umpire data | `sim/data/game_table.parquet` | `umpire_over_rate` |
| YRFI odds | `research/yrfi/data/yrfi_lines_historical.parquet` | 4,399 games |

All tags use the prior TEAM game (any opponent) as the reference, not prior
series game. This gives ~57% coverage (needs both sides' prior-game lineup
data) for lineup-based tags and 100% for umpire.

---

## TAG 1: Top-3 Lineup Stability

**Definition:** Count of top-3 batting order hitters changed vs each team's
prior game. Combined across both sides: 0 total changes = "both_same",
1-2 = "1-2 changed", 3+ = "3+ changed".

**Coverage:** 2,470/4,361 (56.6%)

| State | N | Top1% | Bot1% | YRFI% | NRFI% |
|-------|---|-------|-------|-------|-------|
| both_same | 312 | 0.234 | 0.231 | **0.385** | **0.615** |
| 1-2_changed | 1,437 | 0.274 | 0.292 | 0.480 | 0.520 |
| 3+_changed | 721 | 0.291 | 0.338 | **0.533** | 0.467 |
| ALL | 2,470 | 0.274 | 0.298 | 0.483 | 0.517 |

**Spread: 14.8pp** (both_same 38.5% vs 3+_changed 53.3%)

**Chi-square: chi2=19.239, p=0.0001 — SIGNIFICANT**

By year:
- 2024: both_same=0.367(N=147), 3+_changed=0.532(N=378) — 16.5pp spread
- 2025: both_same=0.400(N=165), 3+_changed=0.534(N=343) — 13.4pp spread

**Stable year-over-year.** Direction and magnitude consistent.

Side-level detail:
- Home 0 changes → bot1_scored=0.278 (vs 0.306 base, −2.8pp)
- Away 0 changes → top1_scored=0.262 (vs 0.274 base, −1.2pp)
- Home 3 changes → bot1_scored=0.433 (vs 0.298 base, **+13.5pp**)
- Away 3 changes → top1_scored=0.310 (vs 0.274 base, +3.6pp)

The "3 changes" side-level bump is dramatic on bot1 (home batting) but N=104.

Team concentration (both_same pool): HHI=0.052, well-distributed across 30
teams. Top teams: NYM(43), SEA(42), ATL(42), PHI(39). **Not a team-quality
proxy.** The "3+ changed" pool is also well-distributed.

### Market Check

| State | N | Act YRFI | Imp YRFI | Residual |
|-------|---|----------|----------|----------|
| both_same | 299 | 0.385 | 0.517 | **−0.132** |
| 1-2_changed | 1,373 | 0.480 | 0.519 | −0.039 |
| 3+_changed | 693 | 0.535 | 0.519 | **+0.016** |

**The market does NOT price lineup stability at all** — implied YRFI is ~52%
in every bucket. The "both_same" bucket has a −13.2pp residual (actual 38.5%
vs implied 51.7%). This is the largest market blind spot in this sweep.

**Caveat:** The −13.2pp residual is from a pool of N=299 where the expected
noise at p=0.50 is ±5.7pp (2σ). So 13.2pp is ~2.3σ — meaningful but still
within the range where N=299 could produce false positives. The year-over-year
stability (16.5pp → 13.4pp, same direction) is the stronger evidence.

### Verdict: PROMISING MICRO FILTER (C)

---

## TAG 2: Leadoff Continuity

**Definition:** Same leadoff hitter as each team's prior game, or changed.
Combined: both_same, one_changed, both_changed.

**Coverage:** 2,470/4,361 (56.6%)

| State | N | YRFI% | NRFI% |
|-------|---|-------|-------|
| both_same | 1,118 | 0.470 | 0.530 |
| one_changed | 1,057 | 0.489 | 0.511 |
| both_changed | 295 | 0.512 | 0.488 |

**Chi-square: chi2=1.843, p=0.3980 — NOT significant**

Spread is 4.2pp with no significance. The leadoff-specific signal (if any) is
already subsumed by the top-3 stability tag.

### Verdict: NO SIGNAL (A)

---

## TAG 3: Same Starter + Different Catcher

**Definition:** For each side, compare the catcher in this game to the catcher
from the same starting pitcher's most recent start. Combined: any side has a
different catcher ("any_diff_catcher") vs both sides have the same catcher as
their SP's prior start ("both_same_catcher").

**Coverage:** 3,499/4,361 (80.2%) — better than lineup tags because it uses
catcher-framing player IDs cross-referenced with lineups.

| State | N | YRFI% | NRFI% |
|-------|---|-------|-------|
| both_same_catcher | 672 | 0.457 | 0.543 |
| any_diff_catcher | 710 | 0.489 | 0.511 |
| same_both (one-sided data) | 1,476 | 0.505 | 0.495 |
| diff_catcher (one-sided data) | 641 | 0.463 | 0.537 |

**Chi-square: chi2=5.840, p=0.1196 — NOT significant**

The states are messy (one-sided fallbacks inflate the count). Even cleaning to
two-sided data only (N=1,382): both_same=45.7% vs any_diff=48.9%. Only 3.2pp
spread. Direction is plausible (new catcher = less pitch-framing coordination
= more runs) but effect is tiny and not significant.

### Verdict: NO SIGNAL (A)

---

## TAG 4: Bullpen / Low-History Starter

**Definition (pregame-safe):**
- **low_history**: starter has ≤5 career starts entering this game
- **recent_short_outing**: starter averaged <4.0 IP in their last 3 starts
  entering this game (proxy for bullpen/opener tendencies)
- **both_normal**: neither side qualifies

**Note:** An earlier version used actual IP pitched (<3 IP) which is post-game
leakage. The results below use only pregame-safe information.

**Coverage:** 2,470/4,361 (56.6%)

| State | N | Top1% | Bot1% | YRFI% | NRFI% |
|-------|---|-------|-------|-------|-------|
| both_normal | 1,743 | 0.268 | 0.290 | 0.473 | 0.527 |
| any_low_history | 422 | 0.296 | 0.296 | 0.488 | 0.512 |
| any_recent_short | 305 | 0.279 | 0.341 | **0.534** | 0.466 |
| ALL | 2,470 | 0.274 | 0.298 | 0.483 | 0.517 |

**Chi-square: chi2=3.927, p=0.1404 — NOT significant**

By year:
- 2024: both_normal=0.477, any_recent_short=0.500 (2.3pp)
- 2025: both_normal=0.470, any_recent_short=0.572 (10.2pp)

Direction is consistent but magnitude is unstable (2.3pp → 10.2pp).

Side-level detail:
- Home bats vs away SP with recent_short_outing: bot1_scored=**0.375** (vs 0.295 base, **+8.0pp**)
- This is the strongest single cell — the home lineup facing a historically short-outing away starter scores 37.5% of the time in the first inning

### Verdict: WEAK CONTEXT TAG (B)

The recent-short-outing tag shows a real mechanism (short-start pitchers
struggle early, are usually low-quality arms), but the pregame-safe version
does not reach significance and the year-over-year instability is concerning.
Worth noting as context, not worth building features for.

---

## TAG 5: Recent Familiarity (21-day lookback)

**Definition:** Either batting team faced the opposing starter within the last
21 days ("any_recent") vs no recent meeting ("no_recent_either").

**Coverage:** 2,470/4,361 (56.6%)

| State | N | YRFI% | NRFI% |
|-------|---|-------|-------|
| any_recent | 179 | 0.520 | 0.480 |
| no_recent_either | 2,291 | 0.481 | 0.519 |

**Chi-square: chi2=0.860, p=0.3537 — NOT significant**

Only 3.9pp spread. N=179 for "any_recent" is small. The familiarity hypothesis
(hitters who recently saw this pitcher adjust) is not supported by first-inning
data. This makes sense: first-inning at-bats are the pitcher's freshest,
regardless of whether the lineup has "familiarity."

Side-level confirms: no meaningful difference on either side.

### Verdict: NO SIGNAL (A)

---

## TAG 6: Umpire Zone Regime

**Definition:** Using `umpire_over_rate` from `sim/data/game_table.parquet`.
Tiers: tight (<0.98), neutral (0.98-1.02), loose (>1.02).

**Coverage:** 4,361/4,361 (100%)

### Broad Tiers

| State | N | YRFI% | NRFI% |
|-------|---|-------|-------|
| tight | 750 | 0.467 | 0.533 |
| neutral | 3,008 | 0.488 | 0.512 |
| loose | 603 | 0.496 | 0.504 |

**Chi-square: chi2=1.188, p=0.5522 — NOT significant**

Spread is only 2.9pp across broad tiers. Most umpires cluster at 1.000
(N=2,208), so the broad tiers are diluted by neutrals.

### Extreme Umpires Only

| State | N | YRFI% |
|-------|---|-------|
| Very tight (≤0.96) | 140 | **0.436** |
| Neutral (0.99-1.01) | 2,518 | 0.486 |
| Very loose (≥1.04) | 105 | **0.552** |

**Spread: 11.7pp** (tight 43.6% vs loose 55.2%)

Finer-grained monotonic pattern:
| Bucket | N | YRFI% |
|--------|---|-------|
| <0.97 | 250 | 0.448 |
| 0.97-0.99 | 714 | 0.478 |
| 0.99-1.01 | 2,518 | 0.486 |
| 1.01-1.03 | 617 | 0.496 |
| >1.03 | 262 | 0.504 |

The pattern is **monotonic** — YRFI rate increases consistently as the umpire
gets looser. This is exactly what you'd expect: a wider zone suppresses walks
and extends counts, while a narrow zone gives more baserunners early.

By year (extreme umpires only):
- 2024: tight=0.451(N=82), loose=0.500(N=50) — 4.9pp spread
- 2025: tight=0.414(N=58), loose=0.600(N=55) — 18.6pp spread

**Direction consistent, magnitude unstable.** The 2025 spread is dramatic but
N is tiny. The 2024 spread is small.

### Market Check

| State | N | Act YRFI | Imp YRFI | Residual |
|-------|---|----------|----------|----------|
| Very tight (≤0.96) | 132 | 0.447 | 0.517 | **−0.070** |
| Neutral (0.99-1.01) | 2,411 | 0.487 | 0.519 | −0.032 |
| Very loose (≥1.04) | 102 | 0.559 | 0.520 | **+0.039** |

**The market does not price umpire extremes into YRFI lines.** Implied
probability is flat (~52%) regardless of umpire assignment. The tight-umpire
residual of −7.0pp and loose-umpire residual of +3.9pp are real but the N is
small (132 and 102).

### Verdict: WEAK CONTEXT TAG (B)

The umpire extreme signal is directionally correct, monotonic, and shows a
market blind spot. But N is too small at the extremes (140/105) to trust the
magnitude. The broad tier test fails significance. Worth carrying as a context
note (e.g., "tight umpire assigned — lean NRFI") but not worth building a
feature for at this sample size.

---

## Summary Table

| Tag | Spread | p-value | Year stable? | Market residual | Verdict |
|-----|--------|---------|-------------|----------------|---------|
| 1. Top-3 Stability | **14.8pp** | **0.0001** | **Yes** | **−13.2pp** (both_same) | **C: PROMISING** |
| 2. Leadoff Continuity | 4.2pp | 0.40 | — | — | A: NO SIGNAL |
| 3. SP + Catcher | 3.2pp | 0.12 | — | — | A: NO SIGNAL |
| 4. Bullpen/Low-History | 6.1pp | 0.14 | Partial | — | B: WEAK TAG |
| 5. Recent Familiarity | 3.9pp | 0.35 | — | — | A: NO SIGNAL |
| 6. Umpire Extreme | 11.7pp | 0.55 (broad) | Partial | −7.0/+3.9pp | B: WEAK TAG |

---

## Final Ranked List

### Most Worth a Deeper Test

**1. Top-3 Lineup Stability (Tag 1)**
- 14.8pp YRFI spread, p=0.0001, stable both years
- "Both teams kept same top 3" → 38.5% YRFI (vs 48.5% base) = **10pp suppression**
- Market charges 51.7% implied on these games — massive blind spot
- Team-distributed (HHI=0.052), not a team-quality proxy
- Key limitation: 56.6% coverage (needs prior-game lineup for both sides)
- **Next step:** Test as a filter on the Phase 4 NRFI parlay helper. If the
  "both_same" pool intersects with the B10+D pool, it could sharpen the parlay
  selector. Also test whether the effect persists in 2022-2023 data (lineups
  exist back to 2022).

### Likely Just Context Notes

**2. Umpire Extreme (Tag 6)**
- Monotonic pattern, correct mechanism, market blind spot
- But broad test fails significance; N at extremes is ~100-140
- Worth noting on the daily card: "tight umpire → lean NRFI slightly"
- Not worth building a feature until 2+ more seasons of data confirm magnitude

**3. Recent Short-Outing SP (Tag 4)**
- Bot1 scoring rate = 37.5% when home faces away SP with recent short history
  (vs 29.5% base)
- But p=0.14 and year-over-year magnitude swings from 2pp to 10pp
- Worth noting if a known opener/bullpen-day arm is starting

### Likely Dead

- **Leadoff Continuity (Tag 2):** subsumed by top-3 stability
- **SP + Catcher (Tag 3):** no signal, messy definition
- **Recent Familiarity (Tag 5):** familiarity doesn't help in inning 1
