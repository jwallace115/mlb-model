# Adjudication — ChatGPT Cross-AI Review
**Date:** 2026-08-28 · **Reviewer:** ChatGPT · **Adjudicated by:** Claude (this session)
**Rule applied:** every reviewer claim that is checkable against repo code, repo data,
or a primary source was checked before being accepted or rejected. Nothing below is
accepted on the reviewer's authority.

---

## VERDICT SUMMARY

| # | Reviewer claim | Status | Basis |
|---|---|---|---|
| Core | "Observe a better price" ≠ "capture a better price" | **ACCEPTED** | Unfalsified assumption in both programs |
| Core | HOLD on §5 integration thesis | **ACCEPTED** | Adopted as governance state |
| Q1 | Order-statistic inflation of t-stats | **PARTLY ACCEPTED** | Line t=58.98 vs P&L t=9.19 (measured) |
| Q1 | Stale-outlier enrichment drives the effect | **REJECTED ON TEST** | Effect survives outlier exclusion |
| Q1 | Stale-*book* enrichment contributes | **ACCEPTED, QUANTIFIED** | 2.44% → 1.84% excluding stale books |
| Q1 | Not monetisable in the operator's account set | **ACCEPTED AND SHARPENED** | Top-3 books = 50.9%; Hard Rock absent |
| Q1 | "0.89 ≈ 0.91 pts" is motivated | **ACCEPTED — RETRACTED** | Point value is nonlinear; our own key-number work proves it |
| Q2 | Correlated errors ⇒ IV attenuated, not inflated | **ACCEPTED** | Algebra verified |
| Q2 | λ invalid — stitched Historical Forecast used | **REJECTED ON FACT** | Code uses `previous-runs-api` |
| Q2 | 17:00 UTC is the bigger problem | **ACCEPTED** | Already a known defect; reviewer correctly ranks it first |
| Q2 | "−0.3106 vs −0.3088 to 0.002" is not independent | **ACCEPTED — AND WORSE** | See internal inconsistency below |
| Q3 | Maker fills are adversely selected; ≠ line shopping | **ACCEPTED** | Structural, not empirical |
| Q4 | Blind spot = non-price venue economics | **ACCEPTED, VERIFIED** | LIP/VIP confirmed at primary source |
| Q5 | Buy $59/100K not $119/5M | **ACCEPTED with a cheaper variant** | `bookmakers=` costs 1 region, not 2 |
| Q6 | 91.8 seasons ⇒ football irrational | **REJECTED AS STATED** | Applies to W/L grading only; CLV is ~10× faster |
| Q6 | Demote football to one boxed experiment | **ACCEPTED** | Consistent with the evidence |

---

## 1. THE HEADLINE NUMBER DID NOT REPRODUCE

The +4.31% shopping figure was computed ad hoc in a shell and **never saved as a
script**. That is a Check 3 (research-object identity) failure committed by this
session, in the same week the session was auditing others for it.

Rebuilt as a saved artifact — `nfl/pipeline/shopping_robustness_audit.py`,
output `research/execution_edge/shopping_robustness_2026-08-28.md`:

| Metric | Value |
|---|---|
| P&L per unit, best − E[random book] | **+2.44%**, t=9.19, N=2,648 |
| Line improvement only | +0.365 pts, t=58.98 |

**+4.31% is withdrawn. +2.44% replaces it** (both sides, real prices, expectation
over all books present rather than a single draw).

The reviewer's order-statistic objection is confirmed *for the line metric*
(t=58.98 is nearly content-free) and does not dispose of the P&L metric.

## 2. THE DECISIVE Q1 TEST — FINDING SURVIVES

Reviewer's requested test was sub-minute quote persistence. **That test cannot be
run on any purchasable history**: the archive holds one snapshot per week and the
vendor's finest historical grid is 10 minutes. Substituted two proxies, stated:

Consensus-distance exclusion (stale-outlier proxy):

| Max \|best − median\| | P&L diff | t | N |
|---|---|---|---|
| no limit | +2.44% | 9.19 | 2648 |
| 1.0 pts | +2.44% | 9.53 | 2625 |
| 0.5 pts | +2.21% | 9.21 | 2396 |

**The effect does not collapse.** Stale-outlier enrichment is not the mechanism.

Quote-age exclusion (stale-*book* proxy, via per-book `last_update`): restricting
to books fresher than each game's median gives **+1.84%, t=7.57**. So ~25% of the
effect is staleness-attributable — real, quantified, not fatal.

## 3. MONETISABILITY — REVIEWER RIGHT, AND IT IS WORSE THAN STATED

Concentration of "who holds the best number":

| Book | Share |
|---|---|
| lowvig | 20.7% |
| draftkings | 18.3% |
| fanduel | 11.9% |

Top-3 = **50.9%**, and the single largest is a reduced-juice offshore book.
`hardrockbet_fl` appears in **zero** of the 22 books captured.

