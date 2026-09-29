NHL LAYERS — WORK ORDER G1: starting-goalie news layer (sources, timing, change alerts) (written 2026-09-29 by
Cowork, NHL chat). Repo ~/mlb-model.

WHY: a backup goalie starting moves an NHL game 3-6 points. If the news reaches us before the price moves (at Hard
Rock especially), that is the most plausible real edge the engine can act on. First, MEASURE whether any free
source gives the starter early enough; only then alert on it. This supersedes item 4 (goalie probe) of
research/nhl_layers/workorder_1_2026-09-27.md.

Read first: CLAUDE.md (ENVIRONMENT TRAPS, ODDS API COST MODEL, VM-default rule, WORK ORDERS),
research/nhl_layers/NHL_LAYERS_DECISION_v1.md (H1, H2 — book of record Pinnacle; Hard Rock absent from the NHL API
feed), research/nhl_sim/amendment_A2_2026-09-29.md (why speed matters).

SETUP
- Worktree `git worktree add ~/mlb-model-nhlg1 -b nhl/goalie-g1 origin/main`. Touch only: nhl/news/ (new package),
  nhl/news/tests/, data/news_archive/nhl/goalies/ (append-only; gitignore the raw JSON, commit nothing > 2 MB),
  research/nhl_layers/, the VM crontab. Do NOT edit nba/ — import nba.modules.notify for Pushover, read-only.
- Each item appends its `### H<n>` entry at the END of research/nhl_layers/NHL_LAYERS_DECISION_v1.md in the same
  commit. The next number = last `^### H` + 1 (expected H3-H5). Commit AND push each item before the next.
- Tests import production code, use fixtures cut from REAL responses, and each must FAIL on a stated mutation you
  run. Pre-registrations are written before looking; HELD / NOT HELD; tune nothing to rescue one.
- Credits (Odds API): item 1 = 0. Item 2 = 3 per detected change (one event call: h2h, spreads, totals, the
  10-book list = 3 markets x 1 region-equivalent). Estimate <= ~30 changes/day -> <= ~90/day. `--floor 3000`
  in every paid call, and the key fingerprint logged. The balance is ~20k after WO2 — report it first.
- Runtime per poll: <= ~16 games x 3 free calls x ~0.5 s ~= 25 s; every 10 min 14:00Z-03:00Z on game days = 78
  polls/day.

ITEM 1 (H3) — starter sources, captured and graded (nhl/news/goalie_sources.py).
- For each game on today's NHL schedule (ET date), poll free structured sources:
  - api-web.nhle.com `gamecenter/{id}/landing` and `gamecenter/{id}/boxscore` (pre-game fields);
  - ESPN `site.api.espn.com/apis/site/v2/sports/hockey/nhl/summary?event=<id>` (map games by team pair + date).
- Record, per poll: game, team, source, goalie name as given, the status word exactly as the source gives it
  ("probable", "confirmed", ...), retrieved_utc, source updated time if any.
- Output: append-only `data/news_archive/nhl/goalies/date=D/polls.parquet` + raw JSON (gz, gitignored) +
  `_pulls.jsonl` with `feed` set (N41 convention). No HTML scraping in this order: list candidates (e.g. team
  press, DailyFaceoff) in the report instead.
- Post-game grading (same script, `--grade D`): each source's last pre-puck name vs the actual starter from the
  play-by-play (goalie on the ice for the first shot against) -> hit rate, and lead time before puck of the first
  correct report.
- Host: VM-default test (both APIs from the VM). Install the cron on the host that passes: every 10 min 14:00Z-03:00Z
  plus a 10:00Z grading run for the previous date. Evidence = SCHEDULED files on origin, not a manual run.
- PRE-REGISTER: the NHL API gives no named confirmed starter before puck (its pre-game data lists both goalies'
  stats, not the starter); ESPN names a probable starter for most games on game day with no confirmation flag.
  Report what each source actually gave for the first 3 game days.
- Test: the parser keeps the source's own status words verbatim (mutation: map them to a fixed vocabulary -> fail).

ITEM 2 (H4) — change detector, price snapshot, phone alert (nhl/news/goalie_alerts.py; runs inside the same cron).
- A CHANGE = a source names a different goalie for a team than its previous poll, OR first names a goalie who is not
  the team's season-to-date primary starter (most starts this season, from the play-by-play event tables).
- On a change:
  - pull that event's odds once (Odds API event endpoint, h2h/spreads/totals, the 10 books);
  - write before/after rows: the last 30-min tape snapshot vs this pull, Pinnacle and every book;
  - send ONE Pushover alert per team per game via nba.modules.notify (read-only import). The alert carries game,
    team, goalie, source + time, Pinnacle moneyline at the last tape snapshot and now, minutes to puck, and the
    line "check Hard Rock in the app".
- Append-only log `data/news_archive/nhl/goalies/alerts.jsonl`.
- No bet is ever suggested or logged by this order.
- Test on a replayed day (fixtures): exactly one alert per changed team; none when nothing changed; the paid call
  is skipped below --floor.

ITEM 3 (H5) — is there time to act? (report after 7 game days of items 1-2; nhl/news/goalie_speed_report.py).
- For every detected change:
  - minutes to puck;
  - Pinnacle's no-vig move from the previous tape snapshot to detection, and from detection to the close (last
    snapshot before puck);
  - share of the total move still to come at detection.
- Also: how many changes were backups, and how often the reported goalie was the one who actually started.
- PRE-REGISTER: for backup confirmations, Pinnacle has already made >= half of its total move by the time any free
  source reports it (median). If that holds, free sources are too slow and the next step is a faster source.
  If it does NOT hold, the alert has real value and the Hard Rock check becomes a standing routine.
- Nothing here is graded on game results; this is a timing measurement only.

CLOSING
- logs/_log_nhl_g1.txt (`git add -f`): RETURNED vs MEANS; each pre-registration HELD / NOT HELD with numbers; credits
  used and balance; the crontab lines installed; NOT DONE; UNVERIFIED; commit shas; ONE merge command. Items 1-2 can
  merge before item 3's 7 days are up — say which commit is safe to merge. Stop.
