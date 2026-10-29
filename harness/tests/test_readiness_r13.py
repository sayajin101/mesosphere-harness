#!/usr/bin/env python3
"""The thirteenth readiness review's NITs stay fixed.

1. A gate whose CHECK ends in `|| true`, with no EXPECT, was declared and could never fail.
2. Four adapters lacked the audit, model per subagent and usage readout rows the docs cite.
3. The review job README said five levels up where the code walks three.
4. The Windows task never set the profile's Python for the mining step.
5. Rarer scrubber phrasings: "the api key <token>", "here's the secret X", "username admin
   pass X", and glrt-, glptt- and npm_ tokens.
6. Throwing away a never declared draft needed `--force close`, which then read as a
   FORCED CLOSE in every session for a day.
7. Contract section 9, pasted into a project repo, cited a section 6 that is not there.
8. The docs read as if the six block release happened once; it holds for the session.
Also: a Windows check runs with CHERE_INVOKING set, so a login shell stays in the root.

  python3 harness/tests/test_readiness_r13.py
    -> "ok: the thirteenth review's NITs stay fixed", exit 0
"""
import os, pathlib, re, subprocess, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _ledgerkit import ENGINE, HARNESS, check, finish, make_repo, stop

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

    # 1: `|| true` with no EXPECT is refused, for HOLD and PROVE alike.
    for suffix in ("|| true", "|| :", "; exit 0"):
        root = make_repo(tmp / f"true{len(suffix)}{suffix[-1]}")
        draft(root, ["- [ ] G1 HOLD: the test suite stays green",
                     f"      CHECK: {sys.executable} -c \"import sys; sys.exit(1)\" {suffix}"])
        r = eng(root, "declare")
        check(f"a CHECK ending in '{suffix}' with no EXPECT is refused",
              r.returncode != 0 and "can never fail" in r.stdout, r.stdout[-300:])

    # 6: a never declared draft is discarded quietly, and nothing reads as forced.
    root = make_repo(tmp / "discard")
    path = draft(root, ["- [ ] G1 PROVE: the release file exists", "      CHECK: test -f release.txt"])
    r = eng(root, "close")
    gone = sorted((root / ".ledger" / "closed").glob("*.md")) if (root / ".ledger" / "closed").is_dir() else []
    check("close discards a never declared draft without --force",
          r.returncode == 0 and not path.exists() and gone and "discarded" in gone[0].name, r.stdout + r.stderr)
    text = gone[0].read_text() if gone else ""
    check("the discarded draft's log says DISCARDED, never FORCED",
          "DISCARDED" in text and "FORCED" not in text, text[-300:])
    res = stop(root, session="s")
    check("the stop gate prints no FORCED CLOSE after a discard", "FORCED" not in str(res), res)

    # Also: a Windows check gets CHERE_INVOKING, so Git Bash's login profile stays put.
    probe = f"""
import sys
sys.path.insert(0, {str(HARNESS)!r})
import ledger
seen = {{}}
class Fake:
    def __init__(self, argv, **kw):
        seen.update(kw.get("env") or {{}})
        raise OSError("stop here")
ledger.os.name = "nt"
ledger.windows_bash = lambda: "/bin/bash"
ledger.subprocess.Popen = Fake
g = ledger.Gate(0, False, "G1", "PROVE", "x")
g.check, g.shell = "true", "bash"
ledger.run_check(g, 5, None)
print(seen.get("CHERE_INVOKING"))
"""
    r = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, timeout=60)
    check("a Windows check runs with CHERE_INVOKING=1", r.stdout.strip() == "1", r.stdout + r.stderr)

# 5: the scrubber phrasings.
sys.path.insert(0, str(HARNESS))
from history import scrub
for s, secret in [("the api key 9a8b7c6d5e4f3a2b1c0d", "9a8b7c"), ("here's the secret abc123XYZ", "abc123"),
                  ("username admin pass hunter2", "hunter2"), ("glrt-abcdefghijklmnopqrst runner", "glrt-abc"),
                  ("glptt-abcdefghijklmnopqrst", "glptt-abc"), ("npm_abcdefghijklmnop1234", "npm_abc")]:
    check(f"scrubbed: {s}", secret not in scrub(s), scrub(s))
for s in ["the api key rotation runbook", "here is the secret sauce", "user guide pass rate",
          "the api key is not in the archive", "see npm_modules folder"]:
    check(f"survives: {s}", scrub(s) == s, scrub(s))

# 2: every shipped adapter answers the three questions the docs send an agent to ask.
for name in ("claude-code", "codex", "cursor", "gemini", "antigravity"):
    caps = (HARNESS / "adapters" / name / "CAPABILITIES.md").read_text(encoding="utf-8")
    check(f"{name} CAPABILITIES has the audit, model per subagent and usage readout rows",
          "coverage audit" in caps and "Model per subagent" in caps and "Usage readout" in caps)

# 3 and 4: the review job docs.
rj = (HARNESS / "review-job" / "README.md").read_text(encoding="utf-8")
check("the review job README says three levels up", "three\nlevels up" in rj and "five\nlevels" not in rj)
win = (HARNESS / "review-job" / "windows" / "README.md").read_text(encoding="utf-8")
check("the Windows README sets the profile's Python for the task",
      re.search(r"SetEnvironmentVariable\('\w+_PYTHON'", win) is not None)

# 7 and 8: the contract and the release.
contract = (HARNESS / "CONTRACT.md").read_text(encoding="utf-8")
check("contract section 9 no longer cites a section 6 by number",
      "lesson candidates under section 6" not in contract)
ledger_md = (HARNESS / "LEDGER.md").read_text(encoding="utf-8")
check("LEDGER.md says the release holds for the session", "holds for that session" in ledger_md)

finish("the thirteenth review's NITs stay fixed")
