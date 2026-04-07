# Phase 3 — Subtype A Shadow Validation Report

**Date:** 2026-04-07
**Scope:** Home Strict Opener Subtype A as F5 UNDER pass filter
**Data:** pitcher_game_logs.parquet (2022-2026), game_table.parquet, market_snapshots.parquet, f5_signals_2026.json

---

## Step 0 — Exact Rule Audit

### Subtype A Rule (plain English)

> Flag fires when the **home starting pitcher** has made **0, 1, or 2 prior starts
> this season** AND either (a) this is their season debut (0 prior starts, so no
> prior IP exists) or (b) their average innings pitched per start in prior
> appearances this season is 3.0 or fewer.

Implementation details:
- **Pregame-safe:** YES. Uses only starts before game_date (expanding window, shifted by one game).
- **Leakage:** NONE. Same-game IP is never included in the prior mean.
- **Debut handling:** season_start_number == 0 always triggers the flag. No prior IP data is needed or consulted.

### Flag Counts (2022-2026)

| Season | Subtype A Flags | Total Home Starts | Share  |
|--------|----------------|-------------------|--------|
| 2022   | 224            | 2,430             | 9.2%   |
| 2023   | 236            | 2,430             | 9.7%   |
| 2024   | 222            | 2,427             | 9.1%   |
| 2025   | 228            | 2,428             | 9.4%   |
| 2026   | 14             | ~142 so far       | 9.9%   |

### Composition Within Subtype A (2022-2025, N=910)

| season_start_number | Count | Share  |
|---------------------|-------|--------|
| 0 (debut)           | 736   | 80.9%  |
| 1                   | 123   | 13.5%  |
| 2                   | 51    | 5.6%   |

**Critical finding:** The flag is overwhelmingly debut-driven. The IP <= 3.0 filter on start_number 1-2 adds only 174 games over four seasons.

---

## Step 1 — Historical Pass-Filter Test

### 1A: 2026 F5 UNDER Signals (Live Sample)

| Pool                          | N   | W-L  | Win Rate | Net Units | ROI     | Mean F5 Actual | Mean F5 Line |
|-------------------------------|-----|------|----------|-----------|---------|----------------|--------------|
| ALL F5 UNDER (baseline)       | 48  | 21-26| 43.8%    | -5.18u    | -14.4%  | 5.25           | 4.57         |
| Kept pool (no Subtype A)      | 40  | 18-21| 45.0%    | -3.48u    | -11.6%  | 5.28           | 4.69         |
| Excluded pool (Subtype A)     | 8   | 3-5  | 37.5%    | -1.70u    | -28.4%  | 5.12           | 4.00         |

**All 8 excluded games are Opening Day 2026 (season_start_number = 0).** No post-Opening-Day Subtype A games have appeared in F5 UNDER signals yet.

Subtype A games in 2026 F5 UNDER signals:

| Date       | Game       | Home Starter          | Prior Starts | Result | F5 Actual | F5 Line |
|------------|------------|-----------------------|-------------|--------|-----------|---------|
| 2026-03-26 | DET@SDP    | Nick Pivetta          | 0           | LOSS   | 8.0       | 3.5     |
| 2026-03-26 | TEX@PHI    | Cristopher Sanchez    | 0           | LOSS   | 5.0       | 4.0     |
| 2026-03-26 | PIT@NYM    | Freddy Peralta        | 0           | LOSS   | 13.0      | 3.5     |
| 2026-03-26 | CHW@MIL    | Jacob Misiorowski     | 0           | LOSS   | 9.0       | 4.0     |
| 2026-03-26 | ARI@LAD    | Yoshinobu Yamamoto    | 0           | LOSS   | 6.0       | 4.5     |
| 2026-03-26 | LAA@HOU    | Hunter Brown          | 0           | WIN    | 0.0       | 4.0     |
| 2026-03-26 | BOS@CIN    | Andrew Abbott         | 0           | WIN    | 0.0       | 4.0     |
| 2026-03-26 | MIN@BAL    | Trevor Rogers         | 0           | WIN    | 0.0       | 4.5     |

Direction is consistent: excluded pool underperforms kept pool. But N=8 is far too small for confidence.

### 1B: Historical F5 Actual (All Games, 2022-2025)

