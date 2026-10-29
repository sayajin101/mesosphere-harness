#!/usr/bin/env python3
"""The twenty-first readiness review's findings stay fixed.

SHOULD FIX: an EXPECT replaces the exit code, so `CHECK: pytest` with `EXPECT: passed`
counted "1 failed, 4 passed" (exit 1) as met. A bare success word is now refused at
declare, and the docs say plainly what EXPECT does.
NITs: phase 6's gate archived the eval score into the vault; a desktop context block in
front of a typed message dropped the whole message; two scrubber shapes; the guard took
`python3 -X utf8 ledger.py` for a write and missed `git stash --all`; the eval template
had no .gitignore; and `map` refused a capital "None:".

  python3 harness/tests/test_readiness_r21.py
    -> "ok: the twenty-first review's findings stay fixed", exit 0
"""
import json, os, pathlib, re, subprocess, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _ledgerkit import ENGINE, GUARD, HARNESS, check, declared, file_check, finish, make_repo

ROOT = HARNESS.parent
CLEAN = {k: v for k, v in os.environ.items()
         if k not in ("LEDGER_DIR", "CLAUDE_SESSION_ID", "CLAUDE_CODE_SESSION_ID",
                      "CLAUDE_PROJECT_DIR", "LEDGER_STOP_GATE_ACTIVE", "LEDGER_DEPTH")}
sys.path.insert(0, str(HARNESS))
import history, ledger


def eng(cwd, *args):
    return subprocess.run([sys.executable, str(ENGINE), "--session", "t", *args], cwd=str(cwd),
                          capture_output=True, text=True, env=CLEAN, timeout=300)


def guard(root, cmd):
    r = subprocess.run([sys.executable, str(GUARD)], input=json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": str(root)}),
        capture_output=True, text=True, cwd=str(root), env=CLEAN, timeout=60)
    return '"deny"' in r.stdout


with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)

    # SHOULD FIX: a test run that prints "1 failed, 4 passed" and exits 1 cannot meet a gate.
    root = make_repo(tmp / "pytest")
    (root / "fake_pytest.py").write_text(
        "import pathlib, sys\n"
        "if not pathlib.Path('done.txt').exists(): print('no tests ran'); sys.exit(5)\n"
        "print('1 failed, 4 passed'); sys.exit(1)\n")
    (root / "p.txt").write_text("make the test suite pass for the new parser\n")
    eng(root, "open", "--title", "tests", "--prompt-file", "p.txt")
    path = root / ".ledger" / "t.md"
    gate = f"- [ ] G1 PROVE: the suite passes\n      CHECK: {sys.executable} fake_pytest.py\n      EXPECT: passed"
    text = path.read_text().replace("-->\n\n## Asks", "-->\n" + gate + "\n\n## Asks", 1)
    path.write_text(re.sub(r"(?m)^(A\d+ .*) -> \?$", r"\1 -> G1", text))
    r = eng(root, "declare")
    check("EXPECT: passed is refused at declare as a bare success word",
          r.returncode != 0 and "bare success word" in r.stdout, r.stdout[-400:])
    for word in ("ok", "/success/", "done"):
        g = ledger.Gate(0, False, "G1", "PROVE", "x")
        g.check, g.expect = f"{sys.executable} fake_pytest.py", word
        check(f"EXPECT {word} is refused", any("bare success word" in b for b in ledger.lint(g)))
    g = ledger.Gate(0, False, "G1", "PROVE", "x")
    g.check, g.expect = "pytest -q", r"/^\d+ passed in /"
    check("an anchored pass line is accepted", not any("bare success word" in b for b in ledger.lint(g)))

    # NIT: the guard knows python -X utf8 ledger.py as the engine, and refuses git stash --all.
    root = make_repo(tmp / "guard")
    declared(root, [("PROVE", "the release file exists", file_check("release.txt"))])
    check("python -X utf8 running the engine is allowed",
          not guard(root, f'{sys.executable} -X utf8 {ENGINE} --file .ledger/t.md evidence G1 "install checked"'))
    check("git stash --all is refused while a ledger is declared", guard(root, "git stash --all"))
    check("a plain git stash is allowed", not guard(root, "git stash"))

    # NIT: map takes "None:" in any case.
    root = make_repo(tmp / "none")
    (root / "p.txt").write_text("build the release file for the next build\n")
    eng(root, "open", "--title", "n", "--prompt-file", "p.txt")
    r = eng(root, "map", "A1", "None: covered by the release work elsewhere")
    check("map accepts a capitalised None: dismissal", "-> None:" in r.stdout, r.stdout + r.stderr)

# NIT: a desktop context block in front of typed words.
out = history.owner_text({"type": "user", "message": {"content":
      '<artifact-view-context id="a">viewing the page</artifact-view-context>\nplease tighten the intro'}})
check("typed words after an artifact context block are kept", out == "please tighten the intro", out)

# NIT: two scrubber shapes.
for s, secret in [("the CI token Ab12Cd34Ef56Gh78Ij90Kl12 expires Friday", "Ab12Cd34"),
                  ("openssl enc -aes-256-cbc -k Hunter22pw -in a.txt", "Hunter22")]:
    check(f"scrubbed: {s[:30]}", secret not in history.scrub(s), history.scrub(s))

# NIT: the eval template ignores a ledger, and phase 6 keeps the score out of evidence.
gi = ROOT / "eval-template" / ".gitignore"
if (ROOT / "eval-template").exists():
    check("the eval template ignores .ledger/", gi.exists() and ".ledger/" in gi.read_text())
boot = ROOT / "BOOTSTRAP.md"
if boot.exists():
    b = boot.read_text(encoding="utf-8")
    check("phase 6's gate keeps the score out of its evidence", "| grep '^coverage:'" in b)
    check("BOOTSTRAP says an EXPECT replaces the exit code", "An `EXPECT` replaces the check's exit code" in b)
ledger_md = (HARNESS / "LEDGER.md").read_text(encoding="utf-8")
check("LEDGER.md says an EXPECT replaces the exit code", "An `EXPECT` replaces the exit code" in ledger_md)

finish("the twenty-first review's findings stay fixed")
