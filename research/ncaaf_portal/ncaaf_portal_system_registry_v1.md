# NCAAF Portal Overcorrection — System Registry v1

**Created:** 2026-08-28
**Trigger:** Program restart after ~3.5-month pause. Decision taken to freeze the badge
for a clean 2026 Weeks 1-4 out-of-sample test before the season starts.
**Governing rule:** ops v9 §6 Rule 7 — Registry → Review → Decision → Code.
No code is written until Registry and Review are complete.

**Status of this document:** Registry (Step 1) + Review (Step 2) combined.
Written locally. **Commit held, push deliberately withheld** pending CFBD API key
rotation (see §7 SECURITY). Rule 6 durability is therefore INCOMPLETE by design.

---

## 1. NINE-FIELD REGISTRY

| # | Field | Value |
|---|---|---|
| 1 | **System name** | NCAAF Portal Overcorrection Badge — "Bucket B" (NEGATIVE_SHOCK + HIGH_RETURNING), tiered 1/2/3 |
| 2 | **Market** | NCAAF FBS regular-season **game spread, ATS, team-side**. Research scope: Weeks 1-4. Live code scope: Weeks **0**-4 (see Review R1). |
| 3 | **Validation artifact** | `research/ncaaf_portal/phase1_portal_shock_mispricing.md`, `research/ncaaf_portal/phase2_composite_test.md`, script `research/ncaaf_portal/phase2_composite_analysis.py` (596 lines). Scope: CFBD data pulled 2026-04-08, seasons 2022-2025 pooled, 534 team-seasons, 2,430 Weeks 1-4 team-game observations. Headline: Bucket B N=259, 56.4% cover, ATS margin +1.77, p=0.047 (binomial, uncorrected). Economics: **flat -110 synthetic only.** |
| 4 | **Live implementation** | `ncaaf/pipeline/portal_shock_signal.py` (348 lines) |
| 5 | **Live output** | `ncaaf/logs/portal_shock_signal_log.json` — 262 rows. **All rows are 2022-2025 backfill, all `logged_at` 2026-04-08T08:21Z. Zero 2026 rows.** File is **GITIGNORED** by `.gitignore:12` (bare `logs/` rule) → has never reached GitHub. |
| 6 | **Consumer / dashboard** | `dashboard.py::_render_ncaaf_portal_tab()` — **STUB.** Function body renders the literal string "System reset — rebuilding." It reads no file and displays no signal. |
| 7 | **Cron / launchd entry** | **UNKNOWN — no reference to `portal_shock` exists anywhere in the repo** outside the script itself and a stale pre-refactor dashboard copy. Not in any `.sh`, `.plist`, `refresh*.py`, or deploy script. Mac launchd and VM crontab are **not inspectable from this session** (Cowork runs in an isolated VM with only the project folders mounted). Evidence strongly indicates the script has never run on a schedule: one manual invocation on 2026-04-08, nothing since. |
| 8 | **Status** | Research: **OPEN — no out-of-sample evidence exists.** Operational: **NOT RUNNING.** Edge: **UNPROVEN.** Promotion: **NOT APPROACHED.** Capital: **NONE.** |
| 9 | **Out-of-scope siblings** | (a) **NCAAF base spread engine** — `ncaaf/build_base_engine.py`, `ncaaf/models/base_ridge_v1.pkl`, `research/ncaaf_base/*`. Separate object. Do not conflate: its OOS ATS is 49.5-50.0% at every edge threshold (−9.1% to −11.1% ROI at -110) and its OOS MAE 13.23 is **worse** than market MAE 11.87. (b) `ncaaf/data/ncaaf_canonical_2022_2025.parquet`. (c) All NFL objects under `nfl/`. |

### Master-doc claim reconciliation

| Master doc v35-v39 claim | Registry finding |
|---|---|
| "NCAAF — Portal Shock Badge: LIVE (activates August 2026)" | **DRIFT — UNSUPPORTED.** Never scheduled, never ran on a 2026 game, output gitignored, dashboard tab is a stub. "LIVE" is not true in any sense. |
| "NCAAF contamination audit: PENDING" (carried v35→v39) | **CONFIRMED STILL PENDING.** This registry is the first audit work done on it. |

---

## 2. REVIEW — RESEARCH OBJECT vs LIVE OBJECT (Check 3)

Eight identity breaks. The live script is **not** the validated object.

