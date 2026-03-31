# Golf Finish Engine — Data Audit

## predictions.parquet
- Rows: 32,000
- Columns: ['event_id', 'calendar_year', 'dg_id', 'player_name', 'fin_text', 'win_prob', 'top_5_prob', 'top_10_prob', 'top_20_prob', 'make_cut_prob', 'is_major']
- Year range: 2020-2025
- Year counts: {2020: 4299, 2021: 5331, 2022: 5873, 2023: 5590, 2024: 5612, 2025: 5295}
- Join keys: ['event_id', 'calendar_year', 'dg_id', 'player_name']
- Null rates: none

## tournament_results.parquet
- Rows: 40,369
- Columns: ['event_id', 'event_name', 'calendar_year', 'dg_id', 'player_name', 'fin_text', 'fin_num', 'made_cut', 'is_tie', 'is_major', 'total_score', 'total_rounds_played', 'total_sg_putt', 'total_sg_arg', 'total_sg_app', 'total_sg_ott', 'total_sg_t2g', 'total_sg_total', 'avg_sg_total', 'avg_sg_putt', 'avg_sg_app', 'avg_sg_arg', 'avg_sg_ott', 'top_5', 'top_10', 'top_20', 'winner', 'field_size']
- Year range: 2019-2025
- Year counts: {2019: 6067, 2020: 4822, 2021: 5912, 2022: 6008, 2023: 5900, 2024: 5918, 2025: 5742}
- Join keys: ['event_id', 'calendar_year', 'dg_id', 'player_name']
- Null rates: {'avg_sg_putt': '14.8%', 'avg_sg_app': '14.8%', 'avg_sg_arg': '14.8%', 'avg_sg_ott': '14.8%'}

## player_rounds.parquet
- Rows: 125,346
- Columns: ['event_id', 'event_name', 'calendar_year', 'dg_id', 'player_name', 'round_num', 'round_score', 'course_par', 'course_name', 'course_num', 'sg_putt', 'sg_arg', 'sg_app', 'sg_ott', 'sg_t2g', 'sg_total', 'driving_acc', 'driving_dist', 'gir', 'scrambling', 'prox_fw', 'prox_rgh', 'birdies', 'pars', 'bogies', 'tee_time', 'tee_time_hour', 'tee_wave', 'start_hole', 'fin_text', 'fin_num', 'made_cut', 'is_tie', 'is_major', 'sg_complete']
- Year range: 2019-2025
- Year counts: {2019: 19049, 2020: 14656, 2021: 18236, 2022: 18486, 2023: 18257, 2024: 18584, 2025: 18078}
- Join keys: ['event_id', 'calendar_year', 'dg_id', 'player_name']
- Null rates: {'sg_putt': '19.8%', 'sg_arg': '19.8%', 'sg_app': '19.8%', 'sg_ott': '19.8%', 'sg_t2g': '19.8%', 'driving_acc': '9.8%', 'driving_dist': '12.9%', 'gir': '11.5%', 'scrambling': '22.5%', 'prox_fw': '22.5%', 'prox_rgh': '24.8%', 'birdies': '0.3%', 'pars': '0.3%', 'bogies': '0.3%'}

## odds_outrights.parquet
- Rows: 339,944
- Columns: ['event_id', 'calendar_year', 'market', 'book', 'dg_id', 'player_name', 'open_odds', 'close_odds', 'open_time', 'close_time', 'bet_outcome_numeric', 'bet_outcome_text', 'open_implied', 'close_implied', 'dead_heat_factor', 'fair_close_prob', 'overround', 'raw_implied']
- Year range: 2019-2025
- Year counts: {2019: 22831, 2020: 38883, 2021: 64647, 2022: 62317, 2023: 48225, 2024: 51092, 2025: 51949}
- Join keys: ['event_id', 'calendar_year', 'dg_id', 'player_name']
- Null rates: none

## odds_matchups.parquet
- Rows: 124,276
- Columns: ['event_id', 'calendar_year', 'book', 'bet_type', 'p1_dg_id', 'p1_name', 'p1_open', 'p1_close', 'p1_outcome', 'p1_outcome_text', 'p2_dg_id', 'p2_name', 'p2_open', 'p2_close', 'p2_outcome', 'p2_outcome_text', 'open_time', 'close_time', 'voided', 'p3_dg_id', 'p3_name', 'p3_open', 'p3_close', 'p3_outcome', 'p3_outcome_text']
- Year range: 2019-2025
- Year counts: {2019: 6281, 2020: 14423, 2021: 23289, 2022: 20237, 2023: 18076, 2024: 21585, 2025: 20385}
- Join keys: ['event_id', 'calendar_year']
- Null rates: {'p3_dg_id': '76.5%', 'p3_name': '76.5%', 'p3_open': '76.5%', 'p3_close': '76.5%', 'p3_outcome': '76.5%', 'p3_outcome_text': '76.5%'}

## events.parquet
- Rows: 320
- Columns: ['event_id', 'calendar_year', 'event_name', 'has_rounds', 'has_odds', 'has_predictions', 'is_major', 'is_team_event']
- Year range: 2019-2025
- Year counts: {2019: 48, 2020: 38, 2021: 47, 2022: 46, 2023: 45, 2024: 49, 2025: 47}
- Join keys: ['event_id', 'calendar_year']
- Null rates: none

