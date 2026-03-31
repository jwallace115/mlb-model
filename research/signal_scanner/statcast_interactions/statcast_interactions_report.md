# Statcast Interaction Family Scanner — Report

Dataset: 4855 games (2024-2025), 4666 non-push

## Summary Table

| Family | Signal | G1 Stable | G2 Robust | G3 WF | G4 Perm | G5 Mkt | G6 V1 | Verdict |
|--------|--------|-----------|-----------|-------|---------|--------|-------|---------|
| F1a: extension standalone | combined_extension_r5 | PASS | FAIL | N/A | N/A | N/A | N/A | **SHELVE** |
| F1b: extension × CSW | F1_extension_x_csw | PASS | PASS | FAIL | N/A | N/A | N/A | **SHELVE** |
| F2: (1-HH) × GB_proxy | F2_suppression | PASS | FAIL | N/A | N/A | N/A | N/A | **SHELVE** |
| F3: spin_loss × contact (UNDER tail check) | F3_spinloss_x_contact | FAIL | N/A | N/A | N/A | N/A | N/A | **SHELVE** |
| F4: OAA × contact suppression | N/A | N/A | N/A | N/A | N/A | N/A | N/A | **SHELVE** |
| F5: pitch tempo × CSW | N/A | N/A | N/A | N/A | N/A | N/A | N/A | **SHELVE** |

## F1a: extension standalone

- Direction: UNDER
- N: 3767
- Gate 1 (stability): PASS — 2024=0.04483, 2025=0.00290
- Gate 2 (robustness): FAIL — p=0.8724
- Gate 3: None
- **Verdict: SHELVE**

## F1b: extension × CSW

- Direction: UNDER
- N: 3767
- Gate 1 (stability): PASS — 2024=0.01272, 2025=0.01130
- Gate 2 (robustness): PASS — p=0.0738
- Gate 3 (walk-forward): FAIL — 2024=-3.153988868274581, 2025=8.600979858464886
- **Verdict: SHELVE**

## F2: (1-HH) × GB_proxy

- Direction: UNDER
- N: 3768
- Gate 1 (stability): PASS — 2024=0.00071, 2025=0.00060
- Gate 2 (robustness): FAIL — p=0.3801
- Gate 3: None
- **Verdict: SHELVE**

## F3: spin_loss × contact (UNDER tail check)

- Direction: UNDER
- N: 2995
- Gate 1 (stability): FAIL — 2024=-0.00366, 2025=-0.00293
- Gate 2: None
- Gate 3: None
- **Verdict: SHELVE**

## F4: OAA × contact suppression

**SHELVE**: INSUFFICIENT_DATA — team OAA not available locally

## F5: pitch tempo × CSW

**SHELVE**: INSUFFICIENT_DATA — pitch tempo not available locally

## Conclusion

**No signals passed sufficient gates for SHADOW or INVESTIGATE.**
All five families SHELVED. The existing S12/P09 overlays appear to capture
the available Statcast interaction signal space adequately.

Shelved: 6 families

