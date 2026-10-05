# FWD7n Mac run — 2026-10-05

S1 and S2 did NOT run on 2026-10-04; HEAD was still b842af343 (FWD7m).

## Step 1 — Starting state

```
Mon Oct  5 00:51:21 UTC 2026
 M nfl/data/pbp/depth_charts.parquet
 M nfl/data/sim/ratings/player_usage_weekly.parquet
b842af343 FWD7m Mac run: D281 on the live page (audit #21 and #22 edits HALT; allowed controls identical to clean), both chains on the installed capture HALT with nothing written (clean replay equals installed), forward tests, primary-path Sunday dry run
b842af34355c0646a811f6353cbfb3015d4091e0
b842af34355c0646a811f6353cbfb3015d4091e0
/dev/disk3s1s1   460Gi    13Gi    59Gi    18%    484k  615M    0%   /
```

Last commit touching nfl/sim:
```
fbc1b34e4 FWD7m (D282): ChatGPT audit #22 NO-GO accepted; ev
```

No fwd_bootstrap or pytest running. PASS.

## Step 2 — D282 patch

```
f4724750aa8a233eaf14f5db6e2923ddf34dedf794b89d0c2b81166d14ad2155  0001-FWD7n-D282.patch
04ca327ded20532e2d797e23cd909678bd216004fff54653ae272b86a38e15d2  a23replay.py
```

```
Applying: FWD7n (D282): ChatGPT audit #23 NO-GO accepted; HTML comments removed by a quote-aware scan of each report section (comment delimiters inside quoted attribute values stay inside their tag and HALT), abruptly/incorrectly closed comments and sections without a real </section> HALT, raw '<' or '>' in attribute values HALT; Z11 re-anchored, Z31-Z34 mutations
To https://github.com/jwallace115/mlb-model.git
   b842af343..b1de3b50d  eng/fwd6 -> eng/fwd6
b1de3b50d FWD7n (D282): ChatGPT audit #23 NO-GO accepted; ...
b842af343 FWD7m Mac run: ...
```

PASS. D282 commit: b1de3b50d.

## Step 3 — Live page (verbatim)

```
status 200 fetched 2026-10-05T00:52:13.262084+00:00 | rows 318 teams 32 game statuses 138
Jayden Daniels [['WAS', 'Out']]
Rachaad White [['WAS', 'Out']]
Chig Okonkwo [['WAS', None]]
split rows 318 identical to clean: True
comment rows 318 identical to clean: True
encoded allowed class rows 318 identical to clean: True
real comment in a cell rows 318 identical to clean: True
six-cell (audit #21 A) HALT: official injury page WAS: unsupported row content (<th> outside a cell) in 'Jayden Daniels QBElbowLimite
quoted comment, aria-label (audit #23 A1) HALT: official injury page section 1: unsupported element (script/template/style/noscript or an unclosed comme
quoted comment, href (audit #23 A1) HALT: official injury page section 1: unsupported element (script/template/style/noscript or an unclosed comme
encoded hidden Out (audit #22 A1) HALT: official injury page section 1: unsupported attribute 'style' on <span>
encoded visibility HALT: official injury page section 1: unsupported attribute 'style' on <span>
comment in style HALT: official injury page section 1: unsupported attribute 'style' on <span>
unknown class HALT: official injury page section 1: unknown class ['hidden'] on <a>
tbody class HALT: official injury page section 1: unsupported attribute 'class' on <tbody>
text in a row HALT: official injury page WAS: unsupported row content (unclosed cell or trailing content) in 'Nick Allegrett
stray HALT: official injury page WAS: unsupported table body structure (15 row tags, 15 complete rows, stray content
```

MEANS: live page parses clean (318 rows, 32 teams); all four allowed controls identical to clean (True); all ten attack mutations HALT. No ADMITTED. PASS.

## Step 4 — Installed capture replay (verbatim)

```
installed capture 2026-10-03T23:10:55.062576+00:00 2711f526d7a38581 405289 bytes
Jayden Daniels [['WAS', 'Out']]
Rachaad White [['WAS', 'Out']]
  https://www.nfl.com/injuries/league/2026/reg4 fetched 2026-10-03T23:10:55.062576+00:00 sha256 2711f526d7a38581: 318 rows, 32 teams, 138 game statuses
  skill players Out/Doubtful officially but not in the feed: 0
clean: ADMITTED | equals installed injuries.parquet: True | rows 35864
six-cell (audit #21 A): HALT "HALT: official injury page WAS: unsupported row content (<th> outside a cell) in 'Jayden Daniels QBElbowLimited Participation in PracticeOut'" | wrote anything: False
Chig Okonkwo [['WAS', None]]
encoded hidden Out (audit #22 A1): HALT "HALT: official injury page section 1: unsupported attribute 'style' on <span>" | wrote anything: False
quoted comment delimiters, aria-label (audit #23 A1): HALT 'HALT: official injury page section 1: unsupported element (script/template/style/noscript or an unclosed comment)' | wrote anything: False
quoted comment delimiters, href (audit #23 A1): HALT 'HALT: official injury page section 1: unsupported element (script/template/style/noscript or an unclosed comment)' | wrote anything: False
```

