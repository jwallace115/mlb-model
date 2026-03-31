# S6 Tournament Segmentation — Validation Report

Generated: 2026-03-30T22:26:19

## Classification: STANDALONE

## Tournament Classes (5)
- **ELEVATED**: 97 events (36 OOS). Examples: Waste Management Phoenix Open, The Genesis Invitational, Arnold Palmer Invitational presented by Mastercard
- **MAJOR**: 21 events (8 OOS). Examples: The Masters, U.S. Open, PGA Championship
- **REGULAR_EASY**: 70 events (20 OOS). Examples: The American Express, Farmers Insurance Open, Sony Open in Hawaii
- **REGULAR_HARD**: 58 events (23 OOS). Examples: AT&T Pebble Beach Pro-Am, The Honda Classic, THE PLAYERS Championship
- **WEAK_FIELD**: 5 events (2 OOS). Examples: Rocket Mortgage Classic, Workday Charity Open, Genesis Scottish Open

## Frozen Thresholds (2020-2022)
- Field skill: LOW < 0.1282, HIGH >= 0.1515
- Scoring variance median: 2.866
- Wave terciles: LOW < -0.183, HIGH >= 0.199
- Tail balance terciles: LOW < -0.0200, HIGH >= 0.0600
- Elite density terciles: LOW < 0.0972, HIGH >= 0.1538

## Key Findings
1. Most distinct class: REGULAR_EASY
2. Amplifies existing signals: Yes
3. DG calibration varies by class: see Brier scores
4. Recommended as context filter: Yes
