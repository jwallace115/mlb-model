# iamnotuncertain.net — Website Build Guide

**For any Claude session in this project (NBA chat, NHL chat, MLB chat, Cowork, Claude Code): read this before you
change the website or put anything on it.** It says how the site works, where every input lives, and the exact recipe for
each common change, so Jeff never has to relay files between chats.

Owner of the decisions: Jeff. Last updated 2026-10-01 by Cowork (pipeline audit session). Companion docs:
`claude/site_runbook.md` (operations), `claude/pipeline_audit_2026-10-01.md` (why it was built this way).
In the repo this file is `site/README.md`.

---

## 1. What the site is

* **URL:** https://iamnotuncertain.net (www redirects to it). Login required (HTTP basic auth, one login per person).
* **What it is:** plain static HTML pages, rebuilt every 5 minutes on the DigitalOcean VM from the files the pipelines
  write. No app server, no database, no JavaScript framework. Streamlit is retired.
* **Pages:** Today (`index.html`), Pipeline health (`health.html`), Tracking (`tracking.html` + one
  `signal-<id>.html` per signal), NFL forward (`forward.html`), Odds archive (`archive.html`).
* **Design:** the mockup is the claude.ai artifact "iamnotuncertain.net site design". IBM Plex Sans/Mono, light and dark
  mode from CSS variables in `CSS` at the top of `build_site.py`. Status colours: green FIRING/LIVE, blue SHADOW,
  amber LATE/UNVALIDATED/QUIET, red SILENT/ERRORING/DEAD, purple NOT_PUSHED/IGNORED, grey OFF.

## 2. How data flows

```
pipelines (VM cron, Mac launchd) ──write──▶ files in /root/mlb-model (data/…, mlb/logs/…, nhl/logs/…)
shared/pipeline/pipeline_health.py (VM, every 15 min) ──▶ status/pipeline_health.json
shared/pipeline/history_spender.py (VM, 06:10–13:00 UTC) ──▶ status/history_spender.json
site/build_site.py (VM, every 5 min, :04/:09/…) ──reads all of the above──▶ /var/www/iamnotuncertain/*.html
Caddy (VM) ──HTTPS + login──▶ browser
```

* Code lives in the public repo `jwallace115/mlb-model` on `main`: `site/` and `shared/pipeline/`. The VM's copy at
  `/root/mlb-model` updates itself: `shared/push_daemon.sh` pulls `main` every 30 min. **A change merged to main is on
  the site within ~35 minutes**, with nothing restarted.
* Before the 2026-10-02 full deploy, a temporary copy ran from `/opt/iamnotuncertain` (systemd timer
  `iamnotuncertain-site.timer`). The full deploy removes it. If `/opt/iamnotuncertain` still exists, the deploy has not run:
  check `claude/pipeline_audit_2026-10-01.md` §9.

## 3. Rules every change must keep (non-negotiable)

1. **Every number traces to a file** and the page shows that file's name and time (`src(...)` helper). Missing,
   unreadable or stale input renders `NODATA` ("no data"), never a guess, an old value, or a placeholder number.
2. **Labels are decisions, not results.** LIVE / SHADOW / UNVALIDATED / DEAD come from `site/signals_registry.json`,
   which mirrors the project's registry decisions. A good or bad record on the page never changes a label by itself.
3. **Real-price ROI first.** Tracking computes ROI from the price captured in the log. Flat −110 is shown only as
   "−110 (triage only)". Every figure shows its N and date range. Signal pages break out by month and price band and
   flag a record that sits ≥ 60 % in one month.
4. **NFL forward experiment: status only.** `forward.html` lists what was frozen and when. No hit rate, Brier, CLV or
   profit appears anywhere on the site before that experiment's pre-registered scoring exists.
5. **Tickets:** each leg = leg + game + one "play to" price + a short AI reason. One card per ask; a revision is a
   new file, never an edit. **No stakes, slip ids, balances or account details — the repo is public.**
