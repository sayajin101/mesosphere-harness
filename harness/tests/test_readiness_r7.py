#!/usr/bin/env python3
"""The seventh review's honest-use findings stay fixed.

A GAPS FOUND audit let status pass and the turn end, credentials in escaped JSON and
in identifiers like DB_PASSWORD_PROD passed the scrubber, and two docs said the stop
gate fails open where it fails closed. (The review job's quiet week with every digest
archived is proven by the macOS selftest's quiet-week-archived case.)

  python3 harness/tests/test_readiness_r7.py
    -> "ok: the seventh review's findings stay fixed", exit 0
"""
import os, pathlib, subprocess, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _ledgerkit import ENGINE, HARNESS, blocked, check, declared, file_check, finish, make_repo, stop

CLEAN = {k: v for k, v in os.environ.items()
         if k not in ("LEDGER_DIR", "CLAUDE_SESSION_ID", "CLAUDE_CODE_SESSION_ID",
                      "CLAUDE_PROJECT_DIR", "LEDGER_STOP_GATE_ACTIVE", "LEDGER_DEPTH")}


def eng(cwd, *args):
    return subprocess.run([sys.executable, str(ENGINE), "--session", "t", *args], cwd=str(cwd),
                          capture_output=True, text=True, env=CLEAN, timeout=300)


with tempfile.TemporaryDirectory() as tmp:
    root = make_repo(pathlib.Path(tmp) / "gaps")
    declared(root, [("PROVE", "the release file exists", file_check("release.txt"))], audit=False)
    (root / "release.txt").write_text("v1")
    eng(root, "run")
    eng(root, "audit", "subagent", "GAPS FOUND: A2 has no gate")
    r = eng(root, "status")
    check("status exits 1 over a gaps verdict", r.returncode == 1 and "AUDIT GAPS" in r.stdout, r.stdout)
    res = stop(root)
    check("the stop gate blocks over a gaps verdict", blocked(res) and "found gaps" in res.get("reason", ""), res)
    eng(root, "audit", "subagent", "COVERED")
    check("and allows once the audit is clean", eng(root, "status").returncode == 0 and not blocked(stop(root)))

sys.path.insert(0, str(HARNESS))
from history import scrub
for s, secret in [('{\\"password\\":\\"Hunter2Pass\\"}', "Hunter2Pass"),
                  ("DB_PASSWORD_PROD=Hunter2pw", "Hunter2pw"),
                  ("dckr" + "_pat_AbCdEfGhIjKlMnOp", "AbCdEfGhIjKlMnOp"),
                  ("the api key is sk1234abcd", "sk1234abcd")]:
    check(f"scrubbed: {s}", secret not in scrub(s), scrub(s))
check("prose survives: the token is not in the archive",
      scrub("the token is not in the archive") == "the token is not in the archive")

caps = (HARNESS / "adapters/claude-code/CAPABILITIES.md").read_text()
check("CAPABILITIES no longer says the stop gate fails open on every error", "Hooks here fail open" not in caps)
ledger_md = (HARNESS / "LEDGER.md").read_text()
check("LEDGER.md states the checkout root rule the code uses", "a submodule's `.git` file is not a root" not in ledger_md)
run_sh = (HARNESS / "review-job/macos/run.sh").read_text()
check("run.sh survives a stage pattern that matches nothing", 'git add -- "$PATTERN" 2>/dev/null || true' in run_sh)

finish("the seventh review's findings stay fixed")
