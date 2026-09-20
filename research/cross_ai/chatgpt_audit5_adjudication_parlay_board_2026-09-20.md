# Adjudication — ChatGPT audit #5, the parlay board after repair + the NFL procedure (2026-09-20)

Audit target `73bf63f` (N43). Adjudicated by Cowork by re-running each probe on production
functions. **Verdict: every finding I could test reproduced. Four of the five headline defects
were in code I wrote or verified today.**

| # | Finding | Reproduced? | Disposition |
|---|---|---|---|
| 1 | NFL final ticket unenforced: `main()` wrote only baselines; the logger accepted two copies of one leg at a 999.5 line and +9999; vetoes checked only if volunteered | YES — "garbage final ticket ACCEPTED" | FIXED (N44): legs are built by code from candidate rows and re-checked against them (line, side, both prices, pull, eligible, one per game); departures from BOTH baselines are derived and each needs reason + source; every final leg needs an availability confirmation; reader inputs/output required; `--final file` reaches it from `main()`, refusing a candidate table whose sha256 changed |
| 2 | An August-1 injury file + fresh props still admitted 50 legs; 154/973 rows have no status, 28 of them eligible | YES — 50; 154; 28 | FIXED: injury file older than 7 h -> nothing eligible. The 28 are healthy starters ESPN never listed (Smith-Njigba, McCaffrey, Stafford...), so "no status" stays eligible but is flagged `feed_status_missing`, and NO leg is final without its own availability source |
| 2b | Status lookup searched both teams | YES (by reading) | FIXED: the resolved player's own team only; test puts an "Out" namesake on the opponent |
| 3 | Usage QB fallback (layer 3) takes the newest depth chart with no date guard; a synthetic December entry became a week-2 starter | YES by reading `usage.py:312-345`; not re-run | **Guard NOT fixed today** (sim-adjacent file, game day). Committed rows checked instead: all 32 week-2 flagged starters ARE their team's week-1 leading passer in `pbp_2026`. Rank ties now take the WORST rank; week-1 target/carry counts shown beside shares. Reader confirms every QB and lead role by hand today |
| 4 | NCAAF `write_ticket_log` raises `KeyError: 'event_id'` on the real log (4 card entries) | YES | FIXED: key = event_id or `card:<card_id>`; duplicate key halts; test runs the writer on a copy of the committed log. **My miss**: the "real full-board build" in N42 never called the writer |
| 5a | News coverage measured before the recency filter; malformed pull times pass | YES | FIXED: coverage = teams with an article the selector would be SHOWN (143/145 on 09-19, was 145/145); an article without a readable pull time does not enter (0 such in the real archive) |
| 5b | `prob_clv_C` used the no-vig entry price: unchanged -110/-110 gave 0, truth -4.55% | YES | FIXED: `d_0` = accepted decimal price. Contradicted my own adjudication of audit #4, which defined C with the entry price |

Accepted without code, as today's procedure: confirm the exact contract and both prices in the
app within five minutes of placing (a changed line or price is a new quote — reconsider, no
tolerance band); early ticket = 17:00Z games only; fewer than five legs or no ticket is a valid
outcome; screenshot the slip before placing; the nightly Hard Rock export supplies the accepted
contract, price and stake. **Corrections to my brief accepted:** the 16:30Z pull MAY arrive before
kickoff (not guaranteed either way); the two "0.70" figures are different quantities (hold on a
cross-game ticket vs the same-game quote ratio R; a same-game ticket needs joint/marginal
G > 1/R = 1.43 just to offset R = 0.70); selected rows' overround was 7.2-8.0%, above the family
medians I quoted; top-q measures market favouritism, not value; vetoed-vs-kept hit rates are not a
causal estimate of reader skill; ~20 legs in four weeks has a standard error near 11 points.

**The sentence for a ticket:** "At the accepted prices, proportional de-vig and independent-game
assumptions give a calculated gross return of about $0.70 per $1 staked (net -$0.30); those
probability assumptions are unvalidated."

**Close capture (must happen today, cannot be reconstructed):** three Sunday T-10 props pulls —
16:50Z, 19:55Z, 20:15Z, `--window-hours 1 --tag close`. Cost 15 credits/event + 1 (N28):
8 + 5 + 3 events = 121 + 76 + 46 = **243 credits per Sunday** (~1,050/month; steady state stays
under the 20K plan; the 3,000 halt is untouched). Installed by cloning the VM's own 16:30 line.

**Still open:** NFL prop grader + outcomes; usage layer-3 date guard; stale quotes inside
`build_ncaaf_board.py` consensus; execution record is a screenshot + the export, not code;
name resolution is still string matching.
