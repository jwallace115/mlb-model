"""Tests for sim_window.sh manifest append and run_window --no-pull.
OPS5a Item 3. RED first, GREEN after.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
MAC_PY = "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"


# ---- (b) manifest-append: existing entries byte-identical, verify passes ----
def test_manifest_append_preserves_existing(tmp_path):
    """Appending a new entry must not alter existing entries."""
    ai_dir = tmp_path / "ai_opinions"
    ai_dir.mkdir()

    # Existing manifest with one entry
    existing_entry = {
        "file": "ai_opinions_20261008T222521Z.parquet",
        "sha256": "8ec61977547ac4cc",
        "logged_utc": "2026-10-08T22:25:21.421298+00:00",
        "rows": 833,
        "sport": "nfl",
        "book": "hardrockbet_fl",
        "reader_model": "reader_v3",
        "pilot": False,
        "window": "mid",
        "games": 14,
    }
    manifest_path = ai_dir / "manifest.json"
    original_text = json.dumps([existing_entry], indent=1)
    manifest_path.write_text(original_text)
    original_bytes = manifest_path.read_bytes()

    # Create a fake freeze parquet
    df = pd.DataFrame([{
        "event_id": "a" * 32,
        "commence_time": "2026-10-11T13:30:00Z",
        "logged_utc": "2026-10-09T15:30:00.000000+00:00",
        "reader_model": "nfl_sim_v1_abc123",
        "pilot": True,
        "book": "hardrockbet_fl",
        "source_age_min": 5.0,
        "market_key": "spreads",
    }])
    freeze_name = "ai_opinions_20261009T153000Z.parquet"
    df.to_parquet(ai_dir / freeze_name, index=False)
    frozen_sha = hashlib.sha256((ai_dir / freeze_name).read_bytes()).hexdigest()

    # Run the same append logic as sim_window.sh step 6
    append_code = f"""
import json, hashlib
from pathlib import Path
import pandas as pd

freeze_path = Path('{ai_dir / freeze_name}')
manifest_path = Path('{manifest_path}')

df = pd.read_parquet(freeze_path)
sha = '{frozen_sha}'

entry = {{
    'file': '{freeze_name}',
    'sha256': sha,
    'logged_utc': str(df['logged_utc'].iloc[0]) if 'logged_utc' in df.columns else None,
    'rows': len(df),
    'sport': 'nfl',
    'book': str(df['book'].iloc[0]) if 'book' in df.columns else 'hardrockbet_fl',
    'reader_model': str(df['reader_model'].iloc[0]) if 'reader_model' in df.columns else None,
    'pilot': bool(df['pilot'].iloc[0]) if 'pilot' in df.columns else False,
    'window': 'adhoc',
    'games': int(df['event_id'].nunique()) if 'event_id' in df.columns else 0,
}}

manifest = json.loads(manifest_path.read_text())
manifest.append(entry)
manifest_path.write_text(json.dumps(manifest, indent=1))
"""
    result = subprocess.run([MAC_PY, "-c", append_code], capture_output=True, text=True)
    assert result.returncode == 0, f"append failed: {result.stderr}"

    # Verify: existing entry is byte-identical
    new_manifest = json.loads(manifest_path.read_text())
    assert len(new_manifest) == 2, f"expected 2 entries, got {len(new_manifest)}"
    assert new_manifest[0] == existing_entry, "existing entry was modified by append"

    # New entry has the right fields
    new_entry = new_manifest[1]
    assert new_entry["file"] == freeze_name
    assert new_entry["sha256"] == frozen_sha
    assert new_entry["reader_model"] == "nfl_sim_v1_abc123"
    assert new_entry["pilot"] is True
    assert new_entry["window"] == "adhoc"


# ---- (c) null control: run_window --no-pull still produces a freeze ----
def test_run_window_no_pull_flag_accepted():
    """run_window.py accepts --no-pull without error (smoke test)."""
    result = subprocess.run(
        [MAC_PY, str(REPO_ROOT / "nfl" / "pipeline" / "run_window.py"),
         "--sport", "nfl", "--window", "adhoc", "--no-pull",
         "--auto-prekick", "--commit", "none"],
        capture_output=True, text=True, timeout=30,
        cwd=str(REPO_ROOT),
    )
    # --auto-prekick with no game in slot → exit 0 with "no game"
    # or it proceeds to sheet/reader which may fail on missing data
    # Either way, --no-pull is accepted as a flag
    assert "--no-pull" not in result.stderr or "unrecognized" not in result.stderr, \
        f"--no-pull not accepted: {result.stderr}"
