# Forward-run runbook — nfl_fwd_v1, weeks 4, 5 (D272)

Reader model: `nfl_sim_v1_156cd057`. Generated 2026-10-03T17:03:17Z by `research/nfl_sim/make_runbook.py`. Run every command from the checkout that holds the refreshed inputs. Every forward run goes through the bootstrap (D266).

## Input refresh (D271/D272) — per window, never at the last minute

```bash
python3 nfl/sim/refresh_inputs.py --week W
```

- About 10 min (ratings.py about 8). Exit 0: every team playing week W passes the forward gate. Exit 1: the refreshed tables ARE installed but the named teams are not ready (usually an unpublished injury report); a run including them HALTs. Exception: refresh failed, old tables restored.
- Sunday: after the final injury reports (Friday 4 PM ET), and again on game morning, finishing at least 30 min before the window's harness start.
- Monday: the final report is due SATURDAY 4 PM ET (D278); refresh after it, and again on game morning, finishing at least 30 min before the harness start.
- TNF: after Wednesday's report, and again Thursday afternoon.
- D277: the refresh fetches the OFFICIAL nfl.com injury report for week W; its rows replace the feed's for every team on the page. A SKILL-position row it cannot identify HALTs the refresh (old tables restored); an unidentified non-skill row is printed and not written. `--no-official` skips it, and a primary run then HALTs at the D277 gate.
- D277: before a primary harness, commit the evidence of the capture the refresh used (fetch record with URL, retrieval UTC and page sha256; the identified rows; the refresh manifest). The page itself stays in the refresh archive:
```bash
python3 nfl/sim/official_injuries.py export --week W --out research/nfl_sim/official_injuries/2026_wW && git add research/nfl_sim/official_injuries/2026_wW && git commit -m "D277: week-W official injury capture" && git push origin eng/fwd6
```
- Never re-pull 2020-2025 PBP; never install or upgrade Python packages (D269/D270).

## Roster information cutoff (declared, D272)

Each window freezes on the rosters and injury report of its LAST refresh before the harness start. Game-day inactives announced after that refresh (about 90 min before each kick) are NOT in the live active universe. The backtest used final game-day rosters, so live and backtest rosters are not identical for late games. This is a declared input difference, not final-roster parity. Out/Doubtful from the official final injury report (nfl.com, D277) ARE applied.

## Week 4

### PIT@CLE — Fri 2026-10-02 00:15Z (Thu 8:15 PM ET)
Games (1): PIT@CLE
- Quotes: the VM's Thu 22:00Z props pull (1.5 h old at start); game lines from the 30-min tape. Max quote age 3 h at the harness start.
- Harness start: **Thu 2026-10-01 23:30Z** (Thu 7:30 PM ET); sim about 0 min.
```bash
python3 -I -S -B nfl/sim/fwd_bootstrap.py harness --week 4 --window-hours 1.5 --pilot   # D276: declared pilot
```

### IND@WAS — Sun 2026-10-04 13:30Z (Sun 9:30 AM ET)
Games (1): IND@WAS
- Quotes: a MANUAL props pull at Sun 2026-10-04 12:15Z; game lines from the 30-min tape. Max quote age 3 h at the harness start.
```bash
python3 nfl/pipeline/pull_hardrock_props.py --window-hours 2 --tag close \
  --out-dir data/odds_archive/nfl/props/season=2026/manual
```
- Harness start: **Sun 2026-10-04 12:45Z** (Sun 8:45 AM ET); sim about 0 min.
```bash
python3 -I -S -B nfl/sim/fwd_bootstrap.py harness --week 4 --window-hours 1.5
```
- D277/D279: PRIMARY only if a ChatGPT audit of the CURRENT pin is GO before the harness start and the harness passes the official-injury-report gate; otherwise run the same command with `--pilot` (a declared pilot, never promoted after outcomes).

### Sunday main + SNF (13 games) — Sun 2026-10-04 [17:00Z, 20:05Z, 20:25Z, 00:20Z] (Sun 1:00 PM ET+)
Games (13): TEN@BAL, NE@BUF, NYJ@CHI, JAX@CIN, DAL@HOU, ARI@NYG, LA@PHI, GB@TB, MIA@MIN, KC@LV, LAC@SEA, DEN@SF, DET@CAR
- Quotes: the VM's Sunday 16:00Z props pull (confirm it arrived); game lines from the 30-min tape. Max quote age 3 h at the harness start.
- Harness start: **Sun 2026-10-04 16:15Z** (Sun 12:15 PM ET); sim about 6 min.
```bash
python3 -I -S -B nfl/sim/fwd_bootstrap.py harness --week 4 --window-hours 9
```
- D277/D279: PRIMARY only if a ChatGPT audit of the CURRENT pin is GO before the harness start and the harness passes the official-injury-report gate; otherwise run the same command with `--pilot` (a declared pilot, never promoted after outcomes).

