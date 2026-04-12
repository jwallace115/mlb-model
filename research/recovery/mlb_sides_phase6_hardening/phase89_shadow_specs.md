# Phase 8-9: Shadow Specs and Monitoring Rules

## bp_adv_dog: SURVIVOR
- Discovery: N=241, resid=+0.0624, ROI=+8.68%
- Validation: N=147, resid=+0.0519, ROI=+6.30%
- OOS: N=179, resid=+0.0416, ROI=+3.73%

### Shadow Specification
- Trigger: MIXED game + bp_adv_dog condition met
- Action: log to shadow, bet dog ML at closing price
- Stake: flat 1 unit
- Minimum sample for go/no-go: 50 bets

### Monitoring Rules
- Track cumulative ROI weekly
- Kill switch: ROI < -15% after 50+ bets
- Promotion gate: ROI > 0% after 100+ bets with residual > +1.5%
- Expected frequency: ~179 per season

## night_dog: SURVIVOR
- Discovery: N=381, resid=+0.0349, ROI=+3.13%
- Validation: N=245, resid=+0.0337, ROI=+2.64%
- OOS: N=268, resid=+0.0533, ROI=+6.50%

### Shadow Specification
- Trigger: MIXED game + night_dog condition met
- Action: log to shadow, bet dog ML at closing price
- Stake: flat 1 unit
- Minimum sample for go/no-go: 50 bets

### Monitoring Rules
- Track cumulative ROI weekly
- Kill switch: ROI < -15% after 50+ bets
- Promotion gate: ROI > 0% after 100+ bets with residual > +1.5%
- Expected frequency: ~268 per season
