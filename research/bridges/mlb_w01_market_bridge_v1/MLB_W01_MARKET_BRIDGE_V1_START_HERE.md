# MLB W01 MARKET BRIDGE V1 — START HERE

## What This Object Is
A one-time market bridge extending MLB_RUNTIME_OBJECT_V1 with a single `closing_total` field (DraftKings full-game closing total). Exists only to support the W01B economic reality check.

## Where It Lives
```
/Users/jw115/mlb-model/research/bridges/mlb_w01_market_bridge_v1/mlb_w01_market_bridge_v1.parquet
```

## Shape
19,430 rows x 131 columns (runtime object 130 + 1 closing_total)

## Coverage
- closing_total null rate: 2.2% (436 rows missing — mostly early-2022 games)
- W01-relevant rows (opp_sp_ip + closing_total both non-null): 16,376
- W01B runs on near-full coverage, not a reduced subset

## What This Is NOT
- NOT a new default runtime object
- NOT a modification of MLB_RUNTIME_OBJECT_V1
- NOT a promotion of the odds source into the frozen package
- NOT authorization for general market-data use

## Read First
1. `MLB_W01_MARKET_BRIDGE_V1_REGISTRY.json`
2. `MLB_W01_MARKET_BRIDGE_V1_FIELD_DICTIONARY.csv`
3. Runtime object: `MLB_RUNTIME_OBJECT_V1_START_HERE.md`
