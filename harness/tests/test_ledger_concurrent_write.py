#!/usr/bin/env python3
"""A slow `run` must not erase what was written while it ran.

`run` used to load the ledger, execute every check, then save the copy it loaded.
On 2026-09-29 a twenty minute check left that window open, and an audit recorded
inside it vanished when the run saved, log line and all, with nothing to say so.
Found while running the harness (2026-10).

Here one check sleeps while an audit, a JUDGE gate's evidence and an abandon are
recorded. All three must survive, and the run's own pass must still land.

Read-only with respect to the repo: temp directories and ledger.py, nothing else.
"""
import os, pathlib, subprocess, sys, tempfile, time

ENGINE = pathlib.Path(os.environ.get("TEST_LEDGER_ENGINE") or
                      pathlib.Path(__file__).resolve().parents[1] / "ledger.py")
PY = f'"{sys.executable}"'
SLOW = f"{PY} -c \"import os,sys,time; time.sleep(6); sys.exit(0 if os.path.exists('done.txt') else 1)\""
NEVER = f"{PY} -c \"import os,sys; sys.exit(0 if os.path.exists('never.txt') else 1)\""

LEDGER = f"""# Ledger: concurrent write test
Lock: open
Audit: pending
Session: race-test
Opened: 2026-01-01 00:00

## Contract

- [ ] G1 PROVE: the slow check passes
      CHECK: {SLOW}
- [ ] G2 JUDGE: a person agrees
- [ ] G3 PROVE: something that will be surrendered
      CHECK: {NEVER}

## Asks
A1 "do the slow thing" -> G1
A2 "get agreement" -> G2
A3 "the doomed thing" -> G3

## Log
2026-01-01 00:00 opened
"""

fails = []


def cli(path, *args, cwd):
    return [sys.executable, str(ENGINE), "--file", str(path), *args]


def expect(cond, label, out=""):
    print(("ok   " if cond else "FAIL ") + label)
    if not cond:
        print("     " + out.strip().replace("\n", "\n     ")[-600:])
        fails.append(label)


with tempfile.TemporaryDirectory() as tmp:
    d = pathlib.Path(tmp)
    led = d / "led.md"
    led.write_text(LEDGER, encoding="utf-8")
    subprocess.run(cli(led, "declare", cwd=d), capture_output=True, text=True, timeout=120, cwd=d)
    (d / "done.txt").write_text("x")

    slow = subprocess.Popen(cli(led, "run", cwd=d), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, cwd=d)
    time.sleep(2)  # the run has loaded the ledger and is inside the slow check
    for args in (("audit", "subagent", "COVERED: written during the run"),
                 ("evidence", "G2", "agreed while the run was going"),
                 ("abandon", "G3", "surrendered while the run was going")):
        subprocess.run(cli(led, *args, cwd=d), capture_output=True, text=True, timeout=60, cwd=d)
    mid_run = slow.poll() is None
    out, _ = slow.communicate(timeout=120)
    text = led.read_text(encoding="utf-8")

    expect(mid_run, "the writes landed while the run was still executing", out)
    expect("Audit: subagent: COVERED: written during the run" in text,
           "an audit written during the run survives its save", text)
    expect("EVIDENCE: agreed while the run was going" in text and "- [x] G2" in text,
           "evidence written during the run survives its save", text)
    expect("ABANDON: surrendered while the run was going" in text,
           "an abandon written during the run survives its save", text)
    expect("- [x] G1" in text and "PASS G1" in out,
           "the run's own pass still lands", out + text)
    log = text.split("## Log")[-1]
    expect(all(s in log for s in ("run executed", "G2 evidence", "G3 ABANDONED")),
           "every log line survives, the run's and the concurrent ones", log)

if fails:
    print(f"\nCONCURRENT WRITE TEST FAILED ({len(fails)} of 6 cases)")
    sys.exit(1)
print("\nCONCURRENT WRITE TEST OK (6 cases)")
