# Picks Ledger — Decisions

## P1 — Contract and pick_id rule (2026-10-05)

**Contract columns** (one row per leg; exact names):
pick_id, ticket_id, owner, source, logged_utc, sport, event_id, commence_time,
home, away, market, player_id, player_name, side, point, price_american, book,
reason, share_link, supersedes, result, graded_utc, result_source, ingested_utc,
source_file, source_row.

**pick_id** = sha256(ticket_id|owner|source|event_id|market|player_name|side|point)[:16].
Deterministic: a re-run appends nothing already present (idempotent append, never edit).

**Owner per source file:**
| Lane | Kind | Owner | Source |
|------|------|-------|--------|
| ncaaf | card | ai_ncaaf | ticket_card |
| ncaaf | game_view | ai_ncaaf | ai_opinion |
| ncaaf | ai_opinion | ai_ncaaf | ai_opinion |
| ncaaf | placement | jeff | jeff_manual |
| nfl | slate_rule | ai_nfl | ai_opinion |
| nfl | slate_final | ai_nfl | ai_opinion |
| nfl | game_ticket_ai | ai_nfl | ticket_card |
| nfl | game_ticket_ai_opinion | ai_nfl | ai_opinion |
| nfl | card | ai_nfl | ticket_card |
| nfl | sgp_card | ai_nfl | ticket_card |
| nfl | placement | jeff | jeff_manual |
| nfl | ai_opinions parquet | ai_nfl | ai_opinion |

## P2 — Tape resolution rule (2026-10-05)

Rows without event_id resolve from the odds tape: snapshots in
[commence − 7 days, commence], normalised (home, away) through pick_sources'
own normalisers AND |snapshot commence − leg commence| ≤ 6 h. Exactly ONE
event_id, else HALT with the row. commence_time is taken from the LATEST
matching snapshot (kick times get revised).

Measured match rate: reported at first real-data run.

## P3 — Store location, backup, retention (2026-10-05)

- **Store:** /root/private/ledger/picks.jsonl (append-only JSONL, one object per line, fsync).
- **Members:** /root/private/ledger/members.json ({"members":["jeff"]}; edited by hand on VM).
- **Backup:** /root/private/ledger_backup/picks_<UTC>.jsonl.gz, daily at 05:35Z, keep newest 30.
- **Dir permissions:** /root/private mode 700.
- **Env:** PICKS_LEDGER_DIR (default /root/private/ledger). Dir absent → adapters/intake/grader HALT.

## P4 — Member-share intake, v1 and v2 note (2026-10-05)

**v1 (this order):** Jeff drops Hard Rock share-card screenshots in ~/private_picks/inbox/.
A Claude chat reads each image and writes ~/private_picks/proposed/<drop_utc>_<owner>.json.
Jeff edits and moves to ~/private_picks/confirmed/ adding confirmed_by + confirmed_utc.
He copies to the VM: `scp ~/private_picks/confirmed/<f>.json do-vm:/root/private/inbox_confirmed/`
picks_intake.py processes inbox_confirmed/ → ledger, moves the file to done/.
share_link is stored as text and never opened.

**v2 note:** automated card parsing through the Anthropic API ≈ one image (~1.5k tokens)
+ ~1k prompt + ~0.5k output per card. Price per token: not checked in this order.
It keeps the confirm step (the model writes proposed/, a human still moves the file to confirmed/).

## P5 — Official result files inventory (2026-10-05)

| Sport | File | Location | Settles in v1? | Notes |
|-------|------|----------|----------------|-------|
| NCAAF | cfbd_games_2026.parquet | Mac + VM | Yes (game markets) | mtime 2026-09-27; stale file leaves week 5+ UNRESOLVED; refresh costs CFBD calls |
| NFL | nflverse schedule via nflreadpy | Mac + VM (network) | Yes (game markets) | live from github.com/nflverse; no API key |
| NFL | pbp_2026.parquet | Mac + VM | v2 (player props) | nflverse play-by-play; player stats derivable |
| NHL | api-web.nhle.com | network only | v2 | nhl_outcomes.py reads NHL API |
| NBA | stats.nba.com | Mac only (blocked on VM) | v2 | |

Props (player markets): UNRESOLVED in v1 for all sports. v2 will derive player stats
from PBP (NFL) and build crosswalk_players_<sport>.parquet.

## P6 — Settlement definitions (2026-10-05)

- **Spread:** home margin = home_score − away_score. Bettor's adjusted margin = margin + point.
  Positive → W, negative → L, zero → P. Rush attempts include kneels (book-faithful).
