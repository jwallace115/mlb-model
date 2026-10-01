# Kill ledger v0 — every negative verdict, audited as hard as the positives (2026-10-01, 00:45Z)

**Why this exists.** Jeff, 2026-10-01: "we also do look to prove things that didn't work... so of course only positive
things get checked again and found to be negative."

The project audits positives until they die, but never re-checks a negative. That is asymmetric scrutiny. An error that
kills a real edge is never looked for, so it is never found. From now on a negative verdict gets the same treatment as
a positive one:
- it can be regenerated from committed code;
- it has been reproduced independently;
- it has a power and positive-control check;
- the object tested is provably the object that was killed.

**How v0 was built.** A read-only sweep of `main` @ `022368d8a` (docs only: about 940 .md, .txt and .json files) found
61 negative verdicts across MLB, Kalshi/execution, NFL, NHL, NBA, WNBA, golf, soccer and NCAAF. Each was recorded with:
- where the verdict is written;
- its headline numbers and odds basis;
- whether a generator is named;
- any recorded independent reproduction;
- warning signs.

The sweep's full table is the working inventory. It is itself unverified: Cowork has spot-checked only the items marked
**[checked]** below.

## Headline facts from the inventory

- **No negative verdict has an independent numeric reproduction**, with one exception: NFL K4 (sim vs book), which Cowork
  recomputed several times. Kalshi was "accepted" by ChatGPT without a recompute.
- **Only 4 negative verdicts name a committed generator:**
  - NFL K4 (`nfl/sim/run_k4.py`);
  - line shopping (`nfl/pipeline/shopping_robustness_audit.py`);
  - WNBA anchor (`wnba_anchor*/pipeline/`);
  - NHL edge-hunt scripts.
- **Several MLB kill artifacts are missing from the repo.** Their verdicts exist as single lines in
  `research/SESSION_LOG.txt`: phase2a, lineup, bullpen-leverage, F5 pass 01, autonomous engine v1, sim engine v1.
- **The golf structural-sim closure has no artifact in the repo.**

## Kills that are wrong as written (transcription or identity errors)

| # | Verdict | Problem | Status |
|---|---|---|---|
| K1 | MLB Clean Kill #3, S12 overlay (`research/recovery/mlb_totals_reset_audit/PHASE7_CLEAN_KILLS.md:31`) | The kill quotes "Active=50.9%, inactive=52.8% (COLLAPSES)". Those are **P09's** numbers (`v2_overlay_revalidation/p09_overlay_report.md:42-43,50`). S12's own overlay report has active > inactive (OOS COMBINED 56.0%, +9.9% flat); its source verdicts say DIMINISHED, not dead. | **[checked] — confirmed.** The kill is unsupported as written. |
| K2 | MLB Clean Kill #7, F5 run line away (`PHASE7_CLEAN_KILLS.md:64-69`) | The kill defines the signal as "xFIP gap <= -1.0" and cites "2025 ROI=-3.5%". The source (`research/f5_runline/f5_runline_research_report.md:32,41`) shows **B_away (xFIP gap<=-1.0): N=316, +18.4% pooled, 2025 +15.2%, permutation 98%**. The −3.5% belongs to **A_away** (CSW gap). | **[checked] — confirmed.** Caveat: that research used season-final xFIP (lookahead). B_away's positive is contaminated too, so its true status is **UNTESTED on point-in-time data**, not dead. |
| K3 | P09 kill | The kill tested cutoff 35.0674. The deployed object and the shadow spec use 31.7305, whose OOS was positive (N=60, +10.5% flat). A different object was killed. | Unchecked |
| K4 | ST02 road-trip fatigue | The kill says "market prices travel fatigue correctly. No residual edge". The source says "Signal is unpriced" (lift +1.83pp, p=0.031, permutation 99.5th pct). It missed the 53% gate by 0.79pp, on synthetic −110, with 2022-23 lines from a different source at 78-82% coverage. | Unchecked |
| K5 | ADJ family VALIDATED_NEGATIVE_DEAD | Two same-day backtests of the same locked definition disagree. One: real closing, −0.6% to −3.6%. The other: about 30% larger N, best price, all five OOS-positive. The memo said MONITOR; the registry escalated to DEAD. ADJ_BB_RATE was killed on N=16. | Unchecked |
| K6 | MLB Over-scanner, team totals (E3) | The team-totals "clean" kill rests on numbers its own document calls contaminated. | Unchecked |

