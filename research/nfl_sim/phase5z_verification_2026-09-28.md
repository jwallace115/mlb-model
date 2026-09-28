# Phase 5Z verification — Cowork, 2026-09-28

Branch `eng/5z` @ `cd160a3` (D177 and D178 commits, D179 only in the session-log commit; base = the 5Y merge).
Read from the committed files; engine diff read line by line.

## Item 0 (D177) — accepted; the class table finally exists and it names the cause
- Tables (a)-(c) delivered. Log-only engine change; player-OFF hash 80848eefb5a45062 unchanged for the new fingerprint.
- The MIX/RATE totals (+74.9 / -77.0 s) cancel by construction: regulation clock is 3,600 s on both sides, so "more
  snaps" and "shorter snaps" are the same fact (pre-registration (1) was mine and ill-posed; its FAIL carries no
  information). What carries information is WHERE the rate shortfall sits, table (c):
  **timeout_followed -49.1 s a game** (sim 8.9 s per snap vs real 18.0; and 2.2 such snaps a game vs 5.4), run -10.3,
  kneel -9.8 (20.3 vs 26.8 s), first_down_rush -8.4. Run / complete / first-down-pass rates now match within 1 s —
  the 5X-5Y fixes worked. The 77 s shortfall is ~2.7 plays: the whole remaining K1 gap (+2.5).
- Mechanism (read in engine.py `_apply_timeouts`): a timeout sets the play's class to `stop_code`, so the runoff is
  drawn from the INCOMPLETE cell (~8 s). Real plays followed by a timeout run 18 s to the stoppage. The sim also
  calls far fewer timeouts (2.2 vs 5.4 timeout-followed snaps a game).
- Gaps vs the order: sack merged into complete_inbounds; the all-1,087-games real table loaded but not reported; the
  real side does not reconcile to 900 s in Q4 (888 s — last plays of halves/games have no next snap); reported, not
  hidden.

## Item 1 (D178) — the count is right; the diagnosis and the proposed fix are wrong
- Sim 0.072 safeties a game, all from the "pre-snap" roll. But the sack and run safety masks being zeros is BY DESIGN
  since 5A-7: the engine replaced the mechanistic branches with MEASURED per-play safety rates by own-goal-line zone
  (constants.json `safety_rate_by_zone`: 98-100 4.06%, 95-97 1.66%, 90-94 0.20%; 45 safeties on pass/run plays in
  2021-24). "Enable the mechanistic branches and reduce the pre-snap rate" would throw away a measured rate for an
  unmeasured one and double-count. Rejected.
- The comparison that matters: real safeties on pass/run plays are 45 in 1,087 games = 0.041 a game; the sim makes
  0.072 with the same per-snap rates — so either the sim has ~1.75x the real number of snaps inside its own 10, or the
  roll is applied to steps that are not scrimmage snaps. The order asked for the per-snap rate inside own 5 / own 10;
  it was not delivered. -> next order.

## Item 2 (D179) — not done, and not declared "NOT DONE" as the order required
- Drives 23.20 vs 21.74 (read); the excess is in own 21-40 (+1.84; 15.29 vs 13.45), own 1-20 slightly FEWER (4.38 vs
  4.45) — prediction (1) FAILED, stated. The start-mix vs efficiency split (the item's deliverable) was not computed
  ("real pts/drive by bucket needed") and no table was committed. Under this order's hard rule the decision should
  have read "ITEM NOT DONE". -> next order.

## Verdict
Merge (diagnosis tooling + log-only counters). The clock question is answered: the remaining plays excess is the
timeout path (runoff drawn from the incomplete cell) plus short kneels. Next order fixes those two with measured
tables, measures the safety roll properly, completes the points-per-drive split, and re-fits once.
