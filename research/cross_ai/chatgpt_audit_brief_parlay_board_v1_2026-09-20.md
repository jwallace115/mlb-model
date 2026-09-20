# ChatGPT audit brief — the parlay board as actually used (2026-09-20)

Fourth external audit, first one of THIS system. Audits #1-#3 were of the NFL simulation
engine. **The engine is out of scope here** — no `engine.py`, `anchor.py`, calibration maps,
pricer, K1 or fit. It continues as a hobby build and does not gate any ticket.

Repo: `jwallace115/mlb-model`, pinned to **`2fed099`** on `main`. Read-only audit.

**Posture: guilty until proven innocent.** Where a claim below was recomputed from committed
artifacts it says so; where it rests on a session's report or on a bet slip, it says that.

---

## 1. What the system is

A parlay builder for entertainment stakes ($10-15 a card), NFL Sundays and college Saturdays,
bet at ONE book: Hard Rock Bet Florida. **No edge is claimed.** The stated goal is an educated
pick with reasoning behind it, and a log good enough that closing-line value accumulates as a
free by-product.

Four layers, no simulation: **lines -> news/injuries/roles -> AI selection -> ticket + CLV log.**

| Layer | What it is | Where |
|---|---|---|
| Lines | Odds API multi-book game lines, NFL + NCAAF every 30 min (14:00-05:30 UTC), since 2026-09-06 | `data/odds_archive/{nfl,ncaaf}/line_history/` |
| Props | Hard Rock NFL player props, 8 scheduled slots/week (Tue open ... Mon close) | `nfl/pipeline/pull_hardrock_props.py`, `data/odds_archive/nfl/props/` |
| News | ESPN per-team news, NFL 32 teams + NCAAF board teams, every 6 h, de-duplicated by article id with a per-pull index | `shared/pipeline/pull_espn_news.py`, `data/news_archive/` |
| Status | ESPN NFL injuries + depth charts every 6 h (gzip, hash-skip); nflverse depth/injuries/rosters daily | `shared/pipeline/pull_espn_nfl_status.py`, `archive_nflverse_depth_delta.py` |
| Kalshi | NFL + NCAAF game / spread / total markets, every 30 min, public endpoint | `shared/pipeline/pull_kalshi_football.py` |
| Roles (NFL) | Player carry/target shares, the one sim-adjacent piece in use | `nfl/sim/usage.py` -> `player_usage_weekly.parquet` |
| Selection (NCAAF) | `claude-haiku-4-5-20251001` picks at most one side per market per game from lines + news, may abstain; forbidden from emitting any pricing number | `ncaaf/pipeline/build_ncaaf_tickets.py` |
| Selection (NFL) | **A chat session.** An LLM reads the props pull, roles and news and writes the ticket in conversation. No frozen prompt, no code path | nowhere in the repo |
| Cards | 5-leg "conviction" card + 10-leg longshot with FILLER legs marked | `ncaaf/pipeline/build_ncaaf_cards.py` |
| Grading | CLV per leg vs the last pre-kick snapshot | `ncaaf/pipeline/grade_ncaaf_tickets.py`, `nfl/sim/grade_week.py` |
| Health | File-age check per feed, hourly, reads filenames only | `shared/pipeline/capture_health.py` |

Decisions: `research/ncaaf_board/NCAAF_BOARD_DECISION_v1.md` (N01-N36). Spec:
`NCAAF_BOARD_SPEC_v1.md`. Capture state: `capture_status_2026-09-20.md`.

## 2. What is claimed, and on what evidence

1. **Cross-game parlays at Hard Rock pay exactly the product of the single-leg prices.**
   NOW MEASURED from Hard Rock's own bet-history export (35 slips, 213 legs, 2026-08-22 ->
   09-19; every leg carries its at-bet decimal price): **16 of 16 one-leg-per-game parlays have
   quoted price / product of legs between 0.9994 and 1.0004**, 3 to 15 legs, four sports. A
   Void or Push leg is repriced to 1.0 (two slips; both reconcile exactly). Replaces the
   one-slip evidence this claim had yesterday.