6. **Never** put API keys, `.env` values, passwords or anyone's personal info into the repo or a page.
7. Do not touch `nfl/sim/`, `research/nfl_sim/`, `nfl/data/board/` or branch `eng/fwd6` while the forward experiment is
   running. The site only reads.

## 4. Files you will touch

| File | What it controls |
|---|---|
| `site/build_site.py` | Every page. One function per page: `build_today`, `build_health`, `build_tracking` (+ `write_signal_page`), `build_forward`, `build_archive`; shared shell in `page()`; nav in `PAGES`; colours in `CSS`; sports on Today/coverage in `SPORTS`; book names in `BOOK_NAMES`; Archive holdings in `ARCHIVE_DIRS`. |
| `site/tickets/*.json` | AI parlay cards on Today (schema in §5.1). |
| `site/signals_registry.json` | Rows on Tracking and the "Signals today" cards. |
| `site/forward_status.json` | NFL forward page (status only). |
| `shared/pipeline/feeds_registry.json` | What the health check expects each scheduled job to write. |
| `shared/pipeline/history_jobs.json` | What the nightly history spender buys, in priority order. |
| `site/ops/iamnotuncertain.caddy`, `site/ops/add_site_user.sh` | Web server block and logins (VM side). |

Test locally before merging: `SITE_REPO_ROOT=<a folder with data/, mlb/, nhl/, site/, status/> python3 site/build_site.py --out /tmp/site`
then open the HTML. Tests for the health check and spender: `python3 -m pytest -q shared/pipeline/tests/`.

## 5. Recipes

### 5.1 Put a ticket card on Today (the most common ask)

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
* The card JSON is also the record: it stays in `site/tickets/` permanently. Still log the pick in the sport's own
  append-only log as that chat's rules require; the site card does not replace the log.

### 5.2 Add a signal to Tracking (and "Signals today")

Add an object to `site/signals_registry.json` → `signals`:

| Key | Meaning |
|---|---|
| `id`, `name`, `market` | `id` = file-safe slug (page `signal-<id>.html`). |
| `label` | LIVE / SHADOW / UNVALIDATED / DEAD — from a recorded decision only. |
| `path` | Repo-relative JSON log. A list, or a dict holding the list under `list_key` (default `signals`). |
| `date_field` | Field holding the game date (YYYY-MM-DD…). |
| `fired_field` | Optional: only rows where this is truthy count (e.g. `signal_fired`, `yrfi_2plus`). |
| `result_field`, `win_values`, `loss_values` | How a graded row says W / L (anything else = not graded yet; "PUSH" = push). |
| `profit_field` | Optional: profit at 1 unit stake already in the log. |
| `price_field` | Optional: captured American price; real-price ROI is computed from it when no `profit_field`. |
| `today`, `show` | `today: true` adds a "Signals today" card listing the `show` fields of today's rows. |
| `note` | One line shown on Tracking. |

No `profit_field` and no `price_field` → the page says "no captured price" and shows only the −110 triage number.
A parquet log needs a small adapter in `bets_for()`; keep its output tuples `(date, "W"/"L"/"P", profit|None, price|None)`.

### 5.3 Add a sport to the Today slate and the coverage table

The slate reads the newest tape snapshot `data/odds_archive/<folder>/line_history/season=*/snap_*Z.parquet`.
Add `("NBA", "nba", 90)` style tuples to `SPORTS` (label, archive folder, max snapshot age in minutes before "no data").
NBA is already listed; it shows "no data" until the tape has NBA files (tape added `basketball_nba` on 2026-10-02).
Hard Rock is only in the Odds API feed for NFL — elsewhere the column says "not on feed"; that is the vendor, not a bug.

### 5.4 Add or change a scheduled feed's health check

1. Add the cron line on the VM (absolute paths, no `%`, `>> /root/logs/<name>.log 2>&1`).
2. Add to `shared/pipeline/feeds_registry.json`: `id`, `label`, `sport`, `cron_match` (a substring unique to that cron
   command), `outputs` (glob, repo-relative or absolute), `ts` (`filename` if the name holds `YYYYMMDDTHHMM[SS]Z`, else
   `mtime`), optional `quiet_ok` (a run that writes nothing is normal), `active_months`, `grace_min`, `write_lag_min`.
   Mac jobs: `host: "Mac"`, `cadence_min` instead of `cron_match`; judged by what reaches the VM through GitHub.
