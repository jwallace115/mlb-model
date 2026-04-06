# NFL Model Project Brief
## Created: April 6, 2026
## Status: QUEUED — Start after WNBA opening day (May 16, 2026)

---

# NFL model brief — build differently from Vegas

## Core principle

Do not try to recreate the sportsbook's full-game spread or total with the same inputs they already dominate. Markets are usually hyper-efficient on means, averages, and static pregame observables, while the places worth attacking are state changes, regime shifts, structural archetypes, and decision-layer filtering. In this stack, WNBA totals regression died but archetypes survived; broad MLB averages were usually priced, while variance/state-transition signals were the productive lane; golf pre-event structural fit was already priced.

Vegas already prices broad team strength, public injuries, weather, and generic pace better than a standard model will. The job is to look for structural mispricing, not to build "our version of Vegas."

---

## What NOT to build first

- Full-game sides
- Full-game totals
- Moneylines
- Generic power ratings
- Season-average EPA / DVOA clones
- "QB + injuries + weather + home field = fair line"

---

## Target markets (in order)

1. 1Q / 1H derivatives
2. Selected player props
3. Team totals / drive-level derivatives
4. Live or same-game correlation work (later)

---

## Data stack

**Core historical football data**
- nflverse / nflfastR: play-by-play back to 1999, drive and series info, completion probability, CPOE, expected YAC back to 2006

**Participation / route / coverage data**
- nflverse participation data
- Pre-2023: NFL Next Gen Stats
- 2023+: FTN after season completes
- Includes route and man/zone coverage fields

**Tracking / NGS metrics**
- NFL Next Gen Stats: completion probability, expected rushing yards, route detection, time on field
- Pressure Probability and pressure rate over expected

**Odds / market data**
- Odds API: NFL h2h, spreads, totals, plus quarter/half and player props via event-level endpoints

---

## Modeling philosophy — 3 layers

**Layer 1 — Descriptive state engine (not a betting model yet)**
Label game states:
- Fast-script offense
- Slow-start offense
- Pressure-fragile pass offense
- Coverage-mismatch environment
- Red-zone compression environment
- Comeback volatility environment
- Pass-funnel / checkdown funnel environment

**Layer 2 — Market-relative test**
- Does the market already price this in the relevant derivative market?
- If yes, move on
- If no, quantify residual

**Layer 3 — Decision framework**
- When is it trustworthy?
- When does it conflict with other signals?
- When to pass?
- Shadow only or live?

---

## Four concrete branches

**Branch A — Opening-script archetypes for 1Q / 1H**
Hypothesis: Some teams are consistently mispriced early because their script quality differs from their full-game strength.

Candidate inputs:
- Neutral-situation early-down pass rate
- Scripted-drive success
- First two drives EPA / success rate
- First-quarter pace vs full-game pace
- Offensive series conversion rate early vs late
- Defensive early-drive suppression vs second-half adjustment profile
- Coordinator / QB / OL interaction

Avoid: full-game points per game, full-game totals as model inputs, season ATS records

**Branch B — Pressure/coverage interaction props**
Hypothesis: Market prices broad target share and yardage, but underprices which receiver types benefit under specific pressure and coverage environments.

Candidate inputs:
- Route participation and type mix
- Target depth
- Man vs zone tendency
- Pressure rate over expected
- Blitz/pressure interaction with checkdowns and slot funnels
- WR archetype vs coverage archetype
- TE / RB outlet role shifts under pressure

**Branch C — Drive-level team totals / first scoring opportunity**
Hypothesis: Drive-start structure and series-conversion shape may matter more for derivative markets than for main spreads/totals.

Candidate inputs:
- Early field position tendencies
- Script aggressiveness on 4th and short
- Red-zone play-call balance
- Series conversion rate
- Pass rate over expected on early downs
- Defensive bend-but-don't-break profile

**Branch D — State-transition injury lags**
Hypothesis: Market handles headline injuries well, but not always the second-order role reallocation.

Examples:
- WR2 inactive → TE/receptions up, not WR3 outside yards
- LT out → pressure/checkdown/attempt depth shift
- CB1 out → route-tree redistribution, not generic pass boost
- RB inactive → rushing attempts split, receptions change by game script

---

## Research design

**Phase 0 — Canonical table**
One row per team-game or game:
- Game metadata + opponent metadata
- Derivative market odds
- Early-drive and first-half structure features
- Injuries / actives / participation
- Drive-level and series-level historical rolling features

**Phase 1 — Archetype / regime labels**
Small interpretable families:
- Offensive script archetypes
- Defensive early-resistance archetypes
- Pressure fragility archetypes
- Coverage funnel archetypes
Keep counts low — tiny-cell explosion kills football too.

**Phase 2 — Matchup-cell tests**
Test whether specific archetype interactions move:
- 1Q scoring
- 1H team total overs/unders
- First-half success-rate residuals
- Derivative market residuals vs close

**Phase 3 — Market-relative controls**
For anything promising, control for:
- Full-game total
- Spread
- Team strength
- Obvious weather
- Major injuries already in the line
If it dies here, it was Vegas in costume.

**Phase 4 — Walk-forward / holdout**
- Freeze thresholds on train only
- Demand OOS support
- CLV as primary long-run validation metric

---

## Kill rules (defined before testing)

- No deployment before clean OOS support
- Minimum sample per candidate bucket
- Permutation or resampling gate for discovery branches
- Hard stop if effect reverses in holdout
- No promotion on thin samples even if ROI is flashy

---

## Practical architecture — 4 modules

**1. Data foundation**
- Canonical game table
- Team-game table
- Player participation / route table
- Odds archive
- Injury / inactive layer
- Market snapshots

**2. Structural feature engine**
- Drive-level features
- Series conversion features
- First-half and first-quarter rolling states
- Role redistribution flags
- Archetype labels

**3. Signal research engine**
- Hypothesis registry
- Pre-registered tests
- Holdout support
- Concentration checks
- Market-relative controls

**4. Live shadow board (only after something survives)**
- Daily board
- Shadow log
- CLV tracker
- Conflict and exclusion logic

---

## Forbidden inputs at clustering / signal-definition stage

- Closing full-game total
- Closing side
- Bookmaker implied team total
- Points per game
- Season ATS / over record

Use these only later as controls.

---

## Build order

1. Canonical NFL game + derivative odds table
2. 1Q / 1H structural feature engine
3. Small archetype / regime feasibility test
4. Derivative market residual test
5. Shadow-only board if something survives
6. Player props after that

Do NOT start with same-game parlays.

---

## What "different from Vegas" means in NFL

Not:
- "Our spread is 2.3 instead of 1.5"
- "Our total is 46.8 instead of 45.5"

Instead:
- "This team starts fast for structural reasons the main line doesn't fully capture"
- "This receiver archetype benefits disproportionately against this coverage/pressure state"
- "This 1H environment is mispriced because the market uses full-game priors"
- "This role redistribution after an injury is not being priced correctly in props"

---

## Bottom line

Build as a structural derivative-market research program, not a general game-picking model.

First shot: NFL 1Q / 1H archetype and regime engine using nflverse play-by-play, participation data, and odds history to test opening-script and early-state effects that are not obvious sportsbook proxies.
