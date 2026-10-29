#!/usr/bin/env python3
"""Proves a declared ledger cannot be closed, and does not report itself clean,
until a coverage audit has been recorded by a party that did not do the work.

Read-only with respect to the repo: a temp directory and ledger.py, nothing else.

  python harness/tests/test_audit_required.py
    -> "ok: audit is required", exit 0
    -> "FAIL: ...", exit 1
"""
import json, pathlib, subprocess, sys, tempfile

ENGINE = pathlib.Path(__file__).resolve().parents[1] / "ledger.py"
PY = pathlib.Path(sys.executable).as_posix()  # the interpreter running this test: `python` is not on every PATH (not on the Mac)

LEDGER = """# Ledger: audit test
Lock: open
Audit: pending
Session: audit-test
Opened: 2026-01-01 00:00

## Contract

- [ ] G1 PROVE: a thing that becomes true when a marker file appears
      CHECK: python -c "import pathlib,sys; sys.exit(0 if pathlib.Path('done.txt').exists() else 1)"

## Asks
A1 "do the thing" -> G1

## Log
2026-01-01 00:00 opened
"""

LEDGER = LEDGER.replace("CHECK: python -c", f'CHECK: "{PY}" -c')

fails = []


def run(path, *args, cwd=None):
    res = subprocess.run([sys.executable, str(ENGINE), "--file", str(path), *args],
                         capture_output=True, text=True, timeout=60, cwd=cwd)
    return res.returncode, (res.stdout or "") + (res.stderr or "")


def status(path, cwd):
    code, out = run(path, "--json", "status", cwd=cwd)
    for line in out.strip().splitlines():
        if line.startswith("{"):
            return code, json.loads(line)
    return code, {}


with tempfile.TemporaryDirectory() as tmp:
    d = pathlib.Path(tmp)
    path = d / "audit.md"
    path.write_text(LEDGER, encoding="utf-8")

    # An undeclared ledger owes no audit: nothing is committed to before the lock.
    _, st = status(path, tmp)
    if st.get("audit") != "n/a":
        fails.append(f"an open ledger should owe no audit, got {st.get('audit')!r}")

    code, out = run(path, "declare", cwd=tmp)
    if code != 0:
        fails.append(f"declare failed, exit {code}: {out.strip()[:200]}")

    # Declared and unaudited: the audit is pending.
    _, st = status(path, tmp)
    if st.get("audit") != "pending":
        fails.append(f"a declared ledger should owe an audit, got {st.get('audit')!r}")

    # Do the work so every gate is met. The ledger must STILL not report clean.
    (d / "done.txt").write_text("done", encoding="utf-8")
    run(path, "run", cwd=tmp)
    code, st = status(path, tmp)
    if st.get("unmet"):
        fails.append(f"the gate should be met after the work: {st.get('unmet')}")
    if code == 0:
        fails.append("status reported clean with every gate met but no audit recorded, "
                     "which is the whole failure this exists to prevent")

    # And close must refuse.
    code, out = run(path, "close", cwd=tmp)
    if code == 0:
        fails.append("close succeeded without an audit")
    if "AUDIT PENDING" not in out:
        fails.append(f"close did not say why it refused: {out.strip()[:200]}")

    # A bad --by value is refused, so the record always names a real party.
    code, out = run(path, "audit", "itself", "all covered", cwd=tmp)
    if code == 0:
        fails.append("audit accepted a party that is not subagent or human")

    # Recorded by a legitimate party: now it closes.
    code, out = run(path, "audit", "subagent", "COVERED: all asks covered by G1", cwd=tmp)
    if code != 0:
        fails.append(f"recording a valid audit failed: {out.strip()[:200]}")
    code, st = status(path, tmp)
    if st.get("audit") != "recorded" or code != 0:
        fails.append(f"after an audit the ledger should be clean, got {st}")
    code, out = run(path, "close", cwd=tmp)
    if code != 0:
        fails.append(f"close still refused after an audit: {out.strip()[:200]}")

if fails:
    for f in fails:
        print(f"FAIL: {f}")
    sys.exit(1)
print("ok: audit is required (pending blocks status and close, only a named party may record it)")
sys.exit(0)
