#!/usr/bin/env python3
"""Every override is visible where a reader looks: status --json, the stop gate, the log.

Found 2026-10-28: forced evidence was missing from `status --json`, so the stop gate
never showed FORCED; `close --force` logged only "closed"; and `relock --force` left
nothing in status to say the lock had been rewritten.

  python3 harness/tests/test_forced_visibility.py
    -> "ok: overrides are visible", exit 0
"""
import json, pathlib, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _ledgerkit import (check, declared, file_check, finish, led, make_repo, stop)

with tempfile.TemporaryDirectory() as tmp:
    root = make_repo(tmp)
    path = declared(root, [("PROVE", "the release file exists", file_check("release.txt")),
                           ("PROVE", "the notes file exists", file_check("notes.txt"))])
    led(root, "--force", "evidence", "G1", "checked it by eye")
    j = json.loads(led(root, "--json", "status").stdout.strip().splitlines()[-1])
    check("status --json lists the forced gate", j.get("forced") == ["G1"], j)
    check("a forced gate whose check fails is still unmet",
          any(u["id"] == "G1" for u in j["unmet"]), j)
    res = stop(root)
    check("the stop gate shows FORCED", "FORCED G1" in json.dumps(res), res)

    r = led(root, "--force", "relock", "the freeze algorithm changed")
    j = json.loads(led(root, "--json", "status").stdout.strip().splitlines()[-1])
    check("status --json flags a relocked ledger", j.get("relocked") is True, j)
    check("status text flags a relocked ledger", "RELOCKED" in led(root, "status").stdout)

    text_before = path.read_text()
    r = led(root, "--force", "close")
    closed = root / ".ledger" / "closed" / path.name
    log = closed.read_text() if closed.exists() else text_before
    check("close --force logs FORCED with the unmet ids",
          "FORCED close over: unmet G1, G2" in log, log[-400:])

finish("overrides are visible")
