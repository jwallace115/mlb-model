# Sim-engine lessons from the NFL sim (24 audits, D1–D282): what NHL and NBA should adopt now

Written by the NFL chat (Cowork), 2026-10-05.
- **Sources:**
  - ChatGPT audits #1–#24 (claude/chatgpt_audit*_reply_* and *_adjudication_*);
  - the NFL decision log;
  - the NFL verification docs;
  - claude/pipeline_audit_2026-10-01.md and claude/line_pull_audit_2026-10-04.md.
- **Lane facts** below come from NHL/NBA docs last written about 2026-10-01 (the status files are still stubs). Each lane
  should re-check them against its own files.

## Why this exists

The NFL sim took 24 ChatGPT audits to reach its first GO (MNF, 2026-10-05). Eleven of the last twelve audits were NO-GO.
Almost every cycle was spent retrofitting things that could have been designed in on day one:
- run bundles and provenance (audits #6–#13);
- raw-row admission (#14–#20);
- a scraped-HTML parser (#19–#23).

Three prime-time windows were lost as primaries while that happened. NHL and NBA are early enough to skip most of it.

**The one-sentence version:** decide what the sim is for, make every input point-in-time and admitted by a strict schema,
have the live run read only a hashed bundle, make every gate HALT and prove each gate by an attack through the real
worker, and verify every claim from files rather than from the report.

---

## Part A. The fourteen rules (each with the NFL evidence behind it)

### A1. Decide what the sim is for before building physics
- **NFL evidence:**
  - About 25 engine orders (5A–6E) chased K1 realism, and K4 never moved: prop Brier was 0.2534 against the book's 0.2316,
    worse in all 8 families.
  - A sim anchored to the market line has no game-line edge by construction (D209 was withdrawn).
  - Prop accuracy lives in the usage/availability layer, not the engine.
- **Rule:** if you anchor to the market, your only possible value is props and joint structure. In that case, put effort
  first into availability and usage:
  - NHL: goalie confirmation, line combinations, TOI;
  - NBA: minutes and rotation, injury status.
  - If you do not anchor, you need a written argument for why the engine beats Pinnacle.
- **NHL check:** "The pre-game engine does not beat the market" (s4c), and the only live lead is a price rule (EV2, L-004).
  Is more engine work justified?

### A2. One as-of accessor for every time-stamped source, plus an all-source point-in-time test
- **NFL evidence:**
  - The worst contamination was a depth-chart merge with no season or week, which pushed future roles into 2021–24 usage.
    It voided every player map and K4 (A2 Q2; D59).
  - The PIT test missed it because it truncated play-by-play only.
  - The same bug came back through a sibling path (the QB fallback, A5).
  - Lines read the newest snapshot without checking `< commence_time`.
  - Eastern-time `gametime` was parsed as UTC.
  - League means were computed over the whole frame (A1 #4).
- **Rule:**
  - Every source (rosters, injuries, depth/lines, odds, news, goalie or minutes feeds) is read only through
    `as_of(source, T)`.
  - Store times in UTC and convert league local times explicitly.
  - **Truncation-equivalence test:** rebuild from data before date D and from all data; the rows for D must be
    byte-identical. Run it for several D values, truncate EVERY source, and include a negative control that fails on a
    planted leak.
  - Make it a standing test that runs per date for nightly sports.

### A3. Write a fit-window ledger; a holdout is consumed the moment anyone looks at it
- **NFL evidence:**
  - 2025 was scored once, and then tiers were chosen with 2025 in view (D19).
  - A shrinkage weight was tuned inside the holdout, and its "20–47% gain" vanished through the live builder (D131).
  - Maps fitted under pre-2025 rules were applied to a season with new rules, and that transfer was never tested; totals
    Brier got worse (0.2419 → 0.2456).
- **Rule:**
  - Keep one table, per season, of discovery / validation / consumed / prospective, and update it the day anything is
    looked at.
  - Before live pricing, treat any rule change as a regime break and run a transfer test.
- **NHL check:** per the docs, 2024-25 was priced in full (the S48-R6 confirmation), EV2 was confirmed on 2024-26, and
  2025-26 was used as a scan holdout. So S-WO5's "locked 2024-25 + 2025-26" is not blind. Write that down before S-WO5
  reports anything.
- **NBA check:** the plan's holdouts (game lines 2024-26, props 2025-26) are clean only if nothing has touched them. RW@SH
  lists were tuned on 2022-25, so those seasons are not out-of-sample for anything RW@SH-related.

### A4. The research object must BE the live object
- **NFL evidence:**
  - Maps were fitted with a 4-step N=1,000 solver, while live used an 8-step N=10,000 solver (D18).
  - The pricer was "wired" by an import with no call site (D80).
  - A metadata gate wrote "SUPPRESSED" into the markdown, and nothing read it (D79).
  - `run_week` read the shared ratings instead of the bundle copy (A8).
  - Every pilot ran on week-1 usage, because the refresh never rebuilt usage and a carried-forward row passed the
    freshness gate (claude/nfl_sim_engine_inputs_finding_2026-10-02.md).
- **Rule:**
  - Fit every parameter through the exact live builder.
  - For every new function, grep for a call site reachable from `main()`.
  - Gate on the content fingerprint of the fit, never on `git HEAD`, which the auto-committer moves every 30 minutes.
- **NHL check:** C-01 means S41–S48 and L-001 came from a non-designed object. `constants_v8` in a worktree differs from
  main.

### A5. Join on IDs only; price comparisons name their scale; settle like the book
- **NFL evidence:**
  - Matching on last name manufactured a "+2.1pp edge" that was −5.4pp with player_id (D17).
  - Close lookups matched on (name, market, line) with `.iloc[0]` and no game.
  - Grading matched games by team pair.
  - Raw and no-vig prices were mixed in CLV three times (D58, D64, D82); an unchanged −110/−110 showed +2.4pp CLV.
  - Dropping kneels manufactured a +18.2% (t=5.3) QB rush-attempt ROI that was really −4.5% (D62).
  - An inactive player's Under graded as a WIN.
- **Rule:**
  - Join only on schedule-derived game/event ids and player ids, with no name fallback.
  - Every price comparison states the scale of each side (raw, no-vig, accepted).
  - Settle with the book's official stat definitions, push and void rules.
  - **Symmetry check before believing any edge:** over ROI + under ROI ≈ −vig.
  - Any anomaly in the outcome-graded metric is a grader bug until proven otherwise.

### A6. Raw-row admission: one schema, run before any dedup or groupby, in every loader and at bundle build
- **NFL evidence (audits #14–#20, seven cycles):**
  - duplicate rows where the gate kept the last row and the consumer used any;
  - a NaT key counted as present;
  - `<NA>` seasons skipped by `(<NA> != s).any()`;
  - `nunique` ignoring NaN;
  - `groupby` silently dropping null keys;
  - `posteam=None`, then `""`, then lowercase.
  - Each patch closed one spelling, and each new spelling moved calibrated probabilities by 5–14 pp.
- **Rule:**
  - "Do not make groupby's null-dropping behavior the policy" (#18).
  - One admission function per source checks dtype, non-null, non-blank, domain (team codes, dates, periods), and
    context invariants derived from counts over the real data.
  - It HALTs with row diagnostics before any write.
  - Its fuzz tests put None, NaN, `<NA>`, `""`, whitespace, wrong case, out-of-domain values and numbers stored as strings
    on a LATER row of an otherwise valid group.

### A7. Scraped inputs: a real parser, an allowlist grammar, two parsers that must agree, and the context bound
This is the single most expensive lesson: five audit cycles (#19–#23) on one injury page.
- **NFL evidence.** Each audit found another way for the parser to read a different status than a human sees:
  - multiple `<tbody>`;
  - a six-cell row;
  - a `display:n&#111;ne` encoded style;
  - `aria-label="<!--"` deleting a visible Out.
- **Root causes:**
  - a regex pipeline guarded by a denylist;
  - validation and extraction running on different representations;
  - an "independent" row count blind to defects inside rows;
  - hashes mistaken for meaning ("a valid manifest proves which bytes were used, not that the parser retained their
    meaning", #20).
- **Rule, for NHL goalie-confirmation HTML (DailyFaceoff, LeftWingLock and the like), NBA injury-report PDFs, and any
  lineup page:**
  1. Use a real parser (html5lib/lxml; a PDF table extractor), never regex.
  2. Declare the exact grammar (table shape, cell count, allowed tags, attributes and classes) and HALT on anything else.
     A false HALT is cheap; a false admit is not.
  3. **Differential parse:** a second, independent parser must give the identical consumed set (team, player_id,
     status), or HALT.
  4. **Bind the context:**
     - expected and final URL;
     - HTTP 200;
     - date and game identity on the page;
     - each team's opponent reconciled with the schedule;
     - retrieval time timezone-aware and inside [publication deadline, cutoff T].
  5. "Verified empty" is different from "missing or unparsed". Never use a quota such as "75% of teams have a status".
  6. Before the first audit, run an attack corpus over the REAL capture through the full refresh → builder → worker path.
     Keep the corpus as regression fixtures. A probe decides only if it is "ADMITTED with a changed consumed set".

### A8. The live run reads one immutable, hashed bundle and nothing else
- **NFL evidence:** about eight orders (FWD1–FWD6e) and audits #6–#13 were spent retrofitting this.
- **What held up:**
  - **Bundle at cutoff T:** every input is copied in and sha256'd.
  - **Read-set proof:** every file the worker parsed is either in the bundle or a manifest-pinned repo file
    (NFL: 45 = 14 + 31, 0 unproven).
  - **Isolated launcher:**
    - `python3 -I -S -B`;
    - a self-hash;
    - wheel RECORD verification of loaded distributions;
    - pinned libraries;
    - the drift baseline is the union across runtimes.
  - **Write-once run directories.** A run is complete only when its manifest is finalised and its sidecar exists, whatever
    any transcript says.
  - **Atomic publication:** the frozen file's hash is in the receipt, and the worker's probability equals the frozen
    probability (Δ 0.0).
- **State the threat model up front.** NFL audits escalated through pytest plugins → sitecustomize → .pyc → native
  readers until D269 said the threat is accidental contamination, not a hostile local user.

### A9. Every gate HALTs, and every gate is proven by an attack that reaches the real worker
- **NFL evidence:**
  - fail-open gates: a calibration-stamp mismatch only disabled ranking; freshness only warned; freshness was judged from
    a snapshot's first row;
  - presence checks: a key existed but its value was NaT; a positive test asserted that a 2099 timestamp is accepted;
  - "four rating units" passed with four arbitrary names.
- **Rule:**
  - No warning-only gates in the primary path.
  - Each gate ships with a test that fails on the pre-fix commit, plus an executed attack showing either a HALT at the
    real worker or a measured prediction delta.
  - A helper-level rejection is not evidence for the path.
  - Describe each guarantee exactly as narrowly as the code implements it.

### A10. Freshness means real data-through date per team, and quotes have a hard age limit
- **NFL evidence:**
  - a carried-forward usage row satisfied the gate;
  - the depth feed was dead for 4.5 days in a live week, while a test kept reporting it and was annotated as a "known
    red";
  - a props cron was installed after its slots and never fired;
  - the first MNF dry run had 0 props because the worktree's quotes were never synced.
- **Rule:**
  - Gate per team, per input, on real data-through; refuse carried-forward rows.
  - Quote age ≤ 3 h, with no stale-quote override in a primary run.
  - Sync quotes into the harness worktree (`git fetch` → `git restore --source=origin/main` → age check) before every run.
  - Check that downstream consumers received the data, not just that it arrived.
- **Both lanes:** the book key is per sport.
  - Hard Rock on the Odds API is `hardrockbet_fl` for NFL and `hardrockbet` for NHL, NBA, NCAAF and MLB
    (line_pull_audit, 10-04: 9/12 NHL events and 8/44 NBA events carried it).
  - The NHL premise that "Hard Rock has no NHL prices" is stale. Re-probe before treating Pinnacle as the only book of
    record.

### A11. Reproducibility: RNG discipline, committed generators, like-for-like targets
- **NFL evidence:**
  - Seeds came from Python `hash()`, which differs per process (fixed with `zlib.crc32`).
  - A Beta draw without `size=N` broadcast one draw to all sims, and 621/1,237 legs differed between Mac and Linux. After
    the fix, the board was 1,443/1,443 bit-identical.
  - One uniform decided two events (D36).
  - Artifacts had no committed producer (K4 tables, the stamp, pullers).
  - A K1 target was hardcoded in four files and counted plays differently from the sim.
- **Rule:**
  - named per-decision RNG streams, vectorised draws, stable sorts;
  - a cross-machine bit-identity test on one board;
  - every committed artifact comes from committed code;
  - write the metric definitions like-for-like (sim vs data) before the first target exists;
  - measure constants from the data and state the derivation (NFL `start_yl100=75.0` was 5 yards wrong for 2024).
- **NHL check:** generators were missing at least five times (constants v3/v4/v6, the finishing term, S46–S48). Key
  artifacts exist only as Cowork files. Data lives only inside worktrees (nhlE 1.2 GB, nhl2, a symlinked pbp cache), so
  pruning a worktree would destroy it.

### A12. Tests that can fail, a committed mutation script, and no "known reds"
- **NFL evidence:**
  - Surviving mutations every round: 8, 4, 13, 28, 15, 5. Causes: stubbed workers, fixtures that exit before the guard,
    `raises(SystemExit)` without a reason asserted, source-text "tests".
  - A red test was relabelled "known" for three cycles while it was correctly reporting stale data.
  - Convergence came from a committed, registered mutation script (81 operators, kills require a named failing test) and
    a full baseline run file by file.
- **Rule:**
  - every guard has a mutation that the suite kills;
  - no `inspect.getsource` tests;
  - run end to end through `main()` on real data once per order;
  - a standing red is an untested hypothesis; never write "structurally impossible" without demonstrating it.

### A13. Verify from files, not reports
- **NFL and NHL evidence:**
  - NFL: "all 4 items done" with a test never written; "127/4" when the truth was 139/4; dry runs skipped three orders in a
    row "due to time"; a run record that attributed completion to a directory with no sidecar (FWD7n, 10-05).
  - Cowork's own misses: it inferred wiring from a deleted alias, checked a function's return value and not its consumer,
    and read the update arithmetic but not the loop.
  - NHL had report-vs-file mismatches in nearly every order (S-WO3, S3c/e/f/r, S4a–d, D-WO1, E-WO1, WO12), and "STOP,
    don't defer" was broken repeatedly.
- **Rule:**
  - a report is a claim;
  - acceptance = numbers recomputed from committed artifacts + one real-data run + an explicit NOT DONE / UNVERIFIED list;
  - "time constraints" is not an accepted reason to skip a deliverable;
  - the run record should be generated from the run directory, not typed;
  - grep for call sites, instrument the run, and assert on outputs. "A diff is not evidence that code runs."

### A14. Process shape that made things converge
- **Work orders:**
  - at most 4 items; commit and push between items;
  - each decision is written into the lane's decision doc in the same commit;
  - pre-register the prediction and a null control before looking;
  - never tune to rescue a failed prediction.
- **Audits:**
  - pin an exact SHA;
  - "attack, don't validate";
  - commit every artifact the auditor needs;
  - save replies verbatim;
  - ask for ALL findings in a class, not one blocker;
  - fix the class, not the instance;
  - give the auditor a crisp decision criterion and a time budget (one extracted tree, bounded batches, `df -h` before
    and after).
- **Forward tests:**
  - declare `MODE: PILOT|PRIMARY` before the harness;
  - PRIMARY requires an empty code-path diff against the audited SHA;
  - any failed precondition demotes to PILOT;
  - never promote after outcomes;
  - append-only logs graded on CLV.
- **Ops:**
  - `~/mlb-model` stays on main; worktrees only;
  - `GIT_OPTIONAL_LOCKS=0` on every bridge git command;
  - no `git add -A`;
  - Mac awake (`caffeinate`) or the job on the VM. The unattended Sunday runs were lost to a sleeping Mac;
  - pin a byte-identical copy of any shared module an experiment hashes. NHL's +558/−67 edit to `log_ai_opinions.py`
    once broke the NFL experiment (FWD5); NHL and NBA now depend on that same logger.

---

## Part B. Day-one checklist (score yourself HAVE / PARTIAL / MISSING, with file evidence)

1. A written purpose: what the sim prices and why it could beat the close (A1).
2. `as_of()` accessor for every time-stamped source; UTC everywhere (A2).
3. Truncation-equivalence test across ALL sources, per date, with a planted-leak negative control (A2).
4. Fit-window/holdout ledger, current, including what has been looked at (A3).
5. Parameters fitted through the live builder; call-site check for new functions; content-fingerprint gate (A4).
6. ID-only joins; price-scale labels; book-faithful settlement; symmetry check (A5).
7. Raw-row admission module per source with a null/blank/case/domain fuzz suite (A6).
8. Scraped inputs: real parser, allowlist grammar, differential parse, context binding, verified-empty, attack corpus
   (A7).
9. Hashed write-once bundle, read-set proof, isolated launcher, pinned libs, sidecar/manifest as the completion proof
   (A8).
10. Every gate HALTs and has an executed attack through the real worker (A9).
11. Per-team real data-through freshness; quote age ≤ 3 h with no override; quote sync before runs; per-sport book keys
    (A10).
12. RNG streams, cross-machine bit identity, committed generators, like-for-like targets, measured constants (A11).
13. Committed mutation script; full baseline file by file; no source-text tests; no "known reds" (A12).
14. Verification from files; generated run records; NOT DONE / UNVERIFIED lists (A13).
15. MODE declared before runs; append-only logs; pinned shared modules; ops hygiene (A14).

## Part C. Lane-specific flags (from docs about 10-01; verify before acting)

**NHL**
- **Holdouts:** per A3, the holdout status of 2024-25 and 2025-26 needs an honest rewrite before S-WO5.
- **Pre-2019 play-by-play** is not in chronological order (2015-16 median state time 3,699 s vs 3,600), so every 2010-18
  rate is suspect until D5 lands.
- **Generators and data custody:** commit generators for constants and finishing term; move Cowork-only artifacts and
  worktree-only data to committed or archived locations before any worktree is pruned.
- **Goalie confirmations** come only from HTML (no structured feed). Build G1 to the A7 standard from the start.
- **Book of record:** re-probe Hard Rock with `hardrockbet`.
- **Leftover:** "xg_per_attempt" is really goals per attempt. Rename it, or a future reader will mis-specify a model.
- **Merge command:** the handoff's merge command (`git checkout main && …`) violates SESSIONS_RULES Rule 1.
- **Status file:** `claude/status_nhl.md` is still a stub.

**NBA**
- **No sim exists yet.** This is the cheapest moment to adopt A2, A6, A7, A8 and A11 as the S1/S2 design rather than as
  retrofits. Write `research/nba_sim/NBA_SIM_DECISION_v1.md` with them as NS1…NSn.
- **Official injury-report PDFs** (Mac only; VM 403) are a scraped input: A7 applies in full. The point-in-time "who was
  known out" history needs the 2024-26 report archive.
- **ESPN injuries have no item timestamps,** so they cannot be point-in-time sources for training.
- **Pending work:** WO2b (props market set, L3 caching, preseason leak) and the `nba/wo2` merge were unconfirmed at last
  doc. NBA event-market cron lines exist (ops, 10-04); whether they capture props depends on B11.
- **Mac auto-commits** (`git add -A` sweeps) have swept unrelated changes into main. The NBA availability job needs its own
  explicit-path push.
- **Status file:** `claude/status_nba.md` is still a stub.
