# NHL Layers — decision log (v1)

One decision doc per sport (LAYERS_GAMEPLAN §7). Entries H1, H2, ... Only the NHL Layers chat and the work
orders it writes append here. Cross-sport rules live in `research/layers/LAYERS_DECISION_v1.md` (L-entries);
football's blind log is N59/N61/N62 in `research/ncaaf_board/NCAAF_BOARD_DECISION_v1.md`.
Before numbering: `grep "^### H" research/nhl_layers/NHL_LAYERS_DECISION_v1.md | tail -1`.

---

### H1 — NHL joins the Layers System: dates, what is scored, what "works" means (2026-09-27)

Source: Jeff, 2026-09-27 (NHL chat opened on the plan `research/layers/LAYERS_GAMEPLAN_2026-09-27.md`, §4, §8,
§9, §10). Written by Cowork BEFORE any NHL opinion exists and before the pilot starts.

- **Slates** are America/New_York calendar dates of puck drop. The NHL regular season opens Tue 2026-09-29
  (NHL.com schedule release).
- **Pilot: slates 2026-09-29 .. 2026-10-04.** Frozen with `--pilot`; never pooled into the record.
  **Record: slates from Mon 2026-10-05.**
- **Reader:** every frozen file names `--reader-model` (N62). Different models are separate pickers, reported
  side by side, never pooled silently. A change of METHOD (reader_method file) is a new version, judged only on
  slates after its date.
- **Universe (pilot default, plan §10):** every game line at the book of record — moneyline (`h2h`), puck line
  (`spreads`), total — with a probability AND a side on every line; `no_view` is not allowed in the NHL pilot.
  **Player props are captured from day one as part of layer L1 but are NOT in the scored universe** until a named
  H-decision made before 2026-10-05, using the measured number of Hard Rock prop lines per slate.
- **Primary metric:** closing-line value vs Pinnacle's close on the sides taken (probability CLV on the SAME
  line; line moves reported separately, never imputed). **Secondary:** Brier vs the de-vigged book at freeze;
  units at the real frozen price of the book of record (never flat -110; CHECK 4).
- **Baselines, logged on the same lines the same way:** (a) the book at freeze, and Pinnacle at the close;
  (b) the best single model layer where one exists (NHL model; `absent` until it produces 2026-27 pre-game
  probabilities — see H2); (c) follow the move (side = direction of Pinnacle's de-vigged move from the event's
  first tape snapshot to the freeze snapshot). If the reader does not beat (b) and (c), the interpretation adds
  nothing over the layers.
- **Pre-registered (expected to HOLD; the log exists to find where they fail):**
  P1 Brier(book) <= Brier(reader) on the scored lines.
  P2 the reader's sides with |p - q| > 0.08 lose units at real prices.
  P3 (added by Cowork) the reader's mean probability CLV on sides taken is <= 0.
- **Checkpoints:** a report at 500 and at 1,500 graded RECORD sides. No keep/kill decision before 1,500; that
  decision is a named pass, not momentum. Arithmetic: at about -110 the ROI standard error is ~1/sqrt(n) —
  +/-4.5 points at 500, +/-2.6 at 1,500 — and three lines per game are correlated, so the effective n is smaller.
  Every report breaks out by reader_model first, then month, market, tag, drivers, |p-q| bucket, and
  October (thin early-season history) vs later (CHECK 5).
- **Discipline:** the packet (what the reader saw) is saved and hashed beside every frozen file; every packet
  item carries a source time before freeze (1a); history layers are point-in-time (1b); the reader method file
  is frozen for the pilot; the sha256 of every frozen file is posted in `claude/capture_status_2026-09-20.md`
  (NHL section) before the first puck of that slate. Nothing is ever called validated, an edge, or +EV (N54).
- **Leakage note (CHECK 2):** the reader's knowledge ends before the 2026-27 season, so the frozen log is true
  OOS by construction. The reader cannot be backtested (plan §2). Any lesson drawn from slates 1..N is a
  hypothesis until it holds on slates after N.

### H2 — Conventions, and what the pre-check found in the files (2026-09-27)

Verified by Cowork from the repo on 2026-09-27 ~13:50Z (files read, not recalled). The first three findings
below were found independently by the main Layers chat and are fixed by its capture work order 12.

- **Tape path:** `data/odds_archive/nhl/line_history/season=<S>/snap_*.parquet`. As written today,
  `shared/pipeline/multi_book_open_capture.py` builds the folder as `sport.replace("americanfootball_", "")`, so
  `icehockey_nhl` would land in `data/odds_archive/icehockey_nhl/` (MLB already lands in `baseball_mlb/`). An
  explicit sport -> folder map is required; MLB stays where it is.
