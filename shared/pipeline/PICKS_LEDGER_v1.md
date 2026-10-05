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
