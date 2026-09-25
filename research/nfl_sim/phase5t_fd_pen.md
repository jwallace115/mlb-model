# Phase 5T Item 3 — fd_pen red diagnosis

Date: 2026-09-25. Diagnosis only; no engine change.
Sim 1.409 FD-by-penalty per team vs real 1.728. Missing: 0.319.

## Pre-registered prediction

The missing 0.32 is concentrated in automatic-first-down fouls (DPI/holding/roughing) that the
sim either lacks or prices at the no-play rate.

## Real breakdown from PBP 2021-24 REG

Total FD by penalty: 3,757 (1,087 games, 1.728/team).

**By mechanism:**
- Automatic first-down fouls: 2,913 (77.5%, 1.340/team)
- Yardage-crossed fouls: 844 (22.5%, 0.388/team)

**Top auto-FD types:**

| type | n | per team |
|------|---|---------|
| Defensive Pass Interference | 1,091 | 0.502 |
| Defensive Holding | 706 | 0.325 |
| Unnecessary Roughness | 421 | 0.194 |
| Roughing the Passer | 411 | 0.189 |
| Illegal Contact | 237 | 0.109 |
| Horse Collar Tackle | 47 | 0.022 |

**Top yardage-crossed types:**

| type | n | per team |
|------|---|---------|
| Face Mask | 218 | 0.100 |
| Illegal Use of Hands | 191 | 0.088 |
| Defensive Offside | 106 | 0.049 |
| Neutral Zone Infraction | 89 | 0.041 |

## Sim penalty model

The engine models penalties as NO-PLAY events only (p_no_play_penalty = 6.7% per scrimmage
play). When fired, the play is replaced by a penalty. Categories (from penalty_detail.json):

| category | per game | auto_first_rate |
|----------|---------|-----------------|
| defense_dpi | 1.01 | 99.2% |
| defense_auto_short | 0.80 | 99.0% |
| defense_auto_long | 0.45 | 95.3% |
| defense_noauto | 1.14 | 21.8% |
| defense_other | 0.05 | 57.1% |

Expected sim auto-FD from defensive penalties: ~2.50/game = 1.25/team.
Actual sim fd_pen: 1.409/team (includes yardage-crossed too).

## Pre-registered evaluation

**HELD.** The missing 0.32 FD/team is concentrated in auto-FD fouls. The sim's category model
has high auto_first rates (99%+ for DPI/holding/roughing), so the per-penalty auto-FD rate is
correct. The deficit comes from the TOTAL COUNT of these penalties:

The sim only fires penalties as NO-PLAY events. In reality, many first-down-by-penalty events
come from LIVE-PLAY penalties: DPI during a pass play, defensive holding during a run, roughing
on a sack. These are plays where the penalty occurred during the play, the penalty is accepted,
and the automatic first down replaces the play result. The engine cannot produce these because
its penalty model fires INSTEAD of the play (no-play), not DURING it.

The ~9.3 no-play penalties/game the sim produces are close to the real ~9.7 no-play penalty
rate. But real football also has ~3-4 accepted live-play penalties per game, many of which carry
automatic first downs. The sim has NO mechanism for live-play penalties.

## Null check

off_pen (5.73, tol 0.5) and def_pen (3.58, tol 0.5) are PASS and not touched.

## NOT DONE
- Adding a live-play penalty mechanism (would require a new penalty branch that fires DURING
  a play, not instead of it).
- Quantifying the exact split of real FD-by-penalty into no-play vs live-play categories.

## UNVERIFIED
- Whether the ~0.32 gap is entirely from missing live-play penalties or partly from the
  no-play rate being slightly low (6.7% sim vs 7.2% real).
