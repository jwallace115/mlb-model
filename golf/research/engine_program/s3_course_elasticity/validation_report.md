# S3 Course Elasticity Engine — Validation Report

Generated: 2026-03-30T20:48:10

## Classification: CONTEXT_FILTER

## Methodology
- Skill proxy: 0.8 * top_20_prob + 0.2 * win_prob
- Course type: classified by SG component correlations from prior editions
- SG coverage threshold: >= 70% of rounds must have non-null SG components
- Minimum 2 prior editions required per event
- Elasticity: player sg_total at course-type minus player baseline sg_total
- Match category: STRONG_MATCH (elast >= +0.2), MISMATCH (elast <= -0.1)
- Minimum 5 prior rounds in course-type bucket for STRONG_MATCH/MISMATCH

## Event Classification
- Eligible (classified): 135
- Excluded (insufficient history): 59
- Excluded (insufficient SG): 57

## Primary Dimension Distribution
primary_dimension
APP     76
PUTT    59

## Match Category Distribution
match_category
ELASTICITY_UNCERTAIN    6961
MISMATCH                3468
STRONG_MATCH            2870
WEAK_MATCH              1297
NEUTRAL                  729

## Course Fit Score
- Coverage: 58.0%
- Mean: -0.0274
- Std: 0.6748

## Final Answers
1. Most affected market: unclear
2. Exploitable standalone: No
3. Adds beyond S2: different mechanism (player-course vs field structure)
4. Most elastic SG dimension: see primary dimension distribution
