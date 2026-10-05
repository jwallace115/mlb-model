# Pre-registration — ROAD_WARRIOR @ STRONG_HOME OVER on 2025-26 at real closing prices
Written by Cowork 2026-09-30T20:03Z, BEFORE any 2025-26 outcome for this signal was computed.

Why: the April 10 revalidation ("SURVIVES, 226 true-OOS games, 63.2%, +20.7%") tested the CURRENT list on 2022-23
and 2023-24, but the list was pruned (58704cd42: -BKN, -LAL, -NOP) and expanded (7868c748e: +ATL both, +BOS home) on
2026-03-22 using 2022-23..2024-25 results (research/nba_venue_pruned_validation.txt,
research/nba_venue_expansion_candidates.txt). Those "OOS" seasons helped choose the list -> CHECK 2 fails; the
63.2% / +20.7% is in-sample, and it was priced at flat -110 (CHECK 4: triage only). The 2025-26 regular season was
not used by any selection step on disk -> the cleanest test available.

Object: list at 7868c748e. away in {ATL,CHI,DAL,DET,GSW,HOU,NYK,PHI,PHX,UTA}, home in
{ATL,BOS,DEN,IND,MIL,OKC,POR,SAS}. Regular season 2025-10-21..2026-04-12. Bet: OVER full-game total.
Price: last pre-tip snapshot in data/odds_archive/nba/history/lines_hourly/season=2025 (close_* and snap_* files,
snapshot_utc < commence_time). Primary book Pinnacle (line + over price). Secondary Hard Rock (hardrockbet), DraftKings.
Outcome: actual_total incl. OT from nba/data/predictions_4b.parquet (to 2026-03-13) and nba/data/nba_results_log.parquet
(2026-03-14..). Push = void. Games without a Pinnacle close or an outcome are counted and reported, not imputed.
Metrics: n, hit rate ex-push, ROI at the Pinnacle over price (units per 1 staked), SE; same at Hard Rock/DK.
Null control: every NON-signal game with the same data: over hit rate and ROI at Pinnacle's over price must sit near
break-even (hit ~48-52%, ROI ~ -1% to -4%). If it does not, the pipeline is wrong, not the signal.
Breakouts: month, away team, home team, line band (<225, 225-235, >235).
PREDICTION: the April figure does not hold. Expected hit rate 50-57%, ROI at Pinnacle between -6% and +8%.
The signal is called "alive" only if ROI at Pinnacle > 0 AND the one-sided 90% lower bound > 0. Nothing is tuned;
the list is not changed after seeing this.
