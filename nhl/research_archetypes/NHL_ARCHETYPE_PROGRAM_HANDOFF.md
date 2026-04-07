NHL ARCHETYPE PROGRAM — FINAL HANDOFF MEMO
Date: 2026-04-06

STATUS: CLOSED

Do NOT reopen NHL team/process archetype research unless a materially new data type or market is introduced.
This branch has been thoroughly tested and is considered complete.

======================================================================
PROGRAM OBJECTIVE
======================================================================

Test whether NHL team/process archetypes — built from non-market process stats
only — could identify totals mispricing beyond what the market and live model
already price.

This was intentionally modeled on the successful WNBA archetype approach:
describe HOW teams play, not HOW MANY goals they score.

The goal was never to build a Vegas-clone totals model.
The goal was to find process/stat structural mismatches that could survive
market-relative testing.

======================================================================
WHAT WAS BUILT AND TESTED
======================================================================

PHASE 0 — DATA AUDIT
Verdict: GO NOW

Result:
- NHL pipeline had strong process-stat coverage from MoneyPuck
- 100% process-stat coverage across 5 seasons
- Enough data existed to build archetype families from:
  - shot volume shape
  - danger mix
  - xG process
  - goalie workload context
  - related process metrics

Conclusion:
The data foundation for archetype research was strong.

----------------------------------------------------------------------
PHASE 1 — DEFENSIVE / OFFENSIVE ARCHETYPE BUILD
Verdict: ADVANCE

Result:
- Built small offensive and defensive archetypes using process stats only
- Found first major structural cell:
  ANEMIC offense × BEND_NOT_BREAK defense
- Raw residual:
  +0.38 goals vs closing line
- Survived basic controls at roughly +0.25
- 4/4 season consistency
- N ~500
- low concentration

Why it was interesting:
- looked structurally real
- not obviously a disguised quality tier
- POROUS allowed fewer goals than BEND_NOT_BREAK in some contexts, suggesting
  the archetypes were about style/volume shape, not generic "bad defense"

This was the strongest early structural finding.

----------------------------------------------------------------------
PHASE 2 — PRACTICAL VALIDATION OF ORIGINAL ANEMIC × BEND_NOT_BREAK
Verdict: ARCHIVE

Critical result:
The effect collapsed in confirmed-starter games.

Key numbers:
- Both starters confirmed:
  ~51.0% over hit rate
  ~+0.7pp market residual
- At least one backup:
  ~53.6% over hit rate
  ~+3.3pp residual

Conclusion:
The original archetype finding was mostly a backup-goalie interaction artifact,
not a clean standalone style-mismatch edge.

Important lesson:
The structural cell was real descriptively, but deployability disappeared when
the backup-goalie effect was removed.

----------------------------------------------------------------------
PHASE 3 — ARCHETYPE EXPANSION QUEUE
Verdict: 4 ADVANCE, 2 NEAR MISS, 2 ARCHIVE

A broader mechanism-first expansion was run across multiple archetype families.
Top advancing branches:

1. Branch 7 — Special Teams Net
- confirmed-starter residual: +0.30
- N = 370
- 4/4 season consistency

2. Branch 6 — Goalie Workload
- confirmed-starter residual: +0.28
- N = 387
- 4/4 seasons

3. Branch 8 — Process Dominance
- confirmed-starter residual: +0.27
- N = 663
- 4/4 seasons
- largest sample

4. Branch 5 — Danger Concentration
- confirmed-starter residual: -0.28
- N = 337
- 3/4 seasons
- UNDER-direction finding

Meaning:
The archetype factory was capable of producing real, stable structural patterns.
This confirmed the archetype framework itself was architecturally sound.

----------------------------------------------------------------------
PHASE 4 — PRACTICAL VALIDATION OF TOP TWO BRANCHES
Verdict: ARCHIVE BOTH

Validated:
- Branch 8 — Process Dominance
- Branch 7 — Special Teams Net

Key result:
The residuals were real structurally but already priced at close.

What Phase 3 suggested:
- starter residuals around +0.27 to +0.30 goals

