"""
IE-0 ITEM 1: Pull one season (2023) of each nfl_data_py source,
probe season availability 2016-2026, and record metadata.
Read-only on existing files. New parquets go to nfl/data/info/.
"""
import os, ssl, certifi
os.environ["SSL_CERT_FILE"] = certifi.where()

import nfl_data_py as nfl
import pandas as pd

OUT_DIR = os.path.join(os.path.dirname(__file__), "../../nfl/data/info")
os.makedirs(OUT_DIR, exist_ok=True)

SOURCES = {
    "ftn_charting": {
        "fn": lambda yrs: nfl.import_ftn_data(yrs),
        "probe_range": range(2016, 2027),
    },
    "ngs_passing": {
        "fn": lambda yrs: nfl.import_ngs_data("passing", yrs),
        "probe_range": range(2016, 2027),
    },
    "ngs_rushing": {
        "fn": lambda yrs: nfl.import_ngs_data("rushing", yrs),
        "probe_range": range(2016, 2027),
    },
    "ngs_receiving": {
        "fn": lambda yrs: nfl.import_ngs_data("receiving", yrs),
        "probe_range": range(2016, 2027),
    },
    "snap_counts": {
        "fn": lambda yrs: nfl.import_snap_counts(yrs),
        "probe_range": range(2016, 2027),
    },
    "pfr_weekly_pass": {
        "fn": lambda yrs: nfl.import_weekly_pfr("pass", yrs),
        "probe_range": range(2016, 2027),
    },
    "officials": {
        "fn": lambda yrs: nfl.import_officials(yrs),
        "probe_range": range(2016, 2027),
    },
    "injuries": {
        "fn": lambda yrs: nfl.import_injuries(yrs),
        "probe_range": range(2016, 2027),
    },
    "rosters_weekly": {
        "fn": lambda yrs: nfl.import_weekly_rosters(yrs),
        "probe_range": range(2016, 2027),
    },
    "depth_charts": {
        "fn": lambda yrs: nfl.import_depth_charts(yrs),
        "probe_range": range(2016, 2027),
    },
    "schedules": {
        "fn": lambda yrs: nfl.import_schedules(yrs),
        "probe_range": range(2016, 2027),
    },
}

results = []

for name, cfg in SOURCES.items():
    print(f"\n{'='*60}")
    print(f"SOURCE: {name}")
    print(f"{'='*60}")

    # 1. Pull 2023
    try:
        df = cfg["fn"]([2023])
        out_path = os.path.join(OUT_DIR, f"{name}_2023.parquet")
        df.to_parquet(out_path, index=False)
        rows = len(df)
        cols = df.columns.tolist()
        print(f"  2023: {rows} rows, {len(cols)} cols")
        print(f"  Columns: {cols}")
    except Exception as e:
        print(f"  2023 FAILED: {e}")
        rows = 0
        cols = []
        df = pd.DataFrame()

    # 2. Detect timestamp vs week key
    has_timestamp = False
    timestamp_col = None
    week_col = None
    for c in cols:
        cl = c.lower()
        if any(t in cl for t in ["timestamp", "datetime", "date_modified",
                                   "report_date", "date_pulled", "report_status_date"]):
            has_timestamp = True
            timestamp_col = c
        if cl in ("week", "game_week"):
            week_col = c

    if has_timestamp:
        pit_status = "TIMESTAMPED"
        pit_col = timestamp_col
    elif week_col:
        pit_status = "WEEK-KEYED"
        pit_col = week_col
    elif any(c in cols for c in ("game_id", "gameday", "game_date")):
        pit_status = "WEEK-KEYED"
        pit_col = next((c for c in cols if c in ("game_id", "gameday", "game_date")), None)
    else:
        pit_status = "UNKNOWN"
        pit_col = None

    # 3. Probe season availability
    available_seasons = []
    for yr in cfg["probe_range"]:
        if yr == 2023:
            if rows > 0:
                available_seasons.append(yr)
            continue
        try:
            test = cfg["fn"]([yr])
            if len(test) > 0:
                available_seasons.append(yr)
                print(f"  {yr}: {len(test)} rows")
            else:
                print(f"  {yr}: 0 rows")
        except Exception as e:
            err_str = str(e)[:80]
            print(f"  {yr}: FAILED ({err_str})")

    results.append({
        "source": name,
        "rows_2023": rows,
        "n_cols": len(cols),
        "key_columns": ", ".join(cols[:10]),
        "all_columns": ", ".join(cols),
        "seasons_available": str(available_seasons),
        "pit_status": pit_status,
        "pit_column": pit_col,
    })
    print(f"  PIT: {pit_status} ({pit_col})")
    print(f"  Seasons: {available_seasons}")

# Save summary
summary_df = pd.DataFrame(results)
summary_df.to_parquet(os.path.join(OUT_DIR, "source_inventory_summary.parquet"), index=False)
print("\n\nDONE — summary saved to nfl/data/info/source_inventory_summary.parquet")
for _, r in summary_df.iterrows():
    print(f"  {r['source']:20s} | {r['rows_2023']:6d} rows | PIT: {r['pit_status']:12s} | seasons: {r['seasons_available']}")