3. Cron lines with no registry entry are still checked from their log (shown as "unregistered job → <log>").

### 5.5 Add a page

Write `build_<name>(now, health)` returning `page("<file>.html", "<Title>", body, health, now)`, add `("<file>.html",
"<Nav title>")` to `PAGES`, and add it to the `pages` dict in `build()`. Use `src()`, `NODATA`, `badge()`, `.card`,
`.tablewrap` + `table`, `.tiles`/`.tile` so it matches. Must work at phone width (tables scroll sideways inside
`.tablewrap`).

### 5.6 Other common changes

* **Forward experiment status:** edit `site/forward_status.json` (`runs`: week, slate, frozen_at, kind, receipt; `next`;
  `scoring`). Status words only.
* **Archive holdings row:** add `(label, repo-relative dir, markets text)` to `ARCHIVE_DIRS`.
* **History to buy:** add a job to `shared/pipeline/history_jobs.json` (kinds `event`, `grid`, `inplay`; see the
  `_doc` there). Never re-list something already held — the spender skips keys on disk or in the ledger, but a
  different snapshot time is a new key.
* **Add a login:** `ssh do-vm 'bash /root/mlb-model/site/ops/add_site_user.sh <name>'` (prints the password once).

## 6. How a chat gets a change live (no copy-paste relays)

| Change | Who does it | Path |
|---|---|---|
| Ticket card | the sport chat | §5.1 — write JSON to `~/cowork_audit/tickets/`, Jeff runs one `scp`. |
| Registry / status JSON, `build_site.py`, health registry | the chat writes the change and tests it; ONE Claude Code prompt commits it | Prompt pattern: `cd ~/mlb-model && GIT_OPTIONAL_LOCKS=0 git pull --rebase --autostash origin main`, apply the patch the chat left in `~/cowork_audit/<date>/`, run `python3 -m pytest -q shared/pipeline/tests/`, stage only the named paths, commit, `git pull --rebase --autostash && git push`. Live on the site ≤ 35 min later. |
| VM-side (cron, Caddy, logins) | one Claude Code prompt over `ssh do-vm` | Back up first (`crontab -l > /root/crontab.bak.<UTC>`, `cp /etc/caddy/Caddyfile …bak…`); Caddy also serves Community Scout (`scout.iamnotuncertain.net`), roofworks and solwatch — never break them. |

Check your change on the site: Pipeline health shows `site_build` FIRING within 5 min; the page footer shows "Built
<time>". If the build crashes, the old pages stay up (the builder swaps a finished directory in), and
`/root/logs/site_build.log` says why.

## 7. Per-sport notes for when a season starts

* **NBA (opens 2026-10-20):** NBA pipelines run on the Mac (stats.nba.com blocks the VM). Tape NBA lines from the VM
  (added 2026-10-02). For Tracking, register NBA signal logs as in §5.2 once they exist; NBA history 2022-26 is on the Mac
  in `data/odds_archive/nba/history/` (not on the VM).
* **MLB (spring 2027):** P09 and YRFI logs (`mlb/logs/p09_shadow_2026.json`, `yrfi_shadow_2026.json`) are already in the
  signals registry; new season files need new `path`s (e.g. `…_2027.json`). In `feeds_registry.json` the MLB feeds use
  `active_months` 3–10, so they turn from OFF to judged automatically. The 2026 lesson: both shadows crashed silently
  from mid-June (MLB API 406) — the health page now shows that kind of failure as ERRORING within one day.
* **NHL:** `nhl/logs/nhl_shadow_aligned_2026.json` has no price field, so Tracking shows −110 triage only until prices
  are logged.
* **NFL / NCAAF:** cards via §5.1; the forward experiment page stays status-only.
