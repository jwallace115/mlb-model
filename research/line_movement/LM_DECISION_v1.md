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
