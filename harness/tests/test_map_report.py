#!/usr/bin/env python3
"""After `map`, the report must describe the ledger as it now is.

Found 2026-10-28: right after a successful `map A1 G1` the engine printed "UNMAPPED A1"
and exited 1, because it reported from the copy parsed before the change. That invites
an agent to retry or hand edit the file.

  python3 harness/tests/test_map_report.py
    -> "ok: map reports fresh", exit 0
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
    led(d, "open", "--title", "map", "--prompt-file", "prompt.txt")
    path = d / ".ledger" / "t.md"
    py = pathlib.Path(sys.executable).as_posix()
    gate = (f"- [ ] G1 PROVE: the release file exists\n      CHECK: {py} -c \"import pathlib,sys;"
            f"sys.exit(not pathlib.Path('release.txt').exists())\"\n")
    path.write_text(path.read_text().replace("-->\n\n## Asks", "-->\n" + gate + "\n## Asks", 1))
    r = led(d, "map", "A1", "G1")
    check("map succeeds", "UNMAPPED A1" not in r.stdout, r.stdout + r.stderr)
    check("the ask now reads as mapped", "A1" in path.read_text() and "-> G1" in path.read_text(), path.read_text()[-300:])

if fails:
    print("\nFAIL\n  " + "\n  ".join(fails))
    sys.exit(1)
print("ok: map reports fresh")
