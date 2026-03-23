# NBA Active Signal Boards — Master Systems Reference

Generated: 2026-03-23

## Board 1A — CORE Venue (DAL/UTA/PHI @ IND/OKC/SAS)
- Signal: OVER
- Sizing: 1.5u
- N: 40, Hit: 77.5%, ME: +10.93, 3/3 seasons consistent
- Standalone — does not stack with OREB or other modifiers

## Board 1B — Pruned Venue + OREB
- Signal: OVER
- Sizing: 1.5u
- Condition: ROAD_WARRIOR away @ STRONG_HOME home + OREB confirmation
- ROAD_WARRIOR: ATL, CHI, DAL, DET, GSW, HOU, NYK, PHI, PHX, UTA
- STRONG_HOME: ATL, BOS, DEN, IND, MIL, OKC, POR, SAS

## Board 2 — Pruned Venue Standalone
- Signal: OVER
- Sizing: 1.0u
- N: 236, Hit: 64.3%, ME: +6.65, 3/3 seasons
- ROAD_WARRIOR @ STRONG_HOME without OREB confirmation

## Board 5 — Referee Crew Tendency
- Signal: crew_high_count >= 2 → OVER | crew_high_count = 0 → UNDER
- crew_high_count = number of top-quartile scoring refs assigned (19 refs in list)

### Validation results:
- crew_high=2: regulation ME=+3.35, p=0.001, N=285, 3/3 seasons
  - Season splits: +5.81 / +4.70 / +5.59 (full), +3.35 regulation
- crew_high=0: regulation ME=-2.20, p<0.001, N=1043, 3/3 seasons
- Venue independence: ME=+5.11 non-Venue (95% retained), p<0.0001
- OT flag: elevated OT rate (8.1% vs 3.4%, p<0.001) — size off regulation ME
- Season stability: 3/3 (tightest range of any signal: 4.70-5.81)
- Line band: flat across all bands (+5.38/+5.47/+5.44) — not band-specific
- Distribution: median ME=+4.50 (broad, not tail-driven)
- Team concentration: no team >9.4% of crew_high=2 games

### Sizing:
- REF_OVER (crew_high >= 2): +0.5u modifier on existing OVER signals (cap 2.0u)
- REF_UNDER (crew_high = 0): 0.75u standalone UNDER, or +0.25u on existing UNDER
- CONFLICT: ref direction opposes existing signal → do not bet
- NONE/UNKNOWN: no adjustment

### Timing:
- Refs available ~90 min pre-tip
- Scrape at 6:30 PM daily via nba/ref_scrape.py (launchd job)

### crew_high=3 (N=33, ME=+9.82):
- Tracked separately via crew_high_exact column
- Not sized differently yet — insufficient N for standalone deployment

## Playoff Boards (April 19+)

### Board P1 — Round 1 Early UNDER
- Signal: R1 Games 1-2 → UNDER
- Sizing: 1.0u
- ME: -6.82, 3/3 seasons (-3.94 / -10.41 / -6.12)

### Board P2 — Round 1 Late OVER
- Signal: R1 Games 5-7 → OVER
- Sizing: 0.75u
- ME: +8.19, 3/3 seasons (+6.40 / +4.85 / +12.86)

### Board P4 — Conference Finals Early OVER
- Signal: CF Games 1-4 non-elimination → OVER
- Sizing: 0.75u
- ME: +9.85, 3/3 seasons (+11.33 / +13.75 / +14.06)

### Finals Modifier
- All Finals games: reduce OVER sizing by 0.25u
- N=17, 82.4% UNDER, ME=-11.29

### Paused in Playoffs:
- Venue OVER — reverses in playoffs (ME flips to -5.04)
- Shot UNDER — reverses in playoffs

## DO NOT BET
- Pace UNDER: 44.0% hit, -16.1% ROI
- Shot UNDER: 47.9% hit, -8.6% ROI
- Shot OVER standalone (former TIER_3): removed

## NULL Signals Tested (no deployment)
- Meeting number: p=0.647 (NULL)
- Free throw environment: p=0.215 (NULL, not independent of Venue)
- 3PAr pairing: p=0.298 (NULL, not independent of Venue)
