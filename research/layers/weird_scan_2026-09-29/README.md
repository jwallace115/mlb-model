# "Get weird" scan — cross-market patterns in props and game lines (Cowork, 2026-09-29)

Jeff: look across every line for odd correlations (e.g. "when a QB's prop is above X the over hits 80%", "when RB1's
carries line is X the game over hits"). Data: 72,978 consensus closing prop lines with outcomes 2023-24 (K4 rows,
eng/6b `phase6b_k4.parquet`), nflverse closing spread/total + scores, players mapped to teams from nflverse weekly.

Design fixed before looking: 88 cells in three families — T (prop-implied offense vs the game total -> over),
S (prop-implied game script vs the spread -> cover), P (prop over-hit vs its own de-vigged price by line level and by
juice). Fits and tercile/quintile cutoffs from 2023 only; 2024 held out. Survive = |z| >= 2.58 in 2023 AND same sign
with |z| >= 1.65 in 2024. Prop prices = consensus close (real); game-line odds from nflverse (~-110, triage only).

Result: 7 of 88 cells cleared 2023; 2 survived 2024, and both are one phenomenon — rushing-yards ALT lines about 11
yards BELOW the main line (1-2 books, over heavily juiced): overs hit ~4-5 points less than priced. Counted per
player-game (rows within a player-game are correlated), the under returns +3.7% (2023, se 5.4%) and +7.6% (2024,
se 5.3%) — not significant. Practical reading: one-sided "To Record 40+ Rushing Yards" overs are poor parlay legs.
Nothing else survived: no QB-prop threshold, no RB-carries -> total, no script -> cover effect.
Watch item (not a signal): when the props' yardage implies MORE than the game total (top third), the over hit
43.5% / 45.0% (T1) and 41.4% / 41.5% (T3) in 2023 / 2024 — same sign both years, not significant (combined z ~ -1.9
for T3). Cheap to test forward: we capture 10-book props and totals.
