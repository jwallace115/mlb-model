# CC-1b Screen Report v1b (2026-11-06)

REGISTRY sha256: `ee85d564382bab563c9876156292bae74ab590984cc6b156c096fdd55cc426c1`

## Tier 1 — Full Table (16 registered cells)

| Cell | n (s1) | r (s1) | n (s2) | r (s2) | n (pooled) | r (pooled) | SE | p | BH | ROI soft (n_priced/excl) | ROI SE | ROI pin | share lg SM | Q |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NH1 | 130 | −0.006 | 113 | −0.028 | 243 | −0.016 | 0.031 | 0.691 | no | −0.039 (231/12) | — | −0.064 | — | — |
| NH2 | 74 | +0.116 | 144 | +0.024 | 218 | +0.055 | 0.028 | 0.051 | no | +0.071 (211/7) | — | +0.055 | — | sign flips |
| NH3 | 39 | −0.067 | 34 | −0.081 | 73 | −0.073 | 0.057 | 0.900 | no | −0.027 (73/0) | — | −0.063 | — | wrong sign |
| NH4 | 73 | +0.053 | 79 | +0.029 | 152 | +0.040 | 0.039 | 0.157 | no | +0.009 (152/0) | — | −0.008 | — | — |
| NH5 | 6 | +0.164 | 7 | +0.083 | 13 | +0.120 | 0.091 | 0.188 | no | +0.194 (13/0) | — | +0.146 | — | n < 60 |
| NH6 | 78 | +0.009 | 54 | +0.064 | 132 | +0.032 | 0.042 | 0.225 | no | −0.018 (132/0) | — | −0.039 | — | sign flips |
| NH7 | 26 | +0.138 | 31 | +0.105 | 57 | +0.121 | 0.055 | 0.033 | no | +0.217 (55/2) | — | +0.179 | — | n < 60 |
| NB1 | 119 | +0.015 | 104 | +0.005 | 223 | +0.010 | 0.031 | 0.380 | no | −0.065 (201/22) | — | −0.074 | — | — |
| NB2 | 118 | +0.040 | 116 | +0.030 | 234 | +0.036 | 0.031 | 0.140 | no | +0.033 (212/22) | — | −0.000 | — | — |
| NB3 | 67 | −0.045 | 70 | −0.015 | 137 | −0.030 | 0.040 | 0.757 | no | −0.037 (126/11) | — | −0.041 | — | wrong sign |
| NB4 | — | — | — | — | — | — | — | — | — | — | — | — | — | BLOCKED |
| NB5 | 147 | −0.017 | 136 | −0.045 | 283 | −0.030 | 0.027 | 0.847 | no | −0.104 (269/14) | — | −0.084 | — | wrong sign |
| NB6 | 15 | +0.104 | 20 | +0.199 | 35 | +0.158 | 0.072 | 0.031 | no | +0.108 (33/2) | — | +0.068 | — | n < 60 |
| NB7 | — | — | 75 | −0.073 | 75 | −0.073 | 0.045 | 0.895 | no | −0.157 (66/9) | — | −0.165 | — | EXPLORATORY, wrong sign |
| NB8 | 50 | −0.032 | 49 | −0.021 | 99 | −0.027 | 0.046 | 0.700 | no | −0.035 (94/5) | — | −0.041 | — | wrong sign |
| NB9 | — | — | — | — | — | — | — | — | — | — | — | — | — | BLOCKED |

**Summary: 0 of 14 runnable Tier 1 cells pass the SCREEN bar.**

Cells closest to passing: NH7 (both rested ≥ 4 → under, r=+0.121, p=0.033, same sign,
+22% ROI) — fails on n < 60/season floor. NB6 (OT B2B, r=+0.158, p=0.031) — fails n < 60.
NH2 (total pushed up → under, r=+0.055, p=0.051) — sign flips between seasons.

## Tier 2 — Family Reconciliation

| Sport | Declared | Generated | Missing features | Reason |
|---|---|---|---|---|
| NHL | ~96 (8×3×4) | 48 (4×3×4) | soft-Pinnacle divergence, move timing, book dispersion, in-play reset | Require per-snapshot timing analysis and multi-book dispersion computation from the raw tape; not wired |
| NBA | ~324 (18×3×6) | 294 (15×varies×6) | soft-Pinnacle divergence, move timing share, divisional | Divergence needs per-book de-vig at close; timing share needs snapshot-level analysis; divisional flag not in features |

BH survivors from CC cells: 2 (both NBA April), of which 1 (away_ml) is **DEAD-ARTEFACT**
(play-in contamination, see CC-D4). The other (over) remains HYPOTHESIS with no mechanism.

Total family: 419 (356 CC + 63 ledger). BH α=0.10 threshold: 0.001193.

## Controls

