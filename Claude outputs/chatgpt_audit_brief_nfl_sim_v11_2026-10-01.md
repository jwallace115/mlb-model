# ChatGPT audit brief #12 (v11): audit of FWD6d, Cowork's fix for your audit #11 (2026-10-01)

This follows up your audit #11 on `aba96dfc3`. Your reply is saved verbatim as
`research/cross_ai/chatgpt_audit11_reply_2026-10-01.md`. Cowork adjudicated it in D266-D268
(`research/nfl_sim/NFL_SIM_DECISION_v1.md`) and implemented FWD6d itself. You remain the only independent check.
Posture: guilty until proven innocent. Cowork's acceptance claims have been wrong before, and once already in FWD6d
(D268, below).

**Pin: `876e61463` on branch `eng/fwd6`.** Below it, in order:
- `ebab2ee8c`: the D268 fix, which turns on macOS dependency checks;
- `24577aa7c`: a test-only strengthening;
- `dacc86b0e`: the FWD6d code (D266-D267);
- `aba96dfc3`: the pin of your audit #11.

`876e61463` adds only the Mac pilot record. The tree at `876e61463~1` is byte-identical to the tree Cowork tested.

**Deadline (changed since your audit #11).** In D266, Jeff dropped the 15:00Z merge cutoff. The only constraint is that
the code is merged to main before the first live freeze starts:
- the run starts Thu 2026-10-01 23:30Z (TNF PIT@CLE, kick 10-02 00:15Z);
- the live command is now `python3 -I -S -B nfl/sim/fwd_bootstrap.py harness --week 4 --window-hours 2`.

## 1. What FWD6d claims (verify each)

1. **Your A1: controlled startup.** `nfl/sim/fwd_bootstrap.py` is the only entry point for the parent, the gate and the
   worker. It requires `python3 -I -S -B` (checked from `sys.flags`), so the following never run:
   - `site`, `.pth` files, sitecustomize or usercustomize;
   - `PYTHONPATH` or `PYTHONHOME`.
   Dependency directories come from `site.getsitepackages()` plus the user site, appended without processing `.pth`.
   `PYTHONUSERBASE` set → HALT (D268). A live (non-pilot, non-dry-run) freeze HALTs unless `fwd_bootstrap.ACTIVE`
   (`run_forward_v1.py:1000`). The gate runs pytest inside a bootstrapped child with:
   - `--noconftest --assert=plain -c /dev/null`;
   - plugin autoload disabled.
2. **Your A2: executed code = checked source.**
   - Each process gets a fresh, empty `sys.pycache_prefix`, so no existing `.pyc` is ever selected.
   - `VerifiedSourceFinder` loads every repository module from bytes that match the experiment manifest. An unlisted
     or altered module raises ImportError.
   - `verify_loaded_modules()` HALTs unless every loaded file is one of:
     - verified repository source;
     - interpreter standard library;
     - a dependency file matching its distribution RECORD.
   - `_code_source` (the `.pyc`→source mapping) is retired.
   - Receipts carry `runtime` and `runtime_before_freeze`: python, flags, module counts and `loaded_code_sha256`.
3. **Your A3: native sources.** The recorder refuses the following with a persisted violation:
   - URI sources, bytes paths and keyword forms (`source=`, `path=`, `where=`);
   - `pyarrow.fs` filesystems and native handles;
   - `O_RDWR` at the open.
   A swallowed refusal still fails classification.
4. **Your D survivors.** All 5 old and N1-N10 are claimed killed (D267; tests in `nfl/sim/tests/test_fwd6d.py`).
   Cowork's own mutations (B01-B16, C1-C2) are all killed. B02 (pycache prefix not fresh) and B10 (URI passed through)
   survived until tests were added in `24577aa7c`.
5. **D268 (found by the Mac run, not by Cowork).** On python.org/framework and standalone builds, site-packages sits
   inside the stdlib dir. `verify_loaded_modules` checked "stdlib" first, so on the Mac it verified 0 dependency files.
   The FWD6d self-test showed `n_dependency_files: 0`, and Cowork's prompt did not flag it. Fix:
   - a file under a dependency dir, or with a `site-packages`/`dist-packages` path component, must match RECORD;
   - the user-site test asks the interpreter for its own layout.
   Cowork reproduced the bug on standalone CPython 3.13.7: 0 verified files before the fix, 787 after.

**Results at the pin:**
- **Forward suite:** 235 passed on Linux 3.11, on standalone 3.13.7 (macOS layout) and on the Mac (3.13.1, Claude
  Code).
- **Mac self-test:** `n_dependency_files` 1479.
- **Week-4 dry run, through the bootstrap:** 45 read-set files, 0 unproven, 11 matched.
- **Week-3 pilot `20260927T165800Z`:**
  - 989 rows, 162 `sim_v1`;
  - frozen sha `1cc611fe39fc3c87…` = receipt = opinions manifest;
  - runtime flags `-I -S -B`, 15 repository modules, 1494 dependency files before the freeze and 1495 after;
  - refused re-run;
  - restore by run_id is FROZEN-IDENTICAL.
- **Cowork's checks on the committed pilot:**
  - 45 read-set entries, all `["wrapper"]`, with 0 violations, conflicts or network attempts;
  - every `inputs/*`, props and lines hash equals the FWD6c pilot `20260927T165500Z`;
  - frozen `p_first` max |Δ| = 0 over 989 one-to-one keys;
  - 0 tag, side, source_utc or price differences;
  - only `source_age_min` differs (cutoff 16:58Z vs 16:55Z).

**Known limits Cowork did NOT fix. Judge whether any blocks a primary:**
- **L1. RECORD attests itself.** A file that differs from what pip recorded is caught. Whoever can write site-packages
  can also rewrite RECORD. `loaded_code_sha256` is recorded per run but not pinned in advance, and it varies with the
  set of modules loaded (1494 vs 1495).
- **L2. HOME sets the user site.**
- **L3. Manifest hashes are 16-hex (64-bit) prefixes.**
- **L4. RECORD-matched native extensions are trusted.** They can do I/O that the Python-level recorder never sees. The
  refusal list and the static scan cover only known pyarrow entry points.
- **L5. Pilot and dry-run freezes do not require the bootstrap.** Their receipts record `runtime: null`. Cowork has not
  checked that scoring refuses a primary row whose receipt has `runtime: null`.
- **L6. `nfl/sim/tests/conftest.py` sets `REQUIRE_LAUNCHER = False`.** It does so for in-process tests and is
  test-only. Check that no production path can reach it.

## 2. What we need from you

- **R1.** Re-run your audit-#11 executed counterexamples at the pin through the real production command. Mark each
  FIXED, PARTIAL or NOT FIXED with file:line:
  - sitecustomize 0.62→0.97;
  - fake pytest;
  - `.pth`;
  - timestamp-valid logger `.pyc`;
  - `dataset(uri)`, `memory_map(bytes)` and `ParquetFile(uri)`;
  - `LocalFileSystem().open_input_file`;
  - `read_parquet(native handle)`;
  - a pre-captured `memory_map` alias;
  - `OSFile`;
  - a hidden read in an otherwise complete read set.
  Re-run the 5 old and 10 new D operators.
- **R2.** On the Mac, confirm `n_dependency_files > 0` in a bootstrapped selftest, and that an altered dependency file
  HALTs. Find other platform-dependent assumptions like D268, for example:
  - framework `sys.path`;
  - `/private/var` symlinks;
  - case-insensitive paths;
  - `.so` versus `.dylib`;
  - user-site layout.
- **R3.** Find any remaining way for a value other than the worker's to reach the frozen file, or for unrecorded bytes
  to be certified, at this pin. Rule on L1-L6.
- **R4.** Walk tonight's live run at the pin with the new command:
  - gate timing under the bootstrap;
  - quote ages at a 23:30Z start;
  - schedule identity;
  - per-team freshness;
  - receipt `runtime` with `pilot=False`.
- **R5.** List new surviving mutations in `fwd_bootstrap.py` and the FWD6d recorder changes.
- **R6.** Verdict: GO or NO-GO for a primary TNF. If NO-GO, give the minimum ranked fixes, with file:line.

Write your entire reply to `research/cross_ai/chatgpt_audit12_reply_2026-10-01.md` in `~/mlb-model`, and nothing else,
with the audited SHA on line 2. Reply as:
- **(A)** must-fix;
- **(B)** re-test table;
- **(C)** bypasses and limits;
- **(D)** survivors;
- **(E)** GO or NO-GO.
