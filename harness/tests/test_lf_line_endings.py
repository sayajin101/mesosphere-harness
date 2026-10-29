#!/usr/bin/env python3
"""Everything the harness writes uses LF, on every machine.

pathlib's write_text translates "\\n" to "\\r\\n" on Windows, so until 2026-09-29
every ledger and closing summary written on Windows carried CRLF, and git printed
a warning on each commit while .gitattributes quietly normalised it. Rule: LF line
endings, always. The engine now writes bytes; verify.py now fails any
vault note with CRLF on disk, whatever wrote it.

Read-only with respect to the repo: temp directories, ledger.py and verify.py.
"""
import os, pathlib, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
ENGINE = pathlib.Path(os.environ.get("TEST_LEDGER_ENGINE") or ROOT / "harness" / "ledger.py")
VERIFY = ROOT / "harness" / "verify.py"
PY = f'"{sys.executable}"'

fails = []


def expect(cond, label, out=""):
    print(("ok   " if cond else "FAIL ") + label)
    if not cond:
        print("     " + str(out).strip().replace("\n", "\n     ")[-400:])
        fails.append(label)


def eng(*args, cwd):
    r = subprocess.run([sys.executable, str(ENGINE), *args], capture_output=True, text=True,
                       timeout=120, cwd=cwd)
    return (r.stdout or "") + (r.stderr or "")


with tempfile.TemporaryDirectory() as tmp:
    d = pathlib.Path(tmp)
    (d / "prompt.txt").write_bytes(b"make the file exist\n")
    eng("--session", "lf", "open", "--title", "lf test", "--prompt-file", "prompt.txt", cwd=d)
    led = d / ".ledger" / "lf.md"
    expect(led.is_file() and b"\r" not in led.read_bytes(), "open writes LF", led.read_bytes()[:200] if led.is_file() else "no ledger")

    text = led.read_bytes().decode("utf-8")
    gate = (f"- [ ] G1 PROVE: the file exists\n"
            f"      CHECK: {PY} -c \"import os,sys; sys.exit(0 if os.path.exists('f.txt') else 1)\"\n")
    text = text.replace("-->\n\n## Asks", "-->\n" + gate + "\n## Asks", 1)
    text = "\n".join(l.replace("-> ?", "-> G1") if l.startswith("A") else l for l in text.split("\n"))
    led.write_bytes(text.encode("utf-8"))
    eng("--session", "lf", "declare", cwd=d)
    expect(b"\r" not in led.read_bytes(), "declare writes LF", led.read_bytes()[:200])

    (d / "f.txt").write_bytes(b"x")
    eng("--session", "lf", "run", cwd=d)
    eng("--session", "lf", "audit", "human", "COVERED: test", cwd=d)
    expect(b"\r" not in led.read_bytes(), "run and audit write LF", led.read_bytes()[:200])

    (d / "out").mkdir()
    out = eng("--session", "lf", "close", "--archive-to", "out", cwd=d)
    summaries = list((d / "out").glob("*.md"))
    expect(summaries and all(b"\r" not in s.read_bytes() for s in summaries), "close writes its summary in LF", out)

# verify.py refuses a CRLF note, and names it.
with tempfile.TemporaryDirectory() as tmp:
    d = pathlib.Path(tmp)
    (d / "episodic").mkdir()
    (d / "episodic" / "crlf-note.md").write_bytes(b"---\r\ntype: episode\r\n---\r\n\r\n# Note\r\n")
    r = subprocess.run([sys.executable, str(VERIFY), "--no-wrappers", "--outcomes", "none.md"],
                       capture_output=True, text=True, timeout=120, cwd=d)
    out = (r.stdout or "") + (r.stderr or "")
    expect(r.returncode != 0 and "crlf-note.md" in out and "CRLF" in out, "verify.py fails a CRLF note and names it", out)

if fails:
    print(f"\nLF TEST FAILED ({len(fails)} of 5 cases)")
    sys.exit(1)
print("\nLF TEST OK (5 cases)")
