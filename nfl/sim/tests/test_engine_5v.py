"""5V tests: INT tables required; play-log clock sums to regulation."""
import sys, os, shutil, tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def test_missing_int_ez_raises():
    """Engine must raise FileNotFoundError if int_ez.parquet is missing."""
    from nfl.sim import engine
    # Save and clear the cache
    old_cache = engine._CACHE.copy()
    engine._CACHE.clear()
    # Create a temp tables dir without int_ez.parquet
    with tempfile.TemporaryDirectory() as tmpdir:
        src = ROOT / "nfl" / "data" / "sim" / "tables"
        dst = Path(tmpdir)
        # Copy all files except int_ez.parquet
        for f in src.iterdir():
            if f.name != "int_ez.parquet" and f.is_file():
                shutil.copy2(f, dst / f.name)
        # Point engine at the temp dir
        old_dir = engine.TABLES_DIR
        engine.TABLES_DIR = dst
        try:
            with pytest.raises(FileNotFoundError, match="int_ez"):
                engine._load_tables()
        finally:
            engine.TABLES_DIR = old_dir
            engine._CACHE.clear()
            engine._CACHE.update(old_cache)
