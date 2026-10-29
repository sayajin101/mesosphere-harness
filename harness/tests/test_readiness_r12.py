#!/usr/bin/env python3
"""The twelfth readiness review's NITs, and two found beside them, stay fixed.

1. The six block release never fired when the agent ran `ledger.py run` between blocks,
   because every run adds a Log line and the progress digest hashed the file's bytes.
2. "COVERED (A2 dismissed: no gate needed)" read as a gaps verdict.
3. "the token is X", "set DB_PASS to X" and "login admin / P@ssw0rd1" survived the scrubber.
4. BOOTSTRAP's private remote gate named a bare `gh` and never said it needs the network.
5. A gate declared with --timeout 300 timed out under a plain run, status or close.
6. A session's .state.json stayed in .ledger after its last ledger closed.
7. A met HOLD gate kept its first run's evidence into the archive.

  python3 harness/tests/test_readiness_r12.py
    -> "ok: the twelfth review's NITs stay fixed", exit 0
"""
import os, pathlib, re, subprocess, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _ledgerkit import ENGINE, HARNESS, blocked, check, file_check, finish, make_repo, stop

ROOT = HARNESS.parent
CLEAN = {k: v for k, v in os.environ.items()
         if k not in ("LEDGER_DIR", "CLAUDE_SESSION_ID", "CLAUDE_CODE_SESSION_ID",
                      "CLAUDE_PROJECT_DIR", "LEDGER_STOP_GATE_ACTIVE", "LEDGER_DEPTH")}


def eng(cwd, *args):
    return subprocess.run([sys.executable, str(ENGINE), "--session", "t", *args], cwd=str(cwd),
                          capture_output=True, text=True, env=CLEAN, timeout=300)


def draft(root, gate_lines):
    (root / "p.txt").write_text("build the release file for the next build\n")
    eng(root, "open", "--title", "kit", "--prompt-file", "p.txt")
    path = root / ".ledger" / "t.md"
    text = path.read_text().replace("-->\n\n## Asks", "-->\n" + "\n".join(gate_lines) + "\n\n## Asks", 1)
    path.write_text(re.sub(r"(?m)^(A\d+ .*) -> \?$", r"\1 -> G1", text))
    return path


with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)

    # 1 and 6: the release fires though the agent runs `run` between blocks, and the
    # block count goes with the last ledger.
    root = make_repo(tmp / "release")
    draft(root, ["- [ ] G1 PROVE: the release file exists", f"      CHECK: {file_check('release.txt')}"])
    eng(root, "declare")
    eng(root, "audit", "subagent", "COVERED")
    results = []
    for _ in range(8):
        # A stop session other than the ledger's own name: `close` already removes
        # <ledger>.state.json, and the leak was the stop gate's own session file.
        results.append(blocked(stop(root, session="s")))
        eng(root, "run")
    check("the stop gate releases within seven stops though `run` ran between them",
          results[0] and not all(results[:7]), results)
    (root / "release.txt").write_text("v1")
    eng(root, "run")
    eng(root, "close")
    stop(root, session="s")
    left = list((root / ".ledger").glob("*.state.json"))
    check("no block count is left behind once the last ledger closed", not left, left)

    # 5: a timeout given at declare is kept with the gate.
    root = make_repo(tmp / "timeout")
    draft(root, ["- [ ] G1 PROVE: the slow build leaves its file",
                 "      CHECK: sleep 2 && test -f built.txt"])
    eng(root, "--timeout", "200", "declare")
    (root / "built.txt").write_text("done")
    r = eng(root, "--timeout", "1", "run")
    check("a gate declared with --timeout 200 passes a 2 second check under --timeout 1",
          "PASS G1" in r.stdout, r.stdout[-400:])

    # 7: a met HOLD gate's evidence is this run's, and the archive's is close's.
    root = make_repo(tmp / "evidence")
    (root / "count.txt").write_text("v1\n")
    draft(root, ["- [ ] G1 HOLD: the counter file reads a version",
                 "      CHECK: grep -E '^v[0-9]+$' count.txt", "      EXPECT: /^v\\d+$/"])
    eng(root, "declare")
    eng(root, "audit", "subagent", "COVERED")
    eng(root, "run")
    (root / "count.txt").write_text("v2\n")
    eng(root, "run")
    body = (root / ".ledger" / "t.md").read_text()
    check("a second run records the HOLD gate's new output", "EVIDENCE: v2" in body, body[-600:])
    (root / "count.txt").write_text("v3\n")
    eng(root, "close", "--archive-to", "episodic")
    arch = "".join(p.read_text() for p in (root / "episodic").glob("*.md"))
    check("the archive carries what close itself saw", "G1: v3" in arch, arch[-400:])

# 2: a dismissal named in a COVERED verdict is not a gap.
sys.path.insert(0, str(HARNESS))
import ledger
check("COVERED with a dismissed ask reads as covered",
      not ledger.audit_found_gaps("subagent: COVERED (A2 dismissed: no gate needed, out of scope)"))
check("COVERED with an uncovered ask still reads as gaps",
      ledger.audit_found_gaps("subagent: COVERED: A2 dismissed as out of scope, A3 not covered"))

# 3: the prose shapes.
from history import scrub
for s, secret in [("the token is ab12cd34ef56gh78", "ab12cd34"), ("the secret is s3cr3tValue99", "s3cr3t"),
                  ("set DB_PASS to Winter2026", "Winter2026"), ("login admin / P@ssw0rd123", "P@ssw0rd")]:
    check(f"scrubbed: {s}", secret not in scrub(s), scrub(s))
for s in ["the token is not in the archive", "the secret is stored in vault", "set the timeout to 30",
          "user guide / 2026 edition", "the token is valid for 24h"]:
    check(f"survives: {s}", scrub(s) == s, scrub(s))

# 4: BOOTSTRAP's gh gate says what it needs.
boot = ROOT / "BOOTSTRAP.md"
if boot.exists():
    text = boot.read_text(encoding="utf-8")
    check("the private remote gate uses gh's absolute path and names its network need",
          "CHECK: gh repo view" not in text and "gh auth status" in text)

finish("the twelfth review's NITs stay fixed")