| Period    | Pool          | N     | Mean F5 Actual | Delta vs Non-SA |
|-----------|---------------|-------|----------------|-----------------|
| 2022      | Subtype A     | 224   | 4.73           | -0.09           |
| 2022      | Non-SA        | 2,196 | 4.82           | --              |
| 2023      | Subtype A     | 236   | 5.27           | +0.04           |
| 2023      | Non-SA        | 2,191 | 5.23           | --              |
| 2024      | Subtype A     | 221   | 5.24           | +0.32           |
| 2024      | Non-SA        | 2,200 | 4.91           | --              |
| 2025      | Subtype A     | 228   | 5.28           | +0.30           |
| 2025      | Non-SA        | 2,199 | 4.97           | --              |
| 2023-2025 | Subtype A     | 685   | 5.26           | +0.22           |
| 2023-2025 | Non-SA        | 6,590 | 5.04           | --              |

**Statistical test (2022-2025 combined):**
- Welch t-test: t=1.234, p=0.217
- Cohen's d = 0.043 (negligible effect size)
- **Not statistically significant.**

### Effect Decomposition by season_start_number (2024-2025, games with closing lines)

| Start Number | N   | Full-Game Over Rate | F5 Over (proxy) | Mean Residual |
|-------------|-----|---------------------|-----------------|---------------|
| 0 (debut)   | 371 | 54.2%               | 54.4%           | +1.02         |
| 1           | 293 | 46.8%               | 52.2%           | +0.37         |
| 2           | 287 | 43.9%               | 48.4%           | +0.32         |
| Non-SA      | 4,399| 46.5%              | 51.8%           | baseline      |

**The over-rate elevation is ENTIRELY in debut games (sn=0).** Start numbers 1 and 2 are at or below baseline. The Subtype A rule as defined conflates a real debut effect with noise from starts 1-2.

---

## Step 2 — 2026 Live-Sample Check

- 8 F5 UNDER signals with home Subtype A, all Opening Day (2026-03-26)
- Win rate: 37.5% (3/8) vs 45.0% (18/40) in kept pool
- Direction: consistent with historical (Subtype A underperforms for UNDER bets)
- **PRELIMINARY:** N=8, all single-day, all debut. No generalizability yet.

---

## Step 3 — Concentration Check

### Top 10 Teams Producing Subtype A Home Starts (2022-2025)

| Team | Count | Share |
|------|-------|-------|
| TBR  | 50    | 5.5%  |
| LAD  | 48    | 5.3%  |
| CIN  | 43    | 4.7%  |
| MIA  | 41    | 4.5%  |
| OAK  | 36    | 4.0%  |
| CHW  | 36    | 4.0%  |
| SFG  | 35    | 3.8%  |
| DET  | 33    | 3.6%  |
| TEX  | 32    | 3.5%  |
| KCR  | 32    | 3.5%  |

- Top 3 share: 141/910 = 15.5% (well-distributed)
- Removing top 2 (TBR, LAD): F5 mean drops from 5.13 to 5.10 (N=812). Effect survives.

### Temporal Concentration (Debut cases, sn=0)

| Month | Count | Share  |
|-------|-------|--------|
| March | 136   | 18.5%  |
| April | 253   | 34.4%  |
| May   | 85    | 11.5%  |
| June  | 77    | 10.5%  |
| July  | 60    | 8.2%   |
| Aug   | 66    | 9.0%   |
| Sep   | 54    | 7.3%   |

Opening week (March + first week of April): 237/736 = 32.2%.
Mid-season (June-September): 262/736, F5 mean = 5.11.

**Concentration is acceptable.** Flags distribute across the full season via callups and IL returns, not just Opening Day.

### Season Stability

| Season | SA F5 Mean | Non-SA F5 Mean | Delta  |
|--------|-----------|----------------|--------|
| 2022   | 4.73      | 4.82           | -0.09  |
| 2023   | 5.27      | 5.23           | +0.04  |
| 2024   | 5.24      | 4.91           | +0.32  |
| 2025   | 5.28      | 4.97           | +0.30  |

**2022 shows opposite direction. 2023 is flat.** The effect only appears in 2024-2025 for full Subtype A. This is a 2-year pattern, not a structural edge.

---

## Step 4 — Market-Relative Check

### Full-Game Over Rate vs Closing Line (2024-2025)

| Period    | Pool      | N     | Over Rate | Mean Residual | Mean Close |
|-----------|-----------|-------|-----------|---------------|------------|
| 2024      | Subtype A | 221   | 54.8%     | +0.86         | 8.46       |
| 2024      | Non-SA    | 2,200 | 47.4%     | +0.42         | 8.31       |
| 2025      | Subtype A | 228   | 53.5%     | +1.03         | 8.55       |
| 2025      | Non-SA    | 2,199 | 45.6%     | +0.36         | 8.46       |
| 2024-2025 | Subtype A | 449   | 54.1%     | +0.95         | 8.50       |
| 2024-2025 | Non-SA    | 4,399 | 46.5%     | +0.39         | 8.39       |

