# Phase 2: Object State Map
Generated: 2026-04-11

## Final State Assignments

### LIVE (actively traded, validated edge)
| Object | Sport | Notes |
|--------|-------|-------|
| Core Ridge Totals Model | NBA | Venue matchup + OREB overlay + REF signal |
| ROAD_WARRIOR @ STRONG_HOME | NBA | Primary archetype matchup, live via TIER_1A/1B |

### SHADOW (running, tracked, not traded live)
| Object | Sport | Notes |
|--------|-------|-------|
| Signal B (F5 Run Line) | MLB | NEW tracker, threshold changed to 1.5 |
| CS028 bullpen blowup | MLB | Continue as before |
| CS013 bullpen deterioration | MLB | Continue as before |
| KP04 K-prop | MLB | Continue as before |
| ST02 road fatigue | MLB | Continue as before |
| CS004 | MLB | Continue as before |
| BASE_HIGH | MLB | Continue as before |
| S12_HIGH | MLB | Continue as before |
| NHL New Aligned Model A | NHL | NEW tracker, new start date |
| Playoff boards P1/P2/P4 | NBA | Continue |
| Soccer | Soccer | Continue as SHADOW until audited |
| Golf | Golf | Continue as SHADOW until audited |
| WNBA | WNBA | Continue as SHADOW until audited |
| NCAAF | NCAAF | Continue as SHADOW until audited |

### INACTIVE (slot preserved, not deployable)
| Object | Sport | Notes |
|--------|-------|-------|
| F5 Totals Engine | MLB | Slot preserved, engine not trusted |
| ADJ Hard Hit | MLB | Slot preserved, not deployable |
| ADJ Contact | MLB | Slot preserved, not deployable |
| ADJ K-rate | MLB | Slot preserved, not deployable |
| ADJ BB rate | MLB | Slot preserved, not deployable |
| ADJ Run Supp | MLB | Slot preserved, not deployable |
| BALANCED_OFF | NBA | Frozen |
| ELITE_OREB | NBA | Frozen |

### ARCHIVED (legacy, historical only)
| Object | Sport | Notes |
|--------|-------|-------|
| V1 Full-Game Totals | MLB | Historical validation void, engine still runs but record unvalidated |
| Signal class structure (BASE_LOW, S12_LOW, P09_LOW, etc.) | MLB | Dead |
| S12 Overlay | MLB | Retired |
| P09 Overlay | MLB | Dead |
| Team Totals | MLB | Never-matched |
| ELITE_DEF2 | NBA | Collapsed |
| NHL old system (MoneyPuck-dependent) | NHL | Identity-broken |
