# Pre-registration — does the engine predict Pinnacle's line move? (Cowork, written before any number was computed)

Idea: an edge that isn't in the closing price can still be in the EARLY price. If the engine's disagreement with
Pinnacle ~24 h before puck predicts which way Pinnacle moves by close, the engine carries information the market only
prices in later. That is bettable at a soft book (Hard Rock) that posts early.

Data:
- Odds API history (lines_all.parquet, NHL WO2). The engine prices come from committed price_games.py (S44 re-price,
  seed = game_id).
- early = the earliest Pinnacle snapshot >= 12 h before puck; close = the last snapshot <= 6 h before puck (the
  build_lines rule).
- Moneyline, home side, de-vigged.

Leak control:
- The engine uses the actual starting goalie, and ratings through day D-1. At the early snapshot the market may not
  know either.
- So the TEST SET excludes:
  - games where either starter is NOT his team's most-used starter that season before D;
  - games where either team played the day before.

Test (2023-24 = validate; 2022-23 reported as fit reference, same code):
- y = logit(p_close) - logit(p_early); x = logit(p_engine) - logit(p_early).
- OLS y ~ x. H1: slope > 0, 90% CI lower bound > 0.
- Also, for |p_engine - p_early| >= 0.04: the share of games where Pinnacle moved toward the engine.
- Economics: bet the engine side at the EARLY median-of-books price when edge >= 0.04 vs the early break-even;
  report ROI (actual outcomes) and CLV (close de-vigged prob minus early break-even), by month.
- One run. If H1 fails, say so.
