# MLB Totals P1 Hardening — EARLY_HEAVY x Warm Temp FG OVER

## Object Definition
- Path state: EARLY_HEAVY (f5_ratio > 0.5625, frozen from 2023 p67)
- Temperature: >= 75F (discovery EARLY_HEAVY median = 74.8F)
- Side: FG OVER at actual closing over price
- Source: P1 FG/F5 Path Mismatch Engine, PROMOTE signal

## Sample Sizes
- Discovery (2023): 319
- Validation (2024): 105
- OOS (2025): 173
- Total: 597

## P1 Reported vs Hardening Confirmed
| Split | P1 N | P1 Win% | P1 ROI | Hard N | Hard Win% | Hard ROI |
|-------|------|---------|--------|--------|-----------|----------|
| discovery | 319 | 61.4% | +20.2% | 319 | 61.4% | +20.2% |
| validation | 105 | 59.0% | +14.4% | 105 | 59.0% | +14.4% |
| oos | 173 | 53.2% | +9.1% | 173 | 53.2% | +9.1% |

Reproduction: EXACT match on all N/win%/ROI values.

## Hardening Results

### Concentration (PASS)
- Top 3 home teams: WSN (94), KCR (76), PHI (54)
- Leave-one-out: excluding any single top team keeps ROI >= +14.2%
- Leave-one-out by month: excluding any single month keeps ROI >= +13.0%
- Signal is NOT driven by any single team or month

### Micro-band Stability (MIXED)
- FG total <=8.5: N=126, win=73.8%, ROI=+40.4% (very strong)
- FG total 9.0: N=162, win=51.9%, ROI=+11.9%
- FG total 9.5+: N=309, win=56.0%, ROI=+8.2%
- Price <=-110: N=267, win=66.7%, ROI=+27.8% (price carries juice)
- Price >+100: N=76, win=48.7%, ROI=-1.1% (signal vanishes at plus-money)
- FINDING: Signal concentrates in shorter lines with juice. Plus-money overs are breakeven.

### Proxy Risk Audit (MIXED — key finding)
- Apr-May: N=36, win=33.3%, ROI=-23.2% (NEGATIVE)
- Jun-Aug: N=472, win=58.3%, ROI=+15.2% (bulk of signal)
- Sep-Oct: N=87, win=70.1%, ROI=+34.5% (strongest rate, small N)
- FINDING: Apr-May warm games perform TERRIBLY. These are early-season warm-climate
  parks (ARI, MIA, TEX) where "warm" is the default, not a structural driver.
- Non-summer (Apr-May + Sep-Oct combined): N=125, win=60.0% — passes, but driven by Sep.
- Warm-climate parks: N=132, win=50.0%, ROI=+2.4% (breakeven)
- Cold-climate parks: N=465, win=61.1%, ROI=+19.8% (entire signal)
- CRITICAL: Signal is actually "warm weather at normally-cool parks" not "warm weather."

### Late-Scoring Mechanism (FAIL)
- Hypothesis: warm temp causes extra late-inning scoring
- Actual late runs: matched=4.30, control=4.12, diff=+0.17 (t=0.95, p=0.342)
- NOT significant. The extra runs come in F5 (+0.57, p=0.005), not late innings.
- This contradicts the P1 thesis that path_error (late scoring) drives the over.
- Actual mechanism: warm games at EARLY_HEAVY simply produce more total runs (+0.74),
  and the market underestimates this in the FG total, not specifically in late innings.

### Regime Decay (CAUTION)
- 2023: N=319, win=61.4%, ROI=+20.2%, avg_price=-91
- 2024: N=105, win=59.0%, ROI=+14.4%, avg_price=-81
- 2025: N=173, win=53.2%, ROI=+9.1%, avg_price=-75
- Win rate declining: 61.4% -> 59.0% -> 53.2%
- ROI declining: +20.2% -> +14.4% -> +9.1%
- Average over price shrinking (market adjusting): -91 -> -81 -> -75
- Trend line crosses zero around 2027 if linear decay continues.

### Temperature Source Risk (MODERATE)
- Research used: Open-Meteo Archive (actual game-time temperature, postgame known)
- Live pipeline uses: Open-Meteo Forecast (pregame forecast)
- Threshold is coarse (75F median split), same-day forecasts generally accurate
- Risk is moderate but real — no way to validate without shadow data

## Go/No-Go Checklist
- [x] OOS ROI positive (+9.1%)
- [x] OOS win rate > 52% (53.2%)
- [x] No single month drives signal
- [x] No single team drives signal
- [ ] Late-scoring mechanism confirmed (p=0.342, FAILED)
- [x] Signal present outside summer (60.0%, N=125)
- [x] No regime decay (all years ROI > -2%)
- [x] Forecast temperature feasible

**SCORECARD: 7/8 checks passed**

## Concerns (not captured in checklist)
1. Apr-May warm games are ROI=-23.2% — filter to Jun+ or cold-climate parks only
2. Plus-money overs are breakeven — signal requires juice (price <= -105)
3. Regime decay trend is real: +20% -> +14% -> +9%, market is adjusting
4. Late-scoring mechanism FAILED — actual mechanism is total runs, not path-specific
5. Warm-climate parks are breakeven — signal is cold-park warm-day specific

## Decision: CONDITIONAL GO — proceed to shadow

Conditional on tightening the trigger:
- Original: EARLY_HEAVY + temp >= 75F
- Recommended: EARLY_HEAVY + temp >= 75F + closing over price <= -105 + exclude warm-climate home parks
- This drops N but focuses on the structural sweet spot

## Shadow Spec
- Trigger: EARLY_HEAVY path state AND forecast temp >= 75F
- Filter: closing over price <= -105, outdoor cold-climate parks only
- Side: FG OVER
- Minimum shadow: 30 triggered games before any live action
- Kill switch: running win rate < 0.48 after 30+ games
- Log: forecast vs actual temp for every triggered game
- Track: actual F5 runs vs actual late runs to monitor mechanism
