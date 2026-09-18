# NCAAF Parlay Board — DECISION LOG v1

Numbered `N01…`, deliberately separate from the `D…` series in
`research/nfl_sim/NFL_SIM_DECISION_v1.md` so the two never collide.

**Contract (from `CLAUDE.md` § WORK ORDERS):** any work-order item that makes a decision
writes its `### NNN — title (date)` entry here **in that same commit**. A decision that
exists only in a commit message does not exist. This has already gone wrong twice on the NFL
side (D59–D61, then D62–D65).

Governing spec: `research/ncaaf_board/NCAAF_BOARD_SPEC_v1.md`.

---

<!-- entries begin -->

### N01 — Book and market universe for NCAAF (2026-09-18)
Probe: 10-book request against americanfootball_ncaaf. hardrockbet_fl absent
from all 90 events. Null control PASS: hardrockbet_fl present on NFL (15/29).

Available books (9 of 10): DK (89), FD (85), BetRivers (75), BetOnline (73),
Bovada (73), BetMGM (72), Pinnacle (72), LowVig (71), Caesars (32).
Cost: 3 credits/call (h2h+spreads+totals in the existing tape).

Per-event probe: team_totals (6 books), alt spreads/totals (7), 1H markets (7).
Player props not tested.

REFERENCE_ONLY: every NCAAF price is from a book Jeff cannot bet.
Pre-registered predictions A (HR absent) and B (team_totals available): both HELD.
