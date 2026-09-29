# Work order 6E — first downs by penalty, the six late-game reds, the freeze (2026-09-29)

Written by Cowork after verifying 6D (`phase6d_verification_2026-09-29.md`, D204). **Order 3 of 3 in the time box:
item 3 freezes the engine whatever state it is in.** Builds on eng/6d.

Pre-check (Cowork): runtime — items 0-2 are PBP measurements and the 200-game sample at N=100 (~5 min each) plus the
late-game test files (~15 min); item 3 is one fit + cal + K1 + K4 + boards + suite (~3-5 h on the Mac, as 6C/6D).
Credits: zero. Files: nfl/sim/engine.py, nfl/sim/tables.py, nfl/data/sim/tables/*.parquet (committed builders only),
nfl/sim/run_k1_table.py (item 0), nfl/sim/tests/test_engine_6e.py (new), research/nfl_sim/phase6e_*.md,
research/nfl_sim/FREEZE_v1.json (new), parquets < 2 MB.

```
Work order 6E (research/nfl_sim/workorder_6E_2026-09-29.md). Branch eng/6e from origin/eng/6d (NOT main) in a
worktree. Gates (git fetch origin first): `git rev-parse --short=9 origin/eng/6d` prints b480e0c25, and
`git show origin/main:research/nfl_sim/phase6d_verification_2026-09-29.md | grep -c "^### D204"` prints 1; if either
fails, STOP and print both. FIRST COMMIT: append the D204 block from that file VERBATIM at the end of
research/nfl_sim/NFL_SIM_DECISION_v1.md. Then items 0-3, ONE COMMIT PER ITEM, push each before the next; decisions
D205-D208 appended in the same commit as their code. Session log appended to logs/_log_6e.txt (git add -f),
timestamps from `date -u`. Never weaken a test. No file > 2 MB. Re-record the player-OFF hash whenever the fingerprint
moves. Sample = research/nfl_sim/phase5z_sample.txt, N=100.

HARD RULES: a table the order asks for is the deliverable. "ITEM NOT DONE" only for a named external blocker;
"deferred", "scope", "time", "needs live data" are not outcomes (the boards run from archived weeks as on every
earlier fit). NO PROXIES: never apply rates measured in one situation to another. Every code claim cites file:line.
Every pre-registration and null gets HELD/FAILED with the number. A new test calls the engine and must FAIL on eng/6d
— run it there and paste the failure. A K1 header that says "-dirty" is a failed item: commit first, then run K1.

Item 0 (D205) — K1 must write its rows. nfl/sim/run_k1_table.py wrote the .txt but not
  phase6d_k1_after_rows.parquet on 6D (it did on 6A-6C). Capture the real error (run without `tail`, stderr to a
  file, `python3 -X faulthandler`), fix the cause (e.g. build the per-game rows while each game's sim is in memory
  and drop the frame, instead of holding all 1,087 frames), cite file:line, and show on 20 games that the .txt
  numbers are unchanged by the fix. No K1 re-run at N=500 here — item 3 runs it.

Item 1 (D206) — first downs by penalty (1.27 vs 1.73 a team; the largest unaddressed efficiency input).
  Deliver, real (PBP 2021-24 REG, the definition K1 uses — cite it) vs sim (sample): first downs by penalty per team
  split by (a) penalty category, (b) automatic first down vs yardage reaching the line to gain, (c) accepted on a
  live play vs a no-play, (d) down and distance band. Name where the sim's 0.46 shortfall sits (engine.py ~2000-2075
  on eng/6d: `_pen_auto_first`, `auto_rate`, `pen_td`), fix it from measured rates, and report drives, points per
  drive and pts/team on the sample before/after.
  PRE-REGISTER: fd_pen within 0.3 of 1.73 (test PASSES); sample pts/team rises 0.2-0.6; drives fall 0.1-0.4.
  NULL: offence and defence penalties per game move < 0.1 (both PASS now).

Item 2 (D207) — the six late-game reds, one by one.
  For each of: test_engine_5a11 OT structure, late-half snaps, timeouts/kneels (5a7), tied-offence kicks (5a8),
  kneels & late snaps (5a9), test_engine_6a kneel table — give the value on main, eng/6c, eng/6d and after this
  item; name the cause with file:line; fix what is measured (e.g. timeouts after kickoffs / punts / field goals /
  no-play penalties, the ~16% of team timeouts the engine never calls — measure them from PBP by quarter and seconds
  bucket and apply them at those events). Where a test's target was set on a different definition than the engine
  now uses, show both numbers and do not change the test.
  PRE-REGISTER: sim team timeouts 6.8-8.5 a game; at least four of the six reds PASS.

Item 3 (D208) — ONE re-fit `fit_6e` and THE FREEZE.
  (a) cal maps committed before K1; K1 table + rows (header clean), K4, W2/W3 boards with team_volume from archived
      weeks, full suite, and the points split for fit_6d and fit_6e on the sample.
  (b) research/nfl_sim/FREEZE_v1.json: engine fingerprint, usage fingerprint, fit name, sha256 of every file in
      nfl/data/sim/tables/, of nfl/sim/calibration_v1.json and nfl/sim/params_v1.json, the git commit, the K1 lines,
      the list of reds with values. Add a test (test_freeze_v1.py) that recomputes the fingerprint and hashes and
      fails if any differs from FREEZE_v1.json. After this commit the engine does not change; any later change is a
      new version (FREEZE_v2) and restarts the forward count.
  PRE-REGISTER: K1 plays 125.8 +- 1.5; drives 22.0-22.6; pts/team 21.6-22.4; safeties 0.028-0.040; fd_pen PASS.
  Name every red with its value and the exit code. Whatever the result, the freeze is written.

Run test_engine_5m, 5w, 5y, 5z, 6a, 6b, 6d, 6e after items 0-2. Every item's report separates what the command
RETURNED from what it MEANS and ends with NOT DONE and UNVERIFIED.
```
