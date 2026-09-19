# CLAUDE.md — mlb-model

Sports-betting research. **Guilty until proven innocent.** This project has lost
weeks of work and hundreds of dollars to contaminated backtests and careless
implementation. The rules below are permanent and are not relaxed for speed.

---

## RESEARCH CHECKS — state results explicitly before building on any finding

**1. Two-class provenance.** (a) Does the live signal use only pre-first-pitch data?
(b) Were training features built point-in-time, or from end-of-season aggregates,
leaderboards, or anything incorporating future-of-game-date information? Passing (a)
is not evidence for (b). Verify separately.

**2. Discovery-validation leakage.** Was the validation window touched during feature
selection, archetype discovery, threshold tuning, or signal selection? A stated
train/validate/OOS split is NOT evidence of clean separation. The only true OOS is
data unavailable at discovery time.

**3. Research object == live object.** Same formulas, thresholds, missing-value
handling, degraded-mode behaviour, inputs. "Similar" is not identical.

**4. Economic reality.** Real closing-price ROI is the deployment gate. Synthetic
flat -110 is triage only and must be labelled as such.

**5. Aggregate hiding.** Break out by month, season, sub-regime, sample depth,
confidence tier. Good aggregate + 90% of fires in one regime = broken.

**Audit triggers:** any mention of a backtest result, historical ROI, or validation
metric; building on a prior finding; the user questioning data quality (treat as an
audit trigger, never as doubt to reassure); anything described as "validated".

**If you catch yourself validating rather than auditing — stop and audit.**

---

## IMPLEMENTATION PRE-CHECKS — state before writing any code

1. **Runtime.** calls x iterations x sleep = seconds -> hours. Over 2h, optimise first.
   Never copy a sleep value from another script without recomputing it.
2. **Conversation parameters.** If Jeff specified a value — timestamp, path, interval,
   threshold, market — use HIS value exactly. Never substitute a "standard" one. Ask.
3. **Credits.** calls/game x games/date x dates x cost/call, against the balance.
4. **Paths.** Must match existing structure. `<sport>/pipeline/`, `research/<topic>/`.
   Never invent a path without checking what exists.
5. **Common sense.** Does this contradict something established? Does the math work
   end to end? Would a competent engineer spot an obvious error?

**HALT ON FAILED CHECK.** Do not silently rebuild a missing prerequisite (Rule 5).
Commit *and push* — a commit not on origin is not durable (Rule 6).
Registry -> Review -> Decision -> Code (Rule 7). Voice uncertainty (Rule 8).

---

## ENVIRONMENT TRAPS — all found the hard way

- **`load_dotenv()` defaults to `override=False`.** An exported shell var silently beats
  `.env` and the run looks healthy on the wrong account. Always
  `load_dotenv(path, override=True)` and log a key fingerprint
  (`sha256(key)[:8]`) at startup. This exact bug hid a free-tier key behind a paid one.
- **Cron on macOS uses a minimal environment.** `/usr/bin/python3` is Apple's system
  Python and lacks pandas/requests/dotenv. Always write the full interpreter path from
  `which python3`. A cron job writing 0-byte logs daily went unnoticed for weeks.
- **`%` is special in crontab.** Do not put `$(date +%Y)` in a cron line.
- **Secrets have leaked from three places:** a PAT embedded in the git remote URL, a
  hardcoded literal in a tracked `.py`, and an `export` in `~/.zshrc`. Only `.env`
  (gitignored) is acceptable. Never print a secret; compare fingerprints instead.
- **Do not paste secrets into a chat.** Use `scripts/set_env_key.sh <VAR>`.

## ODDS API COST MODEL

    live:       cost = markets x regions
    historical: cost = 10 x markets x regions      <- this is what burns budget
    bookmakers= overrides regions=; every 10 books = 1 region-equivalent

`BOOKS` must stay at **<= 10**. An 11th silently doubles every call. The current list
spans `us` and `us2` at one region-equivalent, which is the only reason
`hardrockbet_fl` — Jeff's sole legal book in FL — is reachable at no extra cost.
Log `x-requests-remaining` every run; alert under 3,000.

---

## CURRENT STATE (2026-08-29)