| # | Research object (`phase2_composite_analysis.py`) | Live object (`portal_shock_signal.py`) | Consequence |
|---|---|---|---|
| R1 | Headline computed on `early_no_w0` — Weeks **1-4**, Week 0 explicitly excluded (line 395) | `DEPLOYMENT_WEEKS = {0,1,2,3,4}` — Week 0 **included**, with an inline comment calling it a deployment decision | Live fires on a game class never present in the validated sample |
| R2 | Line selected with an explicit provider preference (`prov` check, line 210) | `for bl in book_lines: ... break` — takes the **first book in the list** that has any spread | Different line source; no book identity recorded |
| R3 | FBS-only via `homeClassification == "fbs"` filter | **No classification filter at all** | Live can log FBS-vs-FCS games that the research excluded |
| R4 | — | `closing_spread` is assigned the **same value** as `spread` | Field name asserts a closing line that was never captured |
| R5 | — | **No price, juice, book, or line timestamp captured anywhere** | Real-price ROI is structurally impossible from this log → Check 4 can never be satisfied |
| R6 | P5 = SEC / Big Ten / Big 12 / ACC / Pac-12, as those existed 2022-2025 | Identical hardcoded set | The 2026 Pac-12 is a **rebuilt non-P5-equivalent conference**. TIER_3 will misclassify its members. |
| R7 | Thresholds derived as pooled quartile/median over 2022-2025 | Frozen constants −29.0 / 0.551 | **This one is correct and desirable** for a forward test — the constants are now fixed and knowable pre-season. Noted as the one clean piece of the port. |
| R8 | Grades post-hoc from completed-season scores | See §3 — cannot grade at all going forward | Fatal for a forward shadow |

### 3. FATAL OPERATIONAL DEFECT — the script cannot run a forward shadow

`main()` dedupes on `(game_id, team)`:

```
existing_keys = {(r["game_id"], r["team"]) for r in existing}
new = [s for s in signals if (s["game_id"], s["team"]) not in existing_keys]
...
combined = existing + all_new
```

A signal logged **before** kickoff is written with `ats_result = None`. On any later run
that same `(game_id, team)` is already in `existing_keys`, so it is filtered out of `new`
and **discarded**. `save_log` writes `existing + all_new` — the stale, ungraded row is
preserved verbatim and never updated.

**Consequence:** every pre-game row stays permanently ungraded. The 262 historical rows
carry results only because they were backfilled *after* those seasons finished, in a
single pass, when scores were already present in the API response.

Running this script as-is for 2026 produces a log of ungraded rows and zero evidence.
This is the same silent-delivery-failure class named in master doc v39 §15 — the pipeline
exits zero and its output reaches nothing.

---

## 4. FIVE MANDATORY RESEARCH CHECKS

| Check | Result | Basis |
|---|---|---|
| **1a — same-day pipeline cleanliness** | **CONDITIONAL PASS** | Live script queries CFBD at run time and uses only endpoints resolvable pre-kickoff. Adequate *if* the classification is snapshotted pre-season (see §5). |
| **1b — historical feature construction** | **FAIL / UNVERIFIED** | `net_star_shock` is built from `/player/portal?year=YYYY` for a **completed** season — i.e. the full year's transfer list. Weeks 1-4 games were then scored against it. If that endpoint includes any transfer recorded after Week 4 (winter window, in-season entries, late resolutions), the research features embed post-game-date information. This is the same end-of-period aggregate contamination class that killed MLB V1. **Not verified either way. Must be treated as contaminated until proven otherwise.** |
| **2 — discovery-validation leakage** | **FAIL** | Bucket B was **selected as the best of six buckets (A-F)** tested on the same pooled 2022-2025 data. It was then further sliced on that same data by spread band, conference tier, favorite/underdog, and week. p=0.047 is uncorrected for that selection; the quoted "favorites 58.8%, p=0.026" is a post-hoc sub-slice. **No held-out OOS window exists anywhere in the research.** |
| **3 — research/live identity** | **FAIL** | Eight breaks, §2. Plus §3 defect. |
| **4 — economic reality** | **FAIL** | Flat -110 synthetic only. Per ops v9 §7, proxy ROI is triage and is never a deployment gate. The live object captures no price at all, so it cannot produce real-price ROI even if it ran. |
| **5 — aggregate hiding** | **PARTIAL** | Season breakdown present: 2022 57.9% (N=107), 2023 54.7% (N=75), **2024 50.0% (N=34)**, 2025 60.5% (N=43). Direction positive in 4/4, but one flat season and heavy N imbalance. G5 subset weak at 51.3% — signal is P5-concentrated. The 7-14 spread band is a 49.2% dead zone with no offered mechanism. No book or month breakdown. |

