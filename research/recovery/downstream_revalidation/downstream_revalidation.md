# Downstream Revalidation

## V1-Dependent Objects

| Object | Path | Depends on V1? | Status |
|--------|------|---------------|--------|
| S12 overlay | mlb_sim/pipeline/st02_overlay.py | NO — independent pipeline | CLEAN |
| P09 overlay | mlb/segment_overlay.py | NO — independent pipeline | CLEAN |
| F5 engine | research/f5/ | Directory exists | REVIEW |
| F5 RL threshold | research/f5_runline/ | Directory exists | REVIEW |
| Combined short exit shadow | mlb_sim/pipeline/combined_short_exit_shadow.py | NO — independent pipeline | CLEAN |
| KP04 shadow | mlb_sim/pipeline/kp04_shadow.py | NO — independent pipeline | CLEAN |
| CS004 shadow | mlb_sim/pipeline/cs004_shadow.py | NO — independent pipeline | CLEAN |

## Assessment

The clean V1 model produces point-in-time features that eliminate lookahead bias.
Any downstream object that consumes V1 predictions or features must be re-evaluated
with the clean feature table.

### Key Finding
If the clean V1 model shows degraded OOS ROI compared to contaminated V1,
this confirms the contaminated model's apparent edge was partially or fully
driven by lookahead. Downstream objects inheriting those predictions would
be equally contaminated (ORPHANED).

### Recommendation
1. Replace V1 model artifacts with clean rebuild
2. Re-run all dependent pipelines with clean inputs
3. Objects that were profitable only with contaminated inputs should be marked ORPHANED
