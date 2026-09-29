# Where do NFL closing totals miss? (Cowork, 2026-09-29) — exploratory, no signal found

Question (Jeff): lines miss by ~13 points; is there a matchup type (strong O vs strong D, pace, archetype) where
they miss in a predictable direction, or where they are more/less accurate?

Design, fixed before looking: nflverse schedules (closing total + scores) and PBP 2020-25 REG. Team features are
POINT-IN-TIME: season-to-date means of PRIOR games only (offense EPA/play, defense EPA/play allowed, plays/game);
games where both teams have >= 3 prior games (n=1,327). Referee over-rate from PRIOR seasons only. Tercile cutoffs
from the discovery set only. Discovery 2020-23 (879 games), validation 2024-25 (448), validation untouched until the
bucket list was fixed. Rule: a bucket survives only if |z| >= 2 in discovery AND same sign with z >= 1 in
validation. Prices: nflverse over/under odds are ~-110 everywhere (not true closes) -> over-rate only; any ROI would
be triage-only (Check 4). A wind bucket was NOT included: its 2018-25 over rate had already been looked at.

Results (buckets_result.csv):
- Accuracy: the miss SD is 11-15 points in EVERY bucket (all games 13.3 / 12.7). No matchup type is priced
  meaningfully more or less accurately.
- Direction: 6 buckets hit |z| >= 2 in discovery (outdoors 43.1% over, |spread| < 3 39.0%, both defenses bad 39.0%,
  weeks 4-9 43.0%, non-divisional 44.6%, primetime 40.5%). **All six reversed or vanished in validation**
  (56.3%, 53.3%, 55.0%, 57.6%, 54.6%, 50.5%). Zero survive.
- Why: the whole market drifts by season (over rate 2021 45.6%, 2022 43.9%, 2023 45.6%, 2024 53.3%, 2025 52.2%;
  lines trail changes in league scoring). Every discovery bucket rode 2021-23's under years.
- The drift is not predictable from the season's first 4 weeks: betting weeks 5-9 in the direction of the weeks 1-4
  miss hit 50.8% (994 games, 2012-25; 8 of 14 seasons > 50%).

Meaning: public team-strength archetypes do not locate a totals edge; the closing total already prices them. What is
left is information the line has not absorbed yet (news, QB changes, weather at the opener) and timing (betting
before it moves), scored forward by closing-line value — the Layers design. Any archetype layer (NFL or NBA) must be
built point-in-time; the NBA archetype layer was a past leakage casualty (end-of-season aggregates).

Files: build_team_pit.py, build_game_features.py, buckets.py (paths are the verifier's scratch paths), buckets_result.csv.
