# MPS DESCRIPTIVE TAXONOMY V1 — FROZEN SPEC

**Status:** MPS remains RESERVED / DATA-BLOCKED. This taxonomy defines a descriptive
market-path language only. No path states have been tested for predictive value,
no signals have been tested, and no changes to the canonical spec have been made.

---

## 1. Scope

Descriptive classification of MLB totals market movement from open to close.
Input: mps_historical_snapshots_2022_2025.parquet
Coverage: 2022–2025 regular seasons (9,715 game-rows).
Output: a frozen set of primitive dimensions + archetypes for use in future annotation.

---

## 2. Input Table

- Source: `research/recovery/mlb_totals_context_engine_v1/mps_historical_acquisition/mps_historical_snapshots_2022_2025.parquet`
- Total rows: 9715
- Columns: 46
- POST_FIRST_PITCH excluded: 0 (column not present in this snapshot = 0)

**Universe split:**
| Universe | Count | % of Total |
|---|---|---|
| PRIMARY_DESCRIPTIVE | 6240 | 64.2% |
| SECONDARY_CROSS_BOOK | 215 | 2.2% |
| INCOMPLETE | 3260 | 33.6% |

PRIMARY_DESCRIPTIVE criteria:
- `same_book_pair == True`
- `open_selected_line`, `close_selected_line` non-null
- `open_selected_over_price`, `close_selected_over_price` non-null
- `open_selected_under_price`, `close_selected_under_price` non-null
- `close_selected_snapshot_timestamp` < `commence_time_utc` where both available
  (rows failing this check: 2503)

SECONDARY_CROSS_BOOK criteria:
- `pair_quality_flag` contains "CROSS" and not in PRIMARY

INCOMPLETE: all remaining rows.

---

## 3. Primitive Dimensions

All dimensions computed on PRIMARY_DESCRIPTIVE universe only.

### A. NUMBER_MOVE_DIRECTION
Formula: `diff = close_selected_line - open_selected_line`
- OVERWARD: diff > 0
- FLAT:     diff == 0
- UNDERWARD: diff < 0

### B. NUMBER_MOVE_SIZE
Formula: `abs_diff = abs(close_selected_line - open_selected_line)`
- ZERO:     abs_diff == 0
- HALF_RUN: 0 < abs_diff < 1.0
- ONE_PLUS: abs_diff >= 1.0

### C. OVER_JUICE_MOVE_DIRECTION
Sign convention: American odds. More negative = more expensive = more action on that side.
Formula: `diff = close_selected_over_price - open_selected_over_price`
- TOWARD_OVER:  diff < 0  (over became more expensive)
- FLAT:         diff == 0
- TOWARD_UNDER: diff > 0  (over became cheaper)

### D. OVER_JUICE_MOVE_SIZE
Formula: `abs_diff = abs(close_selected_over_price - open_selected_over_price)`
Tertile cut points derived from non-zero over-juice moves in PRIMARY 2022–2025:
- P33 = 6.0
- P67 = 14.0
Bins:
- ZERO:   abs_diff == 0
- SMALL:  0 < abs_diff <= 6.0
- MEDIUM: 6.0 < abs_diff <= 14.0
- LARGE:  abs_diff > 14.0

### E. UNDER_JUICE_MOVE_DIRECTION
Sign convention: American odds. More negative = more expensive on under side.
Formula: `diff = close_selected_under_price - open_selected_under_price`
- TOWARD_UNDER: diff < 0  (under became more expensive)
- FLAT:         diff == 0
- TOWARD_OVER:  diff > 0  (under became cheaper)

### F. UNDER_JUICE_MOVE_SIZE
Formula: `abs_diff = abs(close_selected_under_price - open_selected_under_price)`
Tertile cut points derived from non-zero under-juice moves in PRIMARY 2022–2025:
- P33 = 6.0
- P67 = 14.0
Bins:
- ZERO:   abs_diff == 0
- SMALL:  0 < abs_diff <= 6.0
- MEDIUM: 6.0 < abs_diff <= 14.0
- LARGE:  abs_diff > 14.0

### G. BOOK_QUALITY_CLASS
- SAME_BOOK_FANDUEL:   pair_quality_flag == "SAME_FANDUEL"
- SAME_BOOK_DRAFTKINGS: pair_quality_flag == "SAME_DRAFTKINGS"
- CROSS_BOOK:          "CROSS" in pair_quality_flag
- INCOMPLETE:          all other

### H. CLOSE_RULE_CLASS
Direct passthrough from `close_rule_used` field:
- EVENING_1800ET: close snapshot taken at 18:00 ET day-of
- DAY_TMINUS60:   close snapshot taken T-60 minutes before first pitch

---

## 4. Archetype Definitions

