#!/usr/bin/env python3
"""Pre-deploy validation — runs before every deploy.sh push."""
import ast
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)

PASS = True
warnings = []

STDLIB = {
    "os","sys","json","datetime","pathlib","re","math","random","collections",
    "itertools","functools","hashlib","time","urllib","http","io","csv","copy",
    "typing","abc","dataclasses","zoneinfo","calendar","statistics","traceback",
    "logging","threading","subprocess","shutil","tempfile","glob","ast",
    "contextlib","operator","struct","base64","uuid","enum","warnings",
    "inspect","importlib","pickle","string","textwrap","numbers","decimal",
    "fractions","heapq","bisect","array","weakref","types","pprint",
    "reprlib","errno","signal","mmap","codecs","unicodedata","locale",
    "gettext","argparse","optparse","configparser","fileinput","stat",
    "fnmatch","linecache","tokenize","pdb","profile","timeit","trace",
    "gc","dis","code","codeop","compileall","py_compile","zipimport",
    "pkgutil","builtins","__future__","atexit","socket","ssl","select",
    "selectors","asyncio","concurrent","multiprocessing","queue","sched",
    "html","xml","email","mailbox","mimetypes","binascii","quopri",
    "uu","xmlrpc","ipaddress","ftplib","poplib","imaplib","smtplib",
    "telnetlib","socketserver","http","xmlrpc","urllib","webbrowser",
    "cgi","wsgiref","posixpath","ntpath","genericpath","posix",
}

def p(msg, ok=True, warn=False):
    global PASS
    if ok and not warn:
        print(f"  \u2713 {msg}")
    elif warn:
        print(f"  \u26a0 WARNING: {msg}")
        warnings.append(msg)
    else:
        print(f"  \u2717 FAIL: {msg}")
        PASS = False


print("=" * 50)
print("PRE-DEPLOY VALIDATION")
print("=" * 50)

# A. Dashboard compile
try:
    with open("dashboard.py") as f:
        source = f.read()
    ast.parse(source)
    p("dashboard.py compiles clean")
except SyntaxError as e:
    p(f"dashboard.py syntax error line {e.lineno}: {e.msg}", ok=False)

# B. Import check
try:
    tree = ast.parse(source)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".")[0])

    reqs_text = open("requirements.txt").read().lower()
    # Extract package names from requirements
    req_pkgs = set()
    for line in reqs_text.split("\n"):
        line = line.strip()
        if line and not line.startswith("#"):
            pkg = re.split(r"[><=!~\[]", line)[0].strip().replace("-", "_")
            req_pkgs.add(pkg)

    # Known aliases: package name != import name
    aliases = {"beautifulsoup4": "bs4", "python_dateutil": "dateutil",
               "python_dotenv": "dotenv", "scikit_learn": "sklearn",
               "pyarrow": "pyarrow"}
    import_to_req = {v: k for k, v in aliases.items()}
    req_import_names = set()
    for rp in req_pkgs:
        req_import_names.add(rp)
        if rp in aliases:
            req_import_names.add(aliases[rp])

    missing = []
    for imp in imports:
        if imp in STDLIB:
            continue
        if imp in req_import_names:
            continue
        # Local modules
        if os.path.exists(imp) or os.path.exists(f"{imp}.py"):
            continue
        missing.append(imp)

    if missing:
        for m in missing:
            p(f"import '{m}' not in requirements.txt or stdlib", ok=False)
    else:
        p("all imports in requirements.txt or stdlib")
except Exception as e:
    p(f"import check error: {e}", warn=True)

# C. Hardcoded paths
try:
    for i, line in enumerate(source.split("\n"), 1):
        if "/Users/jw115/" in line and not line.strip().startswith("#"):
            p(f"hardcoded path line {i} (non-blocking)", warn=True)
        if "C:\\" in line and not line.strip().startswith("#"):
            p(f"Windows path line {i} (non-blocking)", warn=True)
except Exception:
    pass

# D. Signal files
sig_files = [
    "mlb_sim/logs/signals_2026.json",
    "mlb_sim/logs/f5_signals_2026.json",
    "mlb_sim/logs/f5_runline_2026.json",
    "nba/data/nba_signal_log.parquet",
]
all_present = True
for sf in sig_files:
    if not os.path.exists(sf):
        p(f"signal file missing: {sf}", warn=True)
        all_present = False
if all_present:
    p("signal files present")

# E. Required packages
required = ["streamlit", "pandas", "numpy", "requests", "pyarrow"]
for pkg in required:
    norm = pkg.replace("-", "_")
    if norm not in req_pkgs and pkg not in req_pkgs:
        p(f"MISSING from requirements.txt: {pkg}", ok=False)
if PASS:
    p("requirements.txt complete")

# F. JSON validity
try:
    json_dir = ROOT / "mlb_sim" / "logs"
    bad = []
    for fn in json_dir.glob("*.json"):
        try:
            json.load(open(fn))
        except Exception as e:
            bad.append(f"{fn.name}: {e}")
    if bad:
        for b in bad:
            p(f"corrupt JSON: {b}", ok=False)
    else:
        p("JSON files valid")
except Exception as e:
    p(f"JSON check error: {e}", warn=True)

# G. Parquet validity
try:
    import pandas as pd
    for pf in ["nba/data/nba_signal_log.parquet"]:
        if os.path.exists(pf):
            pd.read_parquet(pf)
    p("parquet files valid")
except Exception as e:
    p(f"corrupt parquet: {e}", ok=False)

# Summary
print()
if PASS:
    print(f"RESULT: PASS \u2014 safe to deploy")
    if warnings:
        print(f"  ({len(warnings)} warnings, non-blocking)")
else:
    print(f"RESULT: FAIL \u2014 fix errors before deploying")

print("=" * 50)
sys.exit(0 if PASS else 1)
