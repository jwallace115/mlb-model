# ChatGPT audit brief #5 — the parlay board after repair, and TODAY's NFL procedure (2026-09-20)

Second audit of this system (audit #4 was this morning, at `2fed099`). The NFL simulation engine
is again **out of scope** — it gates nothing. Read-only audit.

Repo: `jwallace115/mlb-model`, branch `main`. **Pin: the commit whose message begins `N43:`**
(its parent is `8800bcb`, "N41/N42"). If `N43:` is not on `main` yet, audit `8800bcb` and read
section 3 as a specification.

**Posture: guilty until proven innocent.** Audit #4 was right on every defect that could be tested,
and two of them were the verifier's own. Assume the repairs below contain the same classes of error.

**Why now:** tickets are placed today ~16:30-16:45 UTC for 17:00 UTC kickoffs. A reply is most
useful if it separates **(A) what could change today's ticket** from **(B) what only affects the
log and later grading**.

---

## 1. What the system is (unchanged)

Entertainment parlays, $10-15, one book (Hard Rock Bet Florida). **No edge is claimed.** Layers:
lines/props -> roles + injuries + news -> selection -> ticket + log. Decisions:
`research/ncaaf_board/NCAAF_BOARD_DECISION_v1.md` (N01-N43). Adjudication of audit #4:
`research/cross_ai/chatgpt_audit4_adjudication_parlay_board_2026-09-20.md`.

## 2. What changed since audit #4

Work order #11 (another AI session, N37-N40) implemented your findings. The verifier then RAN the
production functions on the real tape / news archive / results file and found the repair half
done (N41, N42). Both layers of change are in the pin.

| Your finding | Repair | Verified how |
|---|---|---|
| Legs were contracts no book offered | A leg is one row of one book; best point, then price, then book name; same-book same-snapshot complement stored; asserted against the tape keyed on event + snapshot (N37, N42) | Real tape, 2 build times: 356 sides, 0 mismatches. Full 89-event board with a mocked model: 154 legs, 154 complements, 0 halts |
| Selector got news for 1 of 146 teams | `load_news(news_dir, build_time)`, both field names, pull-time cutoff (N39); 14-day window actually applied, coverage halt 90% (N42) | 145/145 and 40/40 board teams; 0 articles pulled after build time |
| Grader crashed; CLV ignored the line; any-age close; graded=True unconditional | Grades legs on cards and events; point CLV + probability CLV only on the original threshold with each side's own same-snapshot complement; close = last pre-kick row within 30 min (N38) | point CLV vs an independent formula: 263/263 |
| (found in verification) **no event ticket could get an outcome** — kickoff read from the leg, stored on the ticket; 263/263 `outcome_unavailable`; the test fixture's team names could never match | Unordered team pair within 36 h, points by team name, explicit names where the mascot-stripper fails ("Southern Mississippi" -> "Southern"), `pending` until the results file has the score, `graded` needs every close AND every result, outcome computed without a close, kickoff = the tape's last pre-kick `commence_time` (127/189 events drift; 4 games > 30 min on 09-19) (N41) | 71/71 kicked 09-19 games, 284 legs, 0 disagreements with an independent re-derivation; 188/189 tape events match the results file |
| Health check could read another feed's pulse | Per-feed filter (N40); then every writer tags `feed`, ESPN hash-skip reads only its own lines (N41 — the order said so and it had not been done) | Real log lines as fixtures; health OK x10 in a fresh clone. **Not yet observed on the VM** |
| (found) Card builder untouched by the repair: FILLER legs = consensus point + another book's price | Fillers through the same quote rule; card legs keep snapshot + complement; board built in memory (N42) | 5 + 12 legs, 4 fillers, all real rows |
| (found) Stale quotes: the board keeps each book's last quote however old (max 303 h); 2.8% of quotes, **6.5% of best-quote picks** | Legs only from the event's newest snapshot (N42). **The board's own consensus/dispersion still includes stale quotes** | Real-tape test: a 40-min-old FanDuel -106 loses to a live DraftKings -108 |
| Abstains and inputs not logged | Every game seen writes an entry (ticket or abstain) with model id, prompt sha256, raw response, article keys, tape snapshots (N42) | 89 entries / 12 abstains on the mocked full board. **No live model call has been made since the repair** |
| "0.746 fair value / 6.3% overcharge" | WITHDRAWN. What stands is what Hard Rock charges, from its own slips | — |
| NFL selection = an unlogged chat | Section 3 (N43) | 6 tests, 6 mutations |

Tests: one command, 74 passed. The new tests import production functions and use fixtures cut
from real archives. Honest limit: of the 13 N41/N42 tests, 4 fail on the old code because a
signature changed, not because behaviour did.

## 3. TODAY's NFL procedure (N43) — new, untested in production, attack this first

`nfl/pipeline/build_nfl_candidates.py`, written before today's 15:00 UTC pull exists:

1. Newest Hard Rock props pull <= build time; pre-kick rows; un-kicked games; nothing later is read.
2. Two-way markets de-vigged proportionally from the SAME ROW. One-way (anytime TD) never eligible.
3. Roles from `player_usage_weekly.parquet` (2026, week 2) by normalised name within the game's
   two teams; ESPN injury status from the newest file <= build time.
4. Eligible = receptions / rush attempts / pass attempts / completions AND two-way AND role
   matched AND not Out/Doubtful/IR AND pull <= 3 h old. Pick side = the side the book favours.
5. Two rule baselines, top 5 by de-vigged q, one leg per game: any eligible leg; and Overs on a
   team's top-2 target share / top carry share / starting QB.
6. A reader (an LLM in a chat, reading archived news + injuries) writes the final ticket.
   Logged append-only beside the baselines; a veto without a reason AND a source is refused.

Timeline (UTC): props pulls 15:00 and 16:30, pushed to GitHub up to 30 min later; ESPN injuries
12:30 and 16:40; NFL inactives publish ~15:30; tickets placed ~16:30-16:45; kick 17:00.

**Measured on the real 09-19 15:11Z pull:** two-way hold 6.7-7.0% in every family. Top-5-by-q =
low-line Unders (TE2 receptions U1.5 -230); price 7.29 vs product of de-vigged q 0.0957 ->
**expected return 0.70 per 1 at the book's own numbers.** Lead-role Overs sit at q 0.58-0.59.

## 4. Where I think it is still weak — confirm, refute, or add

1. **The ticket is priced off a pre-inactives pull.** The 16:30 pull cannot reach the reader
   before kickoff; the injury feed's Sunday slot (16:40) is after the bet. What is the minimum
   written rule for "the app shows a different line/price than the candidate table" — skip,
   accept within a band, or re-derive q by hand? Is a 3 h staleness limit defensible at all on a
   Sunday morning?
2. **Proportional de-vig on a 7% hold.** Does ranking by proportional q systematically favour
   low-line Unders / heavy favourites (favourite-longshot, integer-count props with lopsided
   pricing)? Is there a better de-vig for count props, or should q only RANK within a family and
   line band? Is "top-q" a meaningful baseline or just "the most lopsided prices"?
3. **Usage week semantics.** The week-2 rows must contain only information through week 1.
   `nfl/sim/usage.py` is sim-adjacent code the audits have found leaks in before (class 1b:
   2025+ depth charts filling 2021-24). Is the 2026 week-w row point-in-time? Is one 2026 game
   plus a 2025 prior a role, or noise that the rank-within-team rule turns into a hard cut?
4. **Name join.** Roles: normalised name within the game's two teams; a duplicate name ->
   `role_unmatched`. Injury status: (team, normalised name). A player ESPN lists under a
   different spelling silently reads as "no status" — 154 of 973 rows have none on the 09-19 pull.
5. **The reader layer.** It is still an LLM in a chat. The log now records what it overrode and
   why. Pre-registered comparison: final ticket vs each baseline vs the vetoed legs, on hit rate
   and CLV. Is that comparison capable of showing anything at 5 legs a week, and what is the
   honest way to say so?
6. **No NFL grader exists for this log.** Close = last pre-kick Hard Rock pull within 30 min:
   the 20:25 kicks are 40 min from the 19:45 pull. Outcomes not joined. Is the 30-minute rule
   right for props pulled at fixed slots, or should the slots move?
7. **NCAAF point CLV is measured on the best quote across books**, which is biased upward
   against any single book's close, and every NCAAF leg is at books that cannot be bet.
8. **Same-game pricing** (unchanged evidence): cross-game = product on 16/16 slips; NFL prop SGPs
   ~0.91 per extra leg, ~0.70 for a 4-leg one-game ticket. With a 0.70 expected return on a
   5-leg CROSS-game ticket from hold alone, is "one leg per game" still the right default for NFL,
   where same-game legs are genuinely positively correlated?
9. **Guards that cannot fail / code present but not reachable** — the repo's recurring classes.
   Anything in N41-N43 that is asserted by a test but not exercised by the production entry point
   (`main()`), or a halt that a realistic bad input would slip past.

## 5. What a reply is most useful on

(A) **Today:** a ranked list of changes to section 3 that can be made in under two hours and would
change which legs are eligible or how a leg is confirmed at bet time. (B) **Log integrity:** what
must be stored at bet time today that cannot be reconstructed tomorrow. (C) One paragraph: is the
0.70 expected-return number computed correctly, and what is the honest sentence to put on a ticket.
