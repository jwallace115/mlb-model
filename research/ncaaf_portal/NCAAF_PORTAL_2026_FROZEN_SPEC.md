# NCAAF Portal Overcorrection — 2026 FROZEN SPEC

**Frozen:** 2026-08-28, before any 2026 FBS regular-season game in the test window.
**Purpose:** Define, immutably and in advance, the object to be tested against the
2026 Weeks 1-4 out-of-sample window.
**Framing:** This is a **FALSIFICATION TEST**, not an edge deployment. See §6.
**Companion:** `ncaaf_portal_system_registry_v1.md` (registry + review + check results).

> **THIS DOCUMENT IS PINNED. Nothing in §2, §3, or §4 may be changed after the first
> 2026 game in the window has kicked off. Any post-kickoff change to a threshold, a
> week boundary, a filter, or a tier definition VOIDS the out-of-sample status and
> converts this into another contaminated object. If something looks wrong mid-season,
> the correct action is to record the observation and let the season finish.**

---

## 1. WHY A FORWARD TEST IS CLEAN WHEN THE BACKTEST IS NOT

The registry records four failed checks against the 2022-2025 research. Two of them
(Check 2 discovery-validation leakage; Check 1b end-of-period portal aggregation) mean
the 56.4% cover rate **is not trustworthy evidence** and cannot be treated as a prior.

A forward test escapes both, for one reason only: **the classification is snapshotted
and frozen before any game is played.** The features provably predate every outcome they
will be scored against. That property is created by §3 Step 1 and destroyed by any
recomputation. This is why the snapshot must never be regenerated.

---

## 2. FROZEN PARAMETERS

### 2.1 Thresholds

| Parameter | Frozen value | Source |
|---|---|---|
| `NET_STAR_SHOCK_THRESHOLD` | **−29.0** (qualify if `net_star_shock <= -29.0`) | `phase2_composite_test.md`, Metric Definitions table |
| `RETURNING_PPA_THRESHOLD` | **0.551** (qualify if `percentPPA >= 0.551`) | `phase2_composite_test.md`, Metric Definitions table |

> **Documented discrepancy — recorded, not silently resolved.** `phase1_portal_shock_mispricing.md`
> reports the net_star_shock Q25 as **−28.0** over 544 team-seasons. `phase2_composite_test.md`
> reports the Bucket B threshold as **−29.0** over 534 team-seasons. The two research
> documents disagree. **−29.0 is frozen** because it is the value in the artifact that
> produced the 56.4% headline being tested, and it matches the existing live script.
> The −28.0 figure is not used. This note exists so the choice is auditable later.

### 2.2 Metric definitions (identical to research)

- `portal_in_stars` = sum of `stars` over transfers with `destination == team`
- `portal_out_stars` = sum of `stars` over transfers with `origin == team`
- `net_star_shock` = `portal_in_stars − portal_out_stars`
- Missing/null `stars` counts as **0** (research convention, `t.get("stars") or 0`)
- `percentPPA` taken from CFBD `/player/returning` for the same season

### 2.3 Window

**Weeks 1, 2, 3, 4 of the 2026 regular season. Week 0 is EXCLUDED.**

The research headline (`early_no_w0`, `phase2_composite_analysis.py` line 395) filters to
`week >= 1`. The existing live script's `DEPLOYMENT_WEEKS = {0,1,2,3,4}` is identity
break R1 in the registry and is **not carried forward**.

### 2.4 Population filters

- FBS only. A game is in scope only if the qualifying team is FBS-classified for 2026.
  (Research applied `homeClassification == "fbs"`; the old live script applied no filter —
  identity break R3.)
- Regular season only (`seasonType == "regular"`).
- Game must have a spread available at capture time. No spread → not logged, no backfill.

### 2.5 Tiers

| Tier | Definition |
|---|---|
| **TIER_1_BASE** | `negative_shock AND high_returning` — **this is the object under test** |
| TIER_2_STRONG | TIER_1 **AND** team is favored (`team_spread < 0`) |
| TIER_3_PREMIUM | TIER_2 **AND** power conference **AND** `3.0 <= abs(team_spread) <= 14.0` |

**TIER_1 is the headline test.** Tiers 2 and 3 are recorded but are post-hoc sub-slices
from the contaminated research (registry Check 2) and carry no independent evidential
weight in 2026. They are logged for description only.

### 2.6 Power conference set — REQUIRES SIGN-OFF BEFORE WEEK 1

```
POWER_CONFERENCES_2026 = {"SEC", "Big Ten", "Big 12", "ACC"}
```

The research sample (2022-2025) used `{SEC, Big Ten, Big 12, ACC, Pac-12}`, where "Pac-12"
meant the pre-2024 conference. The 2026 Pac-12 is a **rebuilt conference with different
membership** and is not the same population. Including it would misclassify its members
against the research's intent.

**Pac-12 is therefore EXCLUDED from the 2026 power set.** This affects **TIER_3 only** —
it does not touch TIER_1, the object actually under test. Jeff to confirm before Week 1.

### 2.7 Line and price capture

Every logged row captures, at capture time:

