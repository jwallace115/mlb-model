# TB Props Signal Discovery Report

**Date:** 2026-03-27
**Source:** `research/mlb_props/tb_props/tb_props_dataset.parquet` (32,756 records, 2025 season)
**Output:** `research/mlb_props/tb_signal_discovery/`

---

## Executive Summary

| Signal Family | AUC Lift vs Baseline | Coverage | Verdict |
|:--------------|---------------------:|:---------|:--------|
| A: Zero-TB Propensity | +0.0019 | 98.2% | **PRIMARY SIGNAL** |
| B: Pitcher XBH Suppression | +0.0015 | 62.5% | SECONDARY SIGNAL |
| C: Lineup Protection | +0.0017 | 97.4% | **PRIMARY SIGNAL** |
| D: Bullpen Exposure | +0.0010 | 62.2% | SHELVE |
| E: Team Defense (DRS) | +0.0032 | 100.0% | SECONDARY SIGNAL |

**Key findings:**
- Zero-TB propensity and lineup protection are the two strongest signal families
- Protection collapse (high-ISO batter x weak on-deck hitter) produces the most promising market edge pattern: edge shrinks to near-zero (-0.8pp to -1.5pp) vs baseline -5pp
- Defense (DRS) shows the highest raw AUC lift (+0.0032) but has a non-monotonic bucket pattern
- Bullpen exposure adds almost nothing beyond baseline
- All AUC lifts are modest (< 0.005) — this is a distribution-shape problem, not a mean-prediction problem

**Verdict: PROCEED TO TB MODEL BUILD**
**Recommended backbone: Zero-TB distribution model + protection interaction overlay**

---

## Baseline Rates

| Target | Rate | Description |
|:-------|-----:|:------------|
| tb_zero_flag | 38.76% | P(TB = 0) |
| tb_over_1_5 | 36.09% | P(TB >= 2) |
| tb_over_2_5 | 21.57% | P(TB >= 3) |
| tb_tail_flag | 15.08% | P(TB >= 4) |

---

## Family A: Zero-TB Propensity

**Hypothesis:** Books price mean TB but underprice hitters with extreme "all-or-nothing" distributions. Two hitters with the same SLG can have very different zero-TB frequencies.

### Bucket Test: zero_tb_rate_last20 → Under 1.5 TB

| Quintile | Zero-TB Rate Range | N | Actual Over 1.5 | Implied Over | Edge |
|:---------|:-------------------|---:|---:|---:|---:|
| Q1 (lowest) | 0.000-0.300 | 1,662 | 0.3833 | 0.4448 | -0.0615 |
| Q2 | 0.308-0.400 | 1,617 | 0.3673 | 0.4200 | -0.0526 |
| Q3 | 0.417-0.450 | 803 | 0.3474 | 0.4071 | -0.0596 |
| Q4 | 0.455-0.550 | 1,273 | 0.3362 | 0.3879 | -0.0517 |
| Q5 (highest) | 0.556-0.944 | 920 | 0.3326 | 0.3574 | -0.0248 |

**Key observation:** The Q5 (highest zero-TB rate) bucket has the *smallest* Under edge (-2.5pp vs -6.2pp in Q1). This means the market already partially prices zero-TB frequency for the most extreme cases. The value is in Q1-Q4 where the market overprices the Over by 5-6pp consistently.

### Bucket Test: zero_tb_rate_last20 → Under 2.5 TB

| Quintile | Range | N | Actual Over 2.5 | Implied Over | Edge | Under ROI |
|:---------|:------|---:|---:|---:|---:|---:|
| Q1 | 0.000-0.300 | 1,586 | 0.2238 | 0.2766 | -0.0527 | -0.17 |
| Q5 | 0.556-0.944 | 903 | 0.1805 | 0.2092 | -0.0287 | **+0.19** |

The highest zero-TB quintile at line 2.5 shows **+18.6% Under ROI** — the one bright spot in odds-based profitability.

### Controlling for Mean TB

Cross-tabulation of zero_tb_rate (terciles) x mean_tb_last20 (terciles) at line 1.5:

| Mean TB | Zero-TB Rate | N | Actual Over 1.5 | Implied Over | Edge |
|:--------|:-------------|---:|---:|---:|---:|
| High | Low | 1,464 | 0.3996 | 0.4510 | -0.0514 |
| High | Mid | 423 | 0.3853 | 0.4437 | -0.0584 |
| High | **High** | 46 | **0.4783** | 0.4395 | **+0.0387** |
| Low | High | 1,256 | 0.3209 | 0.3560 | -0.0352 |

