# Phase 1: Authoritative NBA Objects

## Core Ridge Model
- **File:** nba/data/ridge_model.pkl
- **Type:** RidgeCV (sklearn)
- **Alpha:** 0.1 (selected by 5-fold CV from logspace 0.1-1000)
- **Training window:** 2022-23 + 2023-24 (TRAINING_SEASONS in config)
- **Validation season:** 2024-25
- **Intercept:** 228.8972
- **Features (15):** home_ortg, away_ortg, home_drtg, away_drtg, home_pace, away_pace, b2b_flag_away, home_ortg_trend, away_ortg_trend, home_pace_trend, away_pace_trend, home_3pa_rate, away_3pa_rate, home_ft_rate, away_ft_rate
- **Scaler:** StandardScaler stored inside pkl alongside model
- **Trained from:** nba/data/features.parquet (3,690 games, 2022-2025)

## Archetype Team Sets (all in nba/run_nba.py)
- **ELITE_DEF:** {BOS, CLE, GSW, MIL, MIN, OKC}
- **ELITE_DEF2:** {HOU, LAC, LAL, MIA, NYK, ORL, SAC}
- **ROAD_WARRIOR:** {ATL, CHI, DAL, DET, GSW, HOU, NYK, PHI, PHX, UTA}
- **STRONG_HOME:** {ATL, BOS, DEN, IND, MIL, OKC, POR, SAS}
- **CORE_AWAY:** {DAL, UTA, PHI}
- **CORE_HOME:** {IND, OKC, SAS}
- **BALANCED_OFF:** {DEN, HOU, IND, NYK, OKC}
- **PASSIVE_DEF:** {BOS, CHI, CLE, DEN, LAL, MIA, MIL, NYK, PHX, SAS, UTA, WAS}
- **THREE_HEAVY_OFF:** {BOS, CHI, CLE, GSW, MIA, MIL, SAC}
- **FOUL_PRONE_DEF:** {HOU, IND, ORL}
- **ELITE_OREB_TEAMS:** {ATL, BOS, CLE, DEN, DET, GSW, HOU, MEM, NOP, NYK, ORL, POR, SAC, TOR, UTA}
- **WEAK_BOXOUT_TEAMS:** {CHA, DAL, DEN, MEM, MIN, NOP, NYK, OKC, PHI, PHX, POR, SAS, TOR, UTA, WAS}

## Archetype Revalidation Verdicts
| Archetype | Verdict | OOS ROI |
|-----------|---------|---------|
| ELITE_DEF2_at_ELITE_DEF | COLLAPSES (KILL) | -18.0% |
| BALANCED_OFF_vs_PASSIVE_DEF | DIMINISHED (MONITOR) | -1.8% |
| ROAD_WARRIOR_at_STRONG_HOME | SURVIVES (KEEP) | +20.7% |
| ELITE_OREB_vs_WEAK_BOXOUT | DIMINISHED (MONITOR) | -3.7% |

## Playoff Boards
- **P1:** R1 Games 1-2 UNDER (sizing 1.0u, hist edge -6.82)
- **P2:** R1 Games 5-7 OVER (sizing 0.75u, hist edge +8.19)
- **P4:** CF Non-Elim G1-4 OVER (sizing 0.75u, hist edge +9.85)
- **Finals modifier:** reduce OVER sizing by 0.25u
- **Activation:** is_playoff flag from NBA API season_type
- **Pauses in playoffs:** Venue OVER, Shot UNDER, combined DOUBLE_SIGNAL UNDER

## Other Active Objects
- **H1 model:** nba/data/h1_ridge_model.pkl (half-time, conservative use)
- **Simulation:** Monte Carlo 10k draws, sigma=18.62 (RS), sigma=20.2 (playoffs)
- **Injury adjustment:** ORtg reduction of 1.5 pts/100 per Out/Doubtful player, capped at 4.5
- **nba/models/totals_base_model.pkl:** NOT used by live pipeline (orphan from earlier phase)
- **nba/models/variance_model.pkl:** NOT used by live pipeline (orphan)
