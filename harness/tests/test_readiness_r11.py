#!/usr/bin/env python3
"""The eleventh readiness review's honest-use finding stays fixed.

With the coverage audit only awaited (awaiting-subagent or awaiting-human), `status`
exited 0 and `close` refused but also exited 0, so "status must exit 0, then close"
passed on a ledger that could not close, and `close && next` went on as if it had.

  python3 harness/tests/test_readiness_r11.py
    -> "ok: the eleventh review's finding stays fixed", exit 0
"""
import json, os, pathlib, re, subprocess, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _ledgerkit import ENGINE, check, file_check, finish, make_repo

CLEAN = {k: v for k, v in os.environ.items()
         if k not in ("LEDGER_DIR", "CLAUDE_SESSION_ID", "CLAUDE_CODE_SESSION_ID",
                      "CLAUDE_PROJECT_DIR", "LEDGER_STOP_GATE_ACTIVE", "LEDGER_DEPTH")}


def eng(cwd, *args):
    return subprocess.run([sys.executable, str(ENGINE), "--session", "t", *args], cwd=str(cwd),
                          capture_output=True, text=True, env=CLEAN, timeout=300)


with tempfile.TemporaryDirectory() as tmp:
    for party in ("awaiting-subagent", "awaiting-human"):
        root = make_repo(pathlib.Path(tmp) / party)
        (root / "p.txt").write_text("build the release file for the next build\n")
        eng(root, "open", "--title", "await -- check", "--prompt-file", "p.txt")
        path = root / ".ledger" / "t.md"
        gate = f"- [ ] G1 PROVE: the release file exists\n      CHECK: {file_check('release.txt')}"
        text = path.read_text().replace("-->\n\n## Asks", "-->\n" + gate + "\n\n## Asks", 1)
        path.write_text(re.sub(r"(?m)^(A\d+ .*) -> \?$", r"\1 -> G1", text))
        eng(root, "declare")
        (root / "release.txt").write_text("v1")
        eng(root, "run")
        eng(root, "audit", party, "dispatched, waiting")
        r = eng(root, "status")
        check(f"{party}: status exits 1 while the verdict is awaited", r.returncode == 1, r.stdout)
        j = json.loads(eng(root, "--json", "status").stdout.strip().splitlines()[-1])
        check(f"{party}: the stop gate still sees no pending audit, so the turn may end",
              j["audit"] == party and not j["unmet"] and not j["unmapped_asks"], j)
        r = eng(root, "close")
        check(f"{party}: close refuses with a non zero exit", r.returncode != 0 and path.exists(), r.stdout)
        eng(root, "audit", "subagent", "COVERED")
        check(f"{party}: status exits 0 once a verdict is recorded", eng(root, "status").returncode == 0)
        eng(root, "close", "--archive-to", "episodic")
        arch = "".join(p.read_text() for p in (root / "episodic").glob("*.md"))
        check(f"{party}: a spaced double hyphen in a title archives as one space",
              "# Ledger: await check" in arch, arch[:300])

finish("the eleventh review's finding stays fixed")
