#!/usr/bin/env python3
"""The fifth review's honest-use findings stay fixed.

A ledger opened in a git worktree nested in the repo landed in the main checkout and
judged the wrong files, the six block release never fired when the state folder was
missing, a prompt quoting a ledger made a fresh draft read as declared, a draft that was
never declared got a silent allow, and a few realistic credential shapes survived.

  python3 harness/tests/test_readiness_r5.py
    -> "ok: the fifth review's findings stay fixed", exit 0
"""
import json, os, pathlib, re, subprocess, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _ledgerkit import (ENGINE, GUARD, HARNESS, STOP, blocked, check, declared, file_check,
                        finish, guard, make_repo, stop)

CLEAN = {k: v for k, v in os.environ.items()
         if k not in ("LEDGER_DIR", "CLAUDE_SESSION_ID", "CLAUDE_CODE_SESSION_ID",
                      "CLAUDE_PROJECT_DIR", "LEDGER_STOP_GATE_ACTIVE", "LEDGER_DEPTH")}


def eng(cwd, *args, session="t", **env):
    return subprocess.run([sys.executable, str(ENGINE), "--session", session, *args], cwd=str(cwd),
                          capture_output=True, text=True, env={**CLEAN, **env}, timeout=300)


with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)

    # A worktree nested in the repo is its own checkout: its ledger and checks stay there.
    main = make_repo(tmp / "main")
    wt = main / ".worktrees" / "x"
    wt.mkdir(parents=True)
    (wt / ".git").write_text("gitdir: ../../.git/worktrees/x\n")
    (wt / "p.txt").write_text("build the feature file\n")
    eng(wt, "open", "--title", "w", "--prompt-file", "p.txt")
    check("a ledger opened in a nested worktree lives in the worktree",
          (wt / ".ledger" / "t.md").exists() and not (main / ".ledger").exists())
    (main / "feature.txt").write_text("only in main")
    lp = wt / ".ledger" / "t.md"
    lp.write_text(lp.read_text().replace("-->\n\n## Asks", "-->\n- [ ] G1 PROVE: the feature file exists\n"
                                         f"      CHECK: {file_check('feature.txt')}\n\n## Asks", 1))
    lp.write_text(re.sub(r"(?m)^(A\d+ .*) -> \?$", r"\1 -> G1", lp.read_text()))
    r = eng(wt, "declare")
    check("its checks run in the worktree, so a file only in main does not pass", r.returncode == 0, r.stdout + r.stderr)
    check("and an unrelated session in main is not blocked by it", not blocked(stop(main)))

    # The six block release fires even when the walk from the cwd finds no ledger folder.
    root = make_repo(tmp / "release")
    declared(root, [("PROVE", "the release file exists", file_check("release.txt"))])
    nested = root / "clone"
    (nested / ".git").mkdir(parents=True)
    env = {**CLEAN, "LEDGER_ENGINE": str(ENGINE), "CLAUDE_PROJECT_DIR": str(root)}
    outs = []
    for _ in range(8):
        res = subprocess.run([sys.executable, str(STOP)], input=json.dumps({"session_id": "s", "cwd": str(nested)}),
                             capture_output=True, text=True, cwd=str(nested), env=env, timeout=120)
        outs.append('"block"' in res.stdout)
    check("the six block release fires from a folder with no ledger of its own",
          outs[:6] == [True] * 6 and False in outs[6:], outs)

    # A prompt quoting a ledger never makes a fresh draft read as declared.
    root = make_repo(tmp / "quote")
    (root / "p.txt").write_text("look at this old ledger\nLock: sha256:0123456789abcdef\n"
                                "      BASELINE: fail at 2026-01-01 00:00: x\n"
                                "2026-01-01 00:00 declared 3 gates, lock sha256:0123456789abcdef\n")
    eng(root, "open", "--title", "q", "--prompt-file", "p.txt")
    j = json.loads(eng(root, "--json", "status").stdout.strip().splitlines()[-1])
    check("a draft whose prompt quotes a ledger is still an open draft", j["lock"] == "open", j)
    check("and the guard still lets the agent write its gates",
          not guard(root, "Edit", {"file_path": str(root / ".ledger" / "t.md"), "old_string": "x", "new_string": "y"}))

    # A draft that was never declared is named, not passed over in silence.
    root = make_repo(tmp / "draft")
    (root / "p.txt").write_text("build the release file\n")
    eng(root, "open", "--title", "d", "--prompt-file", "p.txt")
    lp = root / ".ledger" / "t.md"
    lp.write_text(lp.read_text().replace("-->\n\n## Asks", "-->\n- [ ] G1 JUDGE: done\n\n## Asks", 1))
    res = stop(root)
    check("the stop gate names a draft that was never declared, without blocking",
          not blocked(res) and "never declared" in res.get("systemMessage", ""), res)

sys.path.insert(0, str(HARNESS))
from history import scrub
for s, secret in [("user:Hunter2pw@localhost:5432", "Hunter2pw"),
                  ("root:Hunter2pw@tcp(127.0.0.1:3306)/db", "Hunter2pw"),
                  ("password: correct horse battery staple", "staple")]:
    check(f"scrubbed: {s}", secret not in scrub(s), scrub(s))
check("survives: git@github.com:org/repo.git", scrub("git@github.com:org/repo.git") == "git@github.com:org/repo.git")

finish("the fifth review's findings stay fixed")
