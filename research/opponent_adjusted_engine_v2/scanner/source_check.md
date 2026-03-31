# Source Check — V2 Signal Scanner

Input: research/opponent_adjusted_engine_v2/signal_scanner_input.parquet
Games: 4855 (2024: 2427, 2025: 2428)
Non-push: 4666
V1 under signals: 929

All required fields present: game_id, game_date, season, closing_total,
market_residual, went_under, is_push, p_under, all 7 V2 signals.

V1 trigger: p_under > 0.57 (same as prior research)
