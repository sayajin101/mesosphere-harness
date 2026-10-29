#!/usr/bin/env python3
"""The lock guard refuses the write routes a review walked past it with.

On 2026-10-28 these all wrote into a declared ledger with the guard in place: perl,
dd, ln, install, rsync, ed, awk in place, `cd .ledger && sed -i`, python -c, and a
folder name assembled in a variable. The guard is defence in depth (the re-run checks
are the wall), but the honest path should be the easy one. Reads must stay allowed.

  python3 harness/tests/test_lock_guard_bypasses.py
    -> "ok: guard holds", exit 0
"""
import pathlib, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _ledgerkit import ENGINE, check, declared, file_check, finish, guard, make_repo

WRITES = {
    "cd then sed -i": "cd .ledger && sed -i '' 's/- \\[ \\]/- [x]/' t.md",
    "cd then a redirect": "cd .ledger; echo x >> t.md",
    "perl -pi": "perl -pi -e 's/\\[ \\]/[x]/' .ledger/t.md",
    "python -c": "python3 -c \"import pathlib;p=pathlib.Path('.ledger/t.md');p.write_text('x')\"",
    "python reading a script from stdin": "python3 - .ledger/t.md < /tmp/x.py",
    "node -e": "node -e \"require('fs').writeFileSync('.ledger/t.md','x')\"",
    "bash -c": "bash -c 'printf x > .ledger/t.md'",
    "dd of=": "dd if=/tmp/x of=.ledger/t.md",
    "ln -sf": "ln -sf /tmp/forged.md .ledger/t.md",
    "ed": "printf ',s/x/y/\\nw\\n' | ed .ledger/t.md",
    "install": "install -m 644 /tmp/forged.md .ledger/t.md",
    "rsync": "rsync /tmp/forged.md .ledger/t.md",
    "awk -i inplace": "awk -i inplace '{print}' .ledger/t.md",
    "a folder name built in a variable": "D=.led; F=${D}ger; sed -i '' s/x/y/ $F/t.md",
    "an exported variable": "export L=.ledger && cp /tmp/forged.md $L/t.md",
}
READS = {
    "cat": "cat .ledger/t.md",
    "grep": "grep -n G1 .ledger/t.md",
    "sed -n": "sed -n 1,20p .ledger/t.md",
    "the engine itself": f"python3 {ENGINE} --file .ledger/t.md status",
    "a write elsewhere that merely mentions the folder": "grep ledger notes.md > out.txt",
    "cd elsewhere then write": "cd /tmp && echo x > notes.txt",
}

with tempfile.TemporaryDirectory() as tmp:
    root = make_repo(tmp)
    declared(root, [("PROVE", "the release file exists", file_check("release.txt"))])
    for name, cmd in WRITES.items():
        check(f"denies {name}", guard(root, "Bash", {"command": cmd}), cmd)
    for name, cmd in READS.items():
        check(f"allows {name}", not guard(root, "Bash", {"command": cmd}), cmd)

finish("guard holds")