git status: only the two refresh parquets. MEANS: clean replay equals installed; all four attack chains HALT with nothing written. PASS.

## Step 5 — Selftest

```
exit 0
launcher hash ok: True {'n_repo_modules': 12, 'n_dependency_files': 1090, 'n_distribution_files_verified': 6395}
```

PASS.

## Step 6 — Forward suite

```
nfl/sim/tests/test_fwd2_anchor.py: 3 passed in 0.26s
nfl/sim/tests/test_fwd2_bundle.py: 5 passed in 0.24s
nfl/sim/tests/test_fwd2_experiment.py: 6 passed in 0.97s
nfl/sim/tests/test_fwd2_item0_fixes.py: 7 passed in 1.08s
nfl/sim/tests/test_fwd2_settlement.py: 12 passed, 1 warning in 2.03s
nfl/sim/tests/test_fwd2b_harness.py: 10 passed in 43.20s
nfl/sim/tests/test_fwd3_item0.py: 9 passed in 34.32s
nfl/sim/tests/test_fwd3_item1.py: 3 passed in 0.29s
nfl/sim/tests/test_fwd3_item2.py: 8 passed in 1.20s
nfl/sim/tests/test_fwd4_item0.py: 9 passed in 24.96s
nfl/sim/tests/test_fwd4_item1.py: 4 passed in 6.05s
nfl/sim/tests/test_fwd5_pin.py: 4 passed in 6.27s
nfl/sim/tests/test_fwd6_item0.py: 13 passed in 34.30s
nfl/sim/tests/test_fwd6_item1.py: 12 passed in 63.22s (0:01:03)
nfl/sim/tests/test_fwd6_item2.py: 9 passed in 29.86s
nfl/sim/tests/test_fwd6_item3.py: 5 passed in 10.46s
nfl/sim/tests/test_fwd6b.py: 39 passed in 121.93s (0:02:01)
nfl/sim/tests/test_fwd6c.py: 33 passed in 75.32s (0:01:15)
nfl/sim/tests/test_fwd6d.py: 33 passed in 71.51s (0:01:11)
nfl/sim/tests/test_fwd6e.py: 6 passed in 14.62s
nfl/sim/tests/test_fwd6f.py: 11 passed in 1.87s
nfl/sim/tests/test_fwd7a.py: 27 passed in 3.27s
nfl/sim/tests/test_fwd7c.py: 11 passed in 1.37s
nfl/sim/tests/test_fwd7d.py: 7 passed in 0.58s
nfl/sim/tests/test_fwd7e.py: 7 passed in 0.42s
nfl/sim/tests/test_fwd7f.py: 12 passed in 0.43s
nfl/sim/tests/test_fwd7g.py: 55 passed in 2.34s
nfl/sim/tests/test_forward_v1.py: 8 passed in 0.29s
nfl/sim/tests/test_freeze_v1.py: 4 passed in 0.85s
```

TOTAL: 372 passed, 0 failed, 0 skipped. PASS.

## Step 7 — PRIMARY-path dry run of MNF ATL@NO

### First attempt: 20261005T010236Z (HALTed)

The worktree's quote files were never synced from origin/main. The bundle had Props: 0 and Lines: 6 (the Sep 30 21:00Z snapshot). The sim completed (1/1 converged) but the harness HALTed at step (e):

```
(a) Running test_freeze_v1...
    PASS
    Experiment manifest: OK
    Calibration stamp: OK
    Usage fingerprint: OK

(b) Building bundle at T=2026-10-05T01:02:36.889385+00:00...
  Bundle: nfl/data/board/week=2026_04/sim_runs/20261005T010236Z
  Events: 1, Props: 0, Lines: 6
  Archive: /Users/jw115/mlb-model-archive/nfl_fwd_v1
  Per-team freshness (consumed copies):
    ATL: last_played_week=3, team_ratings=4, tendencies=4, tendencies_situational=4, usage=4, active_universe=4, kickers=4, qb_ratings=4, active_universe_current=15, injury_game_statuses=3, official_rows=7, official_game_statuses=3, official_fetched_utc=2026-10-03T23:10:55.062576+00:00, final_report_deadline_utc=2026-10-03T20:00:00+00:00, official_verified=True
    NO: last_played_week=3, team_ratings=4, tendencies=4, tendencies_situational=4, usage=4, active_universe=4, kickers=4, qb_ratings=4, active_universe_current=15, injury_game_statuses=5, official_rows=13, official_game_statuses=5, official_fetched_utc=2026-10-03T23:10:55.062576+00:00, final_report_deadline_utc=2026-10-03T20:00:00+00:00, official_verified=True

(c) Building sheet from bundle...
    3 lines, 3 two-way

(d) Running sim...
    Sim complete.
Games simulated: 1
Converged: 1/1

    Read set: 45 files — 14 from the run directory, 31 manifest-hashed repo files, 0 unproven
    picks_log: 84 legs
(e) Filling opinions...
    Matched 0 / 3 two-way prop rows

    Coverage: 3 sheet / 3 two-way / 0 matched
HALT: zero sim matches — nothing to freeze
```

