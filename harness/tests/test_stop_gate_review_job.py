#!/usr/bin/env python3
"""The Stop gate must not wall in the scheduled review job.

Contract 9.6 exempts the review job from the ledger, but the Stop hook enforces
every open ledger in the directory and cannot tell which process it is gating. On
2026-09-29 the job's first real run from the clone was blocked six times by an
interactive session's ledgers and took 75 minutes instead of about 13. See
an incident note in the source harness, fourth finding.

Both wrappers now export MESOSPHERE_REVIEW_JOB=1 to the claude they launch, and the
hook allows at once when it sees exactly that. The same unmet ledger must still
block every other process, including one that sets the marker to anything else.

Read-only with respect to the repo: temp directories, the hook and ledger.py.
"""
import json, os, pathlib, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
HOOK = pathlib.Path(os.environ.get("TEST_STOP_GATE") or
                    ROOT / "harness" / "adapters" / "claude-code" / "hooks" / "stop-gate.py")
ENGINE = ROOT / "harness" / "ledger.py"
PY = f'"{sys.executable}"'

LEDGER = f"""# Ledger: stop gate test
Lock: open
Audit: pending
Session: gate-test
Opened: 2026-01-01 00:00

## Contract

- [ ] G1 PROVE: a file that will not exist
      CHECK: {PY} -c "import os,sys; sys.exit(0 if os.path.exists('never.txt') else 1)"

## Asks
A1 "the unmet thing" -> G1

## Log
2026-01-01 00:00 opened
"""

fails = []


def expect(cond, label, out=""):
    print(("ok   " if cond else "FAIL ") + label)
    if not cond:
        print("     " + out.strip().replace("\n", "\n     ")[-400:])
        fails.append(label)


def gate(cwd, marker):
    # Never the owner's real project ledger, and never as a gate nested in a gate.
    env = {k: v for k, v in os.environ.items()
           if k not in ("MESOSPHERE_REVIEW_JOB", "CLAUDE_PROJECT_DIR", "LEDGER_STOP_GATE_ACTIVE")}
    env["LEDGER_ENGINE"] = str(ENGINE)
    if marker is not None:
        env["MESOSPHERE_REVIEW_JOB"] = marker
    r = subprocess.run([sys.executable, str(HOOK)], input=json.dumps({"cwd": str(cwd), "session_id": "no-such-session"}),
                       capture_output=True, text=True, timeout=60, env=env)
    return r.returncode, r.stdout or ""


with tempfile.TemporaryDirectory() as tmp:
    d = pathlib.Path(tmp)
    (d / ".ledger").mkdir()
    led = d / ".ledger" / "unmet.md"
    led.write_text(LEDGER, encoding="utf-8")
    subprocess.run([sys.executable, str(ENGINE), "--file", str(led), "declare"],
                   capture_output=True, text=True, timeout=60, cwd=d)

    rc, out = gate(d, None)
    expect('"decision": "block"' in out, "an unmet ledger blocks an ordinary session", out)

    rc, out = gate(d, "1")
    expect(rc == 0 and "block" not in out, "the review job's marker lets its turn end", out)

    rc, out = gate(d, "0")
    expect('"decision": "block"' in out, "any other marker value still blocks", out)

    rc, out = gate(d, "")
    expect('"decision": "block"' in out, "an empty marker still blocks", out)

if fails:
    print(f"\nREVIEW JOB EXEMPTION TEST FAILED ({len(fails)} of 4 cases)")
    sys.exit(1)
print("\nREVIEW JOB EXEMPTION TEST OK (4 cases)")
