# The Layers System — game plan and build checklist (NHL, then NBA)

Written 2026-09-27 by Cowork for Jeff. This is the document every new sport chat reads FIRST, and the checklist
it works through before its first frozen pick. It lives in the repo at `research/layers/LAYERS_GAMEPLAN_2026-09-27.md`
and in the project as `claude/LAYERS_GAMEPLAN_2026-09-27.md`. One repo (`jwallace115/mlb-model`), one project
("I am not uncertain"), every sport.

Key dates: **NHL opens Tue 2026-09-29** (5 games that night; first puck 21:00Z). **NBA opens Tue 2026-10-20**
(first tip 19:00Z). Odds API plan upgraded 2026-09-27 to 100,000 credits a month.

---

## 1. The idea, in one paragraph

Every system this project has built reads ONE kind of information and bets from it: a regression on stats, a sim,
an archetype board. By Jeff's read, the best of them (MLB) got to matching Vegas; none clearly beat it. What has never been
tried is the thing a good bettor actually does: look at everything at once — what the line and its movement say,
what the news says, what history says, what our own models and sims say — and make a judgement. The Layers System
makes the AI that judgement step. **The layers are the inputs; the AI's reading of them is the pick** (standing
rule N54). If there is an edge, it is in the combination and the interpretation, not in any one layer.

## 2. Why it can only be tested going forward

This is not a preference; it is forced by how the reader works. A language model has read the internet up to its
training cutoff, which includes the results of past games, season outcomes, and who turned out to be good. Any
"historical test" of the reader is contaminated at the source (CHECK 1b and CHECK 2 fail by construction), and no
amount of care in building the historical layers fixes that. So:

- The reader is judged ONLY on picks frozen before the event, hashed, and posted outside the repo (project status
  doc) before the first puck/tip. That is the whole evidence base. It already exists for football (N59/N61/N62).
- Layers themselves (a sim, a goalie model) CAN be tested historically if built point-in-time, and must be, before
  they are trusted as layers. The reader cannot.
- Nothing is tuned on the window being scored. If the reader's method changes, that is a new version, judged only
  on games after the change (N62).

## 3. The layer stack (same for every sport)

Each layer is a set of files with a timestamp. The reader sees a **packet** per slate that pulls them together.
The packet is saved and hashed with the picks, so we can always say exactly what the reader saw (CHECK 3: the
object we score is the object that picked).

| # | Layer | What it holds | Where it comes from |
|---|---|---|---|
| L1 | Market | open, current and line movement at Pinnacle (the sharp reference) and Hard Rock (the bet book), cross-book spread, props | 30-min multi-book tape `data/odds_archive/<sport>/line_history/`; props pulls |
| L2 | News / availability | injuries, confirmed starters (NHL: **starting goalies**; NBA: injury report + rest), travel, back-to-backs | per-sport news capture; every item keeps its source and retrieval time |
| L3 | History | team and player form, AS OF the game (point-in-time), matchup history, schedule spots | existing canonical tables (`nhl/`, `nba/`) |
| L4 | Models and sims | anything we have built: NHL goalie model, NBA venue board, NFL sim. Logged as a vote with its own probability; **gates nothing** | the sport's existing pipeline outputs |
| L5 | Reader | the AI's probability on every line, a side, a primary tag, the layers that drove it, one-to-two-sentence reason, and the model's name | `nfl/pipeline/log_ai_opinions.py` (freeze), extended per sport |
| L6 | Scoring | Brier vs the de-vigged book, units at the real frozen price, closing-line value vs Pinnacle's close, breakouts | same tool, `score` |
| L7 | Cards | tickets for Jeff drawn FROM the frozen log (largest gaps, distinct ideas); placements and the Hard Rock export ledger | `<sport>/data/board/.../*_ticket_placements_*.json`, `bets/` (gitignored) |

Two additions to what football does today, built into NHL from day one:
1. **Packet saved and hashed** alongside each frozen file (football saves reasons, not the packet).
2. **Drivers field**: for every line the reader names which layers moved it (e.g. `market,news`). This is what later
   answers "is the moat the interpretation, or is it just one layer doing the work?" without any historical test.

## 4. What "it works" means — written down now, before any NHL or NBA pick exists

Primary metric: **closing-line value (CLV)** against Pinnacle's close, on the sides the reader takes. It converges
fastest and does not depend on luck in the result. Secondary: Brier score vs the de-vigged book, and units won at the
**real frozen Hard Rock price** (never a flat -110; CHECK 4).

