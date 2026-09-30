NHL sim edge hunt — Cowork session 2026-09-30 (mandate chat). Ledger of record: project doc
claude/nhl_sim_edge_hunt_ledger.md (copy here). Scripts ran in Cowork's container against staged copies of this
repo's data (paths /home/claude/hunt/...). Large outputs not committed: fixed_2022_2023.parquet (fixed-goalie
re-price, 2,624 games, seed = game_id, 2,000 sims), market_grid_v2.npz (grid.py v1 + regulation / P1 / P2 joint
pmfs; final pmf identical to v1). The 2024-25 swapped-engine prices used by the S48-ML-R6 confirmation are in
logs/cowork_stage/prices2024/ (gitignored).
