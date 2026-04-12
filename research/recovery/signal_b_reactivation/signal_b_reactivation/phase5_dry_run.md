# Phase 5: Dry Run Results (2026-04-12)

## Import Test
- Signal generator imports cleanly
- XFIP_GAP_THRESHOLD confirmed as 1.5 (post-fix)
- Status reads as SHADOW (post-fix)
- Current tracker has 7 entries (legacy, pre-fix)

## Today Slate (15 games)
| Matchup | Gap | Away xFIP | Home xFIP | Fires? |
|---------|-----|-----------|-----------|--------|
| SFG@BAL | -0.759 | 4.23 | 4.99 | No |
| ARI@PHI | -0.157 | 4.41 | 4.57 | No |
| MIN@TOR | -0.401 | 4.07 | 4.47 | No |
| LAA@CIN | -0.061 | 4.02 | 4.08 | No |
| OAK@NYM | +0.290 | 4.17 | 3.88 | No |
| MIA@DET | -0.050 | 3.88 | 3.93 | No |
| NYY@TBR | -0.105 | 3.91 | 4.02 | No |
| CHW@KCR | -0.419 | 3.79 | 4.21 | No |
| WSN@MIL | +0.381 | 4.26 | 3.88 | No |
| BOS@STL | +0.221 | 4.48 | 4.26 | No |
| PIT@CHC | +0.162 | 4.37 | 4.21 | No |
| COL@SDP | +0.404 | 4.34 | 3.94 | No |
| HOU@SEA | +0.304 | 4.08 | 3.78 | No |
| TEX@LAD | -0.477 | 3.96 | 4.44 | No |
| CLE@ATL | +0.225 | 4.17 | 3.94 | No |

**0 signals fire today.** Maximum gap is +0.404 (COL@SDP).
This is expected: gap >= 1.5 requires a large SP quality mismatch.
Historical rate: ~32-35 fires per full season at this threshold.

## Operational Readiness
- [x] Signal generator imports and runs
- [x] Threshold correctly set to 1.5
- [x] Status correctly set to SHADOW
- [x] Pitcher DB builds cleanly (1452 entries)
- [x] Schedule fetches cleanly (15 games)
- [x] No signals fire correctly (no gap >= 1.5 today)
