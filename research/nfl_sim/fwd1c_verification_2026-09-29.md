# FWD1c verification — Cowork, 2026-09-29 (22:40Z)

Branch `eng/fwd1` @ `0128616ad` (D218 append; D219-D221 one commit each; log). Read from the committed files. The tests
were re-run on Linux in a clean worktree.
**Verdict: accepted. eng/fwd1 (FWD1, FWD1b, FWD1c) is merged to main with a corrected runbook. The forward test of
FREEZE_v1 starts with the week-4 TNF run, 23:30Z Thu 10-01.**

## What stands
- **D219 — revisions are counted per reader.** `prior_revisions(d, reader_model, pilot)` counts only earlier files in
  the manifest with the same reader_model and pilot flag. A manifest entry with no reader_model counts as "legacy".
  `freeze()` passes both values. Stored revisions in existing files are untouched. Tests (a) and (c) fail on
  54efc5878 and pass now.
- **D220 — `no_view` at the floor.** The validator compares against clip(book, 0.02, 0.98). The `sim_v1` fallback for
  one-way lines is gone, and `fill_sheet` asserts that the number of `sim_v1` rows equals the number of matched
  two-way prop rows.
- **D221 — `--dry-run`, and a week-4 dry run.**
  - nflreadpy returned the 16 week-4 games.
  - All 16 are anchored (largest miss 0.32).
  - PIT@CLE falls inside the 60 h window and no Sunday game does.
  - 11 of 42 two-way prop rows matched, because most week-4 props are not pulled yet.
  - D221's "~27 h to kick" is wrong: it was about 50 h. That does not affect the result.
- **Tests on Linux: 16 passed** (test_freeze_v1 4, test_forward_v1 8, test_log_ai_opinions_fwd1c 4).

## Corrected by Cowork: the runbook's pull times
The FWD1b runbook stated Hard Rock props pull times that do not match the deployed VM schedule. The schedule
(capture_status, WO12 deploy) is:

| Slot | Time (UTC) | Purpose |
|---|---|---|
| Tue | 14:00 | open |
| Wed-Sat | 14:00 | mid |
| Tue-Sat | 02:00 | mid |
| Thu | 22:00 | TNF |
| Sun | 15:00 and 16:00 | close |
| Mon | 23:45 | MNF |

The Monday 23:45Z slot did fire on 09-28: the newest pull on the archive is 2026-09-28T23:45:08Z. Three windows change:

- **TNF.** The run stays at 23:30Z. The newest pull is from 22:00Z (about 1.5 h old), not "23:15Z".
- **London (IND@WAS, 13:30Z).** There is no Sunday slot before 15:00Z, so the 12:45Z run reads the Saturday 14:00Z pull
  (about 23 h old), not "10:00Z". The sim and the book are still compared at the same timestamp, so the test stays
  fair. `source_age_min` records the age.
- **MNF.** The run moves from 23:30Z to **23:55Z**, after the Monday 23:45Z pull lands. At 23:30Z the newest pull would
  be Sunday 16:00Z (about 31 h old). The FWD1b note "no Monday slot" was wrong.

### D222 — Cowork verification of FWD1c: accepted; eng/fwd1 merged with a corrected runbook; forward count of FREEZE_v1 starts at week-4 TNF (2026-09-29)

FWD1c (eng/fwd1 @ 0128616ad) is accepted.
- Revisions are counted per reader_model and pilot flag, so revision 0 is each reader's first opinion on a line.
- A `no_view` line carries clip(book) at the 0.02/0.98 floor.
- `sim_v1` rows equal the matched two-way props exactly.
- `--dry-run` works; the week-4 dry run shows 16 of 16 games anchored.
- 16 tests pass on Linux.

eng/fwd1, which carries FWD1, FWD1b and FWD1c (D210-D221), is merged to main. The runbook's props pull times are
corrected to the deployed VM schedule:
- TNF: pull 22:00Z;
- London: Saturday 14:00Z pull, about 23 h old;
- MNF: run at 23:55Z, after the Monday 23:45Z slot.

The forward count of reader `nfl_sim_v1_156cd057` starts with the week-4 TNF freeze. D210's pre-registration governs
it, with the revision rule reading per reader (D219). Checkpoints are at 500 and 1,500 scored two-way legs. At about
150-175 a week, 500 falls around week 6 or 7.
