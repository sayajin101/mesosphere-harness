#!/usr/bin/env python3
"""The standing wrapper check must REFUSE, not merely exist.

harness/ENGINEERING.md rule 1: a mechanism whose job is to refuse something has
to be tested by making it actually refuse. A check that only ever passes is
indistinguishable from a check that cannot fail.

Stubs stand in for the real suites on purpose. The unit under test is
check_wrappers, not the suites themselves, and the real ones take about 106
seconds to run twice. The real suites are exercised separately, against the real
directory, by this ledger's G2.
"""
import subprocess, sys, tempfile, pathlib, os

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _vault import vault_root
ROOT = vault_root()
VERIFY = ROOT / "harness" / "verify.py"

def run(d):
    r = subprocess.run([sys.executable, str(VERIFY), "--wrappers", "--wrappers-dir", str(d)],
                       capture_output=True, text=True, cwd=ROOT)
    return r.returncode, r.stdout + r.stderr

# Each machine's verify.py runs its own OS's suites, so the stubs take that form:
# zsh on macOS, Windows PowerShell on win32. Elsewhere there is nothing to prove.
KIND = {"darwin": "sh", "win32": "ps1"}.get(sys.platform)
if KIND is None:
    print(f"WRAPPER GATE TEST SKIPPED: no wrapper suites exist for {sys.platform}")
    sys.exit(0)
SELFTEST, MUTATION = f"selftest.{KIND}", f"mutationtest.{KIND}"

def stub(d, name, code):
    p = pathlib.Path(d) / name.replace(".sh", f".{KIND}")
    p.write_text(f"#!/bin/zsh\nexit {code}\n" if KIND == "sh" else f"exit {code}\n")
    p.chmod(0o755)

failures = []
def expect(cond, label, detail=""):
    if cond:
        print(f"ok   {label}")
    else:
        print(f"FAIL {label}: {detail}")
        failures.append(label)

with tempfile.TemporaryDirectory() as d:
    # both green
    stub(d, "selftest.sh", 0); stub(d, "mutationtest.sh", 0)
    rc, out = run(d)
    expect(rc == 0, "green suites pass", f"rc={rc} out={out[-300:]}")

    # selftest red must fail the gate
    stub(d, "selftest.sh", 1)
    rc, out = run(d)
    expect(rc != 0 and SELFTEST in out, "red selftest refuses", f"rc={rc} out={out[-300:]}")

    # mutation test red must fail the gate too
    stub(d, "selftest.sh", 0); stub(d, "mutationtest.sh", 1)
    rc, out = run(d)
    expect(rc != 0 and MUTATION in out, "red mutation test refuses", f"rc={rc} out={out[-300:]}")

    # a missing suite is not a pass
    stub(d, "mutationtest.sh", 0)
    os.remove(pathlib.Path(d) / SELFTEST)
    rc, out = run(d)
    expect(rc != 0 and "missing" in out, "missing suite refuses", f"rc={rc} out={out[-300:]}")

# an unreadable directory is not a pass either
rc, out = run("/nonexistent/wrapper/dir")
expect(rc != 0 and "not found" in out, "absent directory refuses", f"rc={rc} out={out[-300:]}")

if failures:
    print(f"\nWRAPPER GATE TEST FAILED ({len(failures)} of 5)")
    sys.exit(1)
print(f"\nWRAPPER GATE TEST OK (5 checks, including 4 deliberate refusals, {KIND} suites on {sys.platform})")