Rule-based, mutually exclusive, exhaustive over PRIMARY universe.
Discriminator: NUMBER_MOVE_DIR first, then OVER_JUICE_DIR for flat-number rows.
Total archetypes: 7 (within 6–10 hard limit).

| Archetype | Rule |
|---|---|
| STATIC | NUMBER_MOVE_DIR==FLAT AND OVER_JUICE_DIR==FLAT |
| JUICE_ONLY_OVER | NUMBER_MOVE_DIR==FLAT AND OVER_JUICE_DIR==TOWARD_OVER |
| JUICE_ONLY_UNDER | NUMBER_MOVE_DIR==FLAT AND OVER_JUICE_DIR==TOWARD_UNDER |
| NUMBER_UP_SMALL | NUMBER_MOVE_DIR==OVERWARD AND NUMBER_MOVE_SIZE==HALF_RUN |
| NUMBER_UP_LARGE | NUMBER_MOVE_DIR==OVERWARD AND NUMBER_MOVE_SIZE==ONE_PLUS |
| NUMBER_DOWN_SMALL | NUMBER_MOVE_DIR==UNDERWARD AND NUMBER_MOVE_SIZE==HALF_RUN |
| NUMBER_DOWN_LARGE | NUMBER_MOVE_DIR==UNDERWARD AND NUMBER_MOVE_SIZE==ONE_PLUS |

Cross-book (SECONDARY_CROSS_BOOK) and incomplete rows receive no archetype label
and are excluded from all frequency tables above.

---

## 5. Coverage Summary

### Overall archetype counts
ARCHETYPE
JUICE_ONLY_UNDER     1487
NUMBER_DOWN_SMALL    1402
JUICE_ONLY_OVER      1361
NUMBER_UP_SMALL       999
STATIC                425
NUMBER_DOWN_LARGE     320
NUMBER_UP_LARGE       246

### Archetype counts by season
ARCHETYPE  JUICE_ONLY_OVER  JUICE_ONLY_UNDER  NUMBER_DOWN_LARGE  NUMBER_DOWN_SMALL  NUMBER_UP_LARGE  NUMBER_UP_SMALL  STATIC
season                                                                                                                      
2022                   263               350                 75                340               74              252      57
2023                   328               319                 56                325               56              288     112
2024                   331               400                 84                376               62              225     119
2025                   439               418                105                361               54              234     137

### Archetype counts by month
ARCHETYPE  JUICE_ONLY_OVER  JUICE_ONLY_UNDER  NUMBER_DOWN_LARGE  NUMBER_DOWN_SMALL  NUMBER_UP_LARGE  NUMBER_UP_SMALL  STATIC
month                                                                                                                       
3                       33                19                  4                 16                1               15      13
4                      225               245                 47                238               44              190      69
5                      244               226                 62                234               47              201      70
6                      189               247                 57                238               43              162      59
7                      213               237                 44                185               40              144      80
8                      246               250                 58                239               38              163      63
9                      207               254                 42                239               29              118      69
10                       4                 9                  6                 13                4                6       2

### Archetype counts by close_rule_used
ARCHETYPE        JUICE_ONLY_OVER  JUICE_ONLY_UNDER  NUMBER_DOWN_LARGE  NUMBER_DOWN_SMALL  NUMBER_UP_LARGE  NUMBER_UP_SMALL  STATIC
close_rule_used                                                                                                                   
DAY_TMINUS60                 642               683                241                694              197              456     214
EVENING_1800ET               719               804                 79                708               49              543     211

### Archetype counts by book_quality_class
ARCHETYPE             JUICE_ONLY_OVER  JUICE_ONLY_UNDER  NUMBER_DOWN_LARGE  NUMBER_DOWN_SMALL  NUMBER_UP_LARGE  NUMBER_UP_SMALL  STATIC
BOOK_QUALITY_CLASS                                                                                                                     
SAME_BOOK_DRAFTKINGS                0                 0                  1                  0                0                0       0
SAME_BOOK_FANDUEL                1361              1487                319               1402              246              999     425

---

## 6. Sanity Notes

- Juice-size cut points derived from full 2022–2025 PRIMARY distribution.
- Any future taxonomy version MUST re-derive cut points from the same window
  (or document explicitly that it uses a different derivation window).
- Stability flags raised: 0
  (none)

---

## 7. Identity Lock

This spec is frozen as MPS_DESCRIPTIVE_TAXONOMY_V1.
Any change to:
- Primitive dimension formulas
- Sign conventions
- Juice-size cut points
- Archetype definitions or count
- Universe selection criteria
...requires creating Taxonomy V2. There is no in-place amendment.

---

## 8. Status Statement

MPS remains RESERVED / DATA-BLOCKED. This taxonomy defines a descriptive
market-path language only. No path states have been tested for predictive value,
no signals have been tested, and no changes to the canonical spec have been made.
