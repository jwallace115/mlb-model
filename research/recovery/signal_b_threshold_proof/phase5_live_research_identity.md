# Phase 5: Live/Research Identity Check

**Date:** 2026-04-12

---

## Identity Matrix

| Component | Research (Backtest) | Live (Daily Pipeline) | Match? |
|-----------|--------------------|-----------------------|--------|
| xFIP source | sim_inputs parquet (season-final FG) | FanGraphs API (daily-fresh) | DIFFERENT |
| xFIP type | Static per pitcher per season | Season-to-date, updated daily | DIFFERENT |
| PIT-safe | NO | YES | DIFFERENT |
| Gap formula | away_xfip - home_xfip | away_xfip - home_xfip | SAME |
| Threshold | 1.0 | 1.0 (committed) / 1.5 (working tree) | DIVERGENT |
| Bet side | HOME only | HOME only | SAME |
| Market | F5 run line (-0.5/+0.5) | F5 run line (-0.5/+0.5) | SAME |
| Grading | F5 margin > 0 = WIN | F5 margin > 0 = WIN | SAME |

## Critical Divergence: xFIP Source

The research and live pipelines use DIFFERENT xFIP data:

**Research path:**
```
sim_inputs_historical_2022_2024.parquet
  -> feature_table -> season-final FanGraphs xFIP
  -> MacKenzie Gore 2024: 4.151 for ALL starts (static)
```

**Live path:**
```
FanGraphs API -> pitcher_db -> get_pitcher_metrics()
  -> Daily-fresh season-to-date xFIP
  -> BOS starter: 3.854 on Apr 4, 3.504 on Apr 5 (varies by pitcher)
```

This means:
1. The research results (+27.9% ROI) were computed with data the live pipeline
   will NEVER see (end-of-season xFIP is unknowable at game time)
2. The live pipeline operates cleanly — no lookahead is possible
3. The ACTUAL edge of Signal B at the 1.0 threshold is unknown — the only
   clean estimate comes from the PIT FIP gap test (~51% under rate = no edge)
4. At the 1.5 threshold, the PIT-clean test shows ~60% under rate = genuine edge

## Verdict

The live pipeline is clean. The research pipeline was contaminated.
The threshold change from 1.0 to 1.5 corrects for the inflation caused
by using contaminated data to select the original threshold.