### ATL@NO — Tue 2026-10-06 00:15Z (Mon 8:15 PM ET)
Games (1): ATL@NO
- Quotes: a MANUAL props pull at Mon 2026-10-05 23:00Z; game lines from the 30-min tape. Max quote age 3 h at the harness start.
```bash
python3 nfl/pipeline/pull_hardrock_props.py --window-hours 2 --tag close \
  --out-dir data/odds_archive/nfl/props/season=2026/manual
```
- Harness start: **Mon 2026-10-05 23:30Z** (Mon 7:30 PM ET); sim about 0 min.
```bash
python3 -I -S -B nfl/sim/fwd_bootstrap.py harness --week 4 --window-hours 1.5
```
- D277/D279: PRIMARY only if a ChatGPT audit of the CURRENT pin is GO before the harness start and the harness passes the official-injury-report gate; otherwise run the same command with `--pilot` (a declared pilot, never promoted after outcomes).

## Week 5

### TB@DAL — Fri 2026-10-09 00:15Z (Thu 8:15 PM ET)
Games (1): TB@DAL
- Quotes: the VM's Thu 22:00Z props pull (1.5 h old at start); game lines from the 30-min tape. Max quote age 3 h at the harness start.
- Harness start: **Thu 2026-10-08 23:30Z** (Thu 7:30 PM ET); sim about 0 min.
```bash
python3 -I -S -B nfl/sim/fwd_bootstrap.py harness --week 5 --window-hours 1.5
```
- D277/D279: PRIMARY only if a ChatGPT audit of the CURRENT pin is GO before the harness start and the harness passes the official-injury-report gate; otherwise run the same command with `--pilot` (a declared pilot, never promoted after outcomes).

### PHI@JAX — Sun 2026-10-11 13:30Z (Sun 9:30 AM ET)
Games (1): PHI@JAX
- Quotes: a MANUAL props pull at Sun 2026-10-11 12:15Z; game lines from the 30-min tape. Max quote age 3 h at the harness start.
```bash
python3 nfl/pipeline/pull_hardrock_props.py --window-hours 2 --tag close \
  --out-dir data/odds_archive/nfl/props/season=2026/manual
```
- Harness start: **Sun 2026-10-11 12:45Z** (Sun 8:45 AM ET); sim about 0 min.
```bash
python3 -I -S -B nfl/sim/fwd_bootstrap.py harness --week 5 --window-hours 1.5
```
- D277/D279: PRIMARY only if a ChatGPT audit of the CURRENT pin is GO before the harness start and the harness passes the official-injury-report gate; otherwise run the same command with `--pilot` (a declared pilot, never promoted after outcomes).

### Sunday main + SNF (12 games) — Sun 2026-10-11 [17:00Z, 20:05Z, 20:25Z, 00:20Z] (Sun 1:00 PM ET+)
Games (12): CIN@MIA, LV@NE, MIN@NO, CLE@NYJ, IND@PIT, HOU@TEN, NYG@WAS, CHI@GB, DEN@LAC, DET@ARI, SF@SEA, BAL@ATL
- Quotes: the VM's Sunday 16:00Z props pull (confirm it arrived); game lines from the 30-min tape. Max quote age 3 h at the harness start.
- Harness start: **Sun 2026-10-11 16:15Z** (Sun 12:15 PM ET); sim about 6 min.
```bash
python3 -I -S -B nfl/sim/fwd_bootstrap.py harness --week 5 --window-hours 9
```
- D277/D279: PRIMARY only if a ChatGPT audit of the CURRENT pin is GO before the harness start and the harness passes the official-injury-report gate; otherwise run the same command with `--pilot` (a declared pilot, never promoted after outcomes).

### BUF@LA — Tue 2026-10-13 00:15Z (Mon 8:15 PM ET)
Games (1): BUF@LA
- Quotes: a MANUAL props pull at Mon 2026-10-12 23:00Z; game lines from the 30-min tape. Max quote age 3 h at the harness start.
```bash
python3 nfl/pipeline/pull_hardrock_props.py --window-hours 2 --tag close \
  --out-dir data/odds_archive/nfl/props/season=2026/manual
```
- Harness start: **Mon 2026-10-12 23:30Z** (Mon 7:30 PM ET); sim about 0 min.
```bash
python3 -I -S -B nfl/sim/fwd_bootstrap.py harness --week 5 --window-hours 1.5
```
- D277/D279: PRIMARY only if a ChatGPT audit of the CURRENT pin is GO before the harness start and the harness passes the official-injury-report gate; otherwise run the same command with `--pilot` (a declared pilot, never promoted after outcomes).

## Notes

- A freshness or quote-age HALT is the gate working: do not override it for a primary. `--allow-stale-quotes` is pilot/dry-run only.
- Game lines (h2h, spreads, totals) are always no_view (the sim is market-anchored).
- Pilot files are never pooled; scoring follows the pre-registered rules (D269 L5, D270).
