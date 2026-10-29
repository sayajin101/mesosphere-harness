#!/usr/bin/env python3
"""Proves declare refuses a gate that an escaping layer mangled on its way in.

On 2026-10-27 five gates were written through a Python string that was not raw, and
every one was red at declaration for the wrong reason. The broken cases below are
those gates as they landed in the file, byte for byte, trimmed to the lines the lint
reads. Each must be refused at declare and the ledger left unlocked. The sound cases
use the same features done right (a regex with escaped backslashes, quotes inside
quotes, an apostrophe under cmd) and must not be refused. See
an incident note in the source harness.

Read-only with respect to the repo: temp directories and ledger.py, nothing else.
"""
import pathlib, subprocess, sys, tempfile

HERE = pathlib.Path(__file__).resolve().parents[1]
ENGINE = HERE / "ledger.py"
sys.path.insert(0, str(HERE))
import ledger  # noqa: E402

HEAD = """# Ledger: escape lint test
Lock: open
Audit: pending
Session: escape-lint-test
Opened: 2026-01-01 00:00

## Contract

"""
TAIL = """
## Asks
A1 "write the gate correctly" -> G1

## Log
2026-01-01 00:00 opened
"""

# Each broken case: (label, gate text exactly as it landed, a fragment the refusal must name).
BROKEN = [
    ("control character from a collapsed \\1 (G3)",
     "- [ ] G1 PROVE: the mutation test passes\n"
     "      CHECK: powershell.exe -NoProfile -ExecutionPolicy Bypass -File harness/review-job/windows/mutationtest.ps1 | tail -1\n"
     "      EXPECT: /^MUTATION TEST OK \\((1[7-9]|[2-9]\\d) of \x01 mutants killed\\)/\n"
     "      SHELL: bash\n",
     "control character"),
    ("EXPECT split across two lines by a real newline (G4)",
     "- [ ] G1 PROVE: run-review.ps1 carries no claude flags\n"
     "      CHECK: grep -cE 'acceptEdits' run-review.ps1; grep -cE 'acceptEdits' review-job.ps1\n"
     "      EXPECT: /^0\n"
     "1$/\n"
     "      SHELL: bash\n",
     "never closes"),
    ("CHECK split inside its quotes (G5)",
     "- [ ] G1 PROVE: every .ps1 is CRLF only\n"
     "      CHECK: python -c \"import glob; fs=glob.glob('harness/**/*.ps1',recursive=True); bad=[f for f in fs if b'\n"
     "' in open(f,'rb').read().replace(b'\n"
     "\n"
     "',b'')]; print(len(fs),'ps1 files,',len(bad),'LF only',bad)\"\n"
     "      EXPECT: /^(9|[1-9]\\d) ps1 files, 0 LF only/\n"
     "      SHELL: bash\n",
     "unclosed quote"),
    ("doubled backslashes collapsed into a bad regex escape (G6)",
     "- [ ] G1 PROVE: the task action points at the new path\n"
     "      CHECK: powershell.exe -NoProfile -Command '(Get-ScheduledTask -TaskName mesosphere-review).Actions | ForEach-Object { $_.Execute + \" \" + $_.Arguments }'\n"
     "      EXPECT: /vault\\harness\\review-job\\windows\\run-review\\.ps1/\n"
     "      SHELL: bash\n",
     "does not compile"),
    ("EXPECT split after its first line (G8)",
     "- [ ] G1 PROVE: the live run recorded an outcome\n"
     "      CHECK: python -c \"print('written after open:', True); print('outcome:', 'committed')\"\n"
     "      EXPECT: /^written after open: True\n"
     "outcome: (committed|nothing-new)$/\n"
     "      SHELL: bash\n",
     "never closes"),
]

fails = []


def expect(cond, label, out=""):
    print(("ok   " if cond else "FAIL ") + label)
    if not cond:
        print("     " + out.strip().replace("\n", "\n     ")[-600:])
        fails.append(label)


def declare(gate):
    with tempfile.TemporaryDirectory() as tmp:
        d = pathlib.Path(tmp)
        (d / "f.txt").write_text("clean\n")
        path = d / "led.md"
        path.write_text(HEAD + gate + TAIL, encoding="utf-8")
        r = subprocess.run([sys.executable, str(ENGINE), "--file", str(path), "declare"],
                           capture_output=True, text=True, timeout=60, cwd=tmp)
        return r.returncode, (r.stdout or "") + (r.stderr or ""), path.read_text(encoding="utf-8")


# 1. every mangled gate from 2026-10-27 is refused at declare, for the right reason,
#    and the ledger stays a draft
for label, gate, why in BROKEN:
    code, out, text = declare(gate)
    expect(code != 0 and "REFUSED" in out and why in out and "Lock: open" in text,
           f"refused: {label}", out)

# 2. the same features written correctly still declare
SOUND = ("- [ ] G1 PROVE: the marker line exists\n"
         "      CHECK: grep -c \"it's here\" f.txt || true\n"
         "      EXPECT: /^[1-9]\\d*$/\n"
         "      SHELL: bash\n")
code, out, text = declare(SOUND)
expect(code == 0 and "LOCKED" in out, "a sound gate with \\d and nested quotes declares", out)

# 3. lint units: what a gate must still be allowed to say
def gate(check, expect_, shell="bash", outcome="the thing is true"):
    g = ledger.Gate(1, False, "G1", "PROVE", outcome)
    g.check, g.expect, g.shell = check, expect_, shell
    return g

ok_cases = [
    ("an escaped backslash class in a Windows path regex",
     gate("powershell.exe -Command 'x'", r"/Projects[\\]vault[\\]harness/")),
    ("a literal EXPECT that is not a regex", gate("python t.py | tail -1", "ok: history")),
    ("a tab inside a CHECK", gate("printf_free\tcmd x", None)),
    ("an apostrophe under cmd, which has no single quotes", gate("findstr it's f.txt", None, shell="cmd")),
    ("a regex with flags", gate("python t.py", "/^OK$/i")),
]
for label, g in ok_cases:
    probs = ledger.lint_mangled(g)
    expect(not probs, f"not refused: {label}", "; ".join(probs))

bad_cases = [
    ("a carriage return in the outcome", gate("python t.py", "/ok/", outcome="points at harness\review-job"), "outcome holds control"),
    ("an unclosed quote under sh", gate("grep 'x f.txt", "/1/", shell="sh"), "unclosed quote"),
]
for label, g, why in bad_cases:
    probs = ledger.lint_mangled(g)
    expect(any(why in p for p in probs), f"refused: {label}", "; ".join(probs) or "nothing refused")

if fails:
    print(f"FAILED: {len(fails)} escape lint check(s)")
    sys.exit(1)
print("ok: escape lint")
