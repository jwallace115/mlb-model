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

### N04 — Ticket schema, AI output boundary, CLV convention (2026-09-18)
AI layer: one Anthropic call per game (claude-sonnet-4-20250514). Permitted outputs:
  (1) structured flags with headline + published source
  (2) prose rationale
  (3) binary veto with reason
Any numeric pricing field is discarded and logged. An AI-produced number
would be an unvalidated model.

Ticket schema: event_id, home_team, away_team, commence_time, legs (market,
side, point, price, book, implied), ai_flags, ai_rationale, build_time,
reference_only (True per N01), close_price (null, filled by grader),
clv (null, filled by grader), graded (bool).

CLV: no-vig scale, game identity (event_id), push = void (D64 convention).
Closing price = last snapshot strictly before commence_time.
Grader is UPDATE-ONLY: never appends, never re-grades.

Ticket log: ncaaf/logs/ncaaf_board_tickets_2026.json (append-only).
.gitignore allow-listed at line 49.

SPORT_MAP in shared/clv_utils.py updated: "NCAAF" -> "americanfootball_ncaaf".

### N05 — 2025 held-out data; spread is the close, spreadOpen is pre-game (2026-09-18)
cfbd_games_2025.parquet: 3,831 games (3,829 with scores).
cfbd_betting_lines_2025.parquet: 3,345 rows. Bovada: 934 rows, all with
spread + overUnder + both scores (comparable to ~840/yr in 2022-24).
Other providers: ESPN Bet 1,542, DraftKings 805+64.

spread vs spreadOpen: differ on 84.8% of Bovada 2025 rows. Examples show
`spread` tracks the closing line (moves with market), `spreadOpen` is the
opening line available pre-game. For any downstream build that conditions
on a line available when a bet is placed, `spreadOpen` must be used.

cfbd_games_2026.parquet: 3,679 games (757 with scores — season in progress).
Written to SEPARATE files from the 2022-24 data to preserve the audit
guarantee that 2025 was untouched during the exploratory probe.

### N06 — Blowout correlation survives OOS on 2025 (2026-09-18)
Null control PASS: P(cover)=0.524, P(over)=0.496 (both within 3pp of 0.50).
2025 Bovada, N=904 (after dropping pushes).

Pre-registered predictions:
  1. 21+ phi positive ~0.10-0.25: phi=0.280, t=3.94 — **HELD** (larger than 2022-24).
  2. 14-21 positive but smaller: phi=0.148, t=1.69 — **HELD** (positive, below 21+).
  3. 0-3, 3-7, 7-14 flat |t|<2: 0-3 t=-1.66, 3-7 t=0.92, 7-14 t=2.27 — **DID NOT HOLD**
     (7-14 has t=2.27, breaking the prediction).

The blowout correlation (|spread| >= 14) survived out of sample. The 21+
bucket is the strongest result in both windows: phi=0.196 (N=363) discovery,
phi=0.280 (N=198) validation — combined N=561.

Branch decision: **Branch A** — build the joint outcome table for |spread| >= 14.

### N07 — Joint outcome table v1, Branch A (2026-09-18)
joint_outcome_table_v1.parquet: 8 cells keyed on (spread_bucket, total_bucket),
holding empirical P(cover & over), P(cover & under), P(miss & over), P(miss & under).
Restricted to |spread| >= 14 (the buckets that survived N06).

By spread bucket (2022-2025 combined, N=1119):
  14-21: N=523, phi=0.084, t=1.93 (marginal, but consistently positive)
  21+:   N=596, phi=0.224, t=5.48 (strong, all 4 seasons positive)

By season: 2022 phi=0.135 t=2.32, 2023 phi=0.093 t=1.54,
2024 phi=0.177 t=2.62, 2025 phi=0.227 t=4.12.

Generator: ncaaf/pipeline/build_joint_table.py (committed code, reproducible).
Spec checks 1b, 2, 3 updated from N/A to REQUIRES ATTENTION — the joint table
is the first fitted object and introduces provenance requirements.
