# Rink scorer bias -> shots-on-goal props — pre-registration (written before the bias numbers or any prop-by-arena view)

Idea (published hockey-analytics finding, not ours): arena scorekeepers record shots differently, so some rinks
inflate or deflate recorded shots on goal. SOG props are settled on the recorded count; if books price players off
season averages without a rink adjustment, road/home SOG lines at biased rinks are mispriced.

## Estimate (2021-22 .. 2023-24 play-by-play only; no prices)
For each arena (home team) and season: rink factor = SOG recorded in games at that arena / SOG expected from the two
teams' shots in their OTHER games (home team's road games, visitor's road-and-home games excluding this arena),
pooled over the seasons. Stability: correlate each arena's factor season-to-season (2021 vs 2022, 2022 vs 2023).

## Test (2025-26 SOG props, 7 books, ~5 min pre-puck; graded on the official count)
- Arenas in the top quartile of the 2021-24 rink factor -> Over; bottom quartile -> Under. Every SOG line (1.5/2.5/3.5)
  of every player in games at those arenas.
- y - p vs the consensus de-vigged Over probability, game-clustered z; ROI at the median book price for the bet side.
- PASS = the pooled bet side beats its fair probability with z >= 1.64 AND ROI > 0 at the median price, same sign
  in both halves of 2025-26 (Oct-Dec, Jan-Mar).
- Expected (stated now): the rink factors are stable (season-to-season r > 0.4), and the prop test FAILS (books
  already adjust). A pass is a candidate for forward logging at Hard Rock prices, not a result on its own.
- Caveat: 2025-26 props were used in phase 2 of the edge hunt (generic conditions, not arena). Arena was never a
  condition there.
