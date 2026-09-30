# Pre-registration EV2 — confirmation of the early soft-book price rule (Cowork, written before any 2024-26 number)

Origin (stated honestly): PREREG_EV.md's H1 (CLOSE snapshot) FAILED (ROI -16.6%, 131 bets). Its EARLY snapshot was
a pre-declared secondary report, not a test: 157 bets, ROI +2.5% (SE 10%), mean CLV vs Pinnacle close +1.28%
(SE 0.38%), +1.23% in 2022-23 and +1.39% in 2023-24. That CLV pattern is the hypothesis here, chosen after seeing it.

Rule: exactly ev_test.py's EARLY branch, unchanged — earliest snapshot >= 12 h before puck with a Pinnacle moneyline;
Pinnacle multiplicative de-vig; best of the 8 other books at the same point; EV >= 0.02; one side per game x market;
moneyline, total at Pinnacle's point, puck line +/-1.5.

Data: 2024-25 and 2025-26 regular season. These seasons were used in the P3 market scan (other rules) but never with
this rule. The ENGINE is not involved, so this does not touch the engine's S-WO5 holdout evaluation.

H2 (primary): pooled mean CLV = Pinnacle CLOSE fair x bet price - 1 > 0, 90% CI lower bound > 0 (game-clustered).
Secondary (reported, not tested): ROI with SE; each season; market; book; month.
One run. If H2 fails, the early-price lead is dead and is not re-thresholded.