The high-mean-TB + high-zero-TB-rate cell (N=46) actually shows positive edge for the Over — these are true boom-or-bust hitters whose upside exceeds market expectation when they connect. Small sample but directionally interesting for a future Over model.

### TB Variance

| Quintile | Variance Range | N | Actual Over 1.5 | Implied Over | Edge |
|:---------|:---------------|---:|---:|---:|---:|
| Q1 (lowest) | 0.056-1.566 | 1,255 | 0.3291 | 0.3737 | -0.0447 |
| Q5 (highest) | 4.274-18.450 | 1,254 | 0.4075 | 0.4447 | -0.0372 |

Variance is informative but redundant with zero_tb_rate — both capture distribution shape. Zero-TB rate is more interpretable and actionable.

### Head-to-Head Comparison

| Target | Baseline AUC | Signal AUC | Combined AUC | AUC Lift |
|:-------|---:|---:|---:|---:|
| tb_zero_flag | 0.5436 | 0.5369 | 0.5463 | **+0.0027** |
| tb_over_1_5 | 0.5479 | 0.5382 | 0.5491 | +0.0012 |
| tb_over_2_5 | 0.5654 | 0.5490 | 0.5671 | +0.0017 |

**Assessment:** Adds value beyond baseline for all three targets. Strongest on zero-flag prediction. The signal alone (AUC 0.5369) is weaker than baseline (0.5436), but combined (0.5463) shows the features carry complementary information.

### Half-Season Stability

| Half | Quintile | N | Actual Over 1.5 | Implied Over | Edge |
|:-----|:---------|---:|---:|---:|---:|
| H1 | Q1 | 594 | 0.3704 | 0.4294 | -0.0590 |
| H1 | Q5 | 397 | 0.3275 | 0.3443 | -0.0168 |
| H2 | Q1 | 1,068 | 0.3904 | 0.4533 | -0.0629 |
| H2 | Q5 | 523 | 0.3365 | 0.3674 | -0.0309 |

Pattern is stable across both halves: Q1 edge ~-6pp, Q5 edge ~-2pp.

**Family A verdict: PRIMARY SIGNAL.** Zero-TB rate captures distribution shape information the market partially misses. Best used as a foundation feature.

---

## Family B: Pitcher XBH Suppression

**Hypothesis:** Some pitchers allow hits but suppress extra-base hit quality. Books price ERA/WHIP but not the specific TB suppression mechanism.

### Bucket Test: p_barrel_rate_last5 → Under 1.5 TB

| Quintile | Barrel Rate Range | N | Actual Over 1.5 | Implied Over | Edge |
|:---------|:------------------|---:|---:|---:|---:|
| Q1 (lowest) | 0.000-0.014 | 809 | 0.3733 | 0.4078 | -0.0345 |
| Q2 | 0.014-0.026 | 800 | 0.3212 | 0.4097 | **-0.0885** |
| Q3 | 0.026-0.038 | 798 | 0.4023 | 0.4118 | -0.0096 |
| Q4 | 0.038-0.054 | 807 | 0.3383 | 0.4056 | -0.0673 |
| Q5 (highest) | 0.054-0.130 | 797 | 0.3664 | 0.4152 | -0.0488 |

**Key observation:** Non-monotonic pattern. Q2 shows the largest Under edge (-8.9pp) but Q3 shows near-zero edge. This is not a clean signal — barrel rate alone does not reliably separate TB outcomes beyond what the market prices.

### Hard Hit Rate and Exit Velocity

Similar non-monotonic patterns. No clean directional relationship between pitcher contact-quality metrics and TB market edge.

### Head-to-Head Comparison

| Target | Baseline AUC | Combined AUC | AUC Lift |
|:-------|---:|---:|---:|
| tb_zero_flag | 0.5374 | 0.5381 | +0.0007 |
| tb_over_1_5 | 0.5415 | 0.5437 | +0.0022 |
| tb_over_2_5 | 0.5467 | 0.5484 | +0.0017 |

Small positive lift, but lower than Families A and C, with only 62.5% data coverage.