What Phase 4 showed practically:
- Branch 7: ~49.7% over hit rate, market residual about -0.5pp
- Branch 8: ~51.1% over hit rate, market residual about +1.0pp

Conclusion:
These branches described real game shapes but did not produce deployable
mispricing.

Important lesson:
A +0.27 to +0.30 goals structural residual is not automatically enough if the
closing market already prices the corresponding over probability correctly.

----------------------------------------------------------------------
PHASE 5 — ARCHETYPES AS CONDITIONAL LAYERS ON EXISTING EDGE SIGNAL
Verdict: CLOSE

Question:
Could Branch 7 or Branch 8 still help as confidence layers / threshold
modifiers / pass filters on top of the existing live model?

Result:
Not testable in a meaningful way.
The live NHL model fires edge >= 0.12 on only 24 confirmed-starter games across
4 seasons (~1.3% of games), making conditioning splits too thin for reliable
inference.

Conclusion:
No actionable layering result could be supported from those branches.

Important lesson:
Even structurally interesting context can fail to become useful if the baseline
signal set is too selective.

----------------------------------------------------------------------
PHASE 6 — TARGETED RETEST OF ORIGINAL ANEMIC × BEND_NOT_BREAK AS LAYER
Verdict: CLOSE

Question:
Could the original Phase 1 archetype help as a layer on top of the live model,
even if it failed standalone?

Result:
No. It actually underperformed the "none" bucket.

At usable thresholds:
- edge >= 0.08:
  FAVORABLE = 54.5% (N=11)
  NONE = 60.9% (N=69)
- edge >= 0.06:
  FAVORABLE = 55.6% (N=18)
  NONE = 57.4% (N=122)

Conclusion:
The original archetype is not just neutral as a layer — it is counterproductive.

Most likely explanation:
The live model already captures the shot-volume / xG process information that
the archetype is measuring, so the label adds no independent value.

======================================================================
FINAL PROGRAM CONCLUSION
======================================================================

The NHL archetype framework is:
- descriptively valid
- mechanically interpretable
- season-stable
- better than naive heuristics at describing game environments

But it is NOT:
- a standalone deployable totals signal
- a practical overlay on the live model
- a useful threshold modifier
- a useful pass filter

The market and the live model already capture the process information that these
team/style archetypes measure.

Therefore:
NHL team/process archetype research is CLOSED.

======================================================================
KEY LESSONS
======================================================================

1. NHL totals market is highly efficient at pricing process-stat information.
Compared with MLB/golf/soccer, the closing NHL totals market appears stronger at
absorbing xG, shot volume, and danger-mix information.

2. Structural truth does not imply market edge.
Many archetype findings were real, stable, and non-random — but still already
priced.

3. Backup-goalie contamination was the key false-positive trap.
The original strongest branch looked attractive until confirmed-starter splits
revealed the effect was largely backup-goalie-driven.

4. Archetypes are useful for explanation, not selection, in NHL totals.
They help describe why games look a certain way, but do not add enough
independent information to beat the market or improve the current model.

======================================================================
WHAT REMAINS POTENTIALLY ALIVE
======================================================================

Only two NHL threads still make sense for future work:

1. GOALIE-SPECIFIC STATE CHANGE RESEARCH
- backup vs starter
- goalie workload context
- goalie-specific state transitions
- maybe goalie archetype interactions later

2. CONFIRMED-STARTER THRESHOLD AUDIT
A side observation from Phase 6:
- edge >= 0.08 looked better than edge >= 0.12 in confirmed-starter games

Important:
This is NOT an archetype result.
If tested later, it must be a separate threshold-audit branch with its own
discipline.

======================================================================
DO NOT REOPEN
======================================================================

Do NOT reopen any of the following without materially new data or a new market:
- defensive structure archetypes
- offensive structure archetypes
- process dominance
- special teams net
- danger concentration
- ANEMIC × BEND_NOT_BREAK
- layering archetypes on top of the live model
- threshold tweaks justified by archetype context

This branch is closed.

======================================================================
SHORT VERSION
======================================================================

NHL archetypes worked as a descriptive framework but failed as betting signals
and failed as layers.
The market already prices the process information.
Only goalie-specific state change work remains worth pursuing later.