Additional defect the reviewer did not have: median snapshot lead time is
**4.5 days before kickoff**. These are early-week lines — maximum dispersion,
minimum limits. The measurement is taken exactly where the money is hardest to get down.

**Conclusion:** cross-book dispersion has economic value (established).
The operator can monetise it (NOT established, and the evidence now points against
the naive version). The surviving usable form is *consensus as fair value against
which to evaluate a single Hard Rock price* — never measured, because `us2` has
never been pulled.

## 4. WIND — ONE REVIEWER ERROR, ONE REVIEWER UNDERSHOOT

**Rejected:** the λ-invalidation. `build_wind_forecast_pit.py` line 51 calls
`https://previous-runs-api.open-meteo.com/v1/forecast` with
`wind_speed_10m_previous_day{1,2,3}` — genuine separate forecast runs, which is
exactly the product the reviewer prescribed. λ=0.77/0.69 stands on vintage grounds.

**Accepted and extended:** the "agreement to 0.002" is worse than non-independent,
it is internally inconsistent. If the two weather sources correlate 0.683 and that
reflects classical measurement error, reliability λ≈0.68, so the OLS-based sum
should be ~68% of the IV — roughly −0.21, not −0.31. Observed sum −0.3106 against
IV −0.3088 implies λ≈1.0, i.e. **no attenuation at all**, which contradicts the
errors-in-variables premise that motivated using IV in the first place.

Either the IV is not doing what was claimed, or 0.683 does not measure the relevant
error. **Both cannot hold.** This is now the top open defect on the wind branch —
found by pushing the reviewer's objection further than the reviewer took it.

**Also accepted:** 17:00 UTC fixed sampling outranks the 0.683 correlation as a
threat, because kickoff slot correlates with geography, month and TV window, so the
exposure error is not classical and the bias sign is unpredictable.

## 5. Q4 — VERIFIED AT PRIMARY SOURCE, HIGHEST-VALUE ITEM

Both claims check out:

- **Liquidity Incentive Program**: open to most regular U.S. members, **no application
  or approval required**, pays **$1–$1,000 per market per day**, scored by resting-order
  size and proximity to reference price on **1-second snapshots** — and **orders do not
  need to fill to earn**.
- **Volume Incentive Program**: max **$0.005/contract**, contracts priced $0.03–$0.97,
  most U.S. members eligible; individual markets may exclude maker- or taker-side volume.

This changes the P&L identity from `fair value − fill price − fee` to include
liquidity rebate, volume rebate, collateral efficiency and cash yield.

**Governance rule adopted:** any strategy whose EV is positive *only* with incentives
is classified as venue-subsidy harvesting, not alpha, and must be labelled as such in
its registry entry. Incentive terms are venue-discretionary and can be withdrawn.

**Structural note:** April's four-AI consultation missed promotional economics; this
review names venue incentives. These are the *same category*. The blind spot is
recurrent, not novel — which means it needs a standing checklist item, not another
one-off patch.

## 6. Q6 — THE ONE PLACE THE REVIEWER IS MATERIALLY WRONG

"91.8 seasons to prove a 53% win rate" is correct **for outcome (W/L) grading only**.
CLV is a continuous estimator and needs ~125 observations against ~1,200 for the same
discrimination — roughly 10× less sample. A wind rule firing 30–60 bets/season
therefore reads out in **2–4 seasons on CLV**, not 92.

The reviewer used the slow estimator to argue football is irrational, then recommended
a boxed prospective football experiment anyway — those two positions are in tension.
The boxed experiment is right; the 91.8 figure is not the reason.

**Grading rule:** the boxed football experiment is graded on CLV. Outcome W/L is
reported but is not the decision metric.

## 7. Q5 SEQUENCING — ACCEPTED, WITH ONE CORRECTION

Order accepted: (1) governance, (2) repair wind at $0, (3) restore capture,
(4) build the sportsbook↔Kalshi translation layer, (5) shadow maker study,
(6) only then tiny prospective capital.

Pricing verified: $30/20K, **$59/100K**, $119/5M, $249/15M. The $59 tier is correct.

**Correction:** the reviewer proposes `us2` for Hard Rock plus `us` for consensus —
two region-equivalents. The `bookmakers=` parameter *overrides* `regions` and bills
one region-equivalent per 10 books, so a single explicit `bookmakers=hardrockbet_fl,...`
list captures Hard Rock **and** the consensus set at **half** the credit cost.
Historical requests remain 10× live.

---

## OPEN DEFECTS CREATED BY THIS ADJUDICATION

1. IV/attenuation inconsistency on wind (§4) — blocks the wind branch.
2. Non-monotone book-count strata (+3.04% / +3.98% / +1.47% / +2.25%) — not the
   order-statistic signature; probably book-composition, unexplained.
3. Early-week (4.5-day) measurement window never characterised against at-close.
4. Hard-Rock-vs-consensus outlier frequency: never measured, `us2` never pulled.