- **Total:** game total = home_score + away_score vs point. Over: total > point → W, < → L, = → P.
  Under: total < point → W, > → L, = → P.
- **Moneyline:** home_score > away_score → home W, away L. Tie → P (rare in NFL regular season).
- **VOID:** only when the official source marks the game cancelled/postponed (never from missing data).
- **Props:** UNRESOLVED in v1.

Grader cron: 10:10Z daily (after nflverse at 09:30Z).

## P7 — NFL results: local HALTing feed, no network in crosswalk or grader (2026-10-08)

**Finding (Cowork, verified):** `_load_nfl_officials()` imported `nflreadpy` and
downloaded the schedule from GitHub at grade time, swallowing every exception into
an empty frame — fail-open gate (A9) and a network call in a cron that was not
supposed to make any.

**Fix:**
- `pull_nfl_results.py` (new): pulls nflverse schedule via `nflreadpy`, writes
  `data/results_archive/nfl/schedules_2026_<UTC>.parquet`. HALT on empty, <250 rows,
  or no completed game. VM cron `30 9 * * *`, before the 10:10Z grader.
- `event_crosswalk._load_nfl_officials(root)`: reads the NEWEST file from the
  archive; HALT if folder empty or newest file >36 h old. `nflreadpy` removed from
  `event_crosswalk.py`.
- `picks_grader.main()`: exits non-zero when a sport with ungraded past-commence
  picks has no crosswalk file. Previously it graded nothing and exited 0.
- Mac dry-run: `RESULTS_ARCHIVE_DIR` env var redirects output so results never
  appear in `git status` on the Mac checkout.
- Registered in `feeds_registry.json` (`nfl_results`, cron_match `pull_nfl_results.py`).

**Null control:** NCAAF crosswalk output byte-identical (372 rows, sha256 `45b89551...`)
before and after this change.

## P8 — Admit 280 rejected pick-legs, tag/conf columns, sim_nfl owner (2026-10-08)

**Pre-registered expectation:** >=250 of 280 resolve.
**Result:** 215 of 280 resolved. **NOT MET.** 54 of the 65 remaining are prop bets
(player_name only, no game field) — genuinely unresolvable without game association.
The exactly-one rule was not loosened.

**Fixes applied:**

