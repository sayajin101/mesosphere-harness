#!/usr/bin/env python3
"""Issues 1 to 8, filed after the first public release, stay fixed.

Each issue is split into the parts it named, and each part is its own case, labelled
#1a to #8e, so one passing case cannot carry a whole issue.

  1  mining kept image placeholders (a) and pasted terminal output (b) as the owner's words
  2  scrubber missed prose secrets (a), "set the env var X_PASSWORD to" (b), and a bare
     user:password with no host (c)
  3  BOOTSTRAP implied the Claude Code hooks work in other engines (a); the Cursor and
     Gemini wiring left the script path unquoted (b)
  4  BOOTSTRAP setup gaps: no push -u (a), path C's example gate declared green (b), path
     A editing the shared .gitignore (c), __pycache__ never ignored (d)
  5  ledger refusals: a literal path EXPECT was misread (a), "0 failures" matched
     "10 failures" (b), the example ledger's lock reads LOCK BROKEN unexplained (c)
  6  lock guard false positives: .ledger-proof (a), a commit message (b), tar --exclude
     (c), git rm --cached (d)
  7  verify.py: a passing selftest was a warning (a); a new signed page passed (b)
  8  docs: the stop gate docstring (a), where python.exe lives (b), score.py needs
     --scenarios to refuse a skip (c), an after setup pointer (d), Cursor and Linux (e)

Parts that live in files only the public repo has (BOOTSTRAP.md, the README, the eval
template, examples/) report "n/a here" in a repo without them.

  python3 harness/tests/test_issues_1_to_8.py
    -> "ok: issues 1 to 8 stay fixed", exit 0
"""
import datetime, json, os, pathlib, re, shutil, subprocess, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _ledgerkit import GUARD, HARNESS, check, declared, file_check, finish, make_repo

ROOT = HARNESS.parent
CLEAN = {k: v for k, v in os.environ.items()
         if k not in ("LEDGER_DIR", "CLAUDE_SESSION_ID", "CLAUDE_CODE_SESSION_ID",
                      "CLAUDE_PROJECT_DIR", "LEDGER_STOP_GATE_ACTIVE", "LEDGER_DEPTH")}
sys.path.insert(0, str(HARNESS))
import history, ledger, verify


def read(rel):
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else None


def na(label, rel):
    check(f"{label} n/a here: no {rel} in this repo", True)


def guard(root, cmd):
    r = subprocess.run([sys.executable, str(GUARD)], input=json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": str(root)}),
        capture_output=True, text=True, cwd=str(root), env=CLEAN, timeout=60)
    return '"deny"' in r.stdout


def lint(expect, declaring=True):
    """The refusals at declare, or with declaring=False the ones a declared gate meets again."""
    g = ledger.Gate(0, False, "G1", "PROVE", "x")
    g.check, g.expect = f"{sys.executable} t.py", expect
    try:
        return " ".join(ledger.lint(g, declaring=declaring))
    except TypeError:                     # before the fix lint took no such argument
        return " ".join(ledger.lint(g))


def mine(tmp, text, extra=None):
    """Run history.py end to end over one message and return what it kept."""
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    proj = tmp / "projects" / "p"
    proj.mkdir(parents=True)
    (proj / "s.jsonl").write_text(json.dumps(
        {"type": "user", "timestamp": ts, "message": {"content": text}}) + "\n")
    cfg = {"every_days": 0, "workdir": str(tmp / "work"), "start_from": "2020-01-01",
           "sources": [{"type": "claude-code", "path": str(tmp / "projects")}], **(extra or {})}
    (tmp / "mining.json").write_text(json.dumps(cfg))
    subprocess.run([sys.executable, str(HARNESS / "history.py"), "--config", str(tmp / "mining.json")],
                   capture_output=True, text=True, timeout=120, env=CLEAN)
    return "\n".join(json.loads(l)["text"] for f in (tmp / "work").glob("new-*.jsonl")
                     for l in f.read_text().splitlines() if l)


# 1a: an image placeholder is an attachment, not words.
out = history.owner_text({"type": "user", "message": {"content": "[Image #1] why is this button grey [Image #2]"}})
check("#1a image placeholders are dropped from the owner's words", out == "why is this button grey", out)

