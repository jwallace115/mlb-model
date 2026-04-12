# Phase 1: Bullpen PIT-Safety Audit

## Source Chain
- pitcher_game_logs.parquet -> starter_flag==0 -> groupby(team,season,date)
- Rolling: shift(1).expanding().sum() (strictly prior games)
- Minimum: bp_cum_ip >= 10 innings before ERA computed
- NO FanGraphs, NO V1 tables, NO season-final stats in chain

## 5 Worked Examples
- MIL 2023-08-15: computed=4.279, manual=4.279, match=True
- MIL 2023-08-28: computed=4.213, manual=4.213, match=True
- TEX 2023-08-21: computed=5.195, manual=5.195, match=True
- CHC 2023-05-13: computed=3.792, manual=3.792, match=True
- HOU 2024-08-11: computed=3.991, manual=3.991, match=True

All 5 match: True

## Opener/Bulk Contamination Check
- Reliever appearances with IP >= 5.0: 238 (0.37%)
- Verdict: NEGLIGIBLE (< 0.5% of appearances)

## VERDICT: PIT-SAFE AND LIVE-FEASIBLE

bp_adv_dog PASSES Phase 1 gate. Proceed to Phase 2.