- `spread_captured` — team-perspective spread (negative = team favored)
- `line_provider` — the CFBD provider/book string the spread came from
- `line_captured_at_utc` — ISO timestamp of capture
- `spread_open` — CFBD `spreadOpen` where available, else null
- `price_source` — `"CFBD_NO_JUICE"` when CFBD supplies no spread vig

**Known limitation (registry Check 4):** CFBD `/lines` does not reliably expose the vig on
the spread. Grading therefore reports **both** a flat −110 economic column (explicitly
labelled triage-only per ops v9 §7) **and** the raw cover/no-cover record. Real-price ROI
is NOT satisfied by this build. Adding an Odds API spread-price pull (~56 credits across
Weeks 1-4) would close it and is recommended as a follow-on, not a blocker.

---

## 3. BUILD SEQUENCE — ORDER IS LOAD-BEARING

| Step | Action | Owner | Blocking? |
|---|---|---|---|
| 1 | **Rotate the exposed CFBD key**, paste new key into `.env`, strip the literal from `phase2_composite_analysis.py` and `PROJECT_STATUS.md` | Jeff | **YES — nothing pushes until done.** `.env` currently holds the SAME key that is public. |
| 2 | Patch `.gitignore` to allow-list `ncaaf/logs/` per ops v9 §16 | script provided | YES — without it the shadow log never reaches GitHub (v37 YRFI failure) |
| 3 | **Run the snapshot** `portal_2026_freeze_snapshot.py` — writes the immutable 2026 classification | Jeff, on the Mac | **YES — must complete before the first Week 1 kickoff** |
| 4 | Commit + push snapshot, spec, registry, scripts | after step 1 | — |
| 5 | Schedule `portal_2026_shadow_daily.py` and `portal_2026_grading_utils.py` for Weeks 1-4 | Jeff | no |
| 6 | **Touch nothing until the window closes** | — | — |

Step 3 is the one with a hard external deadline. Steps 4-5 can slip; step 3 cannot.

---

## 4. ARTIFACTS

| Artifact | Path | Mutability |
|---|---|---|
| Frozen classification | `ncaaf/data/portal_2026_classification_frozen.json` | **WRITE ONCE.** Script refuses to overwrite. |
| Shadow log | `ncaaf/logs/portal_2026_shadow.json` | Append pre-game; grader updates rows in place |
| Frozen spec | `research/ncaaf_portal/NCAAF_PORTAL_2026_FROZEN_SPEC.md` | This file. Pinned. |
| Registry | `research/ncaaf_portal/ncaaf_portal_system_registry_v1.md` | Pinned |
| Snapshot script | `ncaaf/pipeline/portal_2026_freeze_snapshot.py` | — |
| Shadow runner | `ncaaf/pipeline/portal_2026_shadow_daily.py` | — |
| Grader | `ncaaf/pipeline/portal_2026_grading_utils.py` | — |

`ncaaf/pipeline/portal_shock_signal.py` and `ncaaf/logs/portal_shock_signal_log.json` are
**left untouched** as the historical record. They are not part of this test.

---

## 5. THE DEFECT THIS BUILD FIXES

The existing runner dedupes on `(game_id, team)` and writes `existing + all_new`, so a row
logged pre-game with `ats_result = None` is filtered out of `new` on every later run and
never updated. It cannot grade a forward shadow at all (registry §3).

This build separates the two concerns: the **runner only appends** pre-game rows and never
grades; the **grader only updates** existing rows in place and never appends. The grader
skips any row already marked `graded: true`, so it is idempotent.

---

## 6. WHAT THIS TEST CAN AND CANNOT PROVE

Bucket B yields roughly 34-107 qualifying team-games per season (2022: 107, 2023: 75,
2024: 34, 2025: 43). **2026 will produce roughly 40-60 observations.**

Separating a true 56.4% cover rate from the 52.4% break-even at α=0.05 and 80% power needs
approximately:

    n ≈ (1.96 + 0.84)² × 0.25 / 0.04² ≈ 1,200 observations

**One season delivers about 4% of the sample required to confirm.**

Therefore:

- **CANNOT CONFIRM.** No 2026 result authorises promotion, sizing, or capital. There is no
  number this test can return that means "the signal is real." Confirmation is not
  reachable on any realistic horizon at this sample rate.
- **CAN FALSIFY CHEAPLY.** A 2026 TIER_1 cover rate at or below ~45% is meaningful evidence
  that 56.4% was a best-of-six selection artifact. That is the outcome worth paying for.
- **CAN ADD ONE CLEAN SEASON** to a record that currently contains zero clean seasons.

### Pre-registered interpretation (fixed now, so it cannot be rationalised later)

| 2026 TIER_1 result | Reading |
|---|---|
| ≤ 45% | Signal falsified. Archive the branch. |
| 45-52.4% | Consistent with no edge. Archive unless a later season is run. |
| 52.4-58% | Uninformative at this N. **Not** confirmation. One clean season banked. |
| > 58% | Encouraging, still uninformative at this N. Still no capital. |

**No cell in that table authorises a bet.** Writing this down before the season is the
point — it removes the option of reinterpreting a lucky 60% as validation in December.

---

*End of NCAAF Portal Overcorrection 2026 Frozen Spec.*
