#!/usr/bin/env python3
"""
N03/N14: Pull NCAAF news from ESPN for teams on the board.

Thin wrapper around shared/pipeline/pull_espn_news.py --sport ncaaf.
Kept so the board builder's import path works unchanged.
"""

import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
PULLER = ROOT / "shared" / "pipeline" / "pull_espn_news.py"


def main():
    cmd = [sys.executable, str(PULLER), "--sport", "ncaaf"]
    result = subprocess.run(cmd, cwd=str(ROOT))
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
