#!/usr/bin/env python3
"""The sixth review's honest-use findings stay fixed.

The gap check read "COVERED. No gaps found." as gaps and LEDGER.md's own gap example as
clean, a forced close over a gaps verdict was logged as a plain close, a re-recorded
audit left no trace, two credential shapes passed the scrubber, a baseline that timed
out was locked as a red one, and a missing engine let the turn end in silence.

  python3 harness/tests/test_readiness_r6.py
    -> "ok: the sixth review's findings stay fixed", exit 0
"""
import importlib.util, json, os, pathlib, re, subprocess, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _ledgerkit import (ENGINE, HARNESS, STOP, blocked, check, declared, file_check, finish,
                        make_repo, stop)

CLEAN = {k: v for k, v in os.environ.items()
         if k not in ("LEDGER_DIR", "CLAUDE_SESSION_ID", "CLAUDE_CODE_SESSION_ID",
                      "CLAUDE_PROJECT_DIR", "LEDGER_STOP_GATE_ACTIVE", "LEDGER_DEPTH")}


def eng(cwd, *args, **env):
    return subprocess.run([sys.executable, str(ENGINE), "--session", "t", *args], cwd=str(cwd),
                          capture_output=True, text=True, env={**CLEAN, **env}, timeout=300)


spec = importlib.util.spec_from_file_location("ledger_engine", ENGINE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
for verdict, gaps in [("subagent: VERDICT: COVERED. No gaps found.", False),
                      ("subagent: COVERED", False),
                      ("subagent: GAPS FOUND: A3 has no gate", True),
                      ("subagent: A1 to A4 covered; the prompt also asks to keep the linter clean, which no gate names", True),
                      ("subagent: A1 to A3 covered, nothing in the prompt is uncovered", False),
                      ("subagent: no gaps, every ask covered", False),
                      ("subagent: A3 is not covered by any gate", True)]:
    check(f"audit verdict read right: {verdict[10:60]}", mod.audit_found_gaps(verdict) == gaps)

with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)

    # A forced close over a gaps verdict is FORCED on the record and in the archive.
    root = make_repo(tmp / "gaps")
    path = declared(root, [("PROVE", "the release file exists", file_check("release.txt"))], audit=False)
    (root / "release.txt").write_text("v1")
    eng(root, "run")
    eng(root, "audit", "subagent", "COVERED")
    eng(root, "audit", "subagent", "GAPS FOUND: A2 has no gate")
    text = path.read_text()
    check("a re-recorded audit keeps the verdict it replaced in the log",
          "replacing subagent: COVERED" in text, text[-400:])
    r = eng(root, "--force", "close", "--archive-to", "arch")
    closed = next((root / ".ledger" / "closed").glob("*.md")).read_text()
    check("a forced close over a gaps verdict is logged FORCED", "FORCED close over: a gaps verdict" in closed, closed[-300:])
    arch = next((root / "arch").glob("*.md")).read_text()
    check("the archive keeps the audit and the override", "Audit: subagent: GAPS FOUND" in arch
          and "Closed with --force over" in arch, arch[:600])
    check("and the stop gate names it", "FORCED CLOSE" in stop(root).get("systemMessage", ""))

    # A baseline that times out is refused, not locked as red.
    root = make_repo(tmp / "slow")
    (root / "p.txt").write_text("make it\n")
    eng(root, "open", "--title", "s", "--prompt-file", "p.txt")
    lp = root / ".ledger" / "t.md"
    lp.write_text(lp.read_text().replace("-->\n\n## Asks", "-->\n- [ ] G1 PROVE: slow\n"
                  f"      CHECK: {sys.executable} -c \"import time;time.sleep(5)\"\n\n## Asks", 1))
    lp.write_text(re.sub(r"(?m)^(A\d+ .*) -> \?$", r"\1 -> G1", lp.read_text()))
    r = eng(root, "--timeout", "1", "declare")
    check("a baseline that timed out is refused, naming --timeout",
          r.returncode != 0 and "--timeout" in r.stdout and "Lock: open" in lp.read_text(), r.stdout)

    # A missing engine with ledgers in force blocks rather than allowing in silence.
    root = make_repo(tmp / "noengine")
    declared(root, [("PROVE", "the release file exists", file_check("release.txt"))])
    res = subprocess.run([sys.executable, str(STOP)], input=json.dumps({"session_id": "t", "cwd": str(root)}),
                         capture_output=True, text=True, cwd=str(root), timeout=60,
                         env={**CLEAN, "LEDGER_ENGINE": str(tmp / "missing" / "ledger.py")})
    check("a missing engine blocks a turn over a declared ledger", '"block"' in res.stdout, res.stdout)

sys.path.insert(0, str(HARNESS))
from history import scrub
sg = "SG" + ".abcdefghijklmnopqrstuv.ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopq"
azure = "abc" + "8Q~" + "AbCdEfGhIjKlMnOpQrStUvWxYz0123456"
refresh = "1//" + "0gAbCdEfGhIjKlMnOpQrStUvWxYz"
for s in (sg, azure, refresh):
    check(f"scrubbed: {s[:12]}", "[REDACTED]" in scrub(s) and s[-10:] not in scrub(s), scrub(s))

finish("the sixth review's findings stay fixed")