The reader has to beat three baselines, all logged the same way on the same lines:
- (a) the book itself (de-vigged price at freeze; and at the close),
- (b) the best single model layer where one exists (e.g. the NHL goalie model's own probability),
- (c) "follow the move" (the side the line moved toward from open to freeze).

If the reader does not beat (b) and (c), the interpretation is not adding anything over the layers alone.

How long it takes to know (honest arithmetic): at about -110, the standard error of ROI after n independent bets is
about 1/sqrt(n): ±3.2 points after 1,000 bets, ±1.6 after 4,000. Lines on the same game are correlated, so the
effective n is smaller. Units alone will not settle it in one season. CLV will say something much sooner.
**Checkpoints (pre-registered): report at 500 and at 1,500 graded sides per sport. No keep/kill decision before
1,500, and that decision is a named decision pass, not momentum.** Every report breaks out by month, market, tag,
driver, gap size, reader model, and early-season vs later (CHECK 5).

## 5. How a slate runs (NHL and NBA are daily sports)

1. **Captures run on their own**: line tape every 30 minutes; props and news pulls on a schedule tied to the sport
   (NHL: after morning skate / goalie confirmations; NBA: after the 5:30pm ET injury report).
2. **Packet built** for the slate (automated once built; by hand in the pilot).
3. **Reader reads and writes** a probability and a side on every line, with tag, drivers and reason. Any news the
   reader looked up itself goes INTO the packet with its URL and time, or it cannot be used.
4. **Freeze** with `--reader-model` (N62) before the first puck/tip. Post the sha256 in
   `claude/capture_status_2026-09-20.md` before the event. Late games may be a second file; only revision 0 of a line
   is ever scored.
5. **Cards**, if Jeff wants one, come from the frozen file only.
6. **Grade** the next morning from the league's own finals; score automatically; weekly scorecard.

Later, once the manual loop is stable: a scheduled task on Jeff's Mac can build the packet and wake a reader
session each day. Whatever model runs it is recorded like any other reader.

## 6. Credits (100,000 a month)

Measured today: the whole existing system burns about 590 credits a day. Additions, estimated (week 1 measures
them):
- Line tape: 3 credits per sport per call x ~32 calls a day = **~96 a day per sport** (NHL, NBA).
- NHL props: roughly 1 credit per market per game; ~12 games x ~8 markets ≈ **~100 per pull**, one pull a day.
- NBA props: similar, up to two pulls a day (before and after the injury report) ≈ **~150 a day**.
- NFL props: 15 per game per pull (measured), 3-4 pulls a week.
Total ≈ 1,100-1,400 a day ≈ 35-42k a month: well inside 100k. The per-run floor stays in every paid script
(`--floor`, default 3,000) as a guard against a runaway loop, not as a budget.

## 7. One repo, one project — where things live

- `research/layers/` — this plan, `LAYERS_DECISION_v1.md` (cross-sport rules, entries L1, L2, …; edited only from
  the main Cowork chat), `reader_method_v1.md` (how the reader weighs layers; versioned).
- `shared/layers/` — the packet builder and anything two sports share.
- `nfl/pipeline/log_ai_opinions.py` — the freeze/score tool. It grows `nhl` and `nba` entries in its `SPORTS` table
  and a **date-keyed slate** (daily sports have no weeks). It is not moved mid-season.
- `<sport>/data/board/date=YYYY-MM-DD/ai_opinions/` — frozen picks, packets, manifest, `reader_attribution.json`.
- `research/nhl_layers/NHL_LAYERS_DECISION_v1.md` (entries H1, H2, …), `research/nba_layers/NBA_LAYERS_DECISION_v1.md`
  (B1, B2, …). **One decision doc per sport**, so two chats never append to the same file (the
  `agent_sessions.md` conflicts taught that).
- Project docs: `claude/LAYERS_GAMEPLAN_2026-09-27.md` (this), `claude/nhl_layers_handoff.md`,
  `claude/nba_layers_handoff.md` — each sport chat keeps its own handoff current at the end of every session.
  `claude/capture_status_2026-09-20.md` stays the one place hashes are posted, one section per sport.

**Who edits what:** a sport chat changes only its sport's folders and its decision doc. Changes to shared code
(the freeze tool, the capture script, `shared/layers/`) go through one work order at a time, on a branch, merged by
Jeff with the usual `&&` command. The NFL sim (5Y running now) and NHL work never touch the same files.

## 8. Readiness checklist — work through it before the first frozen pick in a new sport

Each item is checked from FILES, not from a report, and ticked in the sport's handoff doc with the date.

**Capture**
- [ ] The sport is on the 30-min line tape; snapshots are landing (count them for one day).
- [ ] Hard Rock is among the books returned for the sport (the tape logs "books NOT returned"); if not, say so —
      Pinnacle stays the book of record, Hard Rock prices are then Jeff's app only.
- [ ] Props pull works: markets actually offered are listed from the API, cost per pull printed, `--floor` present.
- [ ] News source for the key availability item (NHL starting goalies; NBA injury report) captured with timestamps.

**Log and scoring**
- [ ] `log_ai_opinions.py` has the sport in `SPORTS` (book of record, lines, props, outcomes source), date-keyed.
- [ ] Freeze refuses without `--reader-model`, refuses post-start games, reads prices from the tape (existing tests
      extended to the sport).
- [ ] Packet file written and hashed beside every frozen file; drivers field required on every row.
- [ ] Outcomes loader grades one real finished game end to end (NHL: api-web.nhle.com; NBA: the pipeline's source).
      Overtime / shootout rules stated for each market (NHL moneyline and totals include OT and shootout at most
      books — verify from Hard Rock's rules and write it down).
- [ ] Baselines (b) and (c) from section 4 are logged on the same lines.

**Discipline**
- [ ] Provenance: every packet item has a source time before freeze (1a). Any history layer used is point-in-time (1b).
- [ ] No tuning: the reader method file is frozen for the pilot; changes after the pilot = new version.
- [ ] Pilot dates and record start date written into the sport's decision doc BEFORE the pilot starts.
- [ ] Hash posted in the status doc before the first event, every slate.

## 9. The sport plans

### NHL (opens Tue Sep 29)
Already in the repo: a live NHL model (goalie-vs-team baseline as the primary signal; MoneyPuck xG coverage), the
NHL API (`api-web.nhle.com`) for schedule, boxscores and goalies, canonical tables, and a props folder under
`data/odds_archive/nhl/`. NHL is NOT yet on the 30-min multi-book tape (`multi_book_open_capture.py` covers MLB,
NFL, NCAAF).
- **Before Tue (Sep 27-28):** put `icehockey_nhl` on the tape so opening-night lines are captured; NHL chat opens,
  reads this plan, verifies the files and writes NHL work order 1 (tape + freeze-tool entry + NHL outcomes loader +
  packet builder + props pull).
- **Pilot: Sep 29 - Oct 4** (by hand if the tooling is not finished: game lines from the tape, goalies from the
  news). Pilot files are never pooled.
- **Record starts Mon Oct 5.** First checkpoint at 500 graded sides.
- Known gap: confirmed starting goalies before puck drop are the single most important NHL news item, and the NHL
  API's starter flag is not a reliable pre-game source. Work order 1 measures what the available sources give and
  when.
- Early-season thinness: every history layer is weakest in October; the reader should know that (method file).

### NBA (opens Tue Oct 20)
Already in the repo: live NBA pipeline with signal boards (venue board OVER system), ESPN injury feed in
`nba/run_nba.py`, props folders, graders. The venue board is a model layer (L4) with its own logged probability.
- **Early October:** NBA chat opens, runs the checklist; NBA on the tape from preseason (pipes tested on preseason
  games as an unscored dry run).
- **Pilot: Oct 20 - Oct 25. Record starts Mon Oct 26.**
- News is the heavy layer in the NBA (late scratches, rest, minutes limits): freeze time is after the 5:30pm ET
  injury report; lines that move after freeze are recorded as CLV, never re-picked.

### Football (running)
NFL and NCAAF already run the blind log (N59, N61, N62). They adopt the packet file and drivers field when the
shared tool gets them; nothing about their record changes.

## 10. Decided by Jeff 2026-09-27 ~14:20Z (details: `research/layers/reader_method_v1.md`)
- **A side on every wager, with a reason — every sport, no abstaining.** One side wins, one loses; unrecorded data
  can never be recreated.
- **Confidence ranking:** every line gets `conf` (0-100, conviction that it is a good bet at the price — not the chance
  it wins) and `conf_rank` (1 = best bet of the slate). Scored by rank band (1-10, 11-25, 26-50, 51+); band 1-10 is
  pre-registered to beat the rest on CLV.
- **Top 10** = conf ranks 1-10 frozen by a posting time Jeff sets later; shown first on the website; scored separately.
- **Post-freeze news** (injury, scratch, lineup, goalie change after the picks) is logged as the likely reason for a
  miss, with source and time; it never changes a grade or removes a row.
- **Automate** (scheduled daily run per sport) and **bring the website back** — design pending (work orders).
- **Model:** Opus by default; every file records the model; Fable/Opus compared on paired slates; a clear Fable edge
  -> named decision on a bigger plan.

## 11. Still open
- Top 10 per sport or across all sports each day (default per sport).
- The posting time T for the Top 10.
- How the scheduled run is hosted (VM, Mac, or cloud scheduled task) and what the website shows beyond the Top 10.
