# Own Numbers (ON) — Spec v2: the forward protocol (ON-D7, 2026-10-12)

Adopted from the ChatGPT audit's "valid forward test" section (c23e62419),
verbatim where it is specific.

## Scope

Team-level player-off model. The engine's player layer is inactive for ON.
2021-23 are DEVELOPMENT seasons (mechanics fitted on 2021-24).
2024 is labelled "used in engine development; not a holdout" and is closed
to ON permanently (guard_2024 HALTs any attempt).

## Prediction cutoff

Monday 12:00 America/New_York of the game week, with UTC recorded.
A prior game is admitted only if its kickoff datetime + 4 hours < cutoff
(the previous week's Monday Night game is excluded).

## Inputs

- Only still-upcoming fixtures at the cutoff.
- Immutable input snapshots with a manifest (FROZEN_MANIFEST_v2.json).
- Benchmark = the active `hardrockbet_fl` quote at the cutoff, normalised
  to home margin (q = −h). Pinnacle's stored alongside.

## Selection

|ours_m − q| ≥ err_m AND ≥ 1 pt, with side and exclusions recorded before
any close is observed. Side is fixed at decision time and does not change.

## Endpoints

**PRIMARY:** mean signed decision-to-close movement over ALL selected games
(unchanged lines included), with the paired difference vs the earlier-close
comparator (ON-D8, `comparator_prior_close.py`).

**SECONDARY:**
- Direction accuracy among movers (conditional on the line moving)
- Same-side ATS at the decision line and at the close
- Returns at recorded prices (hypothetical unless placed; placed vs hypothetical
  distinguished)

## Stopping rule

- First valid post-freeze Monday through the end of the 2026 regular season.
- ≥ 60 selected unique games AND ≥ 12 weekly clusters for a confirmatory read;
  otherwise labelled "underpowered".
- Analysis frozen; weekly dependence accounted for.
- No efficacy-based early stopping.
- A missed Monday is missed (Tuesday = labelled pilot).
- Every look logged.

## Changes

Any change to the model, selection rule, scoring rule, or inputs = a new
experiment version. The current version is ON-v2.

## Labels

- 2021-23: DEVELOPMENT (mechanics fitted on 2021-24)
- 2024: used in engine development; not a holdout
- 2026 forward: PRIMARY (after the freeze)
- Pre-freeze 2026 weeks: PILOT

## How to run on Monday (ON-D4, updated for ON-D5/D6)

Every Monday 12:00 ET (or Tuesday if Monday was missed):

```bash
cd ~/mlb-model-on1
SSL_CERT_FILE=$(python3 -c "import certifi; print(certifi.where())") \
  python3 research/own_numbers/run_monday.py --season 2026 --week N
```

HALTs: not Mon/Tue ET, week file exists, snapshot > 3h old, unmapped team,
ambiguous event match, season 2024.

Output: `nfl/data/own/forward/week=2026_NN.parquet` — our number, error bar,
HR and Pinnacle decision + close quotes (with timestamps and prices), gap,
confident flag, side, kickoff_utc, prediction_cutoff_utc. MODE=PILOT until
the freeze is confirmed.
