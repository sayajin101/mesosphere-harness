#!/usr/bin/env python3
"""An amendment adds gates and touches nothing else.

On 2026-10-28 a review sent `--force declare --gates-file F` a file whose first lines
were attribute lines, `CHECK: test -d .`, before its first gate. The parser attached them
to the LAST EXISTING gate, replacing its frozen check, and the amendment re-locked over
the change. Now a gates file must open with a gate, holds only gate and attribute lines,
may not repeat an attribute, and every existing gate must come out unchanged.

  python3 harness/tests/test_ledger_amend_guard.py
    -> "ok: amendments add only", exit 0
"""
import pathlib, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _ledgerkit import PY, check, declared, file_check, finish, led, make_repo

with tempfile.TemporaryDirectory() as tmp:
    root = make_repo(pathlib.Path(tmp) / "repo")
    gates = pathlib.Path(tmp) / "gates.txt"
    path = declared(root, [("PROVE", "the release file exists", file_check("release.txt"))])
    new = f"- [ ] G2 PROVE: the notes file exists\n      CHECK: {file_check('notes.txt')}\n"

    def refused(name, text):
        gates.write_text(text)
        before = path.read_bytes()
        r = led(root, "--force", "declare", "--gates-file", str(gates))
        check(f"{name}: refused", r.returncode != 0, r.stdout + r.stderr)
        check(f"{name}: ledger unchanged", path.read_bytes() == before)

    refused("attribute lines before the first gate",
            f"      CHECK: {PY} -c \"import sys;sys.exit(0)\"\n" + new)
    refused("a repeated attribute line",
            new + f"      CHECK: {PY} -c \"import sys;sys.exit(0)\"\n")
    refused("an ask line", new + 'A9 "a made up ask" -> G2\n')
    refused("a comment opener", new + "<!--\n")
    refused("a gate arriving pre ticked",
            new.replace("- [ ]", "- [x]") + "      EVIDENCE: done\n")

    gates.write_text(new)
    r = led(root, "--force", "declare", "--gates-file", str(gates))
    check("a clean gates file is accepted", r.returncode == 0, r.stdout + r.stderr)
    text = path.read_text()
    check("the existing gate kept its check", "release.txt" in text and text.count("CHECK:") >= 3,
          text)

    # A repeated attribute written by hand breaks the lock, since last wins in the parser.
    lines = path.read_text().split("\n")
    at = max(i for i, l in enumerate(lines) if l.startswith("- [ ] G1 "))  # not the template
    lines.insert(at + 2, f"      CHECK: {PY} -c \"import sys;sys.exit(0)\"")
    path.write_text("\n".join(lines))
    r = led(root, "status")
    check("a hand added second CHECK breaks the lock", r.returncode == 3 and "broken" in r.stdout,
          r.stdout + r.stderr)

finish("amendments add only")
