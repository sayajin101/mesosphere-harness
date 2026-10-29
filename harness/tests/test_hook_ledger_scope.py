#!/usr/bin/env python3
"""The stop gate enforces every open ledger, and the hooks find .ledger from a subfolder.

Two holes found on 2026-10-28. The stop gate enforced only `.ledger/<session>.md` when
that file existed, and ledger.py names new ledgers by session id, so any session that
opened a small ledger of its own silenced a long running one beside it. And both hooks
joined `.ledger` onto the payload's cwd, so after `cd subdir` the wall allowed and the
guard let a write into the root ledger through.

  python3 harness/tests/test_hook_ledger_scope.py
    -> "ok: every ledger, from any folder", exit 0
"""
import pathlib, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _ledgerkit import (blocked, check, declared, file_check, finish, guard, led, make_repo,
                        stop)

with tempfile.TemporaryDirectory() as tmp:
    root = make_repo(tmp)
    sub = root / "src" / "deep"
    sub.mkdir(parents=True)
    (root / "done.txt").write_text("x")
    declared(root, [("PROVE", "the release file exists", file_check("release.txt"))],
             session="long-task")
    mine = declared(root, [("PROVE", "the done file exists", file_check("done-later.txt"))],
                    session="me")
    (root / "done-later.txt").write_text("x")
    led(root, "run", session="me")
    check("this session's own ledger is met", led(root, "status", session="me").returncode == 0)

    res = stop(root, session="me")
    check("another open ledger still blocks this session", blocked(res), res)
    check("the block names the other ledger", "long-task" in str(res), res)

    res = stop(sub, session="nobody")
    check("the stop gate finds .ledger from a subfolder", blocked(res), res)

    target = root / ".ledger" / "long-task.md"
    check("the guard denies a Write into the root ledger from a subfolder",
          guard(sub, "Write", {"file_path": str(target), "content": "x"}))
    check("the guard denies a relative Edit from a subfolder",
          guard(sub, "Edit", {"file_path": "../../.ledger/long-task.md",
                              "old_string": "a", "new_string": "b"}))
    check("the guard denies a Bash write into the root ledger from a subfolder",
          guard(sub, "Bash", {"command": "sed -i '' s/x/y/ ../../.ledger/long-task.md"}))
    r = led(sub, "--json", "status", session="long-task")
    check("ledger.py finds the ledger from a subfolder", '"lock": "intact"' in r.stdout,
          r.stdout + r.stderr)

    with tempfile.TemporaryDirectory() as other:
        res = stop(make_repo(other), session="x")
        check("a different repo's ledgers do not leak in", not blocked(res), res)

finish("every ledger, from any folder")
