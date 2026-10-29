#!/usr/bin/env python3
"""A locked ledger can be amended, and only through the engine.

Until 2026-09-29 the lock guard named `declare --force` as the way to amend a
contract, and made it unreachable: declare re-reads gates from the ledger file,
and the guard denies every write to a locked ledger. See
an incident note in the source harness.

The fix, proven here without a single direct write to a declared ledger:
  declare --force --gates-file F   appends F's gates, baselines only those, relocks, logs
  map <ask> "<target>"             remaps an ask, since mappings are free by design
and the refusals that keep that path honest.

Read-only with respect to the repo: temp directories and ledger.py, nothing else.
"""
import os, pathlib, subprocess, sys, tempfile

ENGINE = pathlib.Path(os.environ.get("TEST_LEDGER_ENGINE") or
                      pathlib.Path(__file__).resolve().parents[1] / "ledger.py")
PY = f'"{sys.executable}"'


def exists_check(name):
    return f"{PY} -c \"import os,sys; sys.exit(0 if os.path.exists('{name}') else 1)\""


LEDGER = f"""# Ledger: amend test
Lock: open
Audit: pending
Session: amend-test
Opened: 2026-01-01 00:00

## Contract

- [ ] G1 PROVE: the first file exists
      CHECK: {exists_check('one.txt')}

## Asks
A1 "make the first file" -> G1
A2 "make the second file" -> none: not yet gated

## Log
2026-01-01 00:00 opened
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


def gate_block(gid, name):
    return f"- [ ] {gid} PROVE: the file {name} exists\n      CHECK: {exists_check(name)}\n"


def baseline_of(text, gid):
    lines = text.split("\n")
    start = next((i for i, l in enumerate(lines) if f"] {gid} " in l), None)
    if start is None:
        return None
    return next((l for l in lines[start + 1:start + 8] if "BASELINE:" in l), None)


with tempfile.TemporaryDirectory() as tmp:
    d = pathlib.Path(tmp)
    led = d / ".ledger" / "led.md"
    led.parent.mkdir()
    led.write_text(LEDGER, encoding="utf-8")
    rc, out = run(led, "declare", cwd=d)
    (d / "one.txt").write_text("x")
    run(led, "run", cwd=d)
    before = led.read_text(encoding="utf-8")
    g1_baseline = baseline_of(before, "G1")

    # The amendment. G1 is met now, so re-running its baseline would pass and be
    # refused as vacuous: an amend must baseline only the gates it adds.
    gf = d / "more-gates.md"
    gf.write_text(gate_block("G2", "two.txt"), encoding="utf-8")
    rc, out = run(led, "--force", "declare", "--gates-file", str(gf), cwd=d)
    after = led.read_text(encoding="utf-8")
    rc_status, st = run(led, "status", cwd=d)
    expect(rc == 0 and "] G2 PROVE" in after and "lock intact" in st,
           "declare --force --gates-file adds a gate and relocks", out + st)
    expect(baseline_of(after, "G2") is not None and "fail at" in (baseline_of(after, "G2") or ""),
           "the new gate gets its own red baseline", after)
    expect(baseline_of(after, "G1") == g1_baseline and "- [x] G1" in after,
           "the old gate keeps its baseline and its tick", after)
    expect("amend" in after.split("## Log")[-1].lower() and "G2" in after.split("## Log")[-1],
           "the amendment is in the log", after)

    # map: an ask moves onto the new gate, lock untouched.
    rc, out = run(led, "map", "A2", "G2", cwd=d)
    after_map = led.read_text(encoding="utf-8")
    rc_s, st = run(led, "status", cwd=d)
    # map answers with the ledger's status like evidence does, so 1 means gates are
    # still unmet, not that the map failed; a usage refusal is 2.
    expect(rc in (0, 1) and 'A2 "make the second file" -> G2' in after_map and "lock intact" in st,
           "map remaps an ask and leaves the lock intact", out + st)

    # Refusals. Each must leave the ledger byte for byte as it was.
    snapshot = led.read_text(encoding="utf-8")

    rc, out = run(led, "map", "A9", "G2", cwd=d)
    expect(rc != 0 and led.read_text(encoding="utf-8") == snapshot, "map refuses an unknown ask", out)

    rc, out = run(led, "map", "A1", "G7", cwd=d)
    expect(rc != 0 and led.read_text(encoding="utf-8") == snapshot, "map refuses a gate that does not exist", out)

    gf.write_text(gate_block("G1", "three.txt"), encoding="utf-8")
    rc, out = run(led, "--force", "declare", "--gates-file", str(gf), cwd=d)
    expect(rc != 0 and led.read_text(encoding="utf-8") == snapshot, "an amend reusing a gate id is refused", out)

    (d / "four.txt").write_text("x")
    gf.write_text(gate_block("G3", "four.txt"), encoding="utf-8")
    rc, out = run(led, "--force", "declare", "--gates-file", str(gf), cwd=d)
    expect(rc != 0 and led.read_text(encoding="utf-8") == snapshot,
           "an amend whose new PROVE gate already passes is refused", out)

    inside = led.parent / "sneaky.md"
    inside.write_text(gate_block("G3", "five.txt"), encoding="utf-8")
    rc, out = run(led, "--force", "declare", "--gates-file", str(inside), cwd=d)
    expect(rc != 0 and led.read_text(encoding="utf-8") == snapshot,
           "a gates file inside the ledger directory is refused", out)

    gf.write_text(gate_block("G3", "five.txt"), encoding="utf-8")
    rc, out = run(led, "declare", "--gates-file", str(gf), cwd=d)
    expect(rc != 0 and led.read_text(encoding="utf-8") == snapshot,
           "an amend without --force is refused", out)

if fails:
    print(f"\nAMEND TEST FAILED ({len(fails)} of 11 cases)")
    sys.exit(1)
print("\nAMEND TEST OK (11 cases)")