# 1b: a pasted terminal log is not mined; the question around it is, and the config can turn it off.
LOG = ("why does the deploy fail now?\n"
       "2026-10-30 10:11:12 ERROR connection refused\n"
       "  at Pool.connect (pool.js:12:3)\n"
       "  at main (index.js:4:1)\n"
       "Traceback (most recent call last):\n"
       "  File \"deploy.py\", line 3, in <module>\n"
       "ConnectionError: refused\n"
       "fix it without touching the tests please")
with tempfile.TemporaryDirectory() as tmp:
    got = mine(pathlib.Path(tmp), LOG)
with tempfile.TemporaryDirectory() as tmp:
    kept = mine(pathlib.Path(tmp), LOG, {"drop_pasted_logs": False})
check("#1b a pasted log is not mined, the owner's words around it are, and drop_pasted_logs: false keeps it",
      "connection refused" not in got and "Traceback" not in got
      and "why does the deploy fail now?" in got and "without touching the tests" in got
      and "Traceback" in kept, (got, kept))
PROSE = ["2026-11-01 10:00 call Sam about the price\n2026-11-02 09:30 send Sam the deck\n"
         "2026-11-03 14:00 decide on pricing with Sam",
         "Q1 2025: 1,234,567 (+12.5%) vs 1,100,000\nQ2 2025: 1,301,000 (+5.4%) vs 1,234,567\n"
         "Q3 2025: 1,402,000 (+7.8%) vs 1,301,000",
         "# keep the price\n# drop the add on\n# ship on Friday"]
check("#1b a typed schedule, a column of figures and # notes are not taken for a log",
      all(history.strip_pasted_logs(p) == p for p in PROSE) if hasattr(history, "strip_pasted_logs") else False)

# 2: scrubber shapes, with ordinary sentences left alone.
for label, s, secret in [("#2a", "root pass is changeme123", "changeme123"),
                         ("#2a", "the wifi psk is SuperSecret99", "SuperSecret99"),
                         ("#2a", "my otp is 492817", "492817"),
                         ("#2b", "set the env var DB_PASSWORD to hunter2x", "hunter2x"),
                         ("#2c", "log in as admin:secret123 for now", "secret123")]:
    check(f"{label} scrubbed: {s}", secret not in history.scrub(s), history.scrub(s))
for label, s in [("#2a", "the pass is green and the otp app is open"), ("#2a", "my exam pass is 10/10"),
                 ("#2a", "my bus pass is 45.00 a month"), ("#2c", "see the admin:settings page"),
                 ("#2c", "meet at 10:30 about the user:42 record"), ("#2c", "use the ubuntu:22.04 image"),
                 ("#2c", "pin postgres:16.4 and node:20-alpine"), ("#2c", "the admin:v2.0.1 release on sa:1433")]:
    check(f"{label} left alone: {s}", history.scrub(s) == s, history.scrub(s))

# 3a: the Claude Code hooks are not for other engines as they are.
boot = read("BOOTSTRAP.md")
if boot is None:
    na("#3a", "BOOTSTRAP.md")
else:
    check("#3a BOOTSTRAP says the stop and guard hooks speak Claude Code's protocol only",
          "speak Claude Code's hook protocol only" in boot)

# 3b: the Cursor and Gemini wiring works from a vault path with a space in it.
with tempfile.TemporaryDirectory() as tmp:
    spaced = pathlib.Path(tmp) / "My Vault"
    shutil.copytree(HARNESS, spaced / "harness", ignore=shutil.ignore_patterns("__pycache__", "tests"))
    for engine in ("cursor", "gemini"):
        doc = (HARNESS / "adapters" / engine / "hooks" / "session-start.py").read_text(encoding="utf-8")
        m = re.search(r'"command":\s*"((?:[^"\\]|\\.)*)"', doc)
        cmd = json.loads('"' + m.group(1) + '"') if m else ""
        cmd = re.sub(r"/ABS/PATH/TO/\w+", str(spaced), cmd).replace("python3", sys.executable, 1)
        r = subprocess.run(["/bin/bash", "-c", cmd], input="{}", capture_output=True, text=True,
                           cwd=tmp, env=CLEAN, timeout=60)
        check(f"#3b the {engine} wiring snippet starts from a path with a space", r.returncode == 0,
              (cmd, r.stderr[-200:]))

