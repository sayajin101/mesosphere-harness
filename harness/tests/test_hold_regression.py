#!/usr/bin/env python3
"""A HOLD gate must be re-checked on every run, and go back to unmet when it regresses.

Found 2026-10-27: `run` skipped every gate already met, HOLD gates included, so a
regression guard proved the system was clean once and never again. An independent
review broke the vault after the guard went green and status still reported it met.

Read-only with respect to the repo: everything happens in a temp directory.

  python3 harness/tests/test_hold_regression.py
    -> "ok: hold gates regress", exit 0
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
    (d / "guarded.txt").write_text("clean\n")
    (d / "prompt.txt").write_text("add the feature file and keep the guarded file clean\n")
    r = led(d, "open", "--title", "hold", "--prompt-file", "prompt.txt")
    check("open", r.returncode == 0, r.stdout + r.stderr)
    path = d / ".ledger" / "t.md"
    text = path.read_text()
    check_guard = (f"{PY} -c \"import pathlib;"
                   f"print('state:',pathlib.Path('guarded.txt').read_text().strip())\"")
    check_feature = (f"{PY} -c \"import pathlib;"
                     f"print('feature:',pathlib.Path('feature.txt').exists())\"")
    gates = (f"- [ ] G1 PROVE: the feature file exists\n      CHECK: {check_feature}\n      EXPECT: /^feature: True$/\n"
             f"- [ ] G2 HOLD: the guarded file stays clean\n      CHECK: {check_guard}\n      EXPECT: /^state: clean$/\n")
    text = text.replace("-->\n\n## Asks", "-->\n" + gates + "\n## Asks", 1)
    lines = [ln if not ln.startswith("A") or "->" not in ln else ln.rsplit("->", 1)[0] + "-> G1, G2"
             for ln in text.split("\n")]
    path.write_text("\n".join(lines))
    r = led(d, "declare")
    check("declare", r.returncode == 0 and "LOCKED" in r.stdout, r.stdout + r.stderr)

    (d / "feature.txt").write_text("done\n")
    led(d, "run")
    body = path.read_text()
    check("the HOLD gate is met while the file is clean", "- [x] G2 HOLD" in body, body)

    (d / "guarded.txt").write_text("broken\n")
    r = led(d, "run")
    body = path.read_text()
    check("the HOLD gate is re-run after it was met", "FAIL G2" in r.stdout, r.stdout)
    check("a regressed HOLD gate is unchecked", "- [ ] G2 HOLD" in body, body)
    check("the regression is recorded as evidence", "REGRESSED at" in body, body)
    r = led(d, "status")
    check("status is no longer clean", r.returncode != 0, r.stdout)
    check("the met PROVE gate is untouched", "- [x] G1 PROVE" in body, body)

    (d / "guarded.txt").write_text("clean\n")
    led(d, "run")
    check("a repaired HOLD gate is met again", "- [x] G2 HOLD" in path.read_text(), path.read_text())

if fails:
    print("\nFAIL\n  " + "\n  ".join(fails))
    sys.exit(1)
print("ok: hold gates regress")
