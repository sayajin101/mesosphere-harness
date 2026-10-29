#!/usr/bin/env python3
"""Proves the ledger lock covers the ask lines, not just the gates.

Read-only with respect to the repo: everything happens in a temp directory, and
the only thing invoked is ledger.py itself. That matters because this file is a
ledger CHECK, and a CHECK runs once before the work exists (harness/LEDGER.md).

  python harness/tests/test_freeze_covers_asks.py
    -> "ok: asks are frozen", exit 0
    -> "FAIL: ...", exit 1

The hole this closes: freezing only gates let an agent delete an ask line so an
unmapped ask stopped blocking. That is silent scope narrowing by the back door.
Mappings must stay editable, because deciding which gate covers an ask is the work,
so this asserts both directions.
"""
import pathlib, subprocess, sys, tempfile

ENGINE = pathlib.Path(__file__).resolve().parents[1] / "ledger.py"

LEDGER = """# Ledger: freeze test
Lock: open
Session: freeze-test
Opened: 2026-01-01 00:00

## Contract

- [ ] G1 PROVE: a thing that is not yet true
      CHECK: python -c "import sys; sys.exit(1)"

## Asks
A1 "do the first thing" -> G1
A2 "do the second thing" -> none: out of scope for this test

## Log
2026-01-01 00:00 opened
"""

fails = []


def run(path, *args):
    res = subprocess.run([sys.executable, str(ENGINE), "--file", str(path), *args],
                         capture_output=True, text=True, timeout=60)
    return res.returncode, (res.stdout or "") + (res.stderr or "")


def lock_state(path, label):
    code, out = run(path, "--json", "status")
    for line in out.strip().splitlines():
        if line.startswith("{") and '"lock"' in line:
            import json
            return json.loads(line)["lock"]
    fails.append(f"{label}: could not read a JSON status (exit {code}): {out.strip()[:200]}")
    return "unknown"


with tempfile.TemporaryDirectory() as tmp:
    path = pathlib.Path(tmp) / "freeze.md"
    path.write_text(LEDGER, encoding="utf-8")

    code, out = run(path, "declare")
    if code != 0:
        fails.append(f"declare should have succeeded, exit {code}: {out.strip()[:300]}")
    elif lock_state(path, "after declare") != "intact":
        fails.append("the lock should be intact immediately after declare")

    # 1. Editing a MAPPING must stay legal: choosing which gate covers an ask is the work.
    original = path.read_text(encoding="utf-8")
    path.write_text(original.replace('A2 "do the second thing" -> none: out of scope for this test',
                                     'A2 "do the second thing" -> G1'), encoding="utf-8")
    if lock_state(path, "after remapping") != "intact":
        fails.append("remapping an ask broke the lock, but mappings must stay editable")

    # 2. Deleting an ask line must break the lock. This is the hole being closed.
    path.write_text(original, encoding="utf-8")
    without = "\n".join(l for l in original.split("\n")
                        if not l.startswith('A2 "do the second thing"'))
    path.write_text(without, encoding="utf-8")
    if lock_state(path, "after deleting an ask") != "broken":
        fails.append("deleting an ask line did NOT break the lock, so an unmapped ask "
                     "can still be made to disappear")

    # 3. Rewording an ask must break the lock too: quietly softening what was asked for
    #    is the same failure wearing different words.
    path.write_text(original.replace("do the second thing", "do a smaller thing"),
                    encoding="utf-8")
    if lock_state(path, "after rewording an ask") != "broken":
        fails.append("rewording an ask did NOT break the lock")

if fails:
    for f in fails:
        print(f"FAIL: {f}")
    sys.exit(1)
print("ok: asks are frozen (mapping stays editable, deletion and rewording break the lock)")
sys.exit(0)
