# Pre-registration — soft-book prices vs Pinnacle fair (Cowork, written before any number was computed)

Context: the CLV test (PREREG_CLV.md) FAILED — the engine does not predict Pinnacle's move. The engine's team-strength
view carries no information Pinnacle lacks. The remaining classical edge is not a better opinion but a better PRICE:
a soft book posting a price that is +EV against Pinnacle's de-vigged probability at the same moment. The sim's later
role (Test A) is to extend Pinnacle's fair price to lines Pinnacle does not hang.

Data: lines_all.parquet (Odds API history, 9 books). Outcomes from games_lines.parquet (hg, ag, home_win).
Seasons 2022-23 and 2023-24 ONLY. 2024-25 and 2025-26 stay locked as ONE confirmation run later (not in this run).

Rule (no fitted parameters):
- Snapshot: CLOSE = the last snapshot <= 6 h before puck (build_lines rule). Secondary: EARLY = the earliest snapshot
  >= 12 h before puck that has Pinnacle.
- Fair probability = Pinnacle two-way multiplicative de-vig, same snapshot, same market and same point.
- Markets: moneyline; total at Pinnacle's point; puck line +/-1.5 at Pinnacle's orientation.
- For each game x market x side: best decimal price among the 8 non-Pinnacle books at the same snapshot and point.
- EV = p_fair x best_dec - 1. Bet 1 unit when EV >= 0.02; if both sides qualify take the larger EV.
- Grading: ML incl. OT/SO; total over/under/push (push returns 0); puck line -1.5 covers if margin >= 2.

H1 (primary): CLOSE snapshot, three markets pooled, 2022-24: ROI > 0 with the 90% CI lower bound > 0 (game-clustered
SE). Also report, not as tests: EARLY snapshot ROI and CLV (Pinnacle close fair x bet price - 1); breakdowns by season,
month, market, book, EV band; bet counts. One run. If H1 fails, say so.

Known limits stated in advance: snapshot prices may be stale by up to the snapshot gap; soft books limit winners;
this measures whether the prices existed, not whether they could be filled at size.
