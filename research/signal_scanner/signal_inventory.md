# MLB Signal Inventory
Total signals: 70 (deduplicated from 152 raw inputs)

## Section 1: Summary
| Bucket | Count |
|--------|-------|
| baserunning | 2 |
| bullpen | 6 |
| catcher | 2 |
| defense | 2 |
| experimental | 12 |
| matchup | 8 |
| offense | 7 |
| park_weather | 5 |
| schedule_travel | 3 |
| starter | 23 |

| Tag | Count |
|-----|-------|
| NEEDS_NEW_DATA | 42 |
| READY_NOW | 25 |
| TOO_VAGUE | 3 |

## Section 2: Full Inventory
| ID | Name | Bucket | Tag | Mechanism |
|-----|------|--------|-----|------------|
| 1 | K-BB% gap between starters | starter | READY_NOW | Better K-BB pitchers suppress runs more reliably than ERA-based pricing captures |
| 2 | CSW% gap between starters | starter | READY_NOW | CSW captures dominance and command better than surface stats, especially early i |
| 3 | xFIP gap between starters | starter | READY_NOW | xFIP mismatch captures starter quality differential — validated as Signal B in F |
| 4 | Stuff+ gap between starters | starter | NEEDS_NEW_DATA | Raw pitch quality mismatches may matter more than public-facing ERA/xFIP |
| 5 | Velocity recency delta | starter | READY_NOW | Velocity drops precede ERA spikes by 2-3 starts; a leading indicator books miss |
| 6 | First-time-through-order suppression | starter | NEEDS_NEW_DATA | Elite sequencers suppress 1st TTO hitters dramatically; F5-specific value |
| 7 | Third-time-through-order collapse | starter | NEEDS_NEW_DATA | Large 3rd TTO penalties are overvalued in full-game markets, undervalued in F5 |
| 8 | Pitch efficiency (pitches per PA) | starter | READY_NOW | Inefficient pitchers create early exits and extra bullpen exposure |
| 9 | Command collapse risk | starter | NEEDS_NEW_DATA | Pitchers who both miss the zone and walk hitters are blow-up candidates |
| 10 | Instability score (BB × hard hit) | starter | NEEDS_NEW_DATA | Walks plus hard contact create explosive innings more than either stat alone |
| 11 | Whiff% gap between starters | starter | READY_NOW | Whiff rate captures swing-and-miss ability; validated in F5 RL Signal C |
| 12 | Starter stamina cliff | starter | NEEDS_NEW_DATA | Pitchers beyond recent conditioning level exit earlier than market expects |
| 13 | Platoon punishment index | starter | NEEDS_NEW_DATA | Lineups stacked against pitcher's platoon weakness create underpriced scoring |
| 14 | Pitch repertoire concentration | starter | NEEDS_NEW_DATA | One-pitch-dependent pitchers are more predictable when that pitch isn't working |
| 15 | Starter-reliever quality gap | starter | READY_NOW | Elite starters with poor bullpens are mispriced between F5 and full-game |
| 16 | Contact suppression index | starter | NEEDS_NEW_DATA | Missing bats while avoiding hard contact identifies hidden aces |
| 17 | Groundball rate | starter | READY_NOW | Groundball tendency interacts with defense, park, and lineup composition |
| 18 | Strikeout drought regression | starter | READY_NOW | If K rate lags while CSW holds, strikeout regression is imminent |
| 19 | Spin rate recovery | starter | NEEDS_NEW_DATA | Rebounding spin forecasts improving pitch quality before ERA changes |
| 20 | Two-start pitcher fatigue | starter | READY_NOW | Short rest with heavy prior workload causes velocity and command decline |
| 21 | Bullpen xFIP gap | bullpen | READY_NOW | Underlying bullpen skill may differ from recent results |
| 22 | Bullpen recent workload | bullpen | READY_NOW | Overused bullpens underperform season averages |
| 23 | Closer unavailability | bullpen | NEEDS_NEW_DATA | Missing primary closer matters more than aggregate bullpen stats suggest |
| 24 | Bullpen fatigue × quality interaction | bullpen | READY_NOW | Bad and tired is exponentially worse than either alone |
| 25 | High-leverage bullpen concentration risk | bullpen | NEEDS_NEW_DATA | Teams relying on two elite arms are fragile when those arms are unavailable |
| 26 | Bullpen handedness mismatch | bullpen | NEEDS_NEW_DATA | Some bullpens are structurally weak against one lineup handedness type |
| 27 | Team wRC+ gap | offense | READY_NOW | Offensive quality differential as priced by the model |
| 28 | Team hard-hit% gap | offense | NEEDS_NEW_DATA | Contact quality leads scoring better than runs/game |
| 29 | Lineup depth score | offense | NEEDS_NEW_DATA | Top-heavy vs balanced lineups score differently than average offense suggests |
| 30 | Team contact rate vs pitcher K rate | offense | NEEDS_NEW_DATA | Contact-heavy teams can neutralize strikeout pitchers |
| 31 | Power density (barrel × flyball) | offense | NEEDS_NEW_DATA | Teams that both barrel and elevate create disproportionate run upside |
| 32 | RISP clutch residual | offense | NEEDS_NEW_DATA | Teams that outperform with RISP may have conditional advantages |
| 33 | Leadoff OBP amplifier | offense | NEEDS_NEW_DATA | High-OBP leadoff hitters create more late-inning scoring opportunities |
| 34 | Defensive runs saved gap | defense | NEEDS_NEW_DATA | Defense suppresses scoring and preserves pitcher edges |
| 35 | Infield defense × groundball pitcher | defense | NEEDS_NEW_DATA | Groundball pitchers need strong infield support |
| 36 | Catcher framing × pitcher command | catcher | NEEDS_NEW_DATA | Elite framers add meaningful value to pitchers who throw in the zone |
| 37 | Backup catcher penalty | catcher | NEEDS_NEW_DATA | Pitchers relying on framing show measurable drops with backup catchers |
| 38 | Team baserunning pressure | baserunning | NEEDS_NEW_DATA | Baserunning pressure creates non-hit run creation |
| 39 | Stolen base suppression index | baserunning | NEEDS_NEW_DATA | Fast-delivery pitchers with elite catchers neutralize speed offenses |
| 40 | Flyball pitcher × HR park factor | park_weather | READY_NOW | Park and batted-ball shape interact strongly for run scoring |
| 41 | Wind × flyball rate | park_weather | READY_NOW | Wind matters more for elevated-contact games |
| 42 | Temperature × exit velocity | park_weather | NEEDS_NEW_DATA | Warm weather amplifies hard contact into extra bases |
| 43 | Park altitude × breaking ball pitcher | park_weather | NEEDS_NEW_DATA | High altitude reduces breaking-ball movement significantly |
| 44 | Team pull rate × park dimensions | park_weather | NEEDS_NEW_DATA | Pull-heavy teams benefit in parks rewarding pulled fly balls |
| 45 | Travel fatigue composite | schedule_travel | NEEDS_NEW_DATA | Compounded travel creates fatigue books rarely price explicitly |
| 46 | Day game after night game | schedule_travel | READY_NOW | Short recovery windows hurt offense and defense |
| 47 | Rest days differential | schedule_travel | READY_NOW | Unequal rest creates performance asymmetries |
| 48 | Umpire strike zone × pitcher command | matchup | READY_NOW | Expansive umpires benefit command pitchers disproportionately |
| 49 | Chase rate mismatch | matchup | NEEDS_NEW_DATA | Pitchers generating chase above what opponents typically chase get extra whiffs |
| 50 | Consecutive series scouting fatigue | matchup | READY_NOW | Repeated recent exposure gives hitters recognition advantages |
| 51 | Interleague familiarity deficit | matchup | READY_NOW | Unfamiliar opponents in interleague create pricing uncertainty |
| 52 | Soft-toss vs power lineup | matchup | NEEDS_NEW_DATA | Soft-tossers are vulnerable to power lineups that generate hard contact without  |
| 53 | Combined pitcher score | matchup | READY_NOW | Multi-factor pitcher quality composite captures mismatch better than any single  |
| 54 | Pitching debut overreaction | experimental | NEEDS_NEW_DATA | Debutants have no MLB scouting history; books may misprice the unknown |
| 55 | Late-season tanking signal | experimental | NEEDS_NEW_DATA | Eliminated teams deploy talent differently than season averages imply |
| 56 | Position player pitching signal | experimental | TOO_VAGUE | Blowouts ending with position-player pitchers inflate late scoring |
| 57 | Blowout revenge game | experimental | READY_NOW | Teams that lost badly come out more aggressive next game |
| 58 | Series clincher pressure | experimental | NEEDS_NEW_DATA | Teams underperform in clinching/elimination dynamics |
| 59 | Lineup protection removal | experimental | NEEDS_NEW_DATA | When the hitter behind a star is out, run production falls |
| 60 | Release point variance | experimental | NEEDS_NEW_DATA | Release-point inconsistency signals mechanical problems before ERA changes |
| 61 | Scoring cluster variance | experimental | NEEDS_NEW_DATA | High-variance offenses create different O/U dynamics than smooth offenses |
| 62 | Opener mis-sequencing | experimental | NEEDS_NEW_DATA | Openers expose top of order twice in first 3 innings |
| 63 | New pitch introduction effect | experimental | NEEDS_NEW_DATA | Pitchers adding a new pitch gain short-term deception |
| 64 | Walk-heavy inning compressor | matchup | READY_NOW | High-walk pitchers + permissive umpires + HR parks = compounding risk |
| 65 | Pitcher age × workload cliff | starter | NEEDS_NEW_DATA | Older pitchers on high workload show steeper performance cliffs |
| 66 | Knuckleball-weather amplifier | experimental | TOO_VAGUE | Knuckleball movement is highly weather-dependent |
| 67 | Shift removal BABIP inflation | starter | NEEDS_NEW_DATA | Shift-dependent groundball pitchers may still be mispriced after rule change |
| 68 | Hitter count preference exploit | matchup | READY_NOW | First-pitch aggression vs strike-first pitchers changes count quality |
| 69 | Rain delay disruption | experimental | TOO_VAGUE | Some pitchers perform far worse after interruption |
| 70 | RISP stranding skill | starter | NEEDS_NEW_DATA | Pitchers consistently stranding above FIP may have sequencing skill |