MEANS: the gate worked — it refused to freeze with zero matches. The cause was unsynced quotes, not a code bug.

### Quote sync (7a)

```
b1de3b50d80f45c3ec469d5fbb731bf3d0a048dd
synced
```

```
now 2026-10-05T10:32:47+00:00 | window to 2026-10-06T16:32:47+00:00 | 1 games with props
  Atlanta Falcons @ New Orleans Saints kick Tue 00:15Z | newest props Sat 14:00:11Z (44.54 h old) 509 rows, Hard Rock yes, file data_2026_10.parquet
newest line snapshot snap_20261005T053005Z.parquet (5.05 h old)
```

### Re-run: 20261005T103258Z (first run), 20261005T103352Z (second run — output recorded)

```
(a) Running test_freeze_v1...
    PASS
    Experiment manifest: OK
    Calibration stamp: OK
    Usage fingerprint: OK

(b) Building bundle at T=2026-10-05T10:33:52.520601+00:00...
  Bundle: nfl/data/board/week=2026_04/sim_runs/20261005T103352Z
  Events: 1, Props: 65, Lines: 6
  Archive: /Users/jw115/mlb-model-archive/nfl_fwd_v1
  Per-team freshness (consumed copies):
    ATL: last_played_week=3, team_ratings=4, tendencies=4, tendencies_situational=4, usage=4, active_universe=4, kickers=4, qb_ratings=4, active_universe_current=15, injury_game_statuses=3, official_rows=7, official_game_statuses=3, official_fetched_utc=2026-10-03T23:10:55.062576+00:00, final_report_deadline_utc=2026-10-03T20:00:00+00:00, official_verified=True
    NO: last_played_week=3, team_ratings=4, tendencies=4, tendencies_situational=4, usage=4, active_universe=4, kickers=4, qb_ratings=4, active_universe_current=15, injury_game_statuses=5, official_rows=13, official_game_statuses=5, official_fetched_utc=2026-10-03T23:10:55.062576+00:00, final_report_deadline_utc=2026-10-03T20:00:00+00:00, official_verified=True

(c) Building sheet from bundle...
    68 lines, 43 two-way

(d) Running sim...
    Sim complete.
Games simulated: 1
Converged: 1/1

    Read set: 45 files — 14 from the run directory, 31 manifest-hashed repo files, 0 unproven
    picks_log: 85 legs
(e) Filling opinions...
    Matched 13 / 43 two-way prop rows

    Coverage: 68 sheet / 43 two-way / 13 matched
    By market:
player_receptions       11
player_rush_attempts     2
(f) Building anchor sidecar...
    1 games, 0 unanchored
  game  target_spread  target_total  anch_m  anch_t  miss_m  miss_t  iterations  converged  anchored                         event_id           run_id
ATL@NO            2.0          47.5  2.1622 47.5566  0.1622  0.0566           3       True      True 8bd90781e17e6d97df3941063cedae1e 20261005T103352Z

--- DRY RUN ---
Tag counts:
tag
no_view    55
sim_v1     13

DRY RUN complete — nothing frozen.
```

Freshness.json:
```
nfl/data/board/week=2026_04/sim_runs/20261005T103352Z
ATL 7 3 True 2026-10-03T23:10:55.062576+00:00
NO 13 5 True 2026-10-03T23:10:55.062576+00:00
```

### Pre-registration results

- P1: HELD — Props: 65 (was 0), Events: 1 (ATL@NO), Hard Rock rows present (509 rows, Sat 14:00:11Z).
- P2: HELD — Matched 13/43 two-way prop rows, reached "DRY RUN complete — nothing frozen."
- Null control: HELD — HEAD b1de3b50d; gate PASS; ATL 7/3/True, NO 13/5/True; fetched 2026-10-03T23:10:55Z; read-set "0 unproven". All identical to 20261005T010236Z.
