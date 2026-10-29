#!/usr/bin/env python3
"""A baseline whose truncated output ends in a space must not break the lock.

Found 2026-10-13: `declare` truncates a failing check's output to 200 characters. When
the cut landed just after a word, the stored BASELINE ended in a space. The lock was
computed over that in-memory value, but the parser strips attribute lines when it
reads the file back, so the very next command reported LOCK BROKEN on a file nobody
had touched. set_attr now stores the value the parser will read back.

Read-only with respect to the repo: everything happens in a temp directory.

  python3 harness/tests/test_lock_trailing_space.py
    -> "ok: trailing space keeps the lock", exit 0
"""
import pathlib, subprocess, sys, tempfile

ENGINE = pathlib.Path(__file__).resolve().parents[1] / "ledger.py"
PY = pathlib.Path(sys.executable).as_posix()  # a backslashed Windows path is stripped by the bash a CHECK runs under
fails = []


def check(name, ok, detail=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}")
    if not ok:
        fails.append(f"{name}: {detail}")


def led(d, *args):
    return subprocess.run([sys.executable, str(ENGINE), "--session", "t", *args],
                          cwd=d, capture_output=True, text=True)


with tempfile.TemporaryDirectory() as d:
    d = pathlib.Path(d)
    (d / "prompt.txt").write_text("make the output check pass for the release\n")
    led(d, "open", "--title", "space", "--prompt-file", "prompt.txt")
    path = d / ".ledger" / "t.md"
    # 199 characters, a space, then more: tail() cuts at 200, so the stored detail
    # ends exactly on that space. Exit 1 keeps the baseline red, as a PROVE gate needs.
    check_cmd = (f"{PY} -c \"import sys,pathlib;"
                 f"print('x'*199+' '+'y'*40);sys.exit(0 if pathlib.Path('done.txt').exists() else 1)\"")
    gate = f"- [ ] G1 PROVE: the release check passes\n      CHECK: {check_cmd}\n"
    text = path.read_text().replace("-->\n\n## Asks", "-->\n" + gate + "\n## Asks", 1)
    text = "\n".join(l[:-1] + "G1" if l.startswith("A") and l.endswith("-> ?") else l
                     for l in text.split("\n"))
    path.write_text(text)
    r = led(d, "declare")
    check("declare locks the contract", r.returncode == 0 and "LOCKED" in r.stdout, r.stdout + r.stderr)
    baseline = [l for l in path.read_text().split("\n") if l.strip().startswith("BASELINE:")]
    check("the baseline was cut at 200 characters", baseline and "x" * 150 in baseline[0], baseline)
    r = led(d, "status")
    check("the untouched file still reports the lock intact",
          "lock intact" in r.stdout and r.returncode != 3, r.stdout + r.stderr)
    (d / "done.txt").write_text("done\n")
    r = led(d, "run")
    check("a run after declare is not refused as a broken lock",
          "LOCK BROKEN" not in r.stdout + r.stderr and "1/1 met" in r.stdout, r.stdout + r.stderr)

if fails:
    print("\nFAIL\n  " + "\n  ".join(fails))
    sys.exit(1)
print("ok: trailing space keeps the lock")
