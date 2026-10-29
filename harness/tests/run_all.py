#!/usr/bin/env python3
"""Run every harness test script and report one line the ledger can match.

Each test in this directory is a plain script: exit 0 means it passed. No test
framework is needed, so the suite runs anywhere Python 3 does.

  python harness/tests/run_all.py
    -> "ALL 15 PASSED", exit 0
    -> "FAILED: 2 of 15 (test_x.py, test_y.py)", exit 1
"""
import pathlib, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
tests = sorted(p for p in HERE.glob("test_*.py"))
failed = []
for t in tests:
    r = subprocess.run([sys.executable, str(t)], cwd=HERE.parents[1],
                       capture_output=True, text=True, timeout=600)
    status = "ok  " if r.returncode == 0 else "FAIL"
    print(f"{status} {t.name}")
    if r.returncode != 0:
        failed.append(t.name)
        print("     " + (r.stdout + r.stderr).strip().replace("\n", "\n     ")[-1500:])

if not tests:
    print("FAILED: no tests found")
    sys.exit(1)
if failed:
    print(f"FAILED: {len(failed)} of {len(tests)} ({', '.join(failed)})")
    sys.exit(1)
print(f"ALL {len(tests)} PASSED")
