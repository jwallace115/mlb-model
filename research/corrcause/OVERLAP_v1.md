# Overlap analysis: CC Tier 1 vs 2026-09-29 edge hunt scan

Reference: `research/layers/nhl_edge_hunt_2026-09-29/README.md` (the old scan).
Old scan: 4,115 cells (123 single conditions + pairwise combinations, n ≥ 200 in discovery),
outcomes ML and totals, seasons 2007-08..2022-23 (D/V/H splits). 0 survivors.

## NHL Tier 1

| Cell | Status | Detail |
|---|---|---|
| NH1 — Total pushed DOWN a full key step | **NEW** | Old scan's total conditions were static line bands (≤5.5, 6, 6.5, ≥7). No opener→close MOVE was a condition — the old scan "used closing lines only (no opener→close moves)" (per registry §1 CHECK 2). The opener→close total move is a market-behaviour variable absent from the old grammar. |
| NH2 — Total pushed UP a full key step | **NEW** | Mirror of NH1; same reasoning. |
| NH3 — Soft-only moneyline move | **NEW** | Old scan used only SBRO closing prices (one book). Multi-book data (Pinnacle + soft books) was not available for the scan's discovery/validation seasons (2007-19). The soft-vs-Pinnacle divergence at close is a market-behaviour variable the old grammar could not express. |
| NH4 — Backup-goalie overshoot | **SIMILAR** to old "backup" / "backup_vs_primary" cells, **but different hypothesis and variable** | Old scan tested `HOME:backup`, `AWAY:backup`, `HOME:backup_vs_primary`, `AWAY:backup_vs_primary` as standalone conditions (ML and totals outcomes). NH4 adds a market-behaviour requirement: Pinnacle ML moved ≥ 2 pts against the backup's team from opener to close. The opener→close ML move is absent from the old scan. Additionally, A-01 and A-02 R3 tested the engine's information and coefficient in backup games, not a market overshoot. 2024-25 was touched by R3 → NH4 confirms FORWARD only per registry §3. |
| NH5 — Post-OT road B2B with travel | **NEW** (triple interaction) | Old scan had B2B conditions: `b2b_opp_not`, `b2b`, `goalie_b2b`, `both_b2b` and `last_ot_loss`. Pairwise combinations were tested (e.g., `rest3plus & last_ot_loss`). BUT: (a) the specific triple B2B + road + game-1-OT/SO + ≥1-timezone-change was not tested (old scan only tested pairs, not triples); (b) grep for "b2b.*ot" and "ot.*b2b" in `scan_results.csv` returns 0 rows — even the B2B×OT pair was not in the scan (likely because `last_ot_loss` refers to the team that LOST in OT, while NH5 fires on any game-1 that WENT to OT regardless of which team won). |
| NH6 — Empty-net-inflated favourite | **NEW** | Old scan's form conditions included `goal difference vs xG difference ≥ +/−0.3/game`, `PDO ≥ 1.02`, `lucky`/`unlucky` — these capture PDO broadly but NOT empty-net goal differential specifically. Grep for "empty", "EN_", "en_goal" in `scan_results.csv` returns 0 rows. The EN-stripped differential is a new variable. The old README §5C/E discusses EN goals descriptively but never tested them as a pre-game condition. |
| NH7 — Both rested ≥ 4 days | **SIMILAR** to old rest cells, differences in threshold and scope | Old scan had `rest3plus` (≥3 days, per team) and pairs like `HOME:rest3plus & HOME:rest_adv2`. It did NOT have a "both teams rested ≥ 4 days" cell — grep for "both.*rest" returns 0 in the cell name column. The closest cells are `HOME:rest3plus & GAME:both_primary` (both teams' primary goalie + home rested 3+) tested at n=1,079/1,310 on totals. NH7 differs: threshold is ≥4 (not ≥3), requires BOTH teams (not just one), and the totals-under mechanism (rust→lower finishing) is distinct from the rest cells' ML outcomes. However, the situational content overlaps — NH7 can pass the screen but can only confirm **FORWARD** (not on 2024-25) because rest-as-a-totals-condition was in the old grammar's totals arm. |

## NHL Tier 2

All 8 NHL Tier 2 features are market-behaviour variables: opener ML/total band, Pinnacle ML/total move,
soft–Pinnacle divergence, move timing, book-consensus dispersion, in-play first-snapshot reset. **None were
in the old scan's grammar** (which used SBRO single-book closing prices only). Confirmed NEW.

## Confirm eligibility summary

Per registry §3, a NHL cell whose defining variable is a market-behaviour variable absent from the old scan can
confirm on 2024-25. Cells whose defining variable was in the old scan confirm FORWARD only.

| Cell | Can confirm on 2024-25? |
|---|---|
| NH1 | YES (opener→close total move: new) |
| NH2 | YES (opener→close total move: new) |
| NH3 | YES (soft–Pinnacle divergence: new) |
| NH4 | NO (backup status was in old scan; market-move component is secondary) → FORWARD only |
| NH5 | YES if treated as new (triple interaction was not testable in old scan's grammar) |
| NH6 | YES (EN-goal differential: new variable) |
| NH7 | NO (rest × totals was in old scan, albeit with different threshold) → FORWARD only |
| NHL Tier 2 | YES (all market-behaviour features: new) |
