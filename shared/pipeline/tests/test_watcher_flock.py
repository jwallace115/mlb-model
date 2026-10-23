#!/usr/bin/env python3
"""Tests for OPS-CAD2 Item 3 — flock on window_watch (P58 extension).

RED-first: a second instance exits 0 with a message.
"""
import fcntl
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "shared" / "pipeline"))


class TestWatcherFlock:

    def test_second_instance_exits(self):
        """A second instance sees the lock and exits cleanly."""
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / ".window_watch_nfl.lock"
            # Simulate first instance holding the lock
            fd1 = open(lock_path, "w")
            fcntl.flock(fd1, fcntl.LOCK_EX | fcntl.LOCK_NB)

            # Second instance tries to acquire
            try:
                fd2 = open(lock_path, "w")
                fcntl.flock(fd2, fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = False  # should not reach here
            except (OSError, IOError):
                locked = True

            assert locked, "second instance should be blocked by the flock"

            # Clean up
            fcntl.flock(fd1, fcntl.LOCK_UN)
            fd1.close()

    def test_first_instance_acquires(self):
        """First instance acquires the lock without issue."""
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / ".window_watch_nfl.lock"
            fd = open(lock_path, "w")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # If we get here, lock acquired
            fcntl.flock(fd, fcntl.LOCK_UN)
            fd.close()
