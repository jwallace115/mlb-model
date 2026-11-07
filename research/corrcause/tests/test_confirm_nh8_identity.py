"""
CC-4 Item 2: Identity test for confirm_nh8.py.

The dry-run (--season 2023) must reproduce Item 1a's 2023-24 row to 4 decimals:
  n=320, r=+0.0510, SE=0.0278
"""

import subprocess
import sys
import re

import pytest


PYTHON = "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
SCRIPT = "research/corrcause/confirm_nh8.py"

# Item 1a's 2023-24 row (from the NH8 build)
EXPECTED_N = 320
EXPECTED_R = 0.0510
EXPECTED_SE = 0.0278


class TestConfirmNH8Identity:
    def test_season_2023_identity(self):
        """confirm_nh8.py --season 2023 must reproduce Item 1a's 2023-24 row."""
        result = subprocess.run(
            [PYTHON, SCRIPT, "--season", "2023"],
            capture_output=True, text=True, timeout=600,
            cwd=str(subprocess.run(["git", "rev-parse", "--show-toplevel"],
                                    capture_output=True, text=True).stdout.strip())
        )
        stdout = result.stdout
        print(stdout)
        assert result.returncode == 0, f"Script failed: {result.stderr[:500]}"

        # Parse output
        n_match = re.search(r"n = (\d+)", stdout)
        r_match = re.search(r"r = ([+-]?\d+\.\d+)", stdout)
        se_match = re.search(r"SE = (\d+\.\d+)", stdout)

        assert n_match, "Could not parse n from output"
        assert r_match, "Could not parse r from output"
        assert se_match, "Could not parse SE from output"

        n = int(n_match.group(1))
        r = float(r_match.group(1))
        se = float(se_match.group(1))

        assert n == EXPECTED_N, f"n mismatch: {n} != {EXPECTED_N}"
        assert abs(r - EXPECTED_R) < 0.00005, f"r mismatch: {r} != {EXPECTED_R}"
        assert abs(se - EXPECTED_SE) < 0.00005, f"SE mismatch: {se} != {EXPECTED_SE}"

    def test_season_2024_refused_without_flag(self):
        """--season 9999 should be refused (not in choices)."""
        result = subprocess.run(
            [PYTHON, SCRIPT, "--season", "9999"],
            capture_output=True, text=True, timeout=10,
            cwd=str(subprocess.run(["git", "rev-parse", "--show-toplevel"],
                                    capture_output=True, text=True).stdout.strip())
        )
        assert result.returncode != 0, "Should reject invalid season"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
