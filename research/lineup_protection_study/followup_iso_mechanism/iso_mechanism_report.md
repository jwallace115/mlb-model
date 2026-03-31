# ISO Mechanism Follow-up — Report

Dataset: 174870 batter-games (2022-2025)

## Critical Data Limitation

**No batter-level pitch attack data available locally.**
Zone rate, first-pitch strike, fastball rate all require pitch-by-pitch data.
Only pitcher-game-aggregate Statcast is available (zone_rate, whiff_rate per start).
This means we CANNOT directly test 'does protector change attack on THIS batter.'
We CAN test indirect effects through batter outcomes and pitcher game aggregates.

## Step 2 — Attack Channel (Pitcher Game Aggregate)

Does lineup-average protector quality change the opposing pitcher's game aggregate?

| Outcome | Ondeck Coef | p-value | Direction |
|---------|-----------|---------|-----------|
| Pitcher Zone Rate | -0.01828 | 0.0235 | - |
| Pitcher Whiff Rate | -0.00457 | 0.6801 | - |
| Pitcher Hard-Hit Allowed | +0.11156 | 0.0000 | + |
| Pitcher Barrel Allowed | +0.02423 | 0.0002 | + |

## Step 3 — Damage Channel (Batter Outcomes)

Does better protector quality increase batter ISO/power/wOBA?

| Outcome | Test | Ondeck Coef | p-value | R² | N |
|---------|------|-----------|---------|-----|---|
| ISO | ondeck_woba | +0.07131 | 0.0000 | 0.003328 | 129924 |
| ISO | ondeck_woba (+ pitcher env) | +0.06506 | 0.0000 | 0.011050 | 129924 |
| Extra-Base-Hit Rate | ondeck_woba | +0.02348 | 0.0000 | 0.002528 | 129924 |
| Extra-Base-Hit Rate | ondeck_woba (+ pitcher env) | +0.02095 | 0.0000 | 0.009788 | 129924 |
| HR Rate | ondeck_woba | +0.02201 | 0.0000 | 0.002530 | 129924 |
| HR Rate | ondeck_woba (+ pitcher env) | +0.02058 | 0.0000 | 0.008122 | 129924 |
| Contact Rate | ondeck_woba | +0.00442 | 0.5961 | 0.006107 | 129924 |
| Contact Rate | ondeck_woba (+ pitcher env) | +0.00077 | 0.9265 | 0.011174 | 129924 |
| wOBA Proxy | ondeck_woba | +0.03492 | 0.0002 | 0.007910 | 129924 |
| wOBA Proxy | ondeck_woba (+ pitcher env) | +0.02972 | 0.0015 | 0.016027 | 129924 |

## Step 4 — Clustering Check

- corr(batter_woba, ondeck_woba): r=0.1277
- corr(batter_iso, ondeck_iso): r=0.0911

Minimal clustering. Raw and residualized results should be similar.

### Residualized Protector Tests

| Outcome | Residual Ondeck Coef | p-value |
|---------|---------------------|---------|
| ISO (residualized) | +0.06535 | 0.0000 |
| Walk Rate (residualized) | +0.00851 | 0.0871 |

## Step 5 — Protector Type Effects

| Protector Type | N | ISO Δ | Walk Δ | XBH Δ | HR Δ |
|---------------|---|-------|--------|-------|------|
| elite_damage | 16244 | +0.0183 | +0.0067 | +0.0059 | +0.0050 |
| high_k_power | 19520 | +0.0115 | +0.0027 | +0.0034 | +0.0039 |
| contact_only | 10337 | +0.0120 | +0.0050 | +0.0035 | +0.0034 |
| average | 67747 | +0.0081 | +0.0027 | +0.0020 | +0.0026 |
| weak | 31659 | +0.0000 | +0.0000 | +0.0000 | +0.0000 |

## Final Interpretation

**ISO effect SURVIVES residualization** — evidence of real protection mechanism.

### Q1: Does protector quality change pitch attack behavior?
CANNOT DEFINITIVELY ANSWER — no per-batter attack data available.
Pitcher-game-aggregate test shows:
  - Pitcher Zone Rate: -0.01828 (p=0.0235)
  - Pitcher Hard-Hit Allowed: +0.11156 (p=0.0000)
  - Pitcher Barrel Allowed: +0.02423 (p=0.0002)

### Q2: Is the ISO effect real or clustering?
ISO effect real after residualization (p=0.0000).

### Q3: Large enough for totals?
Elite protector ISO delta vs weak: +0.0183
**Meaningful** — worth investigating for simulation refinement.

## Final Verdict

**INVESTIGATE**
Real protection mechanism detected at ISO level, survives residualization.
Next step: acquire pitch-level data to test attack channel directly.