## Kills on thin evidence, or that contradict their own positive measurements

- **Golf finishing markets.** Killed on ROI although out-of-sample CLV was **+5.0% to +15.2% at every threshold**. The
  CLV definition is not stated.
- **MLB moneyline Phase 1-3.** Buckets with positive OOS were killed by the validation stage: +9.50% (N=254), +7.31%
  (N=402), +13.70% (N=162). The gate is strict by design, but the validation N of 84-235 has never had a power check.
- **NHL L-001, PREREG_CLV, S42-S44.** Computed on the goalie-swapped engine. Log-loss was re-run after the fix; the CLV
  test was not.
- **NBA threes-under props (P5).** OOS N=4,912, hit 56.7%. ROI_A is +8.2% and ROI_B is −4.7%; the pricing conventions
  are undefined.
- **NBA schedule-fatigue domain.** Closed after 7 simple proxies. FA01H missed its gate by 0.6 percentile points. The
  holdout was never opened.
- **WNBA System C/D.** Killed on N=93 holdouts. v1 trained on 56 rows; the date fix that recovered 449 games came after
  the v1 verdict.
- **SEEP (MLB).** Killed on 52 signals in 12 days, labelled "PRELIMINARY".
- **NHL PREREG_ALT.** 35 bets, CLV +0.90%, point estimate positive.

## Kills that look solid (so far)

- **NFL K4: the sim is worse than the book in all 8 prop families.** It was recomputed independently several times and
  still holds after the one-draw-share bug was fixed (fit_6b/6E). It is in-sample, which flatters the sim, so the
  verdict is conservative.
- **NFL game-line scan** (0 of 2,512 tests pass BH) and **NHL open search** (4,115 cells): large and multiplicity-aware.
  They test outcome rates, not prices.

## Method for every ledger item (to be applied, not yet applied)

1. **Object identity.** The killed object equals the deployed or proposed object: same definition, cutoff, inputs and
   prices.
2. **Regenerate** the verdict's numbers from committed code and data, with one command. If that is impossible, the
   status is UNREPRODUCIBLE, not DEAD.
3. **Positive control.** Plant a synthetic edge of realistic size (for example +3% ROI, or a +2pp hit rate at real
   prices) in the same data and run the exact evaluation pipeline. If the pipeline cannot find the planted edge, the
   verdict is UNTESTED, not DEAD.
4. **Power.** State the smallest edge the sample could detect. A kill whose detectable edge is above any realistic edge
   is INCONCLUSIVE.
5. **Independent re-derivation** by ChatGPT from the public repo for every item that survives steps 1-4 as DEAD, and for
   every item that flips.
6. **Final status:**
   - DEAD (passed 1-5);
   - INCONCLUSIVE (underpowered);
   - UNTESTED (failed the control, or wrong object);
   - REOPEN (the re-derivation finds signal).

   A REOPEN item is a hypothesis for forward testing, never "an edge". The CLAUDE.md rule stands.

**First batch to re-derive (Cowork's ranking):** K2, K1, K3, K4, K5, golf finishing CLV, NHL CLV on the fixed engine,
NBA P5 pricing.

## The same asymmetry inside the NFL forward experiment

The forward scorer (FWD7) will include a positive control. A synthetic reader with a known planted edge must come out
"superior" through the real scoring path, and a reader equal to the book must come out "inconclusive". That way a
"no edge" result from the sim cannot come from a scorer that is unable to see one.
