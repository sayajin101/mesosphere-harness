#!/usr/bin/env python3
"""The fourteenth readiness review's findings stay fixed.

SHOULD FIX: on Windows, verify.py tested `str(p).startswith("raw/")`, which is false for
raw\\x.md, so verbatim evidence in raw/ failed the dash rule and could not be fixed.
NITs: parse_ts dropped odd fraction lengths on Python 3.9; three scrubber phrasings and a
stray "]"; `abandon` on a draft survived declare; `open --file` outside .ledger was never
enforced, without a word; `--force close` printed no FORCED; and five doc lines.

  python3 harness/tests/test_readiness_r14.py
    -> "ok: the fourteenth review's findings stay fixed", exit 0
"""
import os, pathlib, re, subprocess, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _ledgerkit import ENGINE, HARNESS, check, file_check, finish, make_repo

ROOT = HARNESS.parent
CLEAN = {k: v for k, v in os.environ.items()
         if k not in ("LEDGER_DIR", "CLAUDE_SESSION_ID", "CLAUDE_CODE_SESSION_ID",
                      "CLAUDE_PROJECT_DIR", "LEDGER_STOP_GATE_ACTIVE", "LEDGER_DEPTH")}
EM = chr(8212)


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


GATE = ["- [ ] G1 PROVE: the release file exists", f"      CHECK: {file_check('release.txt')}"]

with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)

    # SHOULD FIX: paths rendered the Windows way still exempt raw/ from the dash rule.
    vault = tmp / "vault"
    (vault / "raw" / "interviews").mkdir(parents=True)
    (vault / "raw" / "interviews" / "r1.md").write_text(f"Owner, verbatim: I ship small {EM} always.\n",
                                                        encoding="utf-8")
    probe = f"""
import pathlib, sys
sys.path.insert(0, {str(HARNESS)!r})
import verify
Base = type(pathlib.Path())
class WinStyle(Base):
    # str() the way WindowsPath renders it; the file system still sees the real path.
    def __str__(self): return Base.__str__(self).replace("/", chr(92))
    def __fspath__(self): return Base.__str__(self)
    def as_posix(self): return Base.__str__(self)
real = verify.notes
verify.notes = lambda: (WinStyle(p) for p in real())
verify.check_dashes()
print("FAILS", verify.fail)
"""
    r = subprocess.run([sys.executable, "-c", probe], cwd=str(vault), capture_output=True, text=True, timeout=60)
    check("a dash in raw/ is exempt under Windows style paths",
          r.stdout.strip() == "FAILS []", r.stdout + r.stderr)

    # NIT: abandon refuses a draft, and declare refuses a draft carrying ABANDON.
    root = make_repo(tmp / "abandon")
    path = draft(root, GATE)
    r = eng(root, "abandon", "G1", "not needed")
    check("abandon refuses a gate in an undeclared draft",
          r.returncode != 0 and not re.search(r"(?m)^\s+ABANDON:", path.read_text()), r.stdout + r.stderr)
    root = make_repo(tmp / "abandon-draft")
    path = draft(root, GATE)
    path.write_text(path.read_text().replace(GATE[1], GATE[1] + "\n      ABANDON: given up early"))
    r = eng(root, "declare")
    check("declare refuses a draft gate that carries ABANDON",
          r.returncode != 0 and "ABANDON" in r.stderr, r.stdout + r.stderr)

    # NIT: open --file outside a .ledger folder says it will not be enforced.
    root = make_repo(tmp / "stray")
    (root / "p.txt").write_text("build the release file for the next build\n")
    (root / "notes").mkdir()
    r = eng(root, "--file", str(root / "notes" / "mine.md"), "open", "--title", "x", "--prompt-file", "p.txt")
    check("open --file outside .ledger warns it is advisory only",
          "never see it" in r.stderr, r.stdout + r.stderr)

    # NIT: --force close says FORCED on stdout too.
    root = make_repo(tmp / "forced")
    draft(root, GATE)
    eng(root, "declare")
    eng(root, "audit", "subagent", "COVERED")
    r = eng(root, "--force", "close")
    check("--force close over unmet work prints FORCED", "FORCED close over" in r.stdout, r.stdout)

# NIT: parse_ts on any fraction length, on every Python here, 3.9 included (where the
# bug lived: newer Pythons parse any length themselves).
sys.path.insert(0, str(HARNESS))
import history
pythons = [sys.executable] + [p for p in ("/usr/bin/python3",) if os.path.exists(p)]
for py in pythons:
    r = subprocess.run([py, "-c", f"import sys; sys.path.insert(0, {str(HARNESS)!r}); import history; "
                        "print(all(history.parse_ts(t) for t in ('2026-10-21T11:00:00.5Z', "
                        "'2026-10-21T11:00:00.1234567Z', '2026-10-21T11:00:00.123Z')))"],
                       capture_output=True, text=True, timeout=60)
    check(f"parse_ts reads every fraction length under {py}", r.stdout.strip() == "True", r.stdout + r.stderr)

# NIT: scrubber phrasings, and no stray bracket.
from history import scrub
for s, secret in [("the secret is hunter2", "hunter2"), ("creds are admin/hunter22", "hunter22"),
                  ("heroku key 4f3c2a1b-9d8e-4c7b-a6f5-0e1d2c3b4a59", "4f3c2a1b")]:
    check(f"scrubbed: {s}", secret not in scrub(s), scrub(s))
for s in ["client_secret=GOCSPX-abcdefghijklmnopqrstuv"]:
    check(f"no stray bracket: {s}", "]]" not in scrub(s), scrub(s))
for s in ["request id 4f3c2a1b-9d8e-4c7b-a6f5-0e1d2c3b4a59", "the secret is stored", "the token is valid for 24h"]:
    check(f"survives: {s}", scrub(s) == s, scrub(s))

# Docs.
caps = (HARNESS / "adapters" / "claude-code" / "CAPABILITIES.md").read_text(encoding="utf-8")
provides = caps.split("## Does not provide")[0]
check("the session id bullet sits under Provides", "session id is in the Bash environment" in provides)
boot = ROOT / "BOOTSTRAP.md"
if boot.exists():
    b = boot.read_text(encoding="utf-8")
    check("BOOTSTRAP puts path A's prompt file outside the repo", "prompt file outside the repo" in b)
    check("BOOTSTRAP says to read the setup ledger's Log after the wall proof",
          "afterwards read the ledger's Log" in b)
    check("BOOTSTRAP handles zero forks at the phase 1 selfcheck", "If no forks were found" in b)
    check("BOOTSTRAP gives both review job time bounds", "6900 on Windows" in b)
    check("BOOTSTRAP says how to write a hook path on native Windows", "forward slashes" in b)

finish("the fourteenth review's findings stay fixed")
