"""Stable deterministic seed from any hashable key.

Uses zlib.crc32 for cross-process reproducibility (Python's hash() is
salted and differs across processes since 3.3).
"""

import zlib


def stable_seed(key) -> int:
    """Return a deterministic uint31 seed from a hashable key (tuple, str, etc.)."""
    raw = repr(key).encode("utf-8")
    return zlib.crc32(raw) & 0x7FFFFFFF