2. **Same-game legs are charged, and the charge depends on what is paired.** From the same
   export, 17 parlays with same-game legs; ratio = quoted / product, per extra same-game leg:

   | sport | slips | per-extra-leg factor (median; min-max) | whole-slip ratio (median) |
   |---|---|---|---|
   | NCAAF cover+over pairs | 2 | 0.734 (0.713 - 0.755) | 0.377 |
   | NFL player-prop SGPs | 6 | 0.910 (0.882 - 1.009) | 0.701 |
   | WNBA | 7 | 0.904 (0.695 - 0.986) | 0.686 |
   | MLB | 2 | 0.927 (0.884 - 0.970) | 0.913 |

   So the "0.70 per pair" in `hardrock_sgp_adjustment_2026-09-19.md` was computed against
   ASSUMED -110 legs; with real leg prices the two college slips are 0.713 and 0.755 (the second
   on a BOOSTED quote). A 4-leg one-game NFL prop ticket pays ~0.69-0.72 of the product in total.
   The one slip with a same-game pair on OPPOSING teams (two receivers, TB@CIN) paid 1.009 — no
   charge. The ledger itself is private (gitignored `bets/`); only these aggregates are shared.
3. **Fair value for that pair is 0.746**, from ONE cell of `joint_outcome_table_v2.parquet`
   (|spread| >= 21, OU < 50, n = 137: P(cover & over) 0.3796 vs 0.2831 independent). Hence
   "Hard Rock over-charges 6.3% per pair" and the operating rule **never stack same-game legs.**
4. **Big-favourite cover/over correlation is real**: |spread| >= 21, phi 0.195-0.304, t
   3.75-4.20 across 8 configurations (2 windows x 2 line keys x 2 bin conventions), and "held
   OOS on 2025". The 7-14 extension and the 14-21 bucket were withdrawn. N05-N10.
5. **Hard Rock totals ran a point below consensus, 4 for 4.** Stated as unverified.
6. **Record, from the export, settled slips only:** all 34: 6 won / 27 lost / 1 cashed out,
   staked $495.51, returned $889.72. Slips built by this system (7, tagged by hand): 3 won / 4
   lost, staked $105 (one a $20 bonus bet), returned $753.37 — of which $444.60 is one ticket.
   The other 27 (group-chat and personal picks): -$254.16. 191 settled legs hit 63.9% against a
   mean vig-inclusive implied 61.1%. None of this is a sample. **Correction:** this project's
   notes said the 09-19 cross-game 4-leg "won $195.12". It LOST (1 of 4 legs); $195.12 was the
   potential payout. The pricing identity from that slip stands; the result was misreported.
7. **The capture is sound:** append-only, a failed pull halts and writes nothing, in-play rows
   dropped, health check agrees between the VM and a fresh clone. Verified from a fresh clone
   at `c78b3c8`; every new scheduled feed was then observed firing on its own overnight 09-20,
   EXCEPT props, whose first scheduled slot (2026-09-20 15:00Z) had not arrived at time of writing.
