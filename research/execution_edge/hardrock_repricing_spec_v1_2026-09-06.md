# Hard Rock Repricing Experiment — Prespecified Design v1
**Date frozen:** 2026-09-06 · **Author:** Cowork session (reconciled three-way review, Jeff / ChatGPT / Claude, 2026-09-04..06)
**Status:** SPEC ONLY. Written before any forward capture data existed. This file is
frozen: changes go in a dated AMENDMENTS section at the bottom, never edits in place.
That is the Check-2 protection — a spec quietly rewritten after seeing data is a
tuned spec.

---

## 0. Adjudicated priors this spec is bound by

Corrections both models accepted during the review. Future sessions must not
re-import the withdrawn versions.

1. **Kalshi taker economics.** Fee = `0.07 × C × P × (1−P)` (rounded per the official
   fee schedule). A quoted ask already embeds the spread — do not subtract a generic
   spread allowance on top (double-counting). The venue confers no *taker-side* cost
   advantage over a sportsbook on average (~4.31% vs ~4.55% at median spreads), but a
   specific mispriced offer can still be +EV taken. Evaluate offers, not averages.
2. **The 0.69% maker hurdle is triage, not a validated conversion.** It is a one-day,
   size-weighted 60s markout estimate (no queue model, markout ≠ settlement). No
   profitability claim may be built on "signal > 0.69% therefore profitable".
3. **Sportsbook ladder consistency is CLOSED** — Surface-Consistency Scanner V1 found
   zero monotonicity violations. Do not rebuild it. Kalshi *cross-contract*
   consistency (separate order books) was never tested and remains open as a cheap
   background scan.
4. **Copy-lag V1 supports the mechanism but does not establish a Hard Rock window** —
   Hard Rock was absent from every historical pull (`regions="us"` for three years).
   This experiment supplies the missing measurement.
5. **"Limits are the fastest route to being banned" is folklore, not project
   evidence.** Account capacity is a variable to *measure* (accepted stakes,
   rejections, limit changes), not an assumption.

## 1. Hypothesis

After a public, machine-timestamped information event, `hardrockbet_fl` leaves
related prices unchanged long enough — after realistic execution delay — that the
stale price is favorable net of vig relative to a reference consensus that has
already moved. Secondary, attached wherever contracts match: Kalshi prices the same
event differently (the never-measured cross-venue gap).

This is a hypothesis about **inconsistent repricing speed**, not about modeling
games better. It can be true, false, or true-but-too-brief-to-use; all three are
acceptable outcomes.

## 2. Event classes (exhaustive for v1)

- **E1 — Lineup slot shock.** Official lineup posting where a batter's slot differs
  by ≥3 positions from his median slot over his previous 7 starts, or a first
  appearance after ≥5 consecutive days absent. Source: MLB Stats API
  (`hydrate=lineups`), free.
- **E2 — Probable starter change.** Listed probable replaced after first listing.
  Source: MLB Stats API probables, free.

Event time = first poller observation of the change. Pitcher workload-restriction
*news* is not machine-timestampable and is deferred (would need a curated feed;
v2 at earliest). NFL inactives (T-90) are a natural E3 but football is demoted to
one boxed experiment — adding it requires a dated amendment and Jeff's sign-off,
not a silent scope expansion.

**Poller:** extend `mlb/pipeline/lineup_timing_snapshot.py` (exists, 4x daily) to a
5-minute cadence with per-change first-seen timestamps. Do not write a new script
(Rule 5). MLB Stats API is free; zero Odds API credits. Implementation pre-checks
(runtime, paths) apply at build time.

## 3. Measured quantities per event

From the multi-book capture panel (15-min MLB cadence) plus the Kalshi capture:

- **Reference move:** change in the no-vig consensus (median of pinnacle, fanduel,
  draftkings, betmgm) for the affected market between the last pre-event and first
  post-event snapshot.
- **Hard Rock residual gap:** HR implied probability minus post-move no-vig
  consensus implied probability, at each snapshot until HR re-anchors (within
  0.5pp).
- **Window duration:** event → HR re-anchor. **Censoring, stated in every report:**
  at 15-min cadence, durations under one snapshot are recorded as "<15 min". This
  experiment can establish windows ≥~15 min; it CANNOT rule out shorter exploitable
  windows. A null here is "no slow windows", not "no windows".
- **Kalshi leg** (matching game markets only — ML, totals): best bid/ask at the same
  timestamps; gap vs both HR and consensus.

Markets in scope: ML, FG total, run line (already captured). Player props are OUT of
v1 — each prop market added roughly triples Odds API cost (upgrade trigger in the
runbook) and prop capture isn't running.

## 4. Economics — from actuals, both routes, neither presumed

- **HR side:** EV of taking the stale HR price against post-move no-vig consensus
  fair value, at HR's actual quoted price.
- **Kalshi taker:** EV = fair − ask − fee, fee per §0.1. Reported per event where a
  matching contract has a live ask.