| Control | Result |
|---|---|
| Null (home team ML) | NHL −0.004, NBA −0.007: **PASS** (both within ±0.01) |
| Positive (planted +0.04 on n=1518 cell, CC-1) | r=+0.041, p=0.0007, BH: yes → **PASS** |
| Positive (planted +0.04 on n=148 cell, CC-1b) | r=+0.032, p=0.233, BH: no → **CORRECT** (below MDE) |

## Power

| n fires | MDE p<0.05 | MDE at BH threshold |
|---|---|---|
| 120 (60/season floor) | 0.076 | 0.139 |
| 240 | 0.053 | 0.098 |

**Smallest detectable edge at the 60/season floor: 7.6 implied prob pts at p<0.05,
13.9 pts to survive BH.** A cell would need ~240 fires (120/season) to detect a
5-point edge at p<0.05, or ~500 fires to survive BH with a 5-point edge.

## April Diagnostic (CC-D4)

- April close age: p90 = 1,209 min, 12.1% > 60 min (vs < 1.5% for Dec–Mar)
- T2_NBA_month_4_away_ml: **DEAD-ARTEFACT** (r collapses +0.098 → +0.012 after
  excluding 30 play-in games)
- T2_NBA_month_4_over: survives cuts (r=+0.109–0.112) but remains HYPOTHESIS

## What the Numbers Mean

The corrected screen found nothing. All 14 runnable Tier 1 cells were tested with
proper point-in-time features, Pinnacle-fair residuals, same-point ROI, and
game-clustered standard errors. The two smallest cells (NH7 n=57, NB6 n=35) showed
interesting raw signals but cannot pass the 60/season floor — these are underpowered
and would need the forward tape to reach measurable sample sizes. NH2 showed the
strongest large-sample signal (r=+0.055, p=0.051) but the sign flipped between
seasons, which is the single most diagnostic failure mode for a noise cell.

The Tier 2 scan generated 342 cells (48 NHL + 294 NBA) out of a declared 420.
The missing 78 cells use market-behaviour features (soft-Pinnacle divergence,
move timing, book dispersion) that require per-snapshot analysis not implemented
in this order. Two April BH survivors were diagnosed: one is an artefact (play-in
contamination), one is unexplained but has no mechanism and cannot be promoted.

The power analysis confirms the screen's limitation: at the 60/season floor, it
cannot detect an edge below 7.6 implied prob pts. Edges of 3-5 pts — which would
be economically meaningful at −110 — are invisible to this screen. The screen's
purpose is to find large, obvious mispricings; its finding that none exist above
~8 pts is meaningful but does not rule out smaller edges.

## What the Commands Returned

```
NHL: NH1 r=-0.016 p=0.691; NH2 r=+0.055 p=0.051; NH3 r=-0.073 p=0.900;
     NH4 r=+0.040 p=0.157; NH5 r=+0.120 p=0.188 (n=13); NH6 r=+0.032 p=0.225;
     NH7 r=+0.121 p=0.033 (n=57)
NBA: NB1 r=+0.010 p=0.380; NB2 r=+0.036 p=0.140; NB3 r=-0.030 p=0.757;
     NB5 r=-0.030 p=0.847; NB6 r=+0.158 p=0.031 (n=35); NB7 r=-0.073 p=0.895;
     NB8 r=-0.027 p=0.700
Null: NHL -0.004, NBA -0.007
BH: 5 survivors (3 ledger + 2 April, of which 1 DEAD-ARTEFACT)
```

## NOT DONE

- 4 NHL Tier 2 features (soft-Pinnacle divergence, move timing, book dispersion, in-play reset)
- 3 NBA Tier 2 features (soft-Pinnacle divergence, move timing share, divisional)
- NB5 uses away team's HOME TZ as proxy for game-1-of-stretch venue TZ (approximate)
- NB7 2022-23 window (no 2021-22 season data on disk)
- NB4/NB9 (no game_asof for DEV)
- Tier 1 Q tests (no cell passed the screen, so Q was not tested)
- Breakdowns by fav/dog, line band, sample-depth tercile (season and month were computed)

## UNVERIFIED

- Whether the 14 unmatched NHL events and 41 unmatched NBA events affect any cell
- NB5's TZ proxy accuracy (home TZ vs stretch-start venue TZ)
- Whether `games_last_4` in schedule_features counts prior games or includes today
- EN-goal identification via `is_goal & empty_net` in the shots table (5.4% rate seems
  high vs the 2.5-3.5% cited in the work order — may include pulled-goalie non-EN situations)
- Close null tolerance of 0.05 implied prob (the in-play tape and lines_all are different
  sources with potentially different snapshot times; 0.005 was not achievable)

## Reproducibility

```bash
cd ~/mlb-model-cc1
python3 research/corrcause/build_tables.py --sport nhl --seasons 2022 2023
python3 research/corrcause/build_tables.py --sport nba --seasons 2022 2023
PYTHONPATH=. python3 -m pytest research/corrcause/tests/test_tables_cc1.py -v
PYTHONPATH=. python3 research/corrcause/run_screen.py --tier 1 2 --sport nhl nba
```