**Established.** Kalshi maker hurdle **0.69%** vs ~4.55% at a sportsbook. Naive passive
quoting is **negative**: size-weighted **-0.347c/contract** at 60s markout, from 186,205
fills, with a passing null control (random-time drift ~0, all |t| < 1.9). The venue
does not supply an edge; it lowers the bar a real signal must clear.

**Withdrawn 2026-08-28.** Settlement grading of maker fills. Settlement was inferred
from final observed quote; zero of 140 "settled" markets had an actual settled event.
Outcome-conditioned selection. See `research/execution_edge/kalshi_settlement_grade_2026-08-28.md`.
Do not cite the +0.494c figure.

**Withdrawn.** The +4.31% line-shopping ROI. Rebuilt properly it is **+2.44%**
(t=9.19, N=2,648), falling to **+1.84%** excluding stale books, and 50.9% of best
numbers sit in three books — one offshore. See `research/execution_edge/`.

**Open, unresolved.** (a) markout != settlement — needs real MLB results for
2026-08-15..16; (b) adverse selection is measured on GENERAL flow, not conditional on
a signal firing — a signal-conditional hurdle of 1c would erase the entire Tier-1
re-score; (c) the Hard Rock <-> Kalshi cross-venue gap has never been measured.

**Football.** Demoted to one boxed prospective experiment (wind + execution), graded on
**CLV, not W/L** — CLV needs ~125 observations against ~1,200. No new feature searches.
Kalshi lists **no NCAAF market**.

**Live contradiction, money attached.** `PHASE7_CLEAN_KILLS.md` calls P09 permanently
dead; `research/mlb/mlb_system_registry_v2.md` #14 carries it as VALIDATED_SHADOW with
active stake multipliers (1.25x / 1.5x). Resolve before trusting either.

**Deadline.** `ncaaf/pipeline/portal_2026_freeze_snapshot.py` must run before the first
Week 1 kickoff (3 Sept 2026). Write-once. Never run as of 2026-08-29.

See `RUNBOOK_2026-08-29.md` for the ordered action list.

---

## SESSION LOG — write one at the end of every Claude Code session

Append to `logs/agent_sessions.md`. Keep it factual and short:

    ## 2026-08-29T02:34Z  claude-code
    - RAN: ncaaf/pipeline/portal_2026_freeze_snapshot.py -> 10 TIER_1, internal sha 1a0bca33
    - EDITED: research/mlb/mlb_system_registry_v2.md (P09 -> DEAD)
    - BLOCKED: commit (stale .git/index.lock); divergence 213 local / 590 remote
    - NOT DONE: GitHub PAT revocation (needs the user), CFBD key rotation
    - UNVERIFIED: whether the corrupt mlb_model.db affects prior pipeline outputs

Rules for the log: separate **what a command returned** from **what it means**.
"DONE" means the command exited 0, not that the situation is safe. State what was
NOT done and what remains unverified — those lines are the point of the file.

## PIPELINE ARCHITECTURE — VM-default rule

**Default: every pipeline runs on the VM via cron.** `push_daemon.sh` syncs
writes to GitHub every 30 min. Streamlit Cloud reads from GitHub.

VM: DigitalOcean droplet (`root@142.93.242.4`), repo at `/root/mlb-model`,
Python venv at `/root/mlb-model/venv`. Decision test: SSH to VM, attempt the
data source's API call. 200 OK + resource budget fits → VM. Blocked → Mac
(documented exception). See `iamnotuncertain_operations_v9.md` §15 and
master doc v39 §17 for the full rule.

**Canonical-writer rule:** exactly one host captures per pipeline. No
dual-writer overlap (doubles credit burn or causes data conflicts).

**Current exceptions (Mac-only):**
- NBA (`stats.nba.com` blocks DigitalOcean IPs — permanent)
- Statcast aggregate rebuild (2GB RAM limit — interim)

## DIVISION OF LABOUR

Claude Code (this repo, native): anything touching an API, cron/launchd, files outside
the repo (`~/.zshrc`, LaunchAgents), git operations, long local compute.