- **Kalshi maker:** descriptive only in v1 (could a resting order plausibly have
  been filled at a better price?). No maker P&L claims without settlement grading.
- Any flat −110 figure is labelled TRIAGE.

## 5. Research checks (per CLAUDE.md)

1. **Provenance:** forward-only by construction; every input carries its capture
   timestamp; no historical backfill (also: 10× credit multiplier). 1b risk is nil
   *if* event selection never uses post-event information — the E1/E2 definitions
   use only pre-event history.
2. **Discovery-validation:** this spec is frozen before data. Thresholds in §2–§3
   and gates in §7 are fixed. Any threshold tuned on collected data converts that
   data to in-sample; a tuned variant needs fresh forward data.
3. **Identity:** the measured object is an **API-visible quote**, not an executable
   account price. Explicit gap. Mitigation: a manual subsample (≥10 events) where
   Jeff times a real bet-slip build without placing, to measure personal execution
   delay; plus capacity logging (§0.5) if betting ever goes live.
4. **Economics:** all EV from actual captured prices net of actual fees/vig (§4).
5. **Aggregate hiding:** prespecified breakdowns — event class, market, time-to-
   first-pitch bucket (>4h / 1–4h / <1h), month, day/night. Cells with N<20 are
   labelled INSUFFICIENT, not averaged away.

## 6. Sample and honesty about the calendar

MLB regular season ends ~2026-10-04: roughly four weeks of accrual. N will be what
it is. If qualifying events total <50, the verdict is INSUFFICIENT and the
experiment extends to 2027 opening day **unchanged** — thresholds do not get
loosened to manufacture a result. Monthly interim looks are for data quality only.

## 7. Prespecified gates

- **CLOSE** if <5% of qualifying events show |HR residual gap| ≥ 2.0pp implied
  probability persisting ≥1 snapshot, or if the median such gap favors the *wrong*
  side (HR moves first).
- **PROCEED to an execution-delay phase** if ≥15 events show a gap ≥2.0pp
  persisting ≥2 snapshots (≥30 min at current cadence).
- **Cross-venue gap:** reported descriptively regardless; no gate. It resolves open
  item (c) in CLAUDE.md either way.
- No bets are placed by anything in this spec. Deployment is a separate decision
  with its own gate (real closing-price economics + measured capacity).

## 8. Dependencies (state as of 2026-09-06)

| Dependency | Status |
|---|---|
| Multi-book capture scheduled, HR present | IN PROGRESS — Claude Code session 2026-09-06; spec is inert until confirmed |
| Kalshi capture running | UNVERIFIED (kalshi-edge not visible from Cowork sandbox) |
| Lineup poller at 5-min cadence | NOT BUILT — extend existing script, §2 |
| Push durability (Rule 6) | 284/122 divergence pending push |

## 9. Companion tracks (separate docs, never gates on §7)

Weather pilot (one station; publication-timestamped archives; same-day pre-decision
observations are valid inputs — the ban is on post-decision, revised, or final-max
data). Kalshi cross-contract consistency scan (background). Capacity logging spec
(activates only if live betting resumes).

---

## AMENDMENTS

### A1 — 2026-09-06 (later same day): capture live; §8 dependency table superseded

- Multi-book capture SCHEDULED AND VERIFIED (claude-code session 2026-09-06):
  LaunchAgents `com.mlbmodel.capture.mlb` (15-min) and `com.mlbmodel.capture.football`
  (30-min); key fingerprint `ac6e89a0` (paid) on every run; output under
  `data/odds_archive/{baseball_mlb,nfl,ncaaf}/line_history/season=2026/`.
  Divergence pushed to zero; freeze artifact durable.
- **Credit recompute:** StartInterval runs 24/7, not game-hours — 576 credits/day
  ≈ 17,280/month = **13.6% headroom** on the 20K plan (supersedes the runbook's
  10,080 / 2x figure). No prop markets can be added on this plan. If headroom
  tightens, prefer calendar-windowed schedules over a plan upgrade.
- **OPEN ISSUE — hardrockbet_fl ABSENT on MLB** in all morning snapshots
  (verified 12:18Z: 9/10 books, 15 games, zero HR rows), present on NFL.
  The Aug-28 dry run had HR on 16 MLB games, so this is likely posting-time
  behavior (HR posts MLB near game day/time). MUST verify HR MLB presence in
  afternoon/evening snapshots before treating the experiment as accruing.
  If HR only posts hours before first pitch, the observable pre-game window is
  compressed and the §3 censoring caveat binds harder; record HR
  first-appearance time per game as a measured quantity (no threshold change).
- Hardening (not yet done): capture script hard-stops on any API error;
  add 1 retry / 5s backoff so football capture survives transient resets.
- Unverified: whether zero-game calls cost 0 credits; Kalshi capture status.
- **No thresholds, event definitions, or gates changed.**
