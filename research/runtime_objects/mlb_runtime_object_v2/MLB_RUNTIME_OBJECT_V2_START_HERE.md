# MLB Runtime Object V2 — Start Here

**Built:** 2026-04-22

Extension of V1. Adds 20 batting rolling features (4 metrics × 4 windows + 4 bip volume).
19,430 × 150. Grain: (game_pk, team). Scope: 2022-2025.

V1 is fully preserved — all 130 columns unmodified.
V2 adds: batting_avg_exit_velo, batting_hard_hit_rate, batting_barrel_rate, batting_xwoba_contact, batting_total_bip at last_1/3/5/10.
