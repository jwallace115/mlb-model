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

## P26 — run_window.py orchestrator (2026-10-08)

`nfl/pipeline/run_window.py --sport nfl --window {open,mid,late,prekick,adhoc}
--reader-model <m> [--as-of] [--no-pull]`: one command per window.

Steps: (1) pull props+snapshot unless `--no-pull`; (2) sheet → reader_v3 → freeze
with `--window`, `--reader-model`, `--reader-file`; (3) verify; (4) picks_adapters
→ build_top20.

Each step prints UTC timestamp, command, exit code. Non-zero STOPs the pipeline.
`--window-hours` is passed to both sheet and freeze for prekick/adhoc windows
(so the freeze rebuilds the same narrowed sheet the reader saw).

Scheduled runs: ops proposes `ops/windows` branch merged by Jeff in :00–:44.
The NFL lane has no existing convention for automated window branches.

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

## P27 — Props market name mapping fix (2026-10-08)

**Bug:** `pick_layers._line_movement` and `picks_clv` derived the tape market_key
as `"player_" + market.split(":")[1]`, correct only for `pass_yds` and `rush_yds`.
The other 8 prop markets — `rec`, `rec_yds`, `pass_att`, `pass_cmp`, `rush_att`,
`atd`, `int`, `pass_td` — all produced wrong tape keys (e.g. `player_rec` instead
of `player_receptions`). Consequence: line-movement layer EMPTY and CLV close_point
NULL on 8 of 10 prop markets (1,372 of 1,445 no-close rows per OPS4b-cont finding).

**Fix:** `pick_sources.ledger_to_tape_market(market)` — explicit inverse of
`odds_market()`, built once from the canonical MARKET_LIST in `pull_hardrock_props.py`.
Raises `KeyError` on unknown markets. Used in `_line_movement`, `_sim`, and
`picks_clv.compute_clv` (three call sites replaced the broken `"player_" +` pattern).

**Round-trip test:** for every tape market_key in MARKET_LIST,
`ledger_to_tape_market(odds_market(k)) == k`. RED before fix (AttributeError), GREEN after.

**Fixture test:** prop:rec with tape rows under `player_receptions` → line_movement
has value and n_rows ≥ 1. RED before ("no tape rows"), GREEN after.

**CLV test:** prop:rec close_point = 5.5 from `player_receptions` tape. RED before
(got None), GREEN after.

**Null control:** Cam Ward pass_yds card is byte-identical before and after (pass_yds
was always correct; the fix must not change it).

**Rebuild tooling:**
- `pick_layers.py --rebuild-empty-movement`: walks every pick in `view()` (the full
  deduplicated ledger) and (re)builds any card whose `line_movement` value is null,
  creating cards for picks that had none. Existing cards with a non-null value are
  untouched (write-once stands). Rebuilt cards carry `rebuilt_utc` and
  `rebuilt_reason = "P27 market map"`.
- `picks_clv.py --recompute-null`: re-runs picks whose existing close_point is null,
  appends a corrected row (append-only; newest row per pick_id wins at read time).

**2026-10-08 rebuild run:** first run crashed after 705 cards (NameError in _sim;
hotfix e4aa3918e). Second run completed in ~3 h: 1,941 rebuilt / 4 untouched / 0
still null / 1,945 total. Future runs are expected to touch 0 (new cards get the
correct market mapping from the start).

## P28 — run_window runs unattended and commits what it froze (2026-10-08)

`run_window.py` gains:

**(a) WINDOW_HOURS:** open 168, mid 168, late 72, prekick 6, adhoc 168.
Late widened from 24 → 72 (includes SNF/MNF). Adhoc widened from 48 → 168
(whole upcoming slate).

**(b) --tag expanded:** `pull_hardrock_props.py --tag` now accepts
`{open,mid,late,prekick,adhoc,close}` (was `{open,mid,close}`). `snapshot_tag`
is free text — the three old values keep working. `run_window` passes the window
name as `--tag`.

