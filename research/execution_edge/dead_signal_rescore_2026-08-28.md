# Dead-Signal Re-Score Against the Kalshi Maker Hurdle
**Run:** 2026-08-28 15:47 UTC · **API calls:** 0

> **This is triage, not a finding.** It identifies which shelved signals died
> against a bar that no longer applies. It resurrects nothing. Every row still
> needs its provenance re-verified before anyone acts on it.

Break-even win rate at -110: **52.38%**  
Break-even win rate as a Kalshi maker: **50.35%**  
Difference: **2.04 percentage points**

That gap is the entire subject of this document.

## Tier 1 — market listed AND hurdle measured there

MLB full-game totals. Hurdle = 0.347c/contract, measured on 186,205 fills.

| Signal | N | Win rate | ROI @ -110 | Kalshi maker ROI | Flips? |
|---|---|---|---|---|---|
| ST02 Road-Trip Fatigue | 2,172 | 52.21% | -0.3% | **+3.73%** | **YES** |
| adj_k_rate_last3 | 1,539 | 52.14% | -0.64% | **+3.59%** | **YES** |
| ADJ_RUN_SUPP | 3,159 | 51.51% | -1.82% | **+2.33%** | **YES** |
| ADJ_CONTACT | 3,875 | 51.23% | -2.37% | **+1.77%** | **YES** |
| ADJ_HH | 3,081 | 51.09% | -2.58% | **+1.49%** | **YES** |
| ADJ_BB_RATE | 1,587 | 50.56% | -3.62% | **+0.43%** | **YES** |

Every Tier 1 row flips positive. Before that reads as good news, note that the
largest, ADJ_RUN_SUPP at +2.33%, is a **2.3% ROI on a coin-flip-ish 51.5% signal**
— it survives only because the cost of transacting collapsed, not because the
signal got better. These are thin edges that need everything else to go right.

**Provenance flags on Tier 1:**

- *ST02 Road-Trip Fatigue* — Clean economics kill. 'Market prices travel fatigue correctly.'
- *adj_k_rate_last3* — ADJ family carries an IDENTITY defect - live dropped the p_under>0.57 co-filter.
- *ADJ_RUN_SUPP* — Same ADJ identity defect.
- *ADJ_CONTACT* — Same ADJ identity defect.
- *ADJ_HH* — Same ADJ identity defect.
- *ADJ_BB_RATE* — Also 50.0% on 16 resolved 2026 shadow - closer to noise.

Five of the six are ADJ-family and share one identity defect: the deployed
object dropped a co-filter the research required. Re-scoring the research
object does not make the live object valid. Any revival is a rebuild.

## Tier 2 — market listed, hurdle NOT measured there

Median spreads measured on 1.63M quotes from the same capture. A wider spread
means more capture for a maker but also thinner books and probably more
toxicity — direction unknown, so no ROI is computed.

| Signal | Market | Kalshi series | Median spread | Win rate | Old result |
|---|---|---|---|---|---|
| F5/FG Path Mismatch (F3) | MLB F5 totals UNDER | `KXMLBF5TOTAL` | 3.0c | 53.7% | +2.5% |
| NRFI best combined filter | MLB run-first-inning | `KXMLBRFI` | 1.0c | 55.7% | -3.0% @ -135 |
| Signal B HOME | MLB F5 run line | `KXMLBF5SPREAD` | 5.0c | 53.9% | -6.2% @ -135 |
| KP04 breaking-ball mismatch | MLB strikeout props | `KXMLBKS` | 3.0c | 55.3% | ~breakeven |
| TB props (book-specific) | MLB total-base props | `KXMLBTB` | 3.0c | — | -10% all-books |
| NBA archetype pair | NBA FG totals OVER | `KXNBA*` | n/a | 51.4% | -1.8% |

- *F5/FG Path Mismatch (F3)* — Best near-miss in the repo. But 71% of F5 lines are exactly 4.5, so the feature is largely a function of the FG line.
- *NRFI best combined filter* — Died explicitly of vig, not of signal. Needs Kalshi's RFI price - a win rate is not an edge.
- *Signal B HOME* — Clean PIT number after removing xFIP lookahead. Wide market.
- *KP04 breaking-ball mismatch* — Zero fires in 226 games live - dead code, not a live signal.
- *TB props (book-specific)* — Only survived on one book (BetOnline +22.6%, N=108). Almost certainly a pricing artifact.
- *NBA archetype pair* — Off-season in the capture window - no spread measured.

**NRFI is the conceptually cleanest case in the whole repo.** It was killed in
plain language for the right reason: *'the NRFI market has structural vig of
-135 that absorbs the available edge.'* That is a pure venue kill. But a 55.7%
win rate is not a 5.7-point edge — the edge is win rate minus Kalshi's price,
and Kalshi's RFI price is exactly what has never been measured.

## INELIGIBLE — a cheaper venue does not fix these

| Object | Cause of death | Why the hurdle is irrelevant |
|---|---|---|
| V1 Ridge Totals Engine | CONTAMINATION | 14 of 25 features used end-of-season FanGraphs aggregates. |
| F5 Totals Engine D1/D2 | CONTAMINATION | Entirely parasitic on contaminated V1. |
| Team Totals E1/E2/E3 | CONTAMINATION+IDENTITY | 5/5 red flags; 'most contaminated object in the system'. |
| Over Scanner Wave 1 (all 10) | CONTAMINATION | V1 selection gate + discovery-validation leakage + 10-way multiple testing. |
| Signal B @ threshold 1.0 | CONTAMINATION | Static season-final xFIP applied retroactively. Clean = coin flip. |
| C8 Command vs Stuff | CONTAMINATION | Frozen discovery medians move OOS from +3.48% to -12.06%. |
| MLB Moneyline Phases 1-3 | ECONOMICS but no residual | 0/8, 0/9, 0/10 survived validation. Nothing to re-score. |
| NBA ELITE_DEF2_at_ELITE_DEF | NOISE | 43.0% OOS, -18% ROI. |
| W02 / D02 / H01 / H02 | NOISE | Sign reversals across stages. |
| WNBA archetypes | TRIAGE-ONLY | Proxy odds, never validated on real prices. |
| NCAAF portal badge + ridge | NO VENUE | Kalshi lists no NCAAF market at all. |
| Golf signals | NO VENUE + NOISE | No Kalshi golf market; signals reversed anyway. |

## The risk that can flip all of Tier 1

Adverse selection was measured on **general** MLB order flow: what a random
resting order experiences. A signal-driven order is not random. If your signal
keys on something informed takers also see — a lineup scratch, a weather move,
a late pitcher change — your fills arrive disproportionately when you are wrong,
and your true hurdle is worse than 0.347c.

Tier 1 edges run 0.21c to 1.86c per contract. **A signal-conditional hurdle of
1c would erase most of the table.** Measuring adverse selection conditional on
signal firing is the next real test, and it must come before any capital.

## Also unresolved

- Kalshi prices are assumed equal to vig-free sportsbook fair value. Never measured — that is the blocked cross-venue test.
- Fill rates are not modelled. A passive order that never fills earns nothing.
- NFL spreads here (6-7c) are from **mid-August, before the season**. Not representative; re-measure in-season.
- `PHASE7_CLEAN_KILLS.md` calls P09 permanently dead while `mlb_system_registry_v2.md` carries it as VALIDATED_SHADOW with live stake multipliers. Unrelated to this re-score, but it is a live contradiction with money attached.