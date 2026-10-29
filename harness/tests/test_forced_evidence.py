#!/usr/bin/env python3
"""Forcing evidence onto a PROVE or HOLD gate must be visible, never a silent pass.

A PROVE gate is met by its CHECK. `evidence --force` exists for a deliberate, on the
record override, but until 2026-10-28 it wrote the evidence exactly like a real pass,
so an agent could tick its own homework with one command. The evidence is now stamped
FORCED and every status report names the gate.

  python3 harness/tests/test_forced_evidence.py
    -> "ok: forced evidence is visible", exit 0
"""
import pathlib, subprocess, sys, tempfile

ENGINE = pathlib.Path(__file__).resolve().parents[1] / "ledger.py"
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
    (d / "prompt.txt").write_text("create the release file for the build\n")
    led(d, "open", "--title", "forced", "--prompt-file", "prompt.txt")
    path = d / ".ledger" / "t.md"
    py = pathlib.Path(sys.executable).as_posix()
    gate = (f"- [ ] G1 PROVE: the release file exists\n      CHECK: {py} -c \"import pathlib,sys;"
            f"sys.exit(not pathlib.Path('release.txt').exists())\"\n")
    text = path.read_text().replace("-->\n\n## Asks", "-->\n" + gate + "\n## Asks", 1)
    path.write_text("\n".join(l[:-1] + "G1" if l.startswith("A") and l.endswith("-> ?") else l
                              for l in text.split("\n")))
    led(d, "declare")
    r = led(d, "evidence", "G1", "it is fine, trust me")
    check("plain evidence on a PROVE gate is refused", r.returncode != 0, r.stdout + r.stderr)
    r = led(d, "--force", "evidence", "G1", "it is fine, trust me")
    body = path.read_text()
    check("forced evidence is stamped FORCED in the ledger", "FORCED (not proven by its CHECK)" in body, body[-400:])
    r = led(d, "status")
    check("status names the forced gate", "FORCED G1" in r.stdout, r.stdout)

if fails:
    print("\nFAIL\n  " + "\n  ".join(fails))
    sys.exit(1)
print("ok: forced evidence is visible")
