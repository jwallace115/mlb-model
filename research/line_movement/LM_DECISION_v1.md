# Line-Movement Decision Log v1

### LM-D1 — Registry and ledger freeze (2026-10-11)

**Action:** Committed LM_REGISTRY_v1.md and claude_prediction_ledger.md verbatim
from `~/mlb-model/_cowork_patches/lm1/`, after `shasum -a 256 -c SHA256SUMS` passed.

**SHA256 (verified):**
- LM_REGISTRY_v1.md: `edc972c6373b9c1d5c643320aa53c3b32e7eefcb7825d83b03543c169080e7a1`
- claude_prediction_ledger.md: `ac17f8db82457327ec4de11c6704eec5c213c07f8bc24e627f1acc157625fc3e`

**Data window:** Snapshots 2026-09-06T11:17:06Z through 2026-10-11T05:30:06Z
(NFL 1,390 snapshots, NCAAF 1,381 snapshots).

**Two-look rule:** INTERIM grade in LM-1 (today). FINAL grade after the NFL
regular season ends (early January 2027). No cell is added, dropped, split,
or re-thresholded between the freeze and the final look. The registry text is
committed and its sha256 recorded before any result is read.

### LM-D2 — Interim grade (2026-10-11)

**Action:** Graded all six cells × two sports from the frozen registry, using
`build_lm_tape.py` and `grade_lm_cells.py`. Results in `LM_INTERIM_2026-10-11.md`
and `tape/lm_cell_bets_2026.parquet`.

**Key findings:**
1. **C5 (Hard Rock shade)** is the only cell with consistent positive CLV in both
   sports: +0.91 pp (NFL, t=2.97) and +1.01 pp (NCAAF, t=3.95). Both exceed the
   registry's t ≥ 2.5 bar but both have N = 40 (below the 100 minimum for PASS).
   NFL ATS is 65.0% (26-14).
2. **C2 (Hard Rock lag)** raw CLV is negative, but this is a measurement artifact:
   C2 fires when points differ, and de-vigged probability CLV across different
   points compares different bets. Same-point C2 instances are weakly positive.
   NFL ATS is 62.6% (57-34). Not a data bug.
3. **C1 and C3** are directionally positive but not significant.
4. **C4 and C6** have too few or zero fires for evaluation.
5. **NCAAF ATS is entirely missing:** CFBD file covers only through week 4, but
   all 112 HR NCAAF events are from weeks 5+. Zero overlap.
6. **HR NCAAF coverage** is 31.8% (112/352), not the 86% cited in the registry
   (that figure likely referred to HR timing, not event coverage).

**Ambiguity readings (stricter):** C2's cross-point CLV was reported as NOT
interpretable rather than treating negative CLV as a verdict. C5's N = 40 is
reported as INSUFFICIENT N rather than PASS, despite exceeding the t-bar.