**Family B verdict: SECONDARY SIGNAL.** Some information in pitcher contact suppression, but non-monotonic bucket pattern and lower coverage reduce its value. Include if combining with other families, but not as standalone foundation.

---

## Family C: Lineup Protection Collapse

**Hypothesis:** Weak on-deck hitter protection changes pitch attack patterns and suppresses TB outcomes, especially for power hitters.

### Bucket Test: ondeck_iso_last20 → Under 1.5 TB

| Quintile | On-Deck ISO Range | N | Actual Over 1.5 | Implied Over | Edge |
|:---------|:-------------------|---:|---:|---:|---:|
| Q1 (weakest) | 0.000-0.068 | 1,253 | 0.3480 | 0.4003 | -0.0523 |
| Q3 | 0.113-0.155 | 1,238 | 0.3570 | 0.4079 | -0.0508 |
| Q5 (strongest) | 0.217-0.468 | 1,233 | 0.3585 | 0.4203 | -0.0618 |

Weak protection (Q1) shows *less* edge than strong protection (Q5). This is counterintuitive: the market gives more credit (higher implied Over) to batters with strong protectors, but the *actual* Over rate doesn't rise proportionally. The market overweights protection.

### Protector Type Test at 1.5 Line

| Protector Type | N | Actual Over 1.5 | Zero TB Rate | Implied Over | Edge |
|:---------------|---:|---:|---:|---:|---:|
| weak | 1,505 | 0.3654 | 0.3794 | 0.4016 | **-0.0362** |
| average | 2,926 | 0.3517 | 0.3937 | 0.4059 | -0.0542 |
| elite_damage | 696 | 0.3836 | 0.3621 | 0.4256 | -0.0420 |
| high_k_power | 794 | 0.3476 | 0.3753 | 0.4178 | **-0.0702** |
| contact_only | 465 | 0.3419 | 0.3849 | 0.4059 | -0.0639 |

**Critical finding:** The **"weak" protector type has the smallest Under edge (-3.6pp)** while "high_k_power" has the largest (-7.0pp). This means the market *over-corrects* for strong but K-prone protectors — it gives too much credit to having a power hitter on deck who strikes out a lot.

### Interaction: High-ISO Batter x Weak Protection

| High ISO | Weak Protection | N | Actual Over 1.5 | Implied Over | Edge |
|:---------|:----------------|---:|---:|---:|---:|
| 0 | 0 | 2,894 | 0.3480 | 0.4008 | -0.0529 |
| 0 | 1 | 1,377 | 0.3420 | 0.3960 | -0.0540 |
| 1 | 0 | 1,379 | 0.3771 | 0.4370 | -0.0599 |
| **1** | **1** | **452** | **0.4159** | **0.4240** | **-0.0081** |

**This is the strongest market-edge finding in the entire study.** When a high-ISO batter has weak protection, the edge collapses to -0.8pp (vs -5.3pp baseline). The market expects these hitters to underperform but they don't — likely because pitchers still have to respect the batter's own power even without protection.

### Half-Season Stability of Protection Interaction

| Half | High ISO | Weak Prot | N | Actual | Implied | Edge |
|:-----|:---------|:----------|---:|---:|---:|---:|
| H1 | 1 | 1 | 203 | 0.3892 | 0.4091 | -0.0199 |
| H2 | 1 | 1 | 270 | 0.4407 | 0.4423 | **-0.0015** |

**Remarkably stable.** Edge is near zero in both halves. H2 shows virtual breakeven with the market.

### Head-to-Head Comparison

| Target | Baseline AUC | Combined AUC | AUC Lift |
|:-------|---:|---:|---:|
| tb_zero_flag | 0.5429 | 0.5433 | +0.0004 |
| tb_over_1_5 | 0.5468 | 0.5482 | +0.0014 |
| tb_over_2_5 | 0.5648 | 0.5680 | **+0.0032** |

Strongest AUC lift at the 2.5 line (+0.0032), which is the line where edge matters most for Under bets.

**Family C verdict: PRIMARY SIGNAL.** The protection interaction (high-ISO x weak on-deck) is the single most promising market-edge pattern found. The mechanism is clear: market over-corrects for weak protection on power hitters. Use as primary overlay.

---

## Family D: Bullpen Exposure Quality

**Hypothesis:** Short-leash starters facing elite bullpens suppress TB upside for batters who see more relievers.