**Overall: 4 FAIL, 1 PARTIAL, 1 CONDITIONAL PASS. NOT DEPLOYABLE. NO CAPITAL.**

---

## 5. WHAT A CLEAN 2026 FORWARD TEST ACTUALLY REQUIRES

The Check 2 and Check 1b failures kill the **backtest** as evidence. They do **not** kill
the hypothesis, and they do not block a forward test — because a forward test built from a
**pre-season snapshot** is PIT-safe by construction, regardless of how the history was built.

That is the whole opportunity, and it is the reason this is time-critical.

Minimum required before Week 1, in order:

1. **Rotate the exposed CFBD key** (§7). Blocking — nothing gets pushed until this is done.
2. **Fix `.gitignore` for `ncaaf/logs/`** using the ops v9 §16 allow-list pattern. Without
   this the shadow log never reaches GitHub and the test is invisible — the exact YRFI
   failure from master doc v37 §1.
3. **Snapshot and freeze the 2026 classification now.** Pull `/player/portal?year=2026` and
   `/player/returning?year=2026` today, write team → {net_star_shock, returning_ppa,
   negative_shock, high_returning} to a dated, immutable file, and never recompute it.
   This is what makes Check 1b unfalsifiable-in-our-favour: the features provably predate
   every game they will be scored against.
4. **Write a pinned spec** freezing every parameter before any game: thresholds
   (−29.0 / 0.551), **Weeks 1-4 — matching the research, not the live script's 0-4**,
   FBS-only filter, corrected 2026 P5 set, tier definitions, and the line/book rule.
5. **Rewrite the runner** so it (a) logs pre-game with captured spread **and price and book
   and timestamp**, and (b) hands grading to a **separate** grader that updates existing
   rows in place — fixing the §3 dedup defect.
6. **Do not touch any of it once the season starts.** Any mid-season threshold change
   voids the OOS status and this becomes another contaminated object.

---

## 6. HONEST POWER CALCULATION — READ BEFORE SPENDING TIME ON THIS

Bucket B produces roughly **34-107 qualifying team-games per season** in Weeks 1-4
(2022: 107, 2023: 75, 2024: 34, 2025: 43). One season of 2026 data will therefore yield
on the order of **40-60 observations**.

To distinguish a true 56.4% cover rate from the 52.4% break-even at -110, at 80% power
and α=0.05, requires approximately:

    n ≈ (1.96 + 0.84)² × 0.25 / (0.04)² ≈ **1,200 observations**

One season delivers roughly **4% of the sample needed to confirm this signal.**

**What the 2026 test can and cannot do:**

- It **cannot confirm** the signal. Not in 2026, not in 2027. Confirmation needs a decade
  of clean seasons at this sample rate, which is not a realistic path.
- It **can kill** the signal cheaply. A 2026 result near or below 45% would be strong
  evidence the 56.4% was selection artifact, given it was chosen as best-of-six.
- It **can add one clean, uncontaminated season** to a record that currently contains
  zero clean seasons.

That asymmetry is the entire case for doing it: the cost is a few hours of build plus
zero capital, and the realistic payoff is a cheap kill rather than a confirmation.
It should be framed and budgeted as a **falsification test**, not as an edge hunt.

---

## 7. SECURITY — BLOCKING

`research/ncaaf_portal/phase2_composite_analysis.py` line 15 contains a **hardcoded CFBD
API key in plaintext**. The file is tracked, committed, and present on `origin/main`.
`github.com/jwallace115/mlb-model` was verified **public and anonymously readable** on
2026-08-28. The same key string also appears in `PROJECT_STATUS.md`.

**Required:** rotate the key at collegefootballdata.com, remove the literal from both
files, and rely on the existing `CFBD_API_KEY` entry in `.env` (which the live script
already uses correctly). Rotation removes the exposure; the string remains in git history
until history is rewritten.

Secondary: the `origin` remote URL in `.git/config` embeds a GitHub personal access token
in plaintext. Not pushed, so not publicly exposed, but it prints on every `git remote -v`.

**No push to origin until the key is rotated.**

---

## 8. DECISION REQUIRED (Rule 7 Step 3)

Registry and Review are complete. Per Rule 7, Step 4 (Code) cannot begin until the
decision is made against these findings rather than against the master doc's claims.

The decision is not "freeze it" vs "don't" — it is whether §5's six-step build is worth
a few hours given §6's power reality. Both answers are defensible.

---

*End of NCAAF Portal Overcorrection System Registry v1.*
