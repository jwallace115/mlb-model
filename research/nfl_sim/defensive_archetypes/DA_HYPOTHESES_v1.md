Labels: labels/da_labels_<season>.parquet (DA-1b, cutoffs sha 82106ae377c8de87 as recorded in DA-D8); the
OPPONENT defense's label for the week of the game; UNLABELED rows excluded from every cell.
Targets: (T1) 2023 line residual = official actual − CLOSE, per market, and the over hit at the close;
CLOSE = DraftKings line and prices where present, else the median line across books with >= 3 books and no
price (flag `close_source`); (T2) 2021-23 stats residual = official actual − an AS-OF player baseline (player's
season-to-date mean of that stat blended with prior-season mean, k = 4 games; week 1 = prior only; no prior ->
excluded). T2 exists so cells have three seasons; T1 is the one that matters.
Cells (direction registered; market in parentheses; "top" = top tercile of the opponent label):
 H1 TE funnel: TE players vs top f1_target_share_te -> receptions residual > 0 (receptions)
 H2 RB funnel: RB players vs top f1_target_share_rb -> receptions residual > 0 (receptions)
 H3 run funnel: RB players vs top f2_epa_diff (rush EPA allowed >> pass) -> rush att > 0 and rush yds > 0
 H4 pass funnel: QB vs bottom f2_epa_diff -> attempts > 0 and completions > 0; RB rush att < 0
 H5 explosive pass: WR vs top f3_explosive_pass_rate -> rec yds > 0 (yards, NOT receptions)
 H6 man coverage (2023 only): WR vs top f4_man_rate -> receptions > 0; TE vs top f4_man_rate -> receptions < 0
 H7 pressure (2022+ FTN / 2023 participation): QB vs top f4_pressure_rate -> attempts < 0; RB receptions > 0
 H8 heavy box (2023): RB vs top f4_box8_rate -> rush yds < 0; rec yds > 0
Statistic per cell: mean residual with a game-clustered SE -> z; and over-hit rate vs 50 % (T1 only).
Survival (from the spec): |z| >= 2 in discovery AND same sign with z >= 1 in the ONE 2024-25 validation (DA-3).
Null controls (both must be reported for every cell): N1 shuffled-week labels (permute each defense's weekly
labels within season, 1,000 draws) -- the z must fall inside the null's 95 % band for the cell to count;
N2 own-defense control -- the SAME test with the player's own team's defensive label in place of the
opponent's; expected |z| < 2.
Economics (T1 only; CHECK 4): over and under ROI at the real DK close prices per cell; symmetry check
over ROI + under ROI ~ -vig; flat -110 shown beside it labelled TRIAGE.
Breakouts (CHECK 5), every cell: by season (2021 / 2022 / 2023), by month bucket (Sep-Oct / Nov-Jan), by
position, by line-size tercile, by label sample depth (n_games_into_label <= 4 / 5-9 / 10+), by close_source.
A cell where one season or one team supplies > 50 % of the effect is not a finding.
Cowork priors: DA-2a >= 1 cell clears |z| >= 2 on T1 -- 60 %; DA-2b the strongest T1 cell has the same sign on T2
2021-22 -- 55 %; DA-2c N2 stays |z| < 2 on every cell -- 85 %; DA-2d N1 kills every cell that cleared -- 90 %.
Nothing in this list is edited after the first residual is computed; additions are a new version with its own
sha and are reported as post-hoc.
