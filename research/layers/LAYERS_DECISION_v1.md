# LAYERS DECISION LOG

Decisions are numbered L1, L2, ... and appended in commit order.
Each entry names the code it ships with.

---

### L1 — tape takes any sport safely (2026-09-27)

**What changed:** `shared/pipeline/multi_book_open_capture.py` — three fixes:

1. **Folder map.** Replaced `sport.replace("americanfootball_", "")` with an explicit
   `FOLDER_MAP` dict: `icehockey_nhl -> nhl`, `basketball_nba -> nba`,
   `baseball_mlb -> baseball_mlb` (unchanged). Unknown sports raise `KeyError`.

2. **Season label.** NHL and NBA use start-year rule (month >= 7 -> current year,
   else previous year). A snapshot at 2027-03-15 for `icehockey_nhl` -> `season=2026`.
   Football and MLB keep month >= 3 (unchanged; no existing files move).

3. **Per-sport isolation.** `pull()` returns `None` on failure instead of `sys.exit(1)`.
   `main()` collects failed sports, continues with the rest, and exits 1 at the end
   if any sport failed. A healthy sport always writes its data.

**Tests:** 19 new tests in `shared/pipeline/tests/test_multi_book_capture_l1.py` — all
network-free (mock `requests.get`). Cover folder map (5 sports + unknown), season label
(11 cases incl. NHL March -> prev year), and isolation (HTTP 404 + network error both
allow subsequent sports to write).

**Live check (Mac, dry-run, 3 credits):**
- `icehockey_nhl`: 33 games, 9 books returned, `hardrockbet_fl` ABSENT (preseason not
  posted yet — first puck 2026-09-29), `x-requests-last=3`.
