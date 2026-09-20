# Adjudication — ChatGPT audit #4, the parlay board (2026-09-20)

Audit target `2fed099`. Adjudicated by Cowork against files at `9eb533f`. Each finding below was
re-run here, not taken from the audit's word. **Verdict: the audit is right on every defect I
could test, and two of them are mine.**

## Confirmed by reproduction

| # | Finding | How it reproduced |
|---|---|---|
| 1 | **The scheduled grader crashes on the committed log.** | `grade_tickets(2026)` on a temp copy: `KeyError: 'event_id'`, 0 of 31 graded. 4 card entries carry `event_id` on their legs; `grade_ncaaf_tickets.py:83` reads it at the top level. It writes nothing, so the 13:00Z scheduled grade fails safe. |
| 2 | **Logged legs are contracts no book offered.** | Latest AI build (2026-09-19T11): **17 of 30** spread/total legs pair `consensus_point` with another line's `best_price`/`best_book` (`build_ncaaf_tickets.py:226-228`). e.g. Ohio State -52.5 @ -110 betonlineag, where that book had -52.0. Same count the audit found. In `build_ncaaf_board.py` the Under/h2h branch is worse: median point + the FIRST book's price. |
| 3 | **The selector receives no news.** | Production reader logic on the real archive: 14,526 loaded -> 1,381 retained; **1** has `team_name` — a December 2025 Wyoming article. The new puller writes `_team_name`; the selector filters on `team_name` (`:195`). All 3,820 legacy articles lack `id` and collapse onto one key. The prompt also takes `news_articles[:10]` unsorted. |
| 4 | **CLV ignores the line; pick de-vigged with the closing complement; arbitrary-book fallback.** | Read in source; `point` absent from the grader. (These were in the brief.) |
| 5 | **"Close" has no maximum age, and a missing close still sets `graded=True`.** | `_load_closing_prices` takes the last pre-kick row with no age bound; `ticket["graded"] = True` is unconditional after the leg loop. |
| 6 | **The health check can certify the wrong feed.** | ESPN depth, the nflverse wrapper and the depth-delta script all append to ONE `data/depth_archive/nfl/season=2026/_pulls.jsonl`; `_newest_pulls_age` reads the last line whoever wrote it, and both feeds' checks point at that file. |
| 7 | **A partly failed news pull writes a fresh file.** | `pull_espn_news.py:105-115`: per-team request errors and non-200s are counted and skipped; nothing acts on `errors`. |
| 8 | **The joint table measures HOME cover, not favourite cover**, with closing totals. | `build_joint_table.py:50`: `cover = (homeScore - awayScore) + spread > 0`. A road favourite's blowout is scored as the home dog failing to cover. 2025 was looked at before the final bucket choice, so it is consumed for that choice. |

Not reproduced by me: the bootstrap interval 0.654-0.841 on the home-cover factor (plausible for
n = 137); the two 141.5 h / 148.5 h "closes"; the HTTP-500 news reproduction.

## Where the audit is already out of date (it read `2fed099`; the ledger landed in `9eb533f`)

- **Claim 1 (cross-game = product)** is no longer one slip: **16 of 16** one-leg-per-game parlays
  in Hard Rock's own export price at 0.9994-1.0004 of the product, 3-15 legs, four sports.
- **Claim 2** no longer rests on assumed -110: per extra same-game leg, NCAAF cover+over
  0.713 / 0.755; NFL prop SGPs 0.91 median; opposing-team pair 1.009.
- **Claim 6**: settled ledger exists (34 slips). And one recorded "win" was a loss.
- Its change #1 (execution-and-quote ledger) is mostly met by the export: exact contracts, at-bet
  single-leg prices, the accepted parlay price, stake, settlement, per-leg results. Still missing:
  the complement price of each leg, any closing price, a boost flag, and the link from a slip to
  the recommendation that produced it.

## What I got wrong

- **N36 called the ticket reader "correct, with one nit: articles with an empty id collapse into
  one."** Every legacy article has an empty id, and the field rename went unnoticed. It was not a
  nit; the reader change shipped in #10b and verified by me disconnected the news layer entirely.
  I checked that the reader parsed files, not that the selector received articles.
- **I added the third writer to the shared `_pulls.jsonl`** (the depth-delta script) and told
  Jeff the health check was sound.
- **My brief said the capture "is sound".** Arrival was verified; completeness and correctness
  were not.

## Accepted, and what changes

1. **Retire "Hard Rock over-charges 6.3%" and "fair value 0.746".** The table is home-cover on
   closing totals; the interval spans 0.70-0.80. What survives is only what the ledger measures:
   what Hard Rock CHARGES. **One leg per game stays as a simplicity rule, not an economic proof** —
   and for NFL props the measured charge (~9% per added leg) is a price, not a verdict.
2. **CLV, as defined by the audit:** point CLV always (entry minus close for a spread on the same
   team; close minus entry for an Over; entry minus close for an Under); probability CLV only when
   the ORIGINAL threshold is quoted at the close, each side de-vigged with its own same-book,
   same-snapshot complement, as `C = d0 * qc - 1`; otherwise "unavailable", never the new main
   line. "Close" = last complete pre-kick quote within 30 minutes; older = "last observed";
   missing = pending, never `graded`.
3. **The AI layer is reframed as source-linked news flagging.** Selection is graded in shadow,
   against two pre-declared baselines (equal-count favourites; the favourite on the AI's own
   games), only after the inputs and the grader are repaired. "~125 observations" is withdrawn
   as a bar — there is no universal number.
4. **Nothing in the NCAAF log to date is evidence of anything**: the legs are not real contracts,
   the news never arrived, and the grader cannot run. The record is kept, flagged
   `pre_repair: true`, and excluded from any future scoring.

Work order #11 (`research/ncaaf_board/WORK_ORDER_11_2026-09-20.md`) implements 2-4 and the
capture fixes. The quote experiment (30 distinct-game pair quotes, no stakes) and the totals-vs-
consensus check need Hard Rock quotes the Odds API does not serve for NCAAF — they wait on order #9.
