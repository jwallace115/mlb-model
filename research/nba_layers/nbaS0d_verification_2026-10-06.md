# NBA-S0d verification — 2026-10-06 ~03:45Z (NBA chat, Cowork, read-only from files, no fetch)

Branch nba/s0d at 9beb9125d (0a55f294c B24, bbabaff21 B25, 9332a2a53 B26), built on main with 92824aa35. origin/nba/s0d = 9beb9125d.
Files read: roles.parquet, game_asof.parquet, manifest.parquet at nba/s0d; roles.parquet at 92824aa35; the code.

## Claimed vs checked
| Gate | Claimed | Checked | Verdict |
|---|---|---|---|
| B24 pre_tip published > tip−30 after fix | 0 | 0 (min margin ≥30) | HELD |
| B24 pre_tip files changed | 43 | 43; freeze changed 0 | HELD |
| B24 NULL | 285 unchanged | consistent | HELD |
| B25 asof published > tip−30 | 0 | 0 of 2,481; min margin 30.0 | HELD |
| B25 pre_game share 4–15% | 8.5% | 210/2,481 = 8.46% | HELD |
| B25 NULL (tip ≥18:30 ET → freeze, same sha as roles) | "HELD, 2,153/2,160, 7 non-regular-season exceptions" | 2,153/2,160. The 7 are NOT all non-regular-season (2026-03-28 is regular season). All 7 use a report LATER than 5:30 although the 5:30 report qualified. | **DID NOT HOLD — mis-reported** |
| freeze rows = roles freeze file | — | 0 sha mismatches on dates in roles | HELD |
| No raw PDFs tracked | — | 7 = same test fixtures | HELD |

## Defects
**D1 — Jeff's rule broken on 5 dates outside the schedule file** (2024-12-17 Cup final; 2025-04-15/16 play-in;
2025-04-19 playoffs; 2026-03-28 regular season, missing from dates_2025.json).
- These dates have no roles freeze row, so build_game_asof fell back to "latest report ≤ tip−30" for all 14 games.
- For 7 late games that picks a post-5:30 report: OKC-MIL 12-17 07PM, ORL-ATL / CHI-MIA 06PM, SAC-DAL / GSW-MEM 09PM,
  MEM-CHI 07_30PM, PHX-UTA 09_30PM.
- That is not the object Jeff approved. In the live pilot it would be information after the freeze.

**D2 — newly fetched reports were never written to history_parsed or the manifest.**
- 40 roles files and 87 game_asof files have no parsed parquet and no manifest row. The manifest is still 642 rows.
- The code checked parse status == ok at selection time (`parse_report`), but threw the rows away.
- game_asof points at reports whose contents a consumer cannot read from the committed history.

**D3 — undisclosed deviation: tip source.**
- The work order said ESPN primary, Odds API fallback. The code uses Odds API commence_time primary, ESPN as cross-check only.
- All 654 dated roles rows are `odds_events`. B24 in the decision doc states it; the chat summary did not.
- Recommend ACCEPT: the live pilot reads Odds API events, so this gives identity (CHECK 3). ESPN differs >15 min on 7 dates.

**D4 — minor.**
- 2026-04-11 is not a game date. Its 05_30PM report lists only 04/12 games. dates_2025.json includes it and omits 2026-03-28.
  Status `no_tip` is not the right label for that date.
- **Design note for S1:** a report file's rows can be for a different game_date than the file date. Consumers must
  filter rows by game_date + matchup, never by file date.

**Not checked:** test_b24 run (no pytest on the VM; not installed).

## Verdict
**Hold the merge.** The B24 pre_tip fix and the B26 hygiene are correct. B25 needs D1 and D2 fixed: NBA-S0e on the same
branch. Nothing consumes these files yet, so no reported result changes.