## Section 3: READY_NOW Signals
| ID | Name | Bucket | Data Source |
|-----|------|--------|-------------|
| 24 | Bullpen fatigue × quality interaction | bullpen | pitcher_game_logs + feature_table (bp_xfip) |
| 22 | Bullpen recent workload | bullpen | pitcher_game_logs (IP by reliever, game_date). Derivable fro |
| 21 | Bullpen xFIP gap | bullpen | feature_table (home_bp_xfip, away_bp_xfip), sim_inputs (bull |
| 57 | Blowout revenge game | experimental | Derivable from feature_table (scores, dates, opponents) |
| 53 | Combined pitcher score | matchup | All components in sim_inputs/feature_table |
| 51 | Interleague familiarity deficit | matchup | Derivable from schedule (home/away league, opponent history) |
| 50 | Consecutive series scouting fatigue | matchup | Derivable from schedule/feature_table game dates and opponen |
| 48 | Umpire strike zone × pitcher command | matchup | feature_table (umpire_k_rate, umpire_over_rate). Umpire data |
| 64 | Walk-heavy inning compressor | matchup | feature_table (sp_bb_pct, umpire_over_rate, park_factor_hr) |
| 68 | Hitter count preference exploit | matchup | per_start_csv (f_strike_pct, f_strike_r5). Opponent swing ne |
| 27 | Team wRC+ gap | offense | feature_table (home_wrc_plus, away_wrc_plus) |
| 40 | Flyball pitcher × HR park factor | park_weather | feature_table (park_factor_hr), pitcher_game_logs (fly_outs  |
| 41 | Wind × flyball rate | park_weather | feature_table (wind_factor_effective, wind_speed, wind_direc |
| 46 | Day game after night game | schedule_travel | feature_table (game_hour_utc, date). Derivable from schedule |
| 47 | Rest days differential | schedule_travel | feature_table (home_rest_days, away_rest_days) |
| 18 | Strikeout drought regression | starter | per_start_csv (k_count, csw_r5), pitcher_game_logs (K, BF) |
| 17 | Groundball rate | starter | feature_table (sp_gb_pct), pitcher_game_logs (ground_outs, f |
| 15 | Starter-reliever quality gap | starter | feature_table (sp_xfip, bp_xfip) |
| 11 | Whiff% gap between starters | starter | per_start_csv (whiff_r5), sim_inputs (sp_whiff_pct) |
| 8 | Pitch efficiency (pitches per PA) | starter | pitcher_game_logs (pitches, batters_faced), per_start_csv (t |
| 5 | Velocity recency delta | starter | per_start_csv (fb_velo_r3, fb_velo_season, velo_trend) |
| 3 | xFIP gap between starters | starter | feature_table, sim_inputs (sp_xfip) |
| 2 | CSW% gap between starters | starter | per_start_csv (csw_r5), sim_inputs (sp_csw_pct) |
| 20 | Two-start pitcher fatigue | starter | pitcher_game_logs (game_date, IP), per_start_csv (total_pitc |
| 1 | K-BB% gap between starters | starter | feature_table (sp_k_pct, sp_bb_pct), pitcher_game_logs (K, B |

## Section 4: NEEDS_NEW_DATA Signals
| ID | Name | Bucket | Data Needed |
|-----|------|--------|-------------|
| 39 | Stolen base suppression index | baserunning | Requires catcher pop time + pitcher delivery time |
| 38 | Team baserunning pressure | baserunning | Requires SB%, XBT% from Statcast/FanGraphs |
| 26 | Bullpen handedness mismatch | bullpen | Requires lineup composition + reliever handedness breakdown |
| 25 | High-leverage bullpen concentration risk | bullpen | Requires reliever-level leverage data |
| 23 | Closer unavailability | bullpen | Requires closer identification + recent pitch counts per rel |
| 36 | Catcher framing × pitcher command | catcher | Requires catcher framing metrics from Statcast |
| 37 | Backup catcher penalty | catcher | Requires catcher ID per game + framing data |
| 35 | Infield defense × groundball pitcher | defense | Requires infield defense metrics; gb_pct available |
| 34 | Defensive runs saved gap | defense | Requires DRS/OAA from FanGraphs or Statcast |
| 54 | Pitching debut overreaction | experimental | Debut flag derivable; scouting completeness is conceptual |
| 58 | Series clincher pressure | experimental | Requires series context tracking |
| 59 | Lineup protection removal | experimental | Requires injury data + lineup position tracking |
| 60 | Release point variance | experimental | Requires pitch-level release point data from Statcast |
| 61 | Scoring cluster variance | experimental | Requires inning-level scoring data |
| 62 | Opener mis-sequencing | experimental | Requires opener identification + lineup composition |
| 63 | New pitch introduction effect | experimental | Requires pitch-type tracking over time from Statcast |
| 55 | Late-season tanking signal | experimental | Requires playoff probability data + roster usage patterns |
| 52 | Soft-toss vs power lineup | matchup | Velocity available in per_start_csv; team exit velocity need |
| 49 | Chase rate mismatch | matchup | Requires O-Swing% from Statcast |
| 32 | RISP clutch residual | offense | Requires team RISP splits |
| 31 | Power density (barrel × flyball) | offense | Requires team barrel% and flyball% from Statcast |
| 30 | Team contact rate vs pitcher K rate | offense | Requires team contact% from Statcast; pitcher K% available |
| 28 | Team hard-hit% gap | offense | Requires team-level Statcast batted ball data |
| 33 | Leadoff OBP amplifier | offense | Requires per-game lineup position stats |
| 29 | Lineup depth score | offense | Requires per-game lineup construction with individual hitter |
| 42 | Temperature × exit velocity | park_weather | Temperature available; team exit velocity needs Statcast |
| 43 | Park altitude × breaking ball pitcher | park_weather | Altitude derivable from park lat/lon; breaking ball% needs S |
| 44 | Team pull rate × park dimensions | park_weather | Requires team pull rate from Statcast; park factors partiall |
| 45 | Travel fatigue composite | schedule_travel | Requires travel distance computation from schedule + venue c |
| 65 | Pitcher age × workload cliff | starter | Age requires roster data; workload from pitcher_game_logs |
| 4 | Stuff+ gap between starters | starter | Requires Stuff+ from Statcast pitch-level or FanGraphs Pitch |
| 19 | Spin rate recovery | starter | Requires pitch-level spin rate from Statcast |
| 16 | Contact suppression index | starter | CSW available; hard_hit_pct_allowed needs Statcast |
| 14 | Pitch repertoire concentration | starter | Requires pitch-type usage from Statcast |
| 13 | Platoon punishment index | starter | Requires lineup composition per game + platoon splits |
| 12 | Starter stamina cliff | starter | Pitch counts available; manager hook tendency needs derivati |
| 10 | Instability score (BB × hard hit) | starter | BB% available; hard_hit_pct_allowed needs Statcast pitch-lev |
| 9 | Command collapse risk | starter | Requires zone% from Statcast pitch-level data |
| 7 | Third-time-through-order collapse | starter | Requires TTO splits from Statcast/FanGraphs |
| 6 | First-time-through-order suppression | starter | Requires TTO splits from Statcast pitch-level or FanGraphs |
| 67 | Shift removal BABIP inflation | starter | Requires BABIP splits pre/post shift rule from Statcast |
| 70 | RISP stranding skill | starter | Requires strand rate + FIP from FanGraphs |
