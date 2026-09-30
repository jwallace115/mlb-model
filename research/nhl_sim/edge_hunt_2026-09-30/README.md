Edge hunt 2026-09-30 (Cowork). Read edge_hunt_2026-09-30.md first.
- Pre-registrations: PREREG_CLV, PREREG_EV, PREREG_EV2 and PREREG_ALT. Each was written before its run; the sha256
  values are in the note.
- The scripts ran in Cowork's container. Their paths point at /home/claude/...; the inputs are in this folder:
  - lines_all.parquet, games_lines.parquet;
  - staged engine prices;
  - raw/nhl_goalie_starts.csv (the phase-1 panel).
- market_grid_v1_cowork.npz is grid.py's output. NHL-L1 Item 1 must reproduce it exactly.
- Not to be committed: *.parquet, *.npz.
