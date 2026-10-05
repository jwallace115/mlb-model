# NBA Sim — decision record (entries NS1, NS2, ...)

One decision doc per sport. Only the NBA sim lane appends here. Append at the END of the file.
A decision that exists only in a commit message does not exist.

### NS1 — Rules adopted from the NFL sim (2026-10-05)

Each rule below is a binding design requirement for S1+. Violations are blockers, not warnings.

**A1 — Purpose and market anchor.**
The sim targets player props via minutes/usage on availability news, Q1/H1/team totals, and same-game
joint structure. Full-game sides/totals are not the target. S1 must state in writing whether the engine
is anchored to the market (i.e., the sim's baseline is the book's line, and the model contributes a
delta) and, if not, why it could beat Pinnacle's close on the targeted markets. No design work proceeds
until this is answered and recorded.

**A2 — Temporal accessor: `as_of(source, T_utc)`.**
Every time-stamped source (odds tape, event markets, official injury reports, ESPN injuries, ESPN
finals, box/play-by-play) is accessed through a single `as_of(source, T_utc)` function that returns
only data with timestamps strictly before `T_utc`. All timestamps stored as UTC; ET conversion is
explicit via `zoneinfo.ZoneInfo("America/New_York")`. An all-source truncation-equivalence test runs
per date: rebuild with data < D vs rebuild with all data, rows for D must be byte-identical. A
planted-leak negative control is required: insert one future-dated row and verify the truncation test
catches it. No source may be queried without going through `as_of`.

**A3 — Fit-window ledger.**
See NS2 and `research/nba_sim/fit_window_ledger.md`. Updated the day anything is looked at. Every
season-object-use triple is recorded with a citing file or commit. Viewing data is a use.

**A4 — Fit through the live builder; content gates, not HEAD gates.**
Every parameter is fit through the live builder (the same code path that runs on game day). Gate on
content fingerprints (sha256 of the artifact), never on `git rev-parse HEAD` (the auto-committer
moves HEAD every 30 minutes). For every new function, `grep` for a call site reachable from `main()`;
a function that is defined but not called from the entry point does not exist.

**A5 — Join discipline and price hygiene.**
Joins use schedule event IDs and player IDs only; no name-string fallback. Every price comparison
names its scale: raw (American odds), no-vig (implied probability after vig removal), or accepted
(the price actually taken). Settle like the book (OT included for full-game, regulation-only for
H1/Q1 unless stated otherwise). Over + under symmetry check before believing any edge: compute
ROI on the opposite side of the same games at the same book's closing price.

**A6 — Raw-row admission function.**
One raw-row admission function per source, run before any dedup/groupby. HALT (sys.exit, not a
warning) with row diagnostics on any admission failure. Fuzz suite required: None, NaN, `<NA>`, `""`,
whitespace-only, wrong case, out-of-domain values, numbers-as-strings injected on a LATER row (not
just the first). Every fuzz case is a test fixture.

**A7 — Scraped-input parsing (official PDFs, any HTML).**
Real parser with an allowlist grammar. Two independent parsers must agree on the consumed set.
Context binding (URL date == header date, timestamp consistency, matchup teams play that day).
`verified_empty` is distinct from `unparsed` / `parse_failed`. Attack corpus kept as test fixtures
(>= 10 cases for text-layer mutations). Any non-ok parse status: raw input still archived, pull-log
carries the status, process exits 2. No silent "ok" on zero rows unless the grammar matched an
explicitly empty report.

**A8 — Write-once bundle for live sim.**
The live sim run reads one write-once sha256 bundle. A read-set proof logs every file the sim opened.
Manifest + sidecar = completion (the bundle is not valid until both exist).

**A9 — Gate semantics.**
Every gate HALTs the process (sys.exit with non-zero). No warning-only gates. Each gate is proven by
an executed attack through the real worker entry point (e.g., `capture_nba_availability.py main()`),
not a unit-test helper. The attack must show the gate fires and the process exits non-zero.

**A10 — Freshness and source fidelity.**
Per-team real data-through freshness tracked (no carried-forward rows counted as fresh). Quote age
<= 3 hours or the quote is flagged stale. No override of a stale quote in PRIMARY mode. Sync the
tape from origin before any Mac-side run. NBA Hard Rock key is `hardrockbet` (not `hardrockbet_fl`;
see B-D1).

**A11 — Reproducibility.**
Named per-decision RNG streams seeded with `zlib.crc32(seed_bytes)` (never `hash()`, which is
salted). Vectorised draws with `size=N`, stable sorts (mergesort / kind="stable"). Cross-machine
bit-identity test required. Every committed artifact produced by committed code. Like-for-like
metric definitions written before the first target. Constants measured from data with the derivation
stated.

**A12 — Mutation testing.**
Committed mutation script with named killing tests. No source-text tests (tests must exercise the
code path, not grep for a string). No "known reds" — a standing red is a hypothesis you have not
tested, not a fact about the suite. If a test is red, investigate it.

**A13 — Acceptance and run records.**
Acceptance criteria read from files (not hardcoded in the runner). Run records generated from the
run directory (not from the script's return value alone).

**A14 — Work-order discipline.**
<= 4 items per order. MODE PILOT|PRIMARY declared before a run. Pin a byte-identical copy of any
shared module an experiment hashes.

### NS2 — Fit-window ledger (2026-10-05)

See `research/nba_sim/fit_window_ledger.md` for the full ledger.

**Rule (binding from today):** No season 2022-23 through 2025-26 is blind to this lane. The sim may
use 2024-25 and 2025-26 for validation/holdout only if no S-design choice is tuned on them from today
forward. The first blind evidence for the NBA sim is 2026-27. Any use of data from these seasons —
including viewing summary statistics — must be recorded in the ledger on the day it happens.