The market sets Subtype A games only slightly higher (+0.11 runs on the close line), suggesting the market does NOT fully adjust for the debut effect. But:

- The market-relative effect (+0.56 residual excess) only exists in 2024-2025.
- No closing line data for 2022-2023 to confirm persistence.
- F5-specific proxy residual: SA +1.00 vs Non-SA +0.75 (excess = +0.25 runs F5).

### Home vs Away Debut Comparison

| Pool                    | N     | F5 Mean |
|-------------------------|-------|---------|
| Home debut (sn=0)       | 736   | 5.21    |
| Away debut (sn=0)       | 750   | 5.01    |
| All debut (sn=0)        | 1,486 | 5.11    |

Home debuts run hotter than away debuts by +0.20 F5 runs, consistent with the home-side thesis.

---

## Step 5 — Practical Framing

### Option A: Full Pass Filter (suppress F5 UNDER when home Subtype A)

- **Signals affected:** ~8-12 per season (based on 2026 rate of 8/48 scaled to ~250 annual UNDER signals = ~40 per year; heavily front-loaded in Opening Week)
- **2026 impact:** Would have saved -1.70 units (8 signals removed), improving baseline ROI from -14.4% to -11.6%
- **Risk:** Effect is not statistically significant (p=0.217). Driven by debut games only. 2022-2023 shows no effect.
- **Verdict: NOT RECOMMENDED.** Insufficient evidence for full suppression.

### Option B: Caution Badge (show warning, don't suppress)

- Low-cost intervention. Display "HOME DEBUT STARTER" in F5 signal output.
- Does not alter bet decisions; serves as informational flag.
- **Verdict: VIABLE but limited value.** The badge provides context but the human still must decide.

### Option C: Shadow-Only (log and grade through more sample)

- Add subtype_a flag to F5 signal log. Grade through 2026 season.
- After ~150 resolved F5 UNDER signals, test whether Subtype A subset underperforms.
- Requires ~30 Subtype A-flagged F5 UNDER signals for minimal power.
- **Verdict: RECOMMENDED.** This is the right next step.

### Option D: Close

- The Phase 2 claim (+4.8pp, 56.7%, +8.2% ROI in 2023-2025) does not replicate cleanly.
- The effect is real in F5 actuals but small (+0.22 runs F5 in 2023-2025), not statistically significant across all four years, and absent in 2022.
- The Subtype A rule as defined mixes a genuine debut effect with noise from starts 1-2.
- **Verdict: CLOSE the current rule as defined.** If pursued, narrow to debut-only (sn=0).

---

## Decision

### CLOSE — Subtype A as currently defined does not pass validation.

**Reasons:**

1. **Statistical insignificance.** Welch t-test p=0.217, Cohen's d=0.043 across 2022-2025. The F5 mean difference (+0.15 runs over 4 years) is noise-level.

2. **Misattributed effect.** The over-rate elevation lives ENTIRELY in debut games (sn=0, +7.7pp full-game over rate vs baseline). Start numbers 1 and 2 are at or below baseline (46.8% and 43.9% vs 46.5% baseline). The Subtype A rule dilutes the real signal by including non-signal games.

3. **Temporal instability.** 2022 shows opposite direction (-0.09 delta). 2023 is flat (+0.04). Only 2024-2025 show the effect. Two years of data is insufficient to declare a structural edge.

4. **2026 sample is Opening Day only.** All 8 flagged signals are 2026-03-26. No post-Opening-Day validation exists. The result (3-5 UNDER, -28.4% ROI) is directionally supportive but sample is too small and too concentrated.

5. **Phase 2 claim does not replicate.** The +4.8pp F5 over rate and +8.2% ROI from Phase 2 likely used different data or definitions. Our reconstruction shows +2.5pp F5 over rate (proxy) in 2023-2025 with closing lines, and the full 2022-2025 effect is not significant.

### Recommendation for Follow-Up

If this line of research is revisited, the productive path is:

- **Narrow to debut-only (sn=0, home side).** This has the strongest signal (+7.7pp full-game over rate in 2024-2025, +0.22 F5 runs over 4 years).
- **Log as shadow field** in f5_signals_2026.json for passive grading through the 2026 season.
- **Re-evaluate after 50+ debut-flagged F5 UNDER signals** have been graded (likely mid-July 2026).
- Do NOT implement as a live filter until the debut-specific rule passes significance with p < 0.05 on out-of-sample data.
