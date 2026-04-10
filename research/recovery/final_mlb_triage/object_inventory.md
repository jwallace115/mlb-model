# Final MLB Object Inventory

Date: 2026-04-10
Scope: All remaining MLB signal/overlay/engine objects

## Object List (19 objects)

| # | Object | Type | Pipeline File |
|---|--------|------|--------------|
| 1 | F5 Run Line (Signal B) | Standalone signal | mlb_sim/pipeline/f5_runline_signal_generator.py |
| 2 | ADJ_CONTACT | Shadow signal | mlb_sim/pipeline/shadow_signals.py |
| 3 | ADJ_HH | Shadow signal | mlb_sim/pipeline/shadow_signals.py |
| 4 | ADJ_K_RATE | Shadow signal | mlb_sim/pipeline/shadow_signals.py |
| 5 | ADJ_BB_RATE | Shadow signal | mlb_sim/pipeline/shadow_signals.py |
| 6 | ADJ_RUN_SUPP | Shadow signal | mlb_sim/pipeline/shadow_signals.py |
| 7 | CS013 | Shadow signal | mlb_sim/pipeline/cs013_shadow.py |
| 8 | CS028 | Shadow signal | mlb_sim/pipeline/cs028_shadow.py |
| 9 | KP04 | Shadow signal | mlb_sim/pipeline/kp04_shadow.py |
| 10 | ST02 | Overlay | mlb_sim/pipeline/st02_overlay.py |
| 11 | P09 | Overlay | research (cutoff clean, overlay value V1-contingent) |
| 12 | S12 | Overlay | research (cutoff contaminated, signal unstable) |
| 13 | V2 baseline engine | Model | research/recovery/v2_engine/ |
| 14 | flyball_wind (discrete overlay) | Overlay | research/recovery/v2_overlay_revalidation/ |
| 15 | F5 Totals Engine | Signal | mlb_sim/pipeline/f5_signal_generator.py |
| 16 | F5 Standalone (not built) | Planned | N/A |
| 17 | Team Totals (Home) | Signal | research/team_totals/ + live pipeline |
| 18 | Team Totals (Away) | Signal | research/team_totals/ + live pipeline |
| 19 | Combined Short Exit | Shadow signal | mlb_sim/pipeline/combined_short_exit_shadow.py |
