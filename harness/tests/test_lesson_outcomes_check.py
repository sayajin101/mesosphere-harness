#!/usr/bin/env python3
"""The lesson tracker check must REFUSE, not merely exist.

harness/ENGINEERING.md rule 1: a check that has only ever passed cannot be told apart from one that cannot fail. So each
case below builds a tiny throwaway vault and runs the real verify.py inside it.
"""
import subprocess, sys, tempfile, pathlib

VERIFY = pathlib.Path(__file__).resolve().parents[2] / "harness" / "verify.py"
FM = "---\ntype: {t}\nstatus: draft\nscope: test\nconfidence: low\nupdated: 2026-09-28\n---\n\n"
HEAD = "| id | lesson | first raised | outcome | where | decided | record |\n| --- | --- | --- | --- | --- | --- | --- |\n"


def vault(d, rows=None, page_body="A lesson. Approved by the owner 2026-09-28.\n", tracker=True):
    d = pathlib.Path(d)
    (d / "heuristics").mkdir()
    (d / "episodic").mkdir()
    # Bytes, not write_text: the vault is LF only, and verify.py fails a CRLF note,
    # which write_text produces on Windows.
    (d / "heuristics" / "demo.md").write_bytes((FM.format(t="heuristic") + "# Demo\n\n" + page_body).encode())
    if tracker:
        body = HEAD + "".join(rows or [])
        (d / "episodic" / "lesson-outcomes.md").write_bytes((FM.format(t="episode") + "# Outcomes\n\n" + body).encode())


def run(d):
    r = subprocess.run([sys.executable, str(VERIFY), "--no-wrappers"], capture_output=True, text=True, cwd=d)
    return r.returncode, r.stdout + r.stderr


ADDED = "| L-demo | a lesson | digest | added | `heuristics/demo.md` | 2026-09-28 | note |\n"
failures = []


def expect(cond, label, out):
    print(("ok   " if cond else "FAIL ") + label)
    if not cond:
        print("     " + out.strip().replace("\n", "\n     ")[-600:])
        failures.append(label)


with tempfile.TemporaryDirectory() as d:
    vault(d, [ADDED])
    rc, out = run(d)
    expect(rc == 0, "a true added row passes", out)

with tempfile.TemporaryDirectory() as d:
    vault(d, [ADDED], page_body="A lesson with no marker.\n")
    rc, out = run(d)
    expect(rc != 0 and "approval markers" in out, "a false added row refuses", out)

with tempfile.TemporaryDirectory() as d:
    vault(d, ["| L-demo | a lesson | digest | added | `heuristics/missing.md` | 2026-09-28 | note |\n"])
    rc, out = run(d)
    expect(rc != 0 and "does not exist" in out, "an added row naming a missing page refuses", out)

with tempfile.TemporaryDirectory() as d:
    vault(d, tracker=False)
    rc, out = run(d)
    expect(rc != 0 and "not found" in out, "a missing tracker refuses", out)

with tempfile.TemporaryDirectory() as d:
    vault(d, [])
    rc, out = run(d)
    expect(rc != 0 and "no lesson rows" in out, "an empty tracker refuses", out)

with tempfile.TemporaryDirectory() as d:
    vault(d, ["| L-demo | a lesson | digest | maybe | | | note |\n"])
    rc, out = run(d)
    expect(rc != 0 and "is not one of" in out, "an unknown outcome refuses", out)

with tempfile.TemporaryDirectory() as d:
    vault(d, ["| L-other | another | digest | waiting | `heuristics/demo.md` | | |\n"])
    rc, out = run(d)
    expect(rc == 0 and "without a row" in out, "a marker with no row warns without failing", out)

if failures:
    print(f"\nOUTCOMES CHECK TEST FAILED: {len(failures)} case(s)")
    sys.exit(1)
print("\nOUTCOMES CHECK TEST OK (7 cases, including 5 deliberate refusals)")