8. **No prop family beats the closing price** (from the engine audits, carried here as the
   reason the book's own de-vigged price is treated as the best available probability):
   72,897 real legs 2023-24, Brier book 0.2316 / coin flip 0.2500 / calibrated sim 0.2534.
   Recomputed from `research/nfl_sim/k4_rows_fit_5d2.parquet`.

## 3. Defects I found while writing this brief — unfixed, confirm or refute

- **CLV ignores the line.** `grade_ncaaf_tickets.py` matches the close on
  (event, market, outcome_name, book). `point` appears nowhere in the file. A pick at -24.5
  that closes -27.5 is scored as price-vs-price (-110 vs -110) = ~0 CLV, when the 3 points ARE
  the closing-line value. For spreads and totals the log as built measures almost nothing.
- **The pick is de-vigged with the CLOSING complement** (`pick_devig = pick_imp / (pick_imp +
  comp_imp)`, commented "approx") — two timestamps mixed in one ratio. The project has had
  three defects from mixing price scales already (D58, D64, D82).
- **Fallback to "any book"** takes `match.iloc[0]` — an arbitrary book's close.
- **Nothing grades outcomes.** No win/loss, no hit rate, anywhere in the NCAAF path. 31 tickets
  logged, **0 graded** at the pinned commit (a scheduled grade was due 13:00Z on 09-20).
- **Every NCAAF ticket is `reference_only: true`.** `hardrockbet_fl` has been absent from the
  Odds API's NCAAF feed in every one of ~700 snapshots, so logged prices and CLV are at books
  that cannot be bet, and the card is priced off numbers the bettor never sees.
- **There was no ledger of actual wagers until today.** Results lived in chat transcripts and
  an assistant's memory file, and one was wrong (claim 6). Now: `shared/pipeline/
  ingest_hardrock_bets.py` upserts Hard Rock's export by slip id into a private ledger, halts on
  a changed header or row shape, and derives quoted-vs-product per slip. Still missing: which
  slips this system built is a hand-kept tag; nothing links a slip to the board/ticket that
  produced it; no closing price is attached to a bet leg.

## 4. What I most want attacked

Ranked by how much is lost if I am wrong.

1. **The 0.746 / "never stack same-game" chain.** The price side is now measured (claim 2);
   the soft links left: a fair value from one 137-game cell applied to pairs that were
   not all in that cell; and a rule generalised to NFL player props from college cover+over
   pairs. Is the rule still right if the true factor is 0.75-0.80? What is the minimum logging
   (per slip: every single-leg price at the moment of the quote, the quoted parlay price, the
   boost) that would settle it in a month, and how many slips?
2. **Claim 4 under the project's own leakage rule.** The 21+ cell survived after eight
   configurations were looked at, one bucket was withdrawn and one extension dropped. Was 2025
   touched in any of that before it was called held-out? N09 records a bin-convention change
   between probe and OOS. Is "significant in all eight" eight tests or one test eight ways?
3. **The AI selection layer has no evidence at all, and can it ever get any?** ~125 CLV
   observations was the stated bar — but see section 3: the CLV it would be graded on is broken
   and at unbettable books. 70% abstain on the first slate. A rationale quoted in work order #9
   ("top-6 program at home vs weak FBS opponent") restates what the spread already contains.
   What would a selection layer have to show to be distinguishable from picking favourites?
4. **NFL selection is an unlogged LLM in a chat window.** Considered-and-rejected legs were
   logged once (MNF, 30 legs). Otherwise the process is unreproducible and its record is
   hearsay. What is the smallest frozen procedure that makes it auditable without pretending
   it is a model?
5. **Point-in-time integrity of the new archives.** News is de-duplicated by
   (article id, lastModified) with a per-pull index; depth charts are stored as a delta keyed
   on nflverse's own `dt`; status feeds hash-skip with ESPN's `timestamp` stripped. Can "what
   was knowable at pull T" be reconstructed exactly? Known hole: a retroactive nflverse edit
   is detectable by hash, not reconstructable. Is the ticket builder reading ALL archived
   articles (it does) rather than a recency window a problem for the selection prompt?
6. **The health check measures arrival, not correctness.** It reads filename timestamps. A
   puller that writes a fresh, well-formed, WRONG file is green. The tests for the ticket
   reader still exercise a replica of the code rather than the code (N36).
7. **Hard Rock totals "4 for 4 under consensus."** n = 4. Worth a pre-registered check against
   the 30-min tape, or noise to be dropped?

## 5. Standing failure classes in this repo — look for more of them

- **A failure written into an output field instead of halting** (a 404 into `ai_rationale`; a
  premature grade into `clv`; a swallowed TypeError reported as "feed stale 4,226 h").
- **Guards that cannot fail** (tests asserting types; tests of a replica of the code).
- **Schedules that look installed and write nothing** (the props cron never fired for a week;
  a 0-byte macOS cron log for weeks; a depth feed dead 4.5 days in a game week).
- **Summaries that contradict their own artifacts** ("passes on all 11 seeds" beside a suite
  showing it fail; a storage estimate off by 4x on its own table).

## 6. What a reply is most useful on

Not a general review. (a) Is the same-game pricing rule sound enough to keep acting on, and
what exactly to log to settle it. (b) The correct CLV definition for spreads, totals and props
when the line moves — points, price, or a probability-scale conversion — and whether CLV at
reference books means anything for a Hard Rock-only bettor. (c) Whether the AI selection layer
is worth grading at all, or should be reframed as a news-flagging layer with selection left to
price + role rules that CAN be written down.