**(c) --reader-model** defaults to `reader_v3`. The script is what produced the
opinions; a model name goes there only when a model actually formed the opinion.
The adhoc freeze already recorded `claude-opus-5-5` and stays as frozen; from
tonight the honest label is `reader_v3`.

**(d) --commit {none,main,branch:\<name\>}:** after verify, `git add` the frozen
file + manifest (+ mac props + snapshot) and commit with message
`"window <w> freeze <UTC>: <n> files, reader_v3 <sha8>"`. `main` commits on the
current branch and pushes to origin; `branch:<name>` pushes to that branch;
`none` leaves the files (Mac default). Non-zero anywhere STOPs before commit.

**(e) --auto-prekick:** for the prekick window, check if any game kicks in
`[now + 2h52m, now + 3h08m]` (one 15-minute cron slot). If not, print
"no game in the prekick slot" and exit 0. `--window-hours 6` keeps multi-game
slots in one freeze.

**(f) Injury report:** auto-detects newest file under
`research/nfl_sim/official_injuries/<season>_w<WW>/` when it exists on the host.
Absent → omitted (reason says "no injury report"). VM runs will usually lack it.
Sim lane should export the injury report before each slate.

**(g) --root respects MLB_REPO_ROOT:** `env.setdefault("MLB_REPO_ROOT", str(ROOT))`
so a pre-set value (e.g. from a test fixture) is honoured, not overwritten.
reader_v3 receives `--root` explicitly.

**Tests:** (a) `--tag prekick` accepted by puller (RED: "invalid choice", GREEN: no error);
(b) `_check_prekick_slot` with game at +5h → False, game at +3h → True;
(c) existing halt test still passes (null control).
Smoke test: `--auto-prekick --no-pull --commit none` → "no game in the prekick slot", exit 0.

## P29 — Fixed windows run on the VM (2026-10-08)

The fixed windows (open/mid/late/prekick) run on the VM via cron. The Mac runs
only adhoc by hand (`run_window.py --window adhoc --commit none`; the Mac
auto-commit carries the files to main).

**VM cron (UTC):**
| Schedule | Window | Command |
|----------|--------|---------|
| `0 16 * * 2` | open | `run_window.py --sport nfl --window open --commit main` |
| `0 22 * * 4` | mid | `run_window.py --sport nfl --window mid --commit main` |
| `0 22 * * 6` | late | `run_window.py --sport nfl --window late --commit main` |
| `*/15 * * * *` | prekick | `run_window.py --sport nfl --window prekick --auto-prekick --commit main` |

Logs: `/root/logs/run_window_nfl.log`. `PICKS_LEDGER_DIR=/root/private/ledger`.
Python: `venv/bin/python3`. Working directory: `/root/mlb-model`.

The scheduled tasks are VM cron, not Cowork, because the reader is a script and
needs no model session. Cowork's role is verification and the layers that need a
reader (OPS5).

**Do NOT run mid or prekick by hand on the VM** — a hand run plus the cron run
would freeze the same window twice (revision 1, unscored, ~160 credits wasted).

**Injury report:** VM runs will usually lack it (the sim lane exports on the Mac).
Request the NFL lane to commit the export before each slate. The reader notes
"no injury report" in the reason when absent.

**Tonight's first runs:** 21:15Z prekick for TNF (kick 00:15Z), 22:00Z mid
(whole Sunday + MNF slate). Check: log tails, credits used, sheet lines and
GAMES (mid must show the whole slate, not one game), frozen file sha256,
manifest entry, commit hash, top 20.

## P30 — Plain-English card summaries; "in your favour" direction (2026-10-08)

Detail cards now render a plain-English summary paragraph above each layer's
raw data. The raw dict is folded into a `<details>` element (nothing hidden,
only collapsed). Layer-specific summaries:

**Line movement:** market name + game; consensus open (median, n books, date ET);
book's opening post (point@price, date ET); pick-time snapshot (book + consensus);
movement in points and price since book open; consensus movement; one direction
sentence. Direction rule ("in your favour"):
- **Spreads:** bettor's point going UP is in favour (+7.5 → +8.5 or −9.5 → −8.5).
- **Totals / props:** Over — number going DOWN is in favour; Under — going UP.
- **Moneyline:** bettor's price getting longer (−150 → −130, +120 → +140) is in
  favour; shorter is against ("the market has moved toward your side").
- Missing book rows → "had no quote in the window; consensus only".
- No data → the existing "no data as of …" line, unchanged.

Source line: "\<n\> snapshots / \<n\> pulls" instead of raw file names.

**Weather:** "Outdoor at \<stadium\>: \<wind\> mph wind, \<precip\>% rain …
(NWS forecast as of \<ET\>)" / "Indoor (\<stadium\>, \<roof\>)" / "no forecast".

**Sim:** "The sim's number for this market: \<value\> vs the line \<point\>" /
"no sim number for this freeze".

**Injuries / news / reasoning:** already prose — unchanged except the raw dict
(injuries, reasoning) goes into the `<details>` fold like other layers.

Tests: 7 fixture tests (RED first, GREEN after); 15 total in test_top20_page.py.

## P31 — Pre-commit guard on ~/mlb-model main (2026-10-08)

A LOCAL pre-commit hook on the Mac clone (`~/mlb-model/.git/hooks/pre-commit`)
refuses any commit on `main` unless `MLB_AUTOCOMMIT=1` is set. The Mac
auto-commit job (`shared/push_paths.sh`, cron at :50) exports `MLB_AUTOCOMMIT=1`
before its git commands. The VM's `push_daemon.sh` is a different clone and is
not touched. The hook text is not in the repo (it lives in `.git/hooks/`).
See `claude/SESSIONS_RULES.md` for the rule this enforces.

## P32 — Sim layer finds the sim file, not the newest file (2026-10-09)

`_sim()` in `pick_layers.py` previously picked the newest `ai_opinions_*.parquet`
file with timestamp ≤ `logged_utc`, then checked if it contained `nfl_sim` rows.
When a non-sim reader file (e.g., `claude-fable-5-1`) was timestamped after the
sim file, it shadowed the sim and the layer returned "no sim rows in freeze."
This affected all 47 cards from the 2026-10-08T23:23:34Z freeze.

Fix: `_is_sim_file(p)` reads only the `reader_model` column (cached per path) and
the scan selects only files where `reader_model.str.startswith("nfl_sim")`. The
newest such file ≤ `logged_utc` is used. Pilot flag is now included in the layer
output.

New CLI: `--rebuild-layer <name> --freeze <logged_utc>` rebuilds a single layer on
cards whose sim/layer value is null, scoped to picks from one freeze. Cards with a
value are untouched (write-once).

Tests (RED first, GREEN after):
- (q) sim file at T-3h + non-sim reader at T-1h → layer finds sim (was RED: "no sim rows in freeze")
- (r) sim file at T+1h excluded (leak guard, passed before and after)
- (s) single sim file → output unchanged (null control, passed before and after)
- (t) pilot sim → layer includes `pilot: true` (was RED: key absent)

Dryrun: 1 rebuilt / 0 untouched. Javonte Williams rush attempts: p_first=0.741,
edge=0.241, reader_model=nfl_sim_v1_156cd057, pilot=true.

## P33 — Mac auto-push via SSH deploy key (2026-10-09)

The Mac's remote was HTTPS (`https://github.com/...`), which requires a
username/password prompt. In launchd's minimal environment no TTY is available,
so `push_paths.sh` failed with `could not read Username for 'https://github.com':
Device not configured` — this had been blocking Mac pushes since at least
2026-10-09T00:50Z (5 commits stranded locally).

Fix: ed25519 deploy key (`~/.ssh/mlbmodel_deploy`) added to GitHub repo settings
as a write-enabled deploy key. `~/.ssh/config` Host block `github-mlbmodel` routes
to the key. Remote changed to `git@github-mlbmodel:jwallace115/mlb-model.git`.
The VM's remote is unchanged (it uses its own SSH setup).

Verification:
- `ssh -T git@github-mlbmodel` → "successfully authenticated"
- `env -i HOME=$HOME PATH=/usr/bin:/bin:/usr/local/bin git fetch origin` → OK
- Manual push of 5 stranded Mac outputs commits → succeeded (2a1871115 on origin)
- `push_paths.sh` at :50 with no new changes: "no changes" (correct, no error)

## P34 — Sim runs before every window; freeze lands on main (2026-10-09)

(P34 content unchanged)

## P35 — select_slate: per-game latest freeze (2026-10-09)

`select_slate(view_rows, sport, now)` replaces `select()` for the Picks page.
Instead of picking one newest freeze and showing only its games, it unions across
freezes: for each upcoming event_id, it takes the rows from the newest freeze
(by logged_utc ≤ now) that contains that event. This means a Thursday adhoc read
and a Saturday mid read coexist — every game shows its most recent read.

Returns `{events, props, sides, unranked, n_freezes}`. `events` is a list of
per-game metadata (event_id, away, home, commence_time, freeze_logged_utc,
window, reader, n_picks). `reader` = the view's `reader` column if present,
else `os.path.basename(source_file)`. Rows carry their own freeze fields
(source_file, logged_utc, window).

Per-event cap: at most 20 ranked rows per event per column (applied after
sorting by `_sort_key` across the whole union). The cap prevents one game from
dominating the list.

`top_for_selection(ordered_rows, event_ids)` is the server-side twin of the
browser's JS filter: filter by event, keep server order, renumber 1..n, cap 20.

`select()` stays byte-identical — existing callers and `--print-top` unchanged.

Tests: 5 new in `test_top20_select.py` (multi-freeze, future-leak, null control,
past-game, per-event cap). All green.

The window order is now: refresh → sim → packet → reader. The Mac's
`sim_window.sh` runs 30 min before each VM reader window and freezes the sim
opinions to main via the deploy key. The VM's `run_window.py` now does
`git pull --rebase --autostash` at step 0 so it sees the freeze, and the four
cron lines have `--no-pull` since the Mac already pulled props + snapshots.

**PILOT** until the NFL lane audits D283 (a11469bdd + 39dca1d8c on
eng/fwd6-parser-fix). The pilot check: `git diff --quiet origin/eng/fwd6..HEAD
-- nfl/sim/`; when the diff empties, `--pilot` drops automatically.

**sim_window.sh** (nfl/pipeline/sim_window.sh, Mac):
1. Derives week from `(now - 2026-09-10) / 7 + 1`
2. Pulls props (tag mapped: adhoc→mid, prekick→close, for fwd6 compat) + snapshot
3. `refresh_inputs.py --week W` — HALT on non-zero
4. `git restore` tape from origin/main + overlay fresh captures
5. `fwd_bootstrap.py harness --week W --window-hours H [--pilot]`
6. Copy freeze to main, append manifest, `MLB_AUTOCOMMIT=1 git commit + push`
7. Stage run record to eng/fwd6-parser-fix

**Launchd:** `com.mlbmodel.sim_window.plist` fires at Tue 15:30Z, Thu 21:30Z,
Sat 21:30Z (fixed windows, auto-detected from time) and every 15 min (prekick
--auto-prekick). Single plist, script auto-detects window from UTC day/hour.

**VM crontab:** all four `run_window.py` lines now have `--no-pull`. Step 0
(`git pull`) added so the reader sees the sim freeze.

Real run (adhoc, 14-game full slate):
- Credits: 143 (140 props + 3 snapshot), remaining 232,684
- 14/14 games simulated and converged, 900 lines frozen
- FROZEN sha256: ee0a7e12...88b9680
- Commit ccd5a7466 on origin/main (manifest window=adhoc, pilot=true)
- Run record 324b9870d on eng/fwd6-parser-fix
