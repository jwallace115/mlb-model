# Multi-Sport Market Inventory

## NBA (basketball_nba)
Test event: DET @ BOS, 2025-12-16

### Approved Prop Markets (10)
| Market | Players | Books |
|--------|---------|-------|
| player_points | 17 | 8 |
| player_rebounds | 17 | 8 |
| player_assists | 15 | 8 |
| player_points_rebounds_assists | 15 | 7 |
| player_threes | 14 | 8 |
| player_blocks | 11 | 4 |
| player_steals | 5 | 3 |
| player_points_assists | 13 | 4 |
| player_points_rebounds | 12 | 4 |
| player_rebounds_assists | 11 | 4 |

### Rejected: player_turnovers (no data), player_double_double (kept), all half/quarter markets (no data)

### Approved Core Markets (4)
totals, spreads, h2h, team_totals

### Batches
- A: player_points,player_rebounds,player_assists,player_points_rebounds_assists,player_threes
- B: player_blocks,player_steals,player_points_assists,player_points_rebounds,player_rebounds_assists,player_double_double
- C: totals,spreads,h2h,team_totals

## NFL (americanfootball_nfl)
Test event: WSH @ MIA, 2025-11-16

### Approved Prop Markets (10)
| Market | Players | Books |
|--------|---------|-------|
| player_pass_yds | 2 | 8 |
| player_pass_tds | 2 | 8 |
| player_pass_attempts | 2 | 7 |
| player_pass_completions | 2 | 7 |
| player_pass_interceptions | 2 | 6 |
| player_rush_yds | 6 | 8 |
| player_rush_attempts | 4 | 7 |
| player_reception_yds | 13 | 8 |
| player_receptions | 14 | 8 |
| player_anytime_td | 36 | 8 |

### Approved Core Markets (4)
totals, spreads, h2h, team_totals

### Batches
- A: player_pass_yds,player_pass_tds,player_pass_attempts,player_pass_completions,player_pass_interceptions
- B: player_rush_yds,player_rush_attempts,player_reception_yds,player_receptions,player_anytime_td
- C: totals,spreads,h2h,team_totals

## NHL (icehockey_nhl)
Test event: ANA @ NYR, 2025-12-16

### Approved Prop Markets (5)
| Market | Players | Books |
|--------|---------|-------|
| player_points | 16 | 3 |
| player_goals | 41 | 2 |
| player_assists | 15 | 2 |
| player_shots_on_goal | 17 | 7 |
| player_power_play_points | 13 | 3 |

### Rejected: goalie_saves (no data), all period markets (no data)

### Approved Core Markets (4)
totals, spreads, h2h, team_totals

### Batches
- A: player_points,player_goals,player_assists,player_shots_on_goal,player_power_play_points
- C: totals,spreads,h2h,team_totals
