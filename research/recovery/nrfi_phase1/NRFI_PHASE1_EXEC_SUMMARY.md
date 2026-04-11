# NRFI Phase 1 -- Executive Summary

Generated: 2026-04-11
Data: 9900 MLB games, seasons 2022-2026

## Key Findings

1. **Overall NRFI rate: 51.2%** across 9900 games
   - Top-1 clean (away 0 in 1st): 73.5%
   - Bot-1 clean (home 0 in 1st): 69.3%
   - Fair price (no vig): -95
   - Blind ROI at -135: -10.8%

2. **Full-game total is the strongest NRFI filter**
   - Total <=8.0: NRFI = 55.6% (n=4107)
   - Total >=10.0: NRFI = 38.9% (n=699)
   - Spread: +16.7%

3. **F5 total provides independent confirmation**
   - F5 <=4.0: NRFI = 63.3% (n=1250)
   - F5 >=5.5: NRFI = 36.9% (n=1234)

4. **Best combined filter (FG<=8.5 AND F5<=5.0):**
   - NRFI = 55.6% (n=4130)
   - Lift: +4.4%
   - ROI at -135: -3.2%

5. **Tightest filter (FG<=7.5 AND F5<=4.5):**
   - NRFI = 55.7% (n=1303)
   - ROI at -135: -3.0%

6. **Environment effects are modest**
   - Dome: 50.5%, Outdoor: 51.3%
   - Pitcher park (<97): 53.0%, Hitter park (>103): 50.4%

## Season stability
  2022: NRFI = 51.8% (2430 games)
  2023: NRFI = 49.8% (2430 games)
  2024: NRFI = 53.2% (2425 games)
  2025: NRFI = 49.8% (2428 games)
  2026: NRFI = 55.6% (187 games)

## Actionable framework
Select top-3 NRFI legs daily:
1. Closing total <= 8.5
2. F5 total <= 5.0
3. Micro-model p_yrfi bottom 10%
4. Exclude CONTACT_RISK starters
5. Exclude both-top-3-changed lineups
6. Pitcher park preferred

## Files
- nrfi_research_table.parquet -- 9900 rows
- NRFI_PHASE1_FINAL_TABLE.csv -- same, CSV
- first_inning_cache.json -- MLB API cache
- phase2-8_report.md -- detailed reports