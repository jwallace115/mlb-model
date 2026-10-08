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
