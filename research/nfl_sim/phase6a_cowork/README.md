# Cowork 6A verification scripts (2026-09-28)
Run from Cowork's Linux verification worktrees (eng/6a @ fc3724115 and main @ 07821b7fb), PBP 2021-24 REG.
Paths inside are the verification machine's; they are kept as the record of how each number in
`phase6a_verification_2026-09-28.md` was made, not as pipeline code.
- `run_sample.py` — the 200-game phase5z sample, N=100, seed as 5Z, drive log + play log, on each engine. The zone-snap
  counters (`vz90/vz95/vz98`) came from a LOG-ONLY 3-line patch to an uncommitted copy of engine.py (counts `playing`
  snaps by zone at the pre-snap safety roll; no RNG use); the patch was removed after the run.
- `ppd_real.py`, `real_mix.py`, `analyze.py` — points per drive by start bucket, START MIX / EFFICIENCY split, outcome mix.
- `saf_real.py` — real zone snaps and per-snap safety rates. `timeout_followed_real.py`, `to_calls.py` — real timeouts.
- `kneel_real.py`, `kneel_sim_kcbuf.py` — kneel elapsed like-for-like (final kneels included, capped at the half end).
- `ppd_safety_output.txt`, `sim_clock_class_sample.csv` — outputs.
