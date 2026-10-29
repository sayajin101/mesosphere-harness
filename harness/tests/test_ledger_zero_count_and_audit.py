#!/usr/bin/env python3
"""Proves the three fixes for zero count gates that could never pass (found 2026-09-02).

1. An EXPECT anchored with $ matches a zero count, although the engine joins stdout and
   stderr with a newline, so a clean `0` arrives as "0\\n\\n".
2. A gate that uses grep -c with no EXPECT is refused at declare, because grep exits 1
   on a zero count and such a gate could never pass.
3. close refuses only an audit that actually found gaps, not one that merely mentions
   the word, and re-declaring a contract resets an audit that judged the old one.

Read-only with respect to the repo: temp directories and ledger.py, nothing else.
"""
import pathlib, subprocess, sys, tempfile

ENGINE = pathlib.Path(__file__).resolve().parents[1] / "ledger.py"

HEAD = """# Ledger: zero count test
Lock: open
Audit: pending
Session: zero-count-test
Opened: 2026-01-01 00:00

## Contract

"""
TAIL = """
## Asks
A1 "count must reach zero" -> G1

## Log
2026-01-01 00:00 opened
"""
ZERO_GATE = """- [ ] G1 PROVE: no marker lines remain
      CHECK: grep -c zzz f.txt || true
      EXPECT: /^0$/
"""
BARE_GATE = """- [ ] G1 PROVE: no marker lines remain
      CHECK: grep -c zzz f.txt
"""

fails = []


def run(path, *args, cwd):
    r = subprocess.run([sys.executable, str(ENGINE), "--file", str(path), *args],
                       capture_output=True, text=True, timeout=60, cwd=cwd)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def expect(cond, label, out=""):
    print(("ok   " if cond else "FAIL ") + label)
    if not cond:
        print("     " + out.strip().replace("\n", "\n     ")[-500:])
        fails.append(label)


def fresh(tmp, gate):
    d = pathlib.Path(tmp)
    (d / "f.txt").write_text("zzz\n")
    path = d / "led.md"
    path.write_text(HEAD + gate + TAIL)
    return d, path


# 1. an anchored zero EXPECT can pass
with tempfile.TemporaryDirectory() as tmp:
    d, path = fresh(tmp, ZERO_GATE)
    code, out = run(path, "declare", cwd=tmp)
    expect(code == 0 and "baseline red" in out, "a zero count gate declares red while the marker exists", out)
    (d / "f.txt").write_text("clean\n")
    code, out = run(path, "run", cwd=tmp)
    expect("PASS G1" in out, "/^0$/ matches a zero count once the marker is gone", out)

# 2. a bare grep -c with no EXPECT is refused
with tempfile.TemporaryDirectory() as tmp:
    d, path = fresh(tmp, BARE_GATE)
    code, out = run(path, "declare", cwd=tmp)
    expect(code != 0 and "grep -c" in out, "a bare grep -c gate is refused at declare", out)

# 3a. an audit that mentions gaps but found none does not block close
with tempfile.TemporaryDirectory() as tmp:
    d, path = fresh(tmp, ZERO_GATE)
    run(path, "declare", cwd=tmp)
    (d / "f.txt").write_text("clean\n")
    run(path, "run", cwd=tmp)
    run(path, "audit", "subagent", "COVERED: no gaps, every ask covered", cwd=tmp)
    code, out = run(path, "close", cwd=tmp)
    expect(code == 0 and "closed" in out, "a 'no gaps' verdict lets a met ledger close", out)

# 3b. an audit that found gaps still blocks close
with tempfile.TemporaryDirectory() as tmp:
    d, path = fresh(tmp, ZERO_GATE)
    run(path, "declare", cwd=tmp)
    (d / "f.txt").write_text("clean\n")
    run(path, "run", cwd=tmp)
    run(path, "audit", "subagent", "VERDICT: GAPS FOUND, A1 is not covered", cwd=tmp)
    code, out = run(path, "close", cwd=tmp)
    expect(code != 0 and "gaps" in out.lower(), "a GAPS FOUND verdict still refuses close", out)

# 3c. re-declaring the contract resets an audit of the old one
with tempfile.TemporaryDirectory() as tmp:
    d, path = fresh(tmp, ZERO_GATE)
    run(path, "declare", cwd=tmp)
    run(path, "audit", "subagent", "VERDICT: GAPS FOUND, A1", cwd=tmp)
    code, out = run(path, "--force", "declare", cwd=tmp)
    text = path.read_text()
    expect("Audit: pending" in text and "audit reset" in text,
           "declare --force resets an audit recorded against the old contract", out + text[-300:])

# 4. a refused re-declare must not touch the frozen contract of a locked ledger
with tempfile.TemporaryDirectory() as tmp:
    d, path = fresh(tmp, ZERO_GATE)
    run(path, "declare", cwd=tmp)
    (d / "f.txt").write_text("clean\n")
    run(path, "run", cwd=tmp)
    before = path.read_text()
    code, out = run(path, "--force", "declare", cwd=tmp)  # G1 now passes, so it is refused as vacuous
    after = path.read_text()
    st_code, st = run(path, "status", cwd=tmp)
    same = [l for l in before.split("\n") if "BASELINE" in l] == [l for l in after.split("\n") if "BASELINE" in l]
    expect(code != 0 and "lock intact" in st and same, "a refused declare leaves the lock intact", out + st)

if fails:
    print(f"\nZERO COUNT AND AUDIT TEST FAILED: {len(fails)} case(s)")
    sys.exit(1)
print("\nZERO COUNT AND AUDIT TEST OK (7 cases)")
