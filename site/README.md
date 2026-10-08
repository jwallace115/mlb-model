# iamnotuncertain.net — Website Build Guide

**For any Claude session in this project (NFL, NCAAF, NHL, NBA chats, Cowork, Claude Code): read this before you
change the website or put anything on it.** It says how the site works, where every input lives, and the exact recipe for
each common change, so Jeff never has to relay files between chats.

Owner of the decisions: Jeff. Last updated 2026-10-08 by Cowork (ops chat; mirrors `site/README.md` after OPS2c–OPS4d).
Companion docs: `claude/site_runbook.md` (operations), `claude/pipeline_audit_2026-10-01.md` (why it was built this way),
`shared/pipeline/PICKS_LEDGER_v1.md` (the picks ledger decisions P1–P30). In the repo this file is `site/README.md`.

---

## 1. What the site is

* **URL:** https://iamnotuncertain.net (www redirects to it). Login required (HTTP basic auth). Since 2026-10-08 one
  shared login for the group (Jeff's decision: single login for now, member logins are phase 2); the credentials live
  only in the VM's `/etc/caddy/iamnotuncertain.users` and in Jeff's head — never in a file in the repo or the project.
* **What it is:** plain static HTML pages, rebuilt every 5 minutes on the DigitalOcean VM from the files the pipelines
  write. No app server, no database, no JavaScript framework. Streamlit is retired.
* **Sports (Jeff, 2026-10-06):** NFL, NCAAF, NHL, NBA only. MLB, golf, soccer and WNBA are retired from the pages;
  MLB returns in 2027 through a PIT audit (§7).
* **Pages:** **Picks — the Top-20 page (`index.html`, the product; §5.7)**, Today (`today.html`), Pipeline health
  (`health.html`), Tracking (`tracking.html` + one `signal-<id>.html` per signal), NFL forward (`forward.html`), Odds
  archive (`archive.html`).
* **Design:** the mockup is the claude.ai artifact "iamnotuncertain.net site design". IBM Plex Sans/Mono, light and dark
  mode from CSS variables in `CSS` at the top of `build_site.py`. Status colours: green FIRING/LIVE, blue SHADOW,
  amber LATE/UNVALIDATED/QUIET, red SILENT/ERRORING/DEAD, purple NOT_PUSHED/IGNORED, grey OFF.

## 2. How data flows

```
pipelines (VM cron, Mac launchd) ──write──▶ files in /root/mlb-model (data/…, nfl/data/board/…, nhl/logs/…)
reader windows (VM cron, nfl/pipeline/run_window.py) ──▶ nfl/data/board/week=…/ai_opinions/ai_opinions_<UTC>.parquet
shared/pipeline/picks_adapters.py (VM, :20) ──▶ /root/private/ledger/picks.jsonl        (PRIVATE, never in the repo)
shared/pipeline/pick_layers.py --build-missing (VM, :25) ──▶ /root/private/ledger/layers/<pick_id>.json (write-once)
crosswalk + picks_grader.py (VM, 10:10Z) ──▶ grade rows in picks.jsonl;  picks_clv.py (VM, 10:30Z) ──▶ clv.jsonl
shared/pipeline/pipeline_health.py (VM, every 15 min) ──▶ status/pipeline_health.json
shared/pipeline/history_spender.py (VM, 06:10–13:00 UTC) ──▶ status/history_spender.json
site/build_site.py (VM, every 5 min, :04/:09/…) ──reads all of the above──▶ /var/www/iamnotuncertain/*.html
Caddy (VM) ──HTTPS + login──▶ browser
```

* Code lives in the public repo `jwallace115/mlb-model` on `main`: `site/`, `shared/pipeline/`, `nfl/pipeline/`. The
  VM's copy at `/root/mlb-model` updates itself: `shared/push_daemon.sh` pulls `main` every 30 min. **A change merged to
  main is on the site within ~35 minutes**, with nothing restarted.
* The picks ledger and the cards live under `/root/private/ledger/` (env `PICKS_LEDGER_DIR`), backed up to
  `/root/private/ledger_backup/` at 05:35Z. The Mac has a dry-run copy at `~/private_picks/ledger_dryrun/`. Neither is
  ever committed. The repo is public.

## 3. Rules every change must keep (non-negotiable)

1. **Every number traces to a file** and the page shows that file's name and time (`src(...)` helper). Missing,
   unreadable or stale input renders `NODATA` ("no data"), never a guess, an old value, or a placeholder number.
2. **Labels are decisions, not results.** LIVE / SHADOW / UNVALIDATED / DEAD come from `site/signals_registry.json`,
   which mirrors the project's registry decisions. A good or bad record on the page never changes a label by itself.
   The same rule governs the Picks page: **a result is never an input to ranking** (P14) and CLV is a record, never a
   label and never an input to selection (P22).
3. **Real-price ROI first.** Tracking and the Picks Record compute ROI from the price captured in the log. Flat −110 is
   shown only as "−110 (triage only)". Every figure shows its N and date range. Signal pages break out by month and
   price band and flag a record that sits ≥ 60 % in one month.
4. **NFL forward experiment: status only.** `forward.html` lists what was frozen and when. Owners listed in
   `forward_status.json → embargo_owners` (sim_nfl, ai_nfl) show "scoring not published" on the Picks page.
5. **Tickets and picks:** each leg = leg + game + one "play to" price + a short reason. A revision is a new file or a
   supersedes row, never an edit. **No stakes, slip ids, share links, balances or member names — the repo is public
   and so is the site behind its one login.**
6. **Frozen means frozen.** A detail card reads nothing timestamped after the pick's `logged_utc` (A2, P11); cards are
   write-once; a freeze file or manifest entry is never edited or re-hashed; corrections are supersedes rows.
7. **Never** put API keys, `.env` values, passwords or anyone's personal info into the repo or a page.
8. Do not touch `nfl/sim/`, `research/nfl_sim/` or branch `eng/fwd6` while the forward experiment is running. The site
   only reads. `nfl/pipeline/` is ops-owned (the freeze tool, reader_v3, run_window).
9. **`~/mlb-model` stays on `main` and is only ever pulled.** Every change, the session log included, is committed in a
   worktree on a branch and merged in the :00–:44 window, with the push in the same minute (the Mac's :50 auto-commit
   runs `git pull --rebase`, which flattens an unpushed merge).

## 4. Files you will touch

| File | What it controls |
|---|---|
| `site/build_site.py` | Every page. One function per page: `build_today`, `build_picks`, `build_health`, `build_tracking` (+ `write_signal_page`), `build_forward`, `build_archive`; shared shell in `page()`; nav in `PAGES`; colours in `CSS`; sports on Today/coverage in `SPORTS` (NFL, NCAAF, NHL, NBA); book names in `BOOK_NAMES`; Archive holdings in `ARCHIVE_DIRS`. |
| `shared/pipeline/build_top20.py` | Which picks the Picks page shows and in what order (P10, P14); `--print-top 20` for a chat post. |
| `shared/pipeline/pick_layers.py` | The detail cards (line movement, weather, sim, injuries, news, reasoning). |
| `shared/pipeline/picks_adapters.py`, `pick_sources.py`, `picks_ledger.py`, `picks_grader.py`, `picks_clv.py`, `picks_point_audit.py` | Freeze → ledger → grade → CLV; the sign audit. Decisions in `PICKS_LEDGER_v1.md`. |
| `nfl/pipeline/log_ai_opinions.py`, `reader_v3.py`, `run_window.py` | The freeze tool (`--window`, `--reader-file`), the canonical reader, and the one-command window. |
| `site/tickets/*.json` | Member/Jeff parlay cards on Today (schema in §5.1). |
| `site/signals_registry.json` | Rows on Tracking and the "Signals today" cards; the `retired` list (a record, not rendered). |
| `site/forward_status.json` | NFL forward page (status only) and `embargo_owners`. |
| `shared/pipeline/feeds_registry.json` | What the health check expects each scheduled job to write (`"retired": true` feeds are listed, never judged). |
| `shared/pipeline/history_jobs.json` | What the nightly history spender buys, in priority order. |
| `site/ops/iamnotuncertain.caddy`, `site/ops/add_site_user.sh`, `site/ops/picks_ledger_setup.sh` | Web server block, logins, private ledger folders (VM side). |

Test locally before merging: `SITE_REPO_ROOT=<a folder with data/, nfl/, nhl/, site/, status/> python3 site/build_site.py --out /tmp/site`
then open the HTML (`PICKS_LEDGER_DIR` pointing at a dry-run ledger for the Picks page). Tests:
`python3 -m pytest -q shared/pipeline/tests/ nfl/pipeline/tests/` (three standing reds are known and named in
`claude/status_ops.md`; any other red stops a merge).

## 5. Recipes

### 5.1 Put a ticket card on Today

Schema — one file per card, name `<slate_date>_<short_name>.json`:

```json
{
  "ticket": "NBA opening night 4-leg",
  "slate_date": "2026-10-20",
  "logged_utc": "2026-10-20T22:05Z",
  "prices_from": "hardrockbet_fl app check 22:00Z",
  "legs": [
    {"leg": "BOS -4.5", "game": "NYK @ BOS", "price": -110, "why": "One short reason in the reader's words."}
  ]
}
```

* `slate_date` is the **ET** date the games are played; Today shows cards whose `slate_date` equals today (ET).
* `price` is an integer American price (the play-down-to price). Text is allowed only if there is no number.
* Delivery (fastest path, ~5 min to the page): the chat writes the JSON to the Mac folder
  `~/cowork_audit/tickets/` (outside the repo, via the device bridge) and gives Jeff ONE command:
  `scp ~/cowork_audit/tickets/<file>.json do-vm:/root/mlb-model/site/tickets/`
  The VM is then the only writer of that file; push_daemon commits it to GitHub. **Never commit ticket files from the
  Mac checkout** (two writers of one path = push conflicts).
* The card JSON is also the record: it stays in `site/tickets/` permanently, and the :20 adapters ingest it into the
  ledger (owner from the ticket, `source` site_tickets).

### 5.2 Add a signal to Tracking (and "Signals today")

Add an object to `site/signals_registry.json` → `signals`:

| Key | Meaning |
|---|---|
| `id`, `name`, `market` | `id` = file-safe slug (page `signal-<id>.html`). |
| `label` | LIVE / SHADOW / UNVALIDATED / DEAD — from a recorded decision only. |
| `path` | Repo-relative JSON log. A list, or a dict holding the list under `list_key` (default `signals`). |
| `date_field` | Field holding the game date (YYYY-MM-DD…). |
| `fired_field` | Optional: only rows where this is truthy count (e.g. `signal_fired`). |
| `result_field`, `win_values`, `loss_values` | How a graded row says W / L (anything else = not graded yet; "PUSH" = push). |
| `profit_field` | Optional: profit at 1 unit stake already in the log. |
| `price_field` | Optional: captured American price; real-price ROI is computed from it when no `profit_field`. |
| `today`, `show` | `today: true` adds a "Signals today" card listing the `show` fields of today's rows. |
| `note` | One line shown on Tracking. |

No `profit_field` and no `price_field` → the page says "no captured price" and shows only the −110 triage number.
A parquet log needs a small adapter in `bets_for()`; keep its output tuples `(date, "W"/"L"/"P", profit|None, price|None)`.
A retired signal moves to the top-level `retired` list with the registry's reason; it returns only through a PIT audit
and a recorded decision.

### 5.3 Add a sport to the Today slate and the coverage table

The slate reads the newest tape snapshot `data/odds_archive/<folder>/line_history/season=*/snap_*Z.parquet`.
Add `("NBA", "nba", 90)` style tuples to `SPORTS` (label, archive folder, max snapshot age in minutes before "no data").
Hard Rock is only in the Odds API feed for NFL — elsewhere the column says "not on feed"; that is the vendor, not a bug.

### 5.4 Add or change a scheduled feed's health check

1. Add the cron line on the VM (absolute paths, no `%`, `>> /root/logs/<name>.log 2>&1`), after
   `crontab -l > /root/crontab.bak.<UTC>`.
2. Add to `shared/pipeline/feeds_registry.json`: `id`, `label`, `sport`, `cron_match` (a substring unique to that cron
   command), `outputs` (glob, repo-relative or absolute), `ts` (`filename` if the name holds `YYYYMMDDTHHMM[SS]Z`, else
   `mtime`), optional `quiet_ok`, `active_months`, `grace_min`, `write_lag_min`. Mac jobs: `host: "Mac"`,
   `cadence_min` instead of `cron_match`; judged by what reaches the VM through GitHub.
3. Cron lines with no registry entry are still checked from their log ("unregistered job → <log>"); a cron line that
   matches a `"retired": true` feed is not reported.

### 5.5 Add a page

Write `build_<name>(now, health)` returning `page("<file>.html", "<Title>", body, health, now)`, add `("<file>.html",
"<Nav title>")` to `PAGES`, and add it to the `pages` dict in `build()`. Use `src()`, `NODATA`, `badge()`, `.card`,
`.tablewrap` + `table`, `.tiles`/`.tile` so it matches. Must work at phone width (tables scroll sideways inside
`.tablewrap`).

### 5.6 Other common changes

* **Forward experiment status:** edit `site/forward_status.json` (`runs`, `next`, `scoring`, `embargo_owners`). Status
  words only.
* **Archive holdings row:** add `(label, repo-relative dir, markets text)` to `ARCHIVE_DIRS` (the MLB rows carry the
  "(off-season; MLB restarts 2027)" suffix — holdings are real data).
* **History to buy:** add a job to `shared/pipeline/history_jobs.json` (kinds `event`, `grid`, `inplay`; see the
  `_doc` there). Never re-list something already held.
* **Add a login:** `ssh do-vm 'bash /root/mlb-model/site/ops/add_site_user.sh <name>'` (prints the password once).

### 5.7 The Picks page (Top-20) — the product

`index.html` (the front page) has one tab per sport (NFL, NCAAF, NHL, NBA) and two columns per tab — player props;
sides / totals / moneyline — each ranked 1–20 by the reader's confidence, with the price to play to, the conf, a
one-line reason and "moved: ±x pts" (the pick's own line at its book since the open). Clicking a pick opens its
**detail card** inline: line movement (book open → close, cross-book consensus, P17/P18), weather (NWS, NFL outdoor
stadiums), what the sim says (a prediction, never a result; NFL only), injuries, news (≤ 72 h before the pick), and
the reader's reasoning — all **frozen as of `logged_utc`**: nothing timestamped after the pick is ever read. Each
layer renders a plain-English summary paragraph above the raw data (folded in `<details>`; P30).

* **Data:** `PICKS_LEDGER_DIR/picks.jsonl` (view rows: latest per pick_id after supersedes), `layers/<pick_id>.json`
  (cards, write-once, built on the VM at :25), `clv.jsonl` (closing-line value per pick, 10:30Z). The site build reads
  these and never builds them. Ledger absent → `NODATA`.
* **Selection (`build_top20.select`, P10/P14):** per sport, the latest reader freeze whose games are still upcoming
  (`commence_time > now`, `logged_utc ≤ now`); owner `ai_<sport>` only (sim and member picks are never ranked); order
  = `conf` desc, then a price-distance proxy for edge, then `logged_utc`. **Results and CLV are never inputs.** Rows
  without `conf`, `event_id`, `price_american` or `side` land in the unranked list.
* **Windows (P20/P21):** every freeze carries `window` ∈ {open, mid, late, prekick, adhoc}; the sport header reads
  "<window> freeze · <UTC>"; rows frozen before windows existed show "legacy". The same contract can be frozen once
  per window (revision 0 in each); a second freeze in the same window is revision 1 and unscored.
* **Record section:** graded picks by owner × window: W/L/P, real-price ROI, monthly breakout with the ≥ 60 % flag,
  and CLV (mean clv_points, n, share > 0 — bettor's-favour convention, P22). Owners in `embargo_owners` show "scoring
  not published".
* **Who writes what:** reader freezes come from the VM cron windows (NFL: Tue noon ET open, Thu 6:00 PM ET mid, Sat
  6:00 PM ET late, 3 h before each kick prekick) through `nfl/pipeline/run_window.py`, or on demand from the Mac:
  `python3 nfl/pipeline/run_window.py --sport nfl --window adhoc` (pulls fresh lines, freezes, prints the top 20 per
  column). The reader today is `reader_v3` (a deterministic script; its sha256 is in every manifest; `reader_model`
  must say what actually formed the picks). Other sports' lanes write to the same contract (P13: `conf` 0–100, `tag`
  ≠ no_view, optional `rationale`, `window`; `point` = the bettor's number, P16).
* **Never shown:** stakes, slip ids, share links, balances, member handles (members.json is VM-private).
* **Corrections:** never edit a row or a frozen file; append a supersedes row (`picks_point_audit.py --repair` is the
  model). Cards are rebuilt only when their layer was empty by a recorded defect (P27), and the rebuilt card says so.

## 6. How a chat gets a change live (no copy-paste relays)

| Change | Who does it | Path |
|---|---|---|
| Ticket card | the sport chat | §5.1 — write JSON to `~/cowork_audit/tickets/`, Jeff runs one `scp`. |
| Reader freeze | the VM cron, or Jeff with `run_window.py --window adhoc` | §5.7. The adapters pick it up at :20, cards at :25, the page within 5 min of that. |
| Registry / status JSON, `build_site.py`, pipeline code | the ops chat writes a numbered work order; ONE fresh Claude Code session runs it | Worktree from `origin/main`, branch per order, red-first tests, one commit per item, evidence file under `~/cowork_audit/<date>/`, merge `--no-ff` in the :00–:44 window and push in the same minute. `~/mlb-model` is never committed to. Cowork verifies from origin before the next order. |
| VM-side (cron, Caddy, logins, private ledger) | the same Claude Code session over `ssh do-vm` | Back up first (`crontab -l > /root/crontab.bak.<UTC>`, `cp /etc/caddy/Caddyfile …bak…`, `cp picks.jsonl ledger_backup/…`); Caddy also serves roofworks and solwatch — never break them; Caddyfile mtime must stay 2026-10-02 04:19:56 unless a Caddy change is the order. |

Check your change on the site: Pipeline health shows `site_build` FIRING within 5 min; the page footer shows "Built
<time>". If the build crashes, the old pages stay up (the builder swaps a finished directory in), and
`/root/logs/site_build.log` says why.

## 7. Per-sport notes

* **Retired from the pages 2026-10-06 (Jeff): MLB, golf, soccer, WNBA.** Eight MLB/WNBA signal rows moved to the
  `retired` list in `site/signals_registry.json` with the research registry's status (P09 DEAD; night_dog / bp_adv_dog
  UNVALIDATED, PIT unknown; yrfi VALIDATED_SHADOW, PIT partial; p1b inline only; nrfi_sel not an edge; adj, wnba_a
  DEAD). MLB signal jobs are commented out on the VM (`# RETIRED 2026-10-08`) and 6 Mac plists disabled; the MLB line
  tape and event markets keep running as data capture. **MLB returns in 2027 only through a PIT audit per
  `research/mlb/mlb_system_registry_v2.md` and a recorded decision** — not by uncommenting cron lines.
* **NFL:** the windows above; the freeze's `line` is the home team's number and the adapter converts second-side
  spreads to the bettor's sign (P16) — a lane that writes picks directly must write the bettor's number. The props
  archive is one parquet per month holding rows by `pull_timestamp` (October's file holds late-September pulls):
  read every file and filter by timestamp, never trust the file name. Mac pulls land in `data_<S>_<MM>_mac.parquet`
  beside the VM's file (two writers, two files).
* **NCAAF:** same freeze tool (`--sport ncaaf`, Pinnacle book of record); the reader does not write `conf` yet, so the
  tab stays unranked until it does (P13).
* **NHL / NBA:** write to the ledger contract (owner `ai_nhl` / `ai_nba`, `conf`, `tag`, `window`, bettor's `point`);
  NBA pipelines run on the Mac (stats.nba.com blocks the VM); NBA history 2022–26 is Mac-only.
