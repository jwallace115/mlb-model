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

### N02 — Pre-kick eligibility rule and board field set (2026-09-18)
A row is eligible only if snapshot_utc < commence_time AND snapshot_utc <=
build_time. Never read files[-1] — the tape contains in-play odds.

Regression test: Pitt vs Cuse event f06e90b4, the pre-kick filter returns
point=-10.5/price=-112 (T-30min), not point=-14.5/price=+970 (T+210min
in-play). The naive files[-1] implementation returns the in-play line,
confirming the test can fail. Null control: unstarted games have identical
row counts with and without the filter.

Per game × market × side: consensus point (median), consensus no-vig implied,
best number (extreme point + book), dispersion (max-min), movement
(first-seen → latest), key-number proximity (spreads only, dist to 3/7/10/14),
n_books, newest snapshot age.

Board header: REFERENCE_ONLY from N01, book name per price.

### N03 — News, not injuries, is layer 2 for NCAAF (2026-09-18)
Re-verified: ESPN /teams/99/injuries returns {} (empty). /teams/99 has no
injuries or news key. /news?team={id}&limit=20 WORKS — returns articles with
headline, description, published (ISO8601), categories with team refs.

Team map: 191 board teams matched to ESPN IDs. 179 auto-matched (93.7%),
12 required manual correction (name variants: Hawai'i, App State, Ragin',
SE Louisiana, etc.). Map committed at ncaaf/pipeline/espn_team_map.json.

PIT rule: only articles with published < build_time are eligible. Articles
from after build_time are excluded.