## player_lookup.parquet
- Rows: 1,786
- Columns: ['dg_id', 'player_name']
- Join keys: ['dg_id', 'player_name']
- Null rates: none

## Player Skill / DG Priors (predictions.parquet)
- dg_id: 1569 unique
- win_prob: mean=0.0078, std=0.0152, range=[0.0000, 0.4656]
- top_5_prob: mean=0.0392, std=0.0516, range=[0.0000, 0.8870]
- top_10_prob: mean=0.0784, std=0.0847, range=[0.0000, 0.9677]
- top_20_prob: mean=0.1569, std=0.1376, range=[0.0000, 1.0000]
- make_cut_prob: mean=0.5393, std=0.2136, range=[0.0000, 1.0000]

## Results (tournament_results.parquet)
- fin_num: mean=467.64, nulls=0
- fin_text: {'CUT': 17477, 'WD': 493, 'T13': 421, 'T21': 404, 'T16': 367}
- made_cut: mean=0.55, nulls=0
- top_5: mean=0.05, nulls=0
- top_10: mean=0.09, nulls=0
- top_20: mean=0.18, nulls=0
- winner: mean=0.01, nulls=0
- total_score: mean=219.15, nulls=0

## Round-Level Features (player_rounds.parquet)
- sg_total: mean=0.000, std=2.915, nulls=0 (0.0%)
- sg_ott: mean=-0.000, std=1.098, nulls=24859 (19.8%)
- sg_app: mean=0.000, std=1.646, nulls=24859 (19.8%)
- sg_arg: mean=-0.001, std=1.098, nulls=24859 (19.8%)
- sg_putt: mean=0.000, std=1.702, nulls=24859 (19.8%)
- round_score: 34 unique, nulls=0
- event_id: 67 unique, nulls=0
- calendar_year: 7 unique, nulls=0
- dg_id: 1786 unique, nulls=0
- round_num: 4 unique, nulls=0

## Odds Markets (odds_outrights.parquet)
- Markets: {'win': 96153, 'top_20': 78165, 'top_5': 75871, 'top_10': 70698, 'make_cut': 19057}
- Books: {'draftkings': 148339, 'fanduel': 148293, 'pinnacle': 43312}
- open_odds: present, nulls=0 (0.0%)
- close_odds: present, nulls=0 (0.0%)
- fair_close_prob: present, nulls=0 (0.0%)
- fair_open_prob: NOT PRESENT
- open_implied: present, nulls=0 (0.0%)
- close_implied: present, nulls=0 (0.0%)


## Feature Coverage
Total golfer-events: 32,000

| Feature | Coverage | Notes |
|---------|----------|-------|
| blowup_round_rate_last_50 | 92.3% | |
| calendar_year | 100.0% | |
| ceiling_round_rate_last_50 | 92.3% | |
| dg_id | 100.0% | |
| dg_make_cut_prob | 100.0% | |
| dg_top_10_prob | 100.0% | |
| dg_top_20_prob | 100.0% | |
| dg_top_5_prob | 100.0% | |
| dg_win_prob | 100.0% | |
| event_id | 100.0% | |
| event_name | 100.0% | |
| events_played_total | 100.0% | |
| field_size | 99.5% | |
| field_strength_proxy | 100.0% | |
| fin_num | 99.5% | |
| fin_text | 100.0% | |
| is_major_x | 100.0% | |
| is_major_y | 100.0% | |
| is_team_event | 100.0% | |
| made_cut_result | 99.5% | |
| missed_cut_rate_last_20 | 90.9% | |
| past_event_avg_finish | 48.1% | |
| past_event_made_cuts | 100.0% | |
| past_event_sg_total_avg | 64.5% | |
| past_event_starts | 100.0% | |
| player_name | 100.0% | |
| recent_cut_rate_last_10 | 90.9% | |
| recent_finish_mean_last_5 | 77.7% | |
| recent_sg_app_16_round | 85.9% | |
| recent_sg_app_8_round | 86.9% | |
| recent_sg_ott_16_round | 85.9% | |
| recent_sg_ott_8_round | 86.9% | |
| recent_sg_total_16_round | 93.3% | |
| recent_sg_total_8_round | 95.5% | |
| rolling_sg_app_50_round | 90.7% | |
| rolling_sg_arg_50_round | 90.7% | |
| rolling_sg_ott_50_round | 90.7% | |
| rolling_sg_putt_50_round | 90.7% | |
| rolling_sg_total_50_round | 92.3% | |
| rookie_or_sparse_flag | 100.0% | |
| round_score_std_last_16 | 93.3% | |
| round_score_std_last_50 | 92.3% | |
| rounds_available_long | 100.0% | |
| rounds_available_recent | 100.0% | |
| rounds_available_total | 100.0% | |
| top_10_result | 99.5% | |
| top_20_result | 99.5% | |
| top_5_result | 99.5% | |
| uncertainty_penalty_flag | 100.0% | |
| win_result | 99.5% | |
