# NHL Audit -- Phase 4: Economics Audit

## Date: 2026-04-10

## Price Usage

### Historical Backtest (Phase 5 Performance Report)
- All ROI computed at flat -110 (WIN_PER_UNIT = 100/110 = 0.9091)
- Closing lines from The Odds API (historical, DK/FD priority)
- Over/under prices available for 6426/6506 games (98.8%)

### FINDING F4 -- Flat -110 Assumption in Backtest

Severity: LOW-MODERATE

The performance report and all ROI calculations use a flat -110 price
assumption. In reality, NHL totals can trade at various prices:

Live signal prices observed:
- Over prices range: -425 to +200
- Under prices range: -270 to +300
- Median over: -102, median under: -119

At -110 flat, break-even is 52.38%. But actual prices vary significantly.
When the model takes an UNDER at -130 (break-even 56.52%), the required
hit rate is 4pp higher than assumed.

This creates optimistic bias in the backtest ROI where the model happens
to bet sides with heavier juice.

### FINDING F5 -- No Actual Price ROI Tracking

Severity: MODERATE

The live pipeline captures actual over_price and under_price at signal
time, but the grading system uses flat -110 for ROI calculation. No
system tracks the actual unit economics based on the prices at which
signals would have been executed.

For the 65 graded live signals (27-38 W-L):
- Flat -110 ROI: approximately -20%
- Actual-price ROI: not computed (would likely be worse due to juice skew)

### Edge Calculation Method

Edges are computed as:
    edge = sim_prob - fair_prob
where:
    fair_prob = implied_prob / (implied_over + implied_under)

This is a standard vig-removal approach (proportional method). The method
is acceptable.

### FINDING F6 -- Closing Line vs Opening Line Economics

Severity: LOW

The backtest uses closing lines (total_line from Odds API historical).
Live signals are generated against current lines (which may be opening
or mid-day lines depending on when the pipeline runs).

CLV tracking shows:
- 38 live signals have CLV data
- Mean CLV: +0.026 (slightly positive)
- Median CLV: 0.000

Small positive CLV is mildly encouraging but the sample is too small
and the overall performance (-20% ROI) overwhelms any CLV signal.

## Economic Verdict

The economic methodology has minor issues (flat -110 assumption, no
actual-price tracking) but these are NOT the primary failure mode.
The primary failure is the feature identity mismatch (F3) which
renders the model's edge calculation meaningless at runtime.