# 4: BOOTSTRAP setup gaps.
if boot is None:
    for label in ("#4a", "#4b", "#4c"):
        na(label, "BOOTSTRAP.md")
else:
    check("#4a phase 0 pushes with an upstream, whatever the branch is called",
          "`git push -u origin HEAD`" in boot and "push -u origin main" not in boot)
    path_c = boot.split("## Path C", 1)[-1].split("\n## ", 1)[0]
    declare_at = path_c.find("declare the ledger there BEFORE you delete")
    delete_at = path_c.find("delete the two `example-` scenarios")
    check("#4b path C says to declare the example gate before it says to delete the examples",
          -1 < declare_at < delete_at, (declare_at, delete_at))
    check("#4c path A keeps its lines out of the shared .gitignore by default",
          "to the target repo's `.gitignore`" not in boot
          and "out of git with `.git/info/exclude`, the same way as step 3" in boot)
gi = read("eval-template/.gitignore")
if gi is None or boot is None:
    na("#4d", "eval-template/.gitignore")
else:
    check("#4d __pycache__ is ignored in path A and in the eval template",
          "__pycache__/" in gi and "`__pycache__/`" in boot)

# 5a and 5b: EXPECT refusals that say what is wrong.
check("#5a a literal path EXPECT is refused as a path, an unknown flag as a flag, not as a split regex",
      "literal path" in lint("/tmp/out") and "literal path" in lint("/tmp/out.txt")
      and "flags 'm'" in lint("/ok/m") and "never closes" in lint("/^0")
      and lint("/^ok$/") == "" and lint("/abc/i") == "")
check("#5b a count at the edge of a literal EXPECT is refused, other numbers are not",
      "larger number" in lint("0 failures") and "larger number" in lint("errors: 1")
      and all(lint(e) == "" for e in ("/^0 failures/", "ALL 3 PASSED", "200 OK", "Python 3.12", "exit code 0", "node v20")))
check("#5b the new refusals apply at declare only, so an earlier ledger's gates stay met",
      lint("0 failures", declaring=False) == "" and "literal path" not in lint("/tmp/out", declaring=False))
ex = read("examples/ledger-example.md")
if ex is None:
    na("#5c", "examples/ledger-example.md")
else:
    check("#5c the example ledger says its lock is made up", "Illustration only" in ex and "LOCK BROKEN" in ex)

# 6: guard false positives, each beside a write it must still refuse.
with tempfile.TemporaryDirectory() as tmp:
    root = make_repo(pathlib.Path(tmp) / "g")
    declared(root, [("PROVE", "the release file exists", file_check("release.txt"))])
    # Each hostile partner is a write the narrowing could have let through (review of this fix).
    for label, honest, hostile in [
            ("#6a", ["rm -rf .ledger-proof"], ["rm -rf .ledger", "rm -rf .ledger."]),
            ("#6b", ["git commit -m 'ignore .ledger and install the hooks'",
                     'grep -n "tar\\|rm --cached" .ledger/t.md'],
             ["rm '.ledger/my file'", 'echo "$(rm -rf .ledger) done"', 'git commit -m "$(rm -rf .ledger) msg"',
              'eval "rm -rf .ledger"', 'timeout 9 bash -lc "rm -rf .ledger"', 'xargs perl -e "unlink q(.ledger/t.md)"',
              'git -c alias.z="!rm -rf .ledger" z', 'parallel "rm {}" ::: .ledger/t.md',
              'echo "rm -rf .ledger" | sh', 'printf "mv .ledger/t.md .ledger/closed/\\n" | bash -s',
              'rg --pre "rm -rf .ledger" x .']),
            ("#6c", ["tar czf out.tgz --exclude=.ledger ."],
             ["tar xf a.tgz -C .ledger", "rsync -a --delete --delete-excluded --exclude=.ledger empty/ ./"]),
            ("#6d", ["git rm -r --cached .ledger"],
             ["git rm -r .ledger", "git rm --cached x $(rm -rf .ledger)", "git rm --cached x `rm -rf .ledger`"])]:
        let = [c for c in honest if guard(root, c)]
        missed = [c for c in hostile if not guard(root, c)]
        check(f"{label} allowed: {honest[0]} (and {len(hostile)} writes still refused)",
              not let and not missed, {"refused": let, "let through": missed})

