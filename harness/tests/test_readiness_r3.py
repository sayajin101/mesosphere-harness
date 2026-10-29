#!/usr/bin/env python3
"""The third readiness review's findings stay fixed.

It hid a forged close from the stop gate by putting "FORCED close over:" or
"SUPERSEDED:" in a title, pre-filled the stop gate's state file with the Write tool,
passed checks with an exported bash function, wiped the ledger with `git clean -X`,
outran the hook timeout with two slow ledgers, and got four credential shapes past the
scrubber.

  python3 harness/tests/test_readiness_r3.py
    -> "ok: the third review's findings stay fixed", exit 0
"""
import json, os, pathlib, re, subprocess, sys, tempfile, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _ledgerkit import (ENGINE, HARNESS, STOP, blocked, check, declared, file_check, finish,
                        guard, led, make_repo, stop)

ROOT = HARNESS.parent
CLEAN = {k: v for k, v in os.environ.items()
         if k not in ("LEDGER_DIR", "CLAUDE_SESSION_ID", "CLAUDE_CODE_SESSION_ID",
                      "CLAUDE_PROJECT_DIR", "LEDGER_STOP_GATE_ACTIVE")}


def eng(cwd, *args, **env):
    return subprocess.run([sys.executable, str(ENGINE), "--session", "t", *args], cwd=str(cwd),
                          capture_output=True, text=True, env={**CLEAN, **env}, timeout=300)


def closed_then_broken(tmp, name, title):
    """An honest close, then the work is undone: the stop gate must notice."""
    root = make_repo(pathlib.Path(tmp) / name)
    (root / "prompt.txt").write_text("build the release file\n")
    eng(root, "open", "--title", title, "--prompt-file", "prompt.txt")
    path = root / ".ledger" / "t.md"
    t = path.read_text().replace("-->\n\n## Asks", "-->\n- [ ] G1 PROVE: the release file exists\n"
                                 f"      CHECK: {file_check('release.txt')}\n\n## Asks", 1)
    path.write_text(re.sub(r"(?m)^(A\d+ .*) -> \?$", r"\1 -> G1", t))
    eng(root, "declare")
    eng(root, "audit", "subagent", "COVERED")
    (root / "release.txt").write_text("v1")
    eng(root, "run")
    r = eng(root, "close")
    assert r.returncode == 0, r.stdout + r.stderr
    (root / "release.txt").unlink()
    return root


with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)

    # F1: a FORCED close is named only from the engine's own Log line, so a title carrying
    # the phrase neither names nor hides anything.
    root = closed_then_broken(tmp, "titled", "x FORCED close over: nothing")
    res = stop(root)
    check("a title carrying 'FORCED close over:' is not read as a forced close",
          "FORCED CLOSE" not in res.get("systemMessage", ""), res)

    # F1b: the Write tool cannot touch the state file or the sidecar beside a declared ledger.
    root = make_repo(tmp / "state")
    declared(root, [("PROVE", "the release file exists", file_check("release.txt"))])
    for name in ("t.state.json", "t.declared", "other.state.json"):
        check(f"Write refused for .ledger/{name}",
              guard(root, "Write", {"file_path": str(root / ".ledger" / name), "content": "{}"}))
    check("Write still allowed for a new draft beside it",
          not guard(root, "Write", {"file_path": str(root / ".ledger" / "draft.md"), "content": "x"}))

    # F2: an exported bash function never reaches a check.
    root = make_repo(tmp / "func")
    declared(root, [("PROVE", "the release file exists", "test -f release.txt")])
    r = eng(root, "run", **{"BASH_FUNC_test%%": "() {  return 0\n}"})
    check("an exported `test` function does not pass a check", r.returncode != 0, r.stdout)

    # F3: git clean -x / -X is refused while a ledger is declared; a plain clean is not.
    for cmd in ["git clean -fdX", "git clean -xfd", "git -C . clean -fdx"]:
        check(f"guard refuses: {cmd}", guard(root, "Bash", {"command": cmd}))
    check("guard allows git clean -fd (ignored files kept)", not guard(root, "Bash", {"command": "git clean -fd"}))
    check("guard allows a commit message that mentions git clean -X",
          not guard(root, "Bash", {"command": "git commit -q -m 'refuse git clean -X now'"}))

    # F4: one budget for all ledgers, so two slow ones cannot outrun the hook.
    root = make_repo(tmp / "slow")
    slow = f"{sys.executable} -c \"import time;time.sleep(6)\""
    for s in ("a", "b"):
        declared(root, [("HOLD", "a slow check", slow)], session=s)
        eng(root, "--session", s, "run")
    t0 = time.monotonic()
    res = subprocess.run([sys.executable, str(STOP)], input=json.dumps({"session_id": "z", "cwd": str(root)}),
                         capture_output=True, text=True, cwd=str(root), timeout=120,
                         env={**CLEAN, "LEDGER_ENGINE": str(ENGINE), "LEDGER_STOP_TIMEOUT": "8"})
    took = time.monotonic() - t0
    check("the stop gate keeps one deadline across ledgers and blocks when it runs out",
          '"block"' in res.stdout and took < 20, (took, res.stdout[-300:]))

# The engine honours its caller's deadline.
with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)
    root = make_repo(tmp / "deadline")
    declared(root, [("HOLD", "a slow check", f"{sys.executable} -c \"import time;time.sleep(5)\"")])
    eng(root, "run")
    t0 = time.monotonic()
    r = eng(root, "status", LEDGER_DEADLINE=str(time.time() - 1))
    check("past its caller's deadline the engine starts no check and fails",
          r.returncode == 1 and "time budget ran out" in r.stdout and time.monotonic() - t0 < 4, r.stdout)

# F5: four more shapes.
sys.path.insert(0, str(HARNESS))
from history import scrub
discord = "MTA4NzQ1NjQ3ODk0NTY3ODkw" + ".GaBcDe." + "abcdefghijklmnopqrstuvwxyz0123"
for s, secret in [(discord, "abcdefghijklmnopqrstuvwxyz0123"),
                  ("https://a.blob.core.windows.net/c?sv=2022&" + "sig=AbCdEfGh1234IjKl%2B5678=", "AbCdEfGh1234"),
                  ("sq0" + "atp-AbCdEfGhIjKlMnOpQrStUv", "AbCdEfGhIjKlMnOpQrStUv"),
                  ("pw: Hunter2pw", "Hunter2pw")]:
    check(f"scrubbed: {s[:30]}", secret not in scrub(s), scrub(s))
check("prose survives: the pwd folder", scrub("the pwd folder") == "the pwd folder")

# Fixtures a host's secret scanner would flag are assembled at run time.
tests = HARNESS / "tests"
literal = [p.name for p in tests.glob("*.py")
           if re.search(r"rk_live_[0-9A-Za-z]{6}|\d{8,10}:AAE[0-9A-Za-z_-]{20}", p.read_text())]
check("no live-looking key literal in the test sources", not literal, literal)

ledger_md = (HARNESS / "LEDGER.md").read_text()
check("LEDGER.md names deleting the ledger folder as a limit", "delete the ledger folder" in ledger_md)

finish("the third review's findings stay fixed")
