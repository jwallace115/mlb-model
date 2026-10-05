# NBA-S0c verification — 2026-10-05 ~16:15Z (NBA chat, Cowork, read-only from files)

Branch origin/nba/s0 at c19ce5371 (dff2f5733 B21, fc954f71e B22, f887893ec B23). Compared to 01c7ca076.
Tip times for the timing audit: Odds API events files already on disk
(`data/odds_archive/nba/history/events/events_{2024,2025}.parquet`, commence_time). **0 credits.**
Disclosure: my first command ran `git fetch origin nba/s0` in the main checkout (updates only FETCH_HEAD and the
remote-tracking ref; it does not touch the index). That broke "read-only"; it will not happen again.

## Pre-registered results — checked
| Gate (workorder_S0c) | Claimed | Checked from files | Verdict |
|---|---|---|---|
| ≥95% legacy pre_tip slot ≥17:00 ET | 73.7%, DID NOT HOLD | 165/224 = 73.7% | **FAILED, reported honestly.** My gate was mis-specified: pre_tip follows the first tip (matinees). Not a code defect by itself. |
| ≥95% freeze = 05PM | 100% | 224/224 slot 17:00 | HELD |
| 12PM share of pre_tip ≤5% | 4.9% | 11/224 = 4.91% | HELD (barely) |
| NULL: new-format rows unchanged | 0/208 changed | 206 new-format manifest rows identical to 01c7ca076 (sha, published_utc, status, n_rows, n_nys) | HELD |
| B22: legacy context_mismatch → ok | 4 → 0 | old manifest has **2** legacy context_mismatch; new manifest 642/642 ok | HELD (count off by 2) |
| B23 <20 MB, add/remove counts | 6.6 MB; +420 / −224 / 222 unchanged | +420 / **−213** / 222 common → 642 | Size HELD. "224 removed" is wrong (435 − 222 = 213). Doc fix only. |
| New tests fail on 01c7ca076 | yes | B21: `_5PM` AssertionError; B22: ImportError `is_legacy_format`. Both pass on c19ce5371 (run as scripts; no pytest on the VM, nothing installed) | HELD |
| No raw PDFs tracked | — | 7 tracked PDFs, all test fixtures, the same 7 as at 01c7ca076. No history PDF tracked. | HELD |

Other checks: roles sha256 = manifest sha256 for all 656 rows. Every role file is in the manifest; every manifest
file is in roles. Legacy published_utc − slot = 30 min (430 files) or 45 min (6). New-format = slot (206 files).

## NEW findings (not pre-registered — found by auditing report time against tip time)
**F1. Legacy pre_tip is chosen on SLOT, but the report is published at slot+30.**
Rule: `slot ≤ first_tip − 30 min`. Legacy header = slot + 30 (or +45). So a 7:30pm tip picks the 07PM report,
published 7:30pm, exactly at tip.
- Legacy pre_tip published at or after first tip: **20/224 dates**. Another 20 are under 15 min before tip.
- Legacy pre_tip published inside the 30-min margin the rule intends (published > tip − 30): **42/224**.
  New-format: 1/104, plus 1 date with no Odds API tip.
- Of the 20, 16 are exactly at tip (0 min). The rest: 2024-12-10 −90, 2024-12-11 −30, 2024-12-12 −20, 2025-12-21 −5.
- New-format pre_tip: 0 at or after tip. Its minimum is 10 min before the Odds API tip, which means ESPN's tip and
  the Odds API tip disagree on at least one date.

**F2. The freeze report is published at or after the first tip on 93/328 dates (28%).**
- 61 legacy dates and 32 new-format dates.
- Worst: Christmas or MLK-day noon tips, freeze published 330 min after the first tip.
- roles.parquet is per DATE. Any consumer that uses `freeze` as as-of for a game tipping before ~5:30pm ET reads a
  post-tip report. That is a CHECK 1b leak.
- This is the open early-tip freeze rule. The data now shows it affects most weekend slates.
- Per game: 194/2,467 games (7.9%) tip before 18:00 ET. For those games the 5:30 freeze is not a valid pre-tip as-of.

**F3. Silent default.** `get_first_tip()` returns 19:00 ET when ESPN fails, with no flag. First tip is not stored in
roles, so the number of dates that used the default is unknowable from files.

**F4. Minor.**
- roles.status is blank for all 448 legacy rows; only the 208 new-format rows say `ok`.
- B21/B22 say "208 new-format files". The manifest has 206; 208 is the count of role rows, because some dates use one
  file for both roles.

## Consumers / blast radius
No NBA code reads roles.parquet or history_parsed (`git grep` on origin/main and origin/nba/s0; the only other hit
is mlb/model_m6, which uses its own path). **No reported result uses these files.** F1–F3 change nothing already
reported. They must be fixed before S1 or any L3 history work reads roles.

## Merge readiness
- Code and data are correct as records of the reports. roles.parquet is flawed as an as-of index (F1, F2).
- Recommend: **merge nba/s0 now**, because it fixes the live capture parser before the preseason pipe test. Mark
  roles.parquet "do not consume" until S0d.
- Blockers found at 16:12Z:
  1. A merge is in progress in ~/mlb-model: MERGE_HEAD = origin/nhl/sim-s4b, started 16:06Z, with NHL files staged.
     That merge belongs to the NHL lane. Wait until it is committed and pushed.
  2. Three untracked files in research/nba_layers/ are byte-identical to the branch copies
     (nbaS0_verification, workorder_S0b, workorder_S0c). They will block the merge. Move them aside first.
  3. `logs/agent_sessions.md` conflicts; both sides appended. Resolve by keeping both sides (`git merge-file --union`).
  4. Main is ahead of the merge base (dashboard auto-commits, OPS2), so this is a real merge. That is the only file
     changed on both sides.

## Fix proposed: NBA-S0d (claude/nba_s0d_workorder_2026-10-05.md). NOT run — needs Jeff's yes, because it changes
roles.parquet, a reported B21 result.