# 7a: a passing selftest is reported as a pass, not a warning.
with tempfile.TemporaryDirectory() as tmp:
    for name in ("selftest.sh", "selftest.ps1"):
        (pathlib.Path(tmp) / name).write_text("exit 0\n")
    verify.warn.clear()
    verify.fail.clear()
    verify.check_wrappers(tmp, False)
    if sys.platform in verify.WRAPPER_SUITES:
        check("#7a a passing wrapper suite is not counted as a warning",
              not any(w.endswith(": passed") for w in verify.warn)
              and any(p.endswith(": passed") for p in getattr(verify, "passed", [])),
              (verify.warn, verify.fail))
    else:
        na("#7a", f"wrapper suite for {sys.platform}")

# 7b: a new page that arrives signed is refused; a new unverified page is not.
with tempfile.TemporaryDirectory() as tmp:
    repo = pathlib.Path(tmp) / "v"
    (repo / "heuristics").mkdir(parents=True)
    git = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a],
                                    cwd=str(repo), capture_output=True, text=True)
    git("init", "-q")
    (repo / "README.md").write_text("# vault\n")
    (repo / "heuristics" / "old.md").write_text("---\nstatus: mined-unverified\n---\n# an old draft\n\nits body\n")
    (repo / "heuristics" / "kept.md").write_text("---\nstatus: signed\n---\n# signed by the owner\n\nits body\n")
    git("add", "-A")
    git("commit", "-qm", "base")
    # An honest move of a page already signed is not a new signature.
    (repo / "decisions").mkdir()
    git("mv", "heuristics/kept.md", "decisions/kept.md")
    (repo / "heuristics" / "new.md").write_text("---\nstatus: signed\n---\n# a new page\n")
    (repo / "heuristics" / "draft.md").write_text("---\nstatus: mined-unverified\n---\n# a draft\n")
    git("add", "-A")
    # Untracked, as an agent's new page is mid task, and a rename that flips the status.
    (repo / "heuristics" / "loose.md").write_text("---\nstatus: signed\n---\n# never added\n")
    git("mv", "heuristics/old.md", "heuristics/moved.md")
    (repo / "heuristics" / "moved.md").write_text("---\nstatus: signed\n---\n# an old draft\n\nits body\n")
    git("add", "heuristics/moved.md")
    here = os.getcwd()
    os.chdir(repo)
    try:
        verify.fail.clear()
        verify.check_diff("HEAD")
    finally:
        os.chdir(here)
    flagged = {n for n in ("new.md", "loose.md", "moved.md", "draft.md", "kept.md")
               if any(n in f and "signed" in f for f in verify.fail)}
    check("#7b a new page arriving signed is refused, staged, untracked or renamed; a new draft and a "
          "signed page moved as it was are not",
          flagged == {"new.md", "loose.md", "moved.md"}, verify.fail)
verify.warn.clear()
verify.fail.clear()

# 8a: the stop gate's docstring says what it enforces.
doc = (HARNESS / "adapters" / "claude-code" / "hooks" / "stop-gate.py").read_text(encoding="utf-8")
check("#8a the stop gate docstring says it enforces every open ledger, not only the session's",
      "any open ledger" in doc and "while the session's ledger" not in doc)

# 8b to 8e: the README.
readme = read("README.md")
if readme is None or "## Engine support" not in readme:
    for label in ("#8b", "#8c", "#8d", "#8e"):
        na(label, "public README.md")
else:
    check("#8b the README says where python.exe lives and how to list it", "py -0p" in readme
          and "%LOCALAPPDATA%\\Programs\\Python\\" in readme)
    check("#8c the README says score.py refuses a skip only with --scenarios",
          "given `--scenarios`" in readme)
    check("#8d the README points to OPERATING.md for after setup",
          "After setup, your vault's `OPERATING.md`" in readme)
    check("#8e the README covers Cursor's hook file and Linux hook paths",
          "`~/.cursor/hooks.json`" in readme and "`command -v python3`" in readme)

finish("issues 1 to 8 stay fixed")