### Bucket Test: p_avg_ip_last5 → Under 1.5 TB

| Quintile | IP Range | N | Actual Over 1.5 | Implied Over | Edge |
|:---------|:---------|---:|---:|---:|---:|
| Q1 (short) | 3.24-4.64 | 828 | 0.3684 | 0.4224 | -0.0540 |
| Q3 | 5.05-5.44 | 807 | 0.3606 | 0.4059 | -0.0453 |
| Q5 (deep) | 5.86-7.04 | 742 | 0.3396 | 0.4033 | -0.0636 |

Non-monotonic. Short starters (Q1) don't show larger Under edge than deep starters (Q5).

### Interaction: Short Starter x Fresh Bullpen

| Short Starter | Fresh BP | N | Actual Over 1.5 | Implied Over | Edge |
|:--------------|:---------|---:|---:|---:|---:|
| 0 | 0 | 1,763 | 0.3443 | 0.4083 | -0.0640 |
| 0 | **1** | 790 | **0.3937** | 0.4000 | **-0.0063** |
| 1 | 0 | 1,094 | 0.3592 | 0.4198 | -0.0606 |
| 1 | 1 | 347 | 0.3833 | 0.4123 | -0.0290 |

Interesting: a fresh bullpen behind a *long* starter actually collapses the Under edge to -0.6pp. This may reflect game state — fresh bullpens correlate with games that didn't need bullpen help recently, which could be confounded.

### Head-to-Head Comparison

| Target | Baseline AUC | Combined AUC | AUC Lift |
|:-------|---:|---:|---:|
| tb_zero_flag | 0.5374 | 0.5373 | -0.0001 |
| tb_over_1_5 | 0.5420 | 0.5437 | +0.0017 |
| tb_over_2_5 | 0.5469 | 0.5484 | +0.0015 |

Minimal lift. Zero-flag prediction actually *loses* information when bullpen features are added.

**Family D verdict: SHELVE.** Bullpen exposure does not reliably separate TB outcomes beyond baseline. The interaction finding (fresh BP) is likely confounded. Not worth including in a model.

---

## Family E: Team Defense (DRS)

**Hypothesis:** Books underweight defensive run prevention against specific batter types.

### Bucket Test: DRS → Under 1.5 TB

| Quintile | DRS Range | N | Actual Over 1.5 | Implied Over | Edge |
|:---------|:----------|---:|---:|---:|---:|
| Q1 (worst) | -59 to -4 | 1,312 | 0.3925 | 0.4247 | -0.0322 |
| Q2 | 0 to 16 | 1,364 | 0.3673 | 0.4107 | -0.0434 |
| Q3 | 18 to 31 | 1,310 | 0.3412 | 0.3955 | -0.0543 |
| Q4 | 32 to 42 | 1,411 | 0.3317 | 0.4041 | **-0.0724** |
| Q5 (best) | 46 to 89 | 995 | 0.3548 | 0.4076 | -0.0528 |

Edge is largest at Q4 (-7.2pp), not Q5 (-5.3pp). Non-monotonic in the top quintile.

### Interaction: Bottom-Order Batter x Elite Defense

| Bottom Order | Elite Defense | N | Actual Over 1.5 | Zero TB Rate | Edge |
|:-------------|:-------------|---:|---:|---:|---:|
| 0 | 0 | 2,417 | 0.3835 | 0.3587 | -0.0579 |
| 0 | 1 | 1,201 | 0.3847 | 0.3697 | -0.0555 |
| **1** | **1** | **914** | **0.2965** | **0.4289** | **-0.0661** |

Bottom-order batters vs elite defense have the highest zero-TB rate (42.9%) and the largest Under edge (-6.6pp).

### Head-to-Head Comparison

| Target | Baseline AUC | Combined AUC | AUC Lift |
|:-------|---:|---:|---:|
| tb_zero_flag | 0.5436 | 0.5473 | **+0.0037** |
| tb_over_1_5 | 0.5479 | 0.5523 | **+0.0044** |
| tb_over_2_5 | 0.5654 | 0.5668 | +0.0014 |

Highest AUC lift of any family on tb_zero_flag and tb_over_1_5.