1. `split_game`: fixed parenthetical team names ("Miami (OH) RedHawks @ Cincinnati
   Bearcats" now splits correctly — was splitting on `(` before `@`).

2. `_extract_event_id_from_raw` / `_extract_teams_from_raw`: regex fallback for
   truncated JSON (pick_sources raw field capped at 400 chars). Resolves 39 NCAAF
   card legs whose raw carried event_id + home/away but was invalid JSON.

3. `_resolve_event_from_build_time`: for rows with home/away but no commence_time,
   searches tape in [build_time, build_time + 7d] for the normalised team pair.
   Exactly one event_id → take commence_time from the latest snapshot.
   Zero → rejected "no_tape_event"; two+ → HALT. Resolves 174 no_commence rows.

4. `_resolve_single_team_event`: for NFL text legs with one team name but no game
   (sun_cards_v2 spread picks like "SEA -8.5 -110"), searches tape for any game
   involving that team. Resolves 5 of 8 such rows (3 remain ambiguous — multiple
   games in window).

5. `adapt_nfl_ai_opinions`:
   - Filter: `side in ("first","second") AND tag != "no_view"`.
     No_view rows already excluded by the side filter (side="none"); the tag check
     is defense-in-depth. Verified: 0 no_view rows were previously ingested.
   - Owner: `sim_nfl` when `reader_model.startswith("nfl_sim")`, else `ai_nfl`.
     235 rows (178 from 16:30Z + 57 from 17:00Z freezes) now carry owner `sim_nfl`.
   - Carries `tag` (nullable str) and `conf` (nullable float) into the ledger row.

6. `picks_ledger.COLS`: added `tag` and `conf` (nullable, at end of contract).

**Remaining rejections (65):**
- `no_game_field_prop`: 54 (NFL props with no game field — player_name only)
- `no_tape_event`: 8 (4 NCAAF small-market, 3 NFL post-kickoff, 1 NCAAF not in tape)
- `no_game_field`: 3 (NFL text legs, team has multiple games in window)

**Null controls:**
- Field changes on shared pick_ids (excluding tag/conf/owner): **NONE** (0 changed fields).
- 235 old pick_ids replaced: all sim rows whose pick_id changed because owner went
  ai_nfl → sim_nfl (pick_id is hashed from owner).
- Old NCAAF grades 91W/88L/5P all preserved in the new run (129W/126L/6P; +77 newly
  graded from the resolved rows).

**Store rebuild:** This is the one-time rebuild. From here on, the store is append-only.
Reason: rows with wrong owner (sim as ai_nfl) and ingested no_view rows cannot be
corrected by appending — the pick_id hash changes with the owner.

## P10 — Top-20 selection rules (2026-10-08)

`build_top20.select(view_rows, sport, now)` → `{freeze_logged_utc, props, sides, unranked, n_picks_in_freeze}`.

**Eligibility:** AI owners only (`ai_<sport>`); `sim_nfl` rows are NOT ranked (they feed
the sim layer). Member/jeff rows never appear. A pick whose `commence_time <= now` is
excluded (past games drop at the next build). Only the latest freeze (by `logged_utc`)
whose picks have at least one `commence_time > now` is used; the freeze's `logged_utc`
must be `<= now` (no future freezes).

**Columns:** "props" = market starts with `prop` or `player_`; "sides" = everything else
(h2h, spreads, totals, alternates). ≤ 20 per column.

**Ranking:** `conf` descending; ties by `|edge|` descending (approximated from
`price_american`); ties by `logged_utc` ascending. A row with `conf = null` is never
ranked — it lands in the `unranked` list. Rows beyond the top 20 per column are omitted
(they had conf, so they are not unranked — just not shown).

**HALTs:** Two freezes sharing the same `logged_utc`. A ranked row lacking `event_id`,
`price_american`, or `side`.

**Edge tiebreak:** The ledger carries no `edge` field. The current tiebreak approximates
edge from `price_american` as the distance of the implied probability from 50%. This is
a proxy, not the reader's computed edge (P14).

## P14 — Selection must never look at results (2026-10-08)

OPS3 shipped `select()` filtering `not r.get("result")` — graded picks were silently
dropped. This lost 42 game-line picks (the sides column showed 3 instead of 20) and
reported `n_picks_in_freeze = 805` instead of 847. A result is never an input to
ranking (the registry rule: results never change a label). Fixed by removing the filter.

## P11 — Layer definitions, sources, ≤ logged_utc rule, sim-on-card (2026-10-08)

`pick_layers.build_card(pick, root)` → JSON with layers, each as
`{value, source, as_of}`. Write-once to `PICKS_LEDGER_DIR/layers/<pick_id>.json`.

**A2 rule:** EVERY source file used must have its timestamp ≤ the pick's `logged_utc`.
A file timestamped after `logged_utc` is never read for a card.

**Layers:**
- `line_movement`: tape snapshots in [commence−7d, logged_utc] for the event + market.
  Open/close prices for the pick's book and consensus. Props from the props archive.
- `weather`: NWS forecast snapshot nearest-before `logged_utc`. Dome/retractable →
  `indoor: true`. Fields: temp_f, wind_mph, wind_dir, precip_prob_pct, short_forecast.
  Sports without NWS coverage → "no source".
- `sim`: the `sim_nfl` freeze (latest `≤ logged_utc`) matching event + market + player +
  line + side. Shows `p_first`, `book_p_first`, `edge`. Jeff's 10-07 decision allows this
  on the card — it is a prediction, not a result.
- `injuries`: ESPN injury archive `≤ logged_utc`. Player-specific entry + team Out/
  Doubtful/Questionable lists.
- `news`: news archive `≤ logged_utc`, within 72h, mentioning the player or either team.
- `reasoning`: the ledger row's `reason`, `tag`, and `conf` verbatim.

**Write-once:** `--build-missing` builds cards for currently ranked picks only (≤40 per
sport). An existing card is never rewritten. Cards persist after picks leave the ranked list.

## P15 — Props line movement reads monthly file by pull_timestamp (2026-10-08)

OPS3 shipped `_line_movement` treating monthly props files like timestamped snapshots.
`_file_ts` fell back to `st_mtime` (the file's current mod time), which was always
outside `[commence−7d, logged_utc]`. Result: every prop card said "no tape files in
window" — line movement was empty for the entire props column.

**Fix:** For props, read every monthly file whose month could overlap the window, then
keep only rows with `pull_timestamp` in `[commence−7d, logged_utc]`. Filter by
`event_id + player_name` (not `line`, since the pick's point may differ from the book's
current line). `as_of` = the newest `pull_timestamp` used. Game-line logic unchanged.

## P18 — Nearest line per (timestamp, book) (2026-10-08)

OPS3c's `_nearest_line` was applied to all matched rows of a file at once. For props,
a month of pulls across all books collapsed to only the rows at the pick's exact point;
earlier pulls at different lines vanished. For game lines, books at non-nearest points
were dropped, shrinking the consensus.

**Fix:** `_nearest_line_per_group(df, pick_point, ts_col, book_col)` groups by
(timestamp, bookmaker) and applies nearest-line within each group. The consensus at a
timestamp now correctly counts one row per book.

**Verified (real data, both cards match Cowork's pre-registration):**
- Cam Ward pass_yds: book open 189.5 (09-24) → close 177.5 (09-27), move −12.0;
  consensus close 178.0 n_books 8; n_rows 11.
- Seattle Seahawks spread: book open −6.5 (09-21) → close −8.5 (09-27), move −2.0;
  consensus open −2.5 n_books 3; consensus close −8.5 n_books 10.

## P16 — Spread sign convention and tape audit (2026-10-08)

**Convention:** the ledger's `point` is the **bettor's number**. The freeze `line` is
from **first_side's perspective**. For spread + `side == "second"`, the adapter must
negate: `point = -line`. Totals and props are unchanged.

**Adapter fix:** `adapt_nfl_ai_opinions` now calls `_freeze_point(market, side, line)`
which negates for second-side spreads. The NCAAF `p_ai_opinions` path in pick_sources
has the same convention — its rows also went through the same audit.

**Audit:** `picks_point_audit.py --report` compares every spread row's `point` against
the tape's `outcome_name + point` for the pick's side. Classes: AGREES, SIGN_FLIPPED,
MAGNITUDE, NO_TAPE. `--repair` appends a correction row (supersedes the old) and regrades.

**Pre-registered vs actual:** expected 8 NFL SIGN_FLIPPED; found 8 NFL + 37 NCAAF = 45.
The NCAAF freeze has the same convention (first_side line) and the same adapter bug.
All 45 repaired via supersedes rows; 44 regraded (1 no crosswalk match).

**Classifier (amended P19):** opposite sign ⇒ SIGN_FLIPPED, whatever the magnitude
(e.g. stored −7.0 vs tape +6.5: the sign is wrong and the bettor also bought 0.5 pts).
Same sign, different magnitude ⇒ MAGNITUDE (report only, no repair).

## P19 — p_ai_opinions gets the same sign rule (2026-10-08)

OPS3c fixed `adapt_nfl_ai_opinions` but `pick_sources.p_ai_opinions` (NCAAF + any sport
that routes through it) still emitted `point = line` for second-side spreads.
`_freeze_point(market, side, line)` is now defined in `pick_sources.py` (one definition)
and used by both parsers. Verified: adapters run appends 0 (fixed parser produces
the same pick_ids the correction rows already carry).

## P23 — OPS4a leftovers (2026-10-08)

(a) `p_ai_opinions` now carries `window` from the freeze row into the raw dict.
(b) Record section groups by `(owner, window)` with CLV column.
(c) `picks_clv` performance: cached pull_timestamp parse, snapshot index, close_price
    to int, nearest-line per book for consensus. Spot checks unchanged.

## P22 — CLV per pick, deterministic, in a sidecar (2026-10-08)

`picks_clv.py` computes closing line value for every kicked pick. Output:
`PICKS_LEDGER_DIR/clv.jsonl` (append-only, one row per pick_id).

**Closing quote:** the pick's book's row in the LAST tape snapshot (game lines) or
LAST props pull with timestamp ≤ `commence_time`. Same matching as P17/P18 (event_id
+ market + outcome/side + nearest line per (timestamp, book)). Fallback: cross-book
median, flagged `close_basis = "consensus"`.

**Conventions:** `clv_points` is in the bettor's favour:
- Spread: `pick_point − close_point` (SEA −8.5 closes −9.5 ⇒ +1.0)
- Over: `close − pick`; Under: `pick − close`
- Moneyline: null

`clv_price_pct` = `implied(close_price) − implied(pick_price)`, raw, no de-vig.

CLV is a record, never a label and never an input to selection.

## P21 — Window through the ledger to the page (2026-10-08)

`window` (nullable string: open/mid/late/prekick/adhoc) added to the ledger contract.
`view()` fills missing/null window with `"legacy"` at read time — no existing rows
rewritten. The adapter carries `window` from the freeze row. The page shows
`"<window> freeze · <logged_utc>"` and "moved: <move_points> pts" from the card.

## P20 — Window is part of the freeze (2026-10-08)

`freeze` gains `--window {open, mid, late, prekick, adhoc}`, REQUIRED (like --reader-model).
Written on every row and into the manifest entry. Revision counting and cross-dedup
are keyed by `(reader_model, pilot, window)`: the same contract frozen in `mid` and
later in `prekick` is revision 0 in each.

Non-prekick/adhoc windows EXCLUDE any game kicking within 3 h (the prekick band).
`prekick` HALTs if no game kicks within 3 h.

## P17 — Line movement must describe the pick's own line (2026-10-08)

OPS3/3b shipped `_line_movement` filtering by `event_id` only. Props matched every
market for the player (anytime TD mixed with pass yards). Game lines matched both
outcomes (Seattle's card showed Washington's +8.5).

**Fix:** Both branches now filter by:
- **Props:** `event_id + player_name + market_key` (e.g. `player_pass_yds`), then
  nearest line to the pick's point for alt ladders.
- **Game lines:** `event_id + market + outcome_name` matching the pick's side via
  `nfl_team()` normaliser, then nearest point.

**Value structure:** `{book: {open: {point, price, as_of}, close: {...}, move_points,
move_price}, consensus: {open: {median_point, n_books, as_of}, close: {...}}, n_rows}`.
Consensus = median point across books (one row per book) at earliest and latest timestamps.

## P12 — Top-20 page rules (2026-10-08)

`picks.html` is the Top-20 page with one tab per sport (NFL, NCAAF, NHL, NBA).

**Layout per tab:** Two columns (props / sides-totals-ML), each ≤20 rows ranked by
confidence. Each row: rank, pick description, price, confidence, one-line reason.
`<details>/<summary>` opens the detail card inline (no JavaScript). Permalink via
`picks.html#<pick_id>`.

**Record section:** below the columns per tab, by owner × source: N graded, date range,
W-L-P, hit rate, real-price ROI (1 unit; pushes 0), flat −110 (triage), by month,
≥60%-in-one-month flag. `embargo_owners` from `forward_status.json` → "scoring not
published" with N and dates only.

**Never on the page:** stakes, slip IDs, share links, member rows, balances.

**No freeze → "no picks logged yet"** with nothing else invented. Ledger absent → NODATA.

## P24 — reader_v3 canonical (2026-10-08)

`nfl/pipeline/reader_v3.py` is the canonical reader, replacing the untracked
`research/layers/_to_delete/ai_w4/reader_v2.py` (205 lines, sha256 315b44e2…).

**What changed:** inputs are selected by `--as-of <UTC>` (newest ≤ as-of for
snapshots; `pull_timestamp ≤ as-of` for props). Kalshi ticker prefix is derived
from the slate date, not hardcoded. Injury report is via `--injury-report <path>`,
absent → empty news layer. All input files and their timestamps are printed.
reader_v3 prints its own sha256.

**What did NOT change:** every rule, weight, threshold, and formula is an exact
port of reader_v2. Identity test: 917/954 rows identical on p_first; 36 diffs
are all from input selection (12 injury-report absent, 24 Kalshi snapshot
timestamp), zero from rule changes. 1 key mismatch from line movement between
snapshots.

`log_ai_opinions.py freeze` gains `--reader-file <path>` → writes `reader_sha256`
into the manifest entry. Optional for legacy; `run_window` always passes it.

reader_v2 stays untouched in `_to_delete`.

## P25 — Mac props + snapshot captures (2026-10-08)

`pull_hardrock_props.py --archive` writes a separate `data_YYYY_MM_mac.parquet`
beside the VM's monthly file (canonical-writer rule: two writers, distinct files).
Both `reader_v3._load_inputs` and `picks_clv` read all `data_*.parquet` in the
season/month dirs, so _mac files are found automatically.

`multi_book_open_capture.py` writes to the same `line_history/season=YYYY/` dir.
No code change needed — the Mac's .env has the key, and each snap gets a unique
timestamp filename.

First real captures from Mac: TNF TB@DAL props (602 rows, 10 credits, hardrockbet_fl
70 rows) + game-line snapshot (1,340 rows, 3 credits). Total 13 credits.

## P13 — Lane contract for reader freezes (2026-10-08)

Every reader freeze (ai_opinions parquet) must carry:
- `conf` (0–100): the reader's confidence. Required for ranking on the Top-20 page.
  Without it, the pick lands in the unranked list.
- `tag` (string): the signal tag. Never `no_view` for a pick.
- `rationale` (free text, optional): a paragraph explaining the pick. The card shows it
  under "reasoning" when present. A longer reason than the one-line `reason` field.
- `player_id` (optional): when the source has one (ESPN id).

**Current status:** NCAAF reader freezes carry no `conf` today → NCAAF tab stays
entirely unranked until the reader adds it. This is correct, not a failure.
