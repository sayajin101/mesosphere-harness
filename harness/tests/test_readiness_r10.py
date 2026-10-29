#!/usr/bin/env python3
"""The tenth readiness review's honest-use findings stay fixed.

On Windows without WSL, Git Bash was never searched for, so `test -f` gates were
declared under cmd.exe and could never pass; clean COVERED verdicts with detail ("nothing
missing") read as gaps; and "user admin password Winter2026" survived the scrubber.

  python3 harness/tests/test_readiness_r10.py
    -> "ok: the tenth review's findings stay fixed", exit 0
"""
import os, pathlib, re, subprocess, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _ledgerkit import ENGINE, HARNESS, check, file_check, finish, make_repo

CLEAN = {k: v for k, v in os.environ.items()
         if k not in ("LEDGER_DIR", "CLAUDE_SESSION_ID", "CLAUDE_CODE_SESSION_ID",
                      "CLAUDE_PROJECT_DIR", "LEDGER_STOP_GATE_ACTIVE", "LEDGER_DEPTH")}


def eng(cwd, *args):
    return subprocess.run([sys.executable, str(ENGINE), "--session", "t", *args], cwd=str(cwd),
                          capture_output=True, text=True, env=CLEAN, timeout=300)


with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)

    # F1: a Windows layout with Git's cmd folder on PATH, no bash on PATH, and no WSL.
    git_bash = tmp / "Git" / "bin" / "bash.exe"
    git_bash.parent.mkdir(parents=True)
    git_bash.write_text("")
    probe = f"""
import sys, shutil
sys.path.insert(0, {str(HARNESS)!r})
import ledger
ledger.os.name = "nt"
ledger.shutil.which = lambda n: {{"git.exe": {str(tmp / "Git" / "cmd" / "git.exe")!r}}}.get(n)
print(ledger.resolve_shell("auto"))
print(ledger.resolve_shell("bash"))
"""
    r = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, timeout=60)
    lines = r.stdout.strip().splitlines()
    want = f"('bash', [{str(git_bash)!r}, '-lc'])"
    check("auto finds Git Bash when bash is not on PATH and there is no WSL",
          len(lines) == 2 and lines[0] == want, r.stdout + r.stderr)
    check("a frozen bash gate finds Git Bash the same way",
          len(lines) == 2 and lines[1] == want, r.stdout + r.stderr)

    # NIT: a gate written inside the template's comment is named as the reason.
    root = make_repo(tmp / "comment")
    (root / "p.txt").write_text("build the release file for the next build\n")
    eng(root, "open", "--title", "c", "--prompt-file", "p.txt")
    r = eng(root, "declare")
    check("no gates names the template comment as a likely cause",
          r.returncode != 0 and "comment" in r.stderr, r.stderr)

    # NIT: an EXPECT that is a whole different word from the CHECK's is not a tautology.
    root = make_repo(tmp / "taut")
    (root / "p.txt").write_text("build the release file for the next build\n")
    eng(root, "open", "--title", "t", "--prompt-file", "p.txt")
    path = root / ".ledger" / "t.md"
    (root / "tests").mkdir()
    (root / "tests" / "hooks_test.py").write_text("print('ok')\n")
    gate = ("- [ ] G1 HOLD: the hooks test says ok\n"
            f"      CHECK: {sys.executable} tests/hooks_test.py\n"
            "      EXPECT: /ok/")
    text = path.read_text().replace("-->\n\n## Asks", "-->\n" + gate + "\n\n## Asks", 1)
    path.write_text(re.sub(r"(?m)^(A\d+ .*) -> \?$", r"\1 -> G1", text))
    r = eng(root, "declare")
    check("EXPECT /ok/ is not refused because the CHECK names hooks_test.py",
          "tautology" not in r.stdout, r.stdout)

# F2: a COVERED head reads as gaps only on an outright contradiction.
sys.path.insert(0, str(HARNESS))
import ledger
for v in ["COVERED: all 4 asks are covered, nothing missing", "COVERED: no asks are uncovered",
          "COVERED: each ask has at least one gate; nothing is left uncovered",
          "COVERED: no ask lacks a gate", "COVERED: none missing", "COVERED: every ask maps to a gate",
          "COVERED: A1 to A3 covered, nothing in the prompt is uncovered"]:
    check(f"clean: {v}", not ledger.audit_found_gaps("subagent: " + v))
for v in ["Covered: A1, A2. Not covered: A3 (changelog)", "COVERED except A3, which no gate covers",
          "COVERED: A3 lacks a gate", "COVERED but A3 has no gate", "GAPS FOUND: A2"]:
    check(f"gaps: {v}", ledger.audit_found_gaps("subagent: " + v))

# F3: the bare word, then the value.
from history import scrub
for s, secret in [("ssh root@10.0.0.5 password Hunter2!", "Hunter2"),
                  ("username admin password Winter2026", "Winter2026")]:
    check(f"scrubbed: {s}", secret not in scrub(s), scrub(s))
for s in ["password reset flow", "the password field", "password manager 1Password",
          "password123 is weak", "password policy needs 12 chars", "password protected zip v2"]:
    check(f"survives: {s}", scrub(s) == s, scrub(s))

finish("the tenth review's findings stay fixed")