Cowork (cloud, bridged): cross-session continuity via the Claude Project, work while
away from this Mac, and **independent verification of what a terminal session actually
changed** — reading the artifacts rather than the report. Note the limit: same model
family, so this catches claim-vs-file mismatches, not shared misconceptions. Its sandbox **cannot reach** `api.collegefootballdata.com`,
`api.the-odds-api.com`, or `api.elections.kalshi.com`, and mounts only the three
project folders.

## SESSION CONDUCT

Do not estimate, budget, or narrate how long this work will take you, and do not pause to ask whether to split it up. Runtime pre-checks apply to scripts you run, not to your own session. Correctness is the only criterion; take a faster path only when it is also the right one. Work until the assertions pass and the commit is pushed.

## WORK ORDERS — the standing contract for a numbered-item prompt

These are binding on the session regardless of whether the prompt that arrives
repeats them. They exist because each one has already cost a cycle.

**Shape.** At most 4 items. Commit AND push each item before starting the next.
Never batch. The 14-item prompts produced deferrals three sessions running.

**Decisions.** Any item that makes a decision writes its `### DNN — title (date)`
entry into `research/nfl_sim/NFL_SIM_DECISION_v1.md` **in that same commit**.
Twice, decisions landed only in commit messages and the doc silently fell behind
the code (D59–D61, then D62–D65). A decision that exists only in a commit message
does not exist.

**Pre-registration.** Where an item tests a hypothesis, write the prediction into
the report BEFORE looking at the numbers, then state whether it held. If it did
not hold, say so plainly — never tune anything to rescue it. Include a null
control: something the change must NOT move. State it, and check it.

**Reporting a run.** Separate what a command RETURNED from what it MEANS. "DONE"
means the command exited 0, not that the situation is safe. State what was NOT
done and what remains UNVERIFIED — those lines are the point.

**Exit codes.** This suite has zero `xfail`/`skip`/`parametrize` markers, so
pytest exits non-zero if anything genuinely fails. An exit 0 reported alongside
red tests means a wrapper swallowed it, not that the reds are expected. Say which.

**Known reds.** Before calling a red "pre-existing", check it fails at the parent
commit with the same value. And check it CAN go green — `test_starting_qb_identity_2026`
was carried as a known red for three cycles before anyone noticed the usage
carry-forward invents a week `max_w+1` that no starter is ever assigned to, so it
fails every week of the season forever. A permanently-red test trains people to
ignore reds.

**Measure, do not assume.** Constants about the world get derived from the data in
this repo and the derivation stated. `start_yl100` sat at a hardcoded `75.0` with
the comment "will be refined" for four seasons and was 5 yards wrong for 2024,
which contaminated a quarter of the fit window.

**Stamps and gates.** Never gate on `git rev-parse HEAD`. The Mac auto-committer
moves HEAD every 30 minutes, so a HEAD-based gate goes red within half an hour of
every re-fit, forever, and then gets ignored. Gate on content (see D72). A git
comparison is also blind to uncommitted edits, which is how `fit_5d1` got produced
by an uncommitted `run_fit.py`.

**Generators.** Anything that produces a committed artifact must itself be
committed code. K4 had no generator until D63; the calibration stamp had no writer
until D72. Both were hand-run scripts whose outputs could not be reproduced.

**Pushing.** `git push` alone will usually be rejected: `push_daemon.sh` on the VM
pushes every 30 min and the pipelines keep the tree dirty. Use
`git pull --rebase --autostash && git push` (aliased as `git sync`).
`logs/` is gitignored — `git add -f logs/agent_sessions.md`.

**`git status` from the Cowork bridge creates `.git/index.lock` and cannot remove
it.** The bridge VM has no delete permission, so every bare `git status` there
leaves a 0-byte lock that blocks the Mac auto-committer until someone runs
`rm -f .git/index.lock`. This killed the auto-committer for ~90 minutes on
2026-09-18 and was misdiagnosed as a stale lock. From the bridge, prefix
EVERY git command with `GIT_OPTIONAL_LOCKS=0` — not just `git status`. `git diff`,
`git grep` and others refresh the index and take the same lock, and a command
killed by the bridge's 180s timeout is the likeliest way to strand one (this
happened twice on 2026-09-18, the second time from a timed-out `git diff --stat`).
Prefer narrow, fast git commands from the bridge for the same reason.