- **Season partition for NHL = the season's start year** (2026 = 2026-27): month >= 7 -> year, else year - 1.
  The capture script's rule (month >= 3 -> year) would split one NHL season at 1 March. Football and MLB keep
  their rule.
- **Capture is owned by capture work order 12** (main Layers chat, `research/layers/capture_workorder12_nhl_2026-09-27.md`,
  branch `eng/cap12`, decisions L1-L4 in `research/layers/LAYERS_DECISION_v1.md`): it puts NHL on the tape and adds
  multi-book event markets (props, every game market, 10 books incl. Hard Rock and Pinnacle) at
  `data/odds_archive/nhl/event_markets/season=<S>/snap_<UTC>.parquet`, and deploys the VM cron. NHL work orders do
  NOT edit `shared/pipeline/` while WO12 is open; they read its files. The existing `data/odds_archive/nhl/props/`
  and `game_markets/` are last season's historical backfill (Oct 2025 - Mar 2026; betrivers, betmgm, draftkings,
  betonlineag, williamhill_us, fanduel, bovada — no Hard Rock, no Pinnacle) with calendar-year partitions
  (`season=2026` there = Jan-Mar 2026); nothing live is written there.
- **Frozen tree:** `nhl/data/board/date=YYYY-MM-DD/ai_opinions/` (opinions, packet, manifest,
  `reader_attribution.json`).
- **Book of record — rule fixed BEFORE measuring:** `hardrockbet_fl` if, in the first multi-book NHL pull that
  lists them (WO12's dry run or NHL WO1's fixture pull, whichever comes first; the numbers are recorded), it quotes
  all three game markets on >= 90% of the games on slates 2026-09-29 .. 2026-10-01; otherwise `pinnacle` (N61
  precedent), with units labelled as Pinnacle prices. NHL WO1 item 1 applies the rule and records it.
  **ADDENDUM 2026-09-27 ~14:35Z — rule applied (measured by capture WO12, commit 996bab4bd on eng/cap12,
  `logs/_log_cap12.txt`):** the first multi-book NHL pull (14:12Z dry run) returned 33 games from 9 books with
  `hardrockbet_fl` ABSENT on every game; `/markets` discovery on FLA@CAR and MTL@TOR (both 2026-09-29 REGULAR-season
  openers, which the WO12 log mislabels "preseason") showed Hard Rock 0 markets, Pinnacle 22 (game-level only, no
  player props yet). Hard Rock is at 0% against a 90% bar, so **the NHL book of record is `pinnacle`** — units at
  Pinnacle's price, labelled so; Jeff's tickets keep Hard Rock's slip price (N49). Why Hard Rock is absent (not yet
  posted 2 days out, or not offered via the API for NHL) is UNKNOWN. The pilot runs on Pinnacle whatever happens.
  For the RECORD (from 2026-10-05) only a named H-decision can change the book, taken before 2026-10-05 from Hard
  Rock's measured NHL coverage in pilot week — coverage, never results.
- **Settlement.** MEASURED: the NHL API boxscore final score includes the shootout winner's +1 (canonical
  table: game 2025020006 CGY @ EDM, went_to_so, final 3-4, regulation 3-3). 2025-26 regular season in the
  canonical table: 1,312 games, 326 flagged OT (includes shootouts), 119 shootouts.
  ASSUMED for Hard Rock FL, UNVERIFIED: moneyline, puck line and totals settle on that final (OT + shootout);
  player props count regulation + OT only (no shootout); a player who does not dress = void. To be verified
  from Hard Rock's own rules before the record starts (checklist item).
- **Model layer (L4):** `nhl/nhl_model_outputs.parquet` ends 2025-04-17; `nhl/nhl_decisions.parquet` ends
  2026-05-09. Nothing produces a 2026-27 pre-game probability today, so baseline (b) is `absent` until the NHL
  model runs for the new season — and it is not trusted as a layer before its own historical audit (CHECK 1b, 2).
- **Seen, not changed here (belongs to other chats):**
  `shared/pull_opening_lines_all.py` already sees 2026-27 NHL events (CAR-FLA 2026-09-29T21:00:47Z, TOR-MTL
  23:10Z in its 06:05Z pull) — totals only, 3 books, and `load_dotenv()` without `override=True` (the
  documented trap). `nfl/pipeline/pull_hardrock_props.py` saves every row of a run into the month of the LAST
  event in its loop and hardcodes 15 credits/event. `log_ai_opinions.py score` grades a player absent from PBP
  as 0 — for NHL a scratched player must be void.