**Family E verdict: SECONDARY SIGNAL.** DRS adds genuine complementary information, especially for zero-TB and Under 1.5 prediction. The non-monotonic top quintile and seasonal nature of team defense (doesn't change within season) limit its weight, but it belongs in a combined model.

---

## Signal Family Ranking

| Rank | Family | Avg AUC Lift | Coverage | Key Finding | Verdict |
|:-----|:-------|---:|:---------|:------------|:--------|
| 1 | **C: Protection** | +0.0017 | 97.4% | High-ISO x weak protection: edge → -0.8pp (vs -5.3pp baseline) | **PRIMARY** |
| 2 | **A: Zero-TB** | +0.0019 | 98.2% | Zero-TB rate captures distribution shape; stable across halves | **PRIMARY** |
| 3 | E: Defense | +0.0032 | 100.0% | DRS adds to zero-flag; non-monotonic top quintile | SECONDARY |
| 4 | B: Pitcher XBH | +0.0015 | 62.5% | Some signal in barrel rate Q2; non-monotonic overall | SECONDARY |
| 5 | D: Bullpen | +0.0010 | 62.2% | Near-zero lift on zero-flag; confounded fresh-BP interaction | SHELVE |

---

## Answers to Key Questions

### 1. Which signal family best explains TB distribution shape?
**Family A (Zero-TB Propensity)** best captures distribution shape — it directly measures the overdispersion that mean-based pricing misses. Family C (Protection) best explains *market edge* — it identifies where the market systematically misprices.

### 2. Is zero-TB propensity the strongest foundation for an Under TB model?
**Yes.** Zero-TB rate is the most natural foundation feature. It captures the key distribution-shape information (P(TB=0) varies from 0% to 94% across the rolling window), has 98% coverage, and is stable across half-seasons. However, it should be paired with the protection interaction to target the specific situations where market edge exists.

### 3. Which families add value beyond simple mean-based stats?
All except D (Bullpen). Ranked by average AUC lift over baseline:
1. E: Defense (+0.0032)
2. A: Zero-TB (+0.0019)
3. C: Protection (+0.0017)
4. B: Pitcher XBH (+0.0015)
5. D: Bullpen (+0.0010, negative on zero-flag)

### 4. Which families are primary vs secondary model candidates?
- **Primary:** A (Zero-TB Propensity) + C (Lineup Protection)
- **Secondary:** E (Defense DRS) + B (Pitcher Barrel Rate)
- **Shelve:** D (Bullpen Exposure)

### 5. Which families should be shelved?
**Family D (Bullpen Exposure)** should be shelved. Near-zero or negative AUC lift on zero-flag prediction, non-monotonic bucket patterns, and the interaction finding is likely confounded by game-state correlation.

---

## Verdict: PROCEED TO TB MODEL BUILD

### Recommended Model Backbone

**Zero-TB distribution model + protection interaction overlay**

Architecture:
1. **Core:** Logistic model predicting P(TB=0), P(TB≥2), P(TB≥3) using:
   - zero_tb_rate_last20 (distribution shape)
   - pct_2plus_tb_last20 (tail frequency)
   - tb_var_last20 (overdispersion)
   - iso_last20, slg_last20 (baseline power)
   - batting_order_slot (lineup context)

2. **Primary overlay:** Protection interaction features:
   - ondeck_iso_last20
   - ondeck_woba_proxy_last20
   - protector_type
   - high_iso_batter x weak_protection interaction term

3. **Secondary features:** Include if they pass feature selection:
   - defensive_runs_saved (opponent)
   - p_barrel_rate_last5 (opposing pitcher)
   - p_hard_hit_rate_last5

4. **Target strategy:** The model should predict distribution shape (zero-TB probability + tail probability), not just mean TB. The edge exists in distribution shape, not in mean prediction.

5. **Market edge targeting:** Focus model evaluation on the protection interaction cell (high-ISO x weak protection) where edge is near zero — this is the most likely source of deployable edge once vig is considered.

---

## Supporting Files

| File | Description |
|:-----|:------------|
| `family_a_zero_tb.parquet` | Family A bucket test results |
| `family_b_xbh_suppression.parquet` | Family B bucket test results |
| `family_c_protection.parquet` | Family C bucket test results |
| `family_d_bullpen_exposure.parquet` | Family D bucket test results |
| `family_e_defense_fit.parquet` | Family E bucket test results |
| `signal_family_ranking.parquet` | Final ranking table |
| `logistic_comparison.parquet` | Head-to-head logistic regression results |
| `source_audit.md` | Full data source audit |
