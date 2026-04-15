# MLB UMPIRE RATINGS 2026 REPAIR REPORT

**Date:** 2026-04-15  
**Scope:** Frozen 2026 rebuild of `modules/umpires.py` UMPIRE_RATINGS table  
**Authorized by:** Narrow repair protocol — PIT-safety mandatory  

---

## 1. PROBLEM STATEMENT

The pre-repair `modules/umpires.py` contained 62 static umpire entries, but only 50 of those matched umpire names actually appearing in `sim/data/game_table.parquet`. Coverage was 45.0% of the 111 unique umpires in the game table and 50.8% at the game level. This meant the umpire factor was silently neutral (1.000) for 55% of all games — creating systematic bias in any projection that used umpire-adjusted run totals.

Two specific bugs were confirmed:

- **Lance Barrett bug**: Lance Barrett appears 122 times in game_table (2022-2025) with a +1.9% run-environment tendency, but was **completely absent** from UMPIRE_RATINGS. The old last-name-only fallback would have incorrectly matched him to Ted Barrett (0.975 runs_factor), compounding the error.
- **Alfonso Márquez unicode bug**: game_table stores the name as `Alfonso Márquez` (accented). The old table used the ASCII key `Alfonso Marquez`. The last-name-only fallback happened to catch this correctly, but the exact-match path was failing silently.

Additionally, the old table contained entries for umpires whose names differ from the MLB Stats API format (e.g., pre-2022 active umpires now retired), contributing to the coverage gap.

---

## 2. METHODOLOGY

### Data source
- **Input:** `sim/data/game_table.parquet` — 9,902 games (2022-2026)
- **Scope for ratings:** 2022-2025 completed games only; 2026 data excluded
- **Total qualifying games:** 9,715 (2022: 2430, 2023: 2430, 2024: 2427, 2025: 2428)

### League average
```
league_avg_total = 8.870 runs/game (across 9,715 completed 2022-2025 games)
```

### Eligibility threshold
- **Minimum 30 games** required for a non-neutral rating
- 92 umpires met threshold; 19 did not (neutral 1.000 assigned)

### runs_factor calculation
```
runs_factor = ump_avg_total / league_avg_total
```
Clamped to `[0.900, 1.100]`. Ten umpires hit bounds:
- **Floor (0.900):** Austin Jones (raw 0.8549), Brennan Miller (0.8715), Cory Blaser (0.8878), Alex MacKay (0.8909), Phil Cuzzi (0.8982), John Bacon (0.8989), Jacob Metz (0.8992)
- **Ceiling (1.100):** Dan Bellino (raw 1.1056), Jeff Nelson (1.1153), Mark Wegner (1.1206)

### k_tendency
Not rebuildable from game_table alone (no K% data). Set to `0.000` for all entries.

### sigma_mult
Not rebuildable without per-game standard deviation from a game-level simulation. Set to `1.00` for all entries.

### Unicode normalization fix
The new `get_umpire_rating()` applies NFKD decomposition to strip combining accents before lookup. A module-level `_NORM_LOOKUP` dict maps normalized names to canonical keys. The last-name-only fallback has been **removed entirely** to prevent cross-family collisions.

---

## 3. COVERAGE RESULTS

| Metric | Before | After |
|--------|--------|-------|
| Rated umpires in UMPIRE_RATINGS | 62 | 92 |
| GT umpires matched (45.0% → 82.9%) | 50/111 | 92/111 |
| Game-level coverage | 5,027/9,902 (50.8%) | 9,626/9,902 (97.2%) |
| Neutral fallback games | ~4,875 | 276 |

**By season (umpire-level coverage):**

| Season | Before | After |
|--------|--------|-------|
| 2022 | 49/96 (51.0%) | 84/96 (87.5%) |
| 2023 | 45/94 (47.9%) | 91/94 (96.8%) |
| 2024 | 42/90 (46.7%) | 87/90 (96.7%) |
| 2025 | 41/92 (44.6%) | 84/92 (91.3%) |

**Still neutral (19 umpires, all < 30 games in game_table 2022-2025):**
Bill Welke, David Arrieta, Dexter Kelley, Ed Hickox, Greg Gibson, James Jean, Jen Pawol, Jerry Meals, Jim Reynolds, Jonathan Parra, Jose Navas, Lew Williams, Marty Foster, Randy Rosenberg, Steven Jaschinski, Ted Barrett, Tom Hallion, Tyler Jones, Willie Traynor

---

## 4. BUG FIXES

### Lance Barrett (FIXED)
- **Before:** Not present in UMPIRE_RATINGS; last-name fallback would match Ted Barrett (rf=0.975)
- **After:** `"Lance Barrett": {"runs_factor": 1.0193, ...}` — 122 games, avg 9.041/gm
- **Impact:** Every Lance Barrett game was receiving a -2.5% runs_factor error. Over 122 games this represents a persistent mismatch between projected and actual run environments.

### Alfonso Márquez unicode (FIXED)
- **Before:** Table key was `Alfonso Marquez` (ASCII); game_table uses `Alfonso Márquez` (accented). Old last-name fallback caught it but exact-match failed.
- **After:** Table key is `Alfonso Márquez` (canonical accented). `_NORM_LOOKUP` normalizes both to `Alfonso Marquez`, so both the accented and ASCII spellings resolve correctly.
- **Impact:** Match is now deterministic and does not depend on fallback chain.

### Last-name-only fallback (REMOVED)
- **Before:** `get_umpire_rating()` would fall back to last-name matching, causing Lance Barrett → Ted Barrett cross-collision.
- **After:** Lookup chain is exact match → NFKD normalized match → neutral. No last-name fallback.

---

## 5. FILES MODIFIED

| File | Action |
|------|--------|
| `modules/umpires.py` | Full replacement — 92-entry UMPIRE_RATINGS, new `get_umpire_rating()` with unicode normalization |
| `modules/umpires.py.bak_2026` | Backup of pre-repair file (on VM only) |

---

## 6. PIT-SAFETY AUDIT

- **No 2026 game data used in ratings computation.** Only 2022-2025 `actual_total` values.
- **No model weights or projection logic changed.** Only the static lookup table and matching function.
- **Backward-compatible function signature.** `get_umpire_rating(name)` returns same dict schema.
- **k_tendency and sigma_mult preserved as neutral.** No fabricated values.
- **No commits or pushes performed.**
- **No files created outside authorized paths.**

---

## 7. KEY RATINGS (range extremes)

| Umpire | runs_factor | Games | Avg Total | Status |
|--------|-------------|-------|-----------|--------|
| Austin Jones | 0.9000 | 36 | 7.583 | Floor clamped (raw 0.8549) |
| Brennan Miller | 0.9000 | 104 | 7.731 | Floor clamped (raw 0.8715) |
| Phil Cuzzi | 0.9000 | 121 | 7.967 | Floor clamped (raw 0.8982) |
| Ryan Blakney | 0.9162 | 118 | 8.127 | |
| Mark Wegner | 1.1000 | 100 | 9.940 | Ceiling clamped (raw 1.1206) |
| Jeff Nelson | 1.1000 | 56 | 9.893 | Ceiling clamped (raw 1.1153) |
| Dan Bellino | 1.1000 | 124 | 9.806 | Ceiling clamped (raw 1.1056) |
| Andy Fletcher | 1.0892 | 121 | 9.661 | |
| Lance Barrett | 1.0193 | 122 | 9.041 | Previously missing |
| Alfonso Márquez | 1.0700 | 118 | 9.492 | Unicode fixed |
