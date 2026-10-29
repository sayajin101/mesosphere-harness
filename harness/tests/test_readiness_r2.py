#!/usr/bin/env python3
"""The second readiness review's findings stay fixed.

It forged a success with engine commands alone (a renamed LEDGER_DIR or a fake bash first
on PATH, then `close`, which took the ledger out of the stop gate's sight), found that
the suite and the stop gate recursed into a fork bomb, forged checks from ~/.bash_profile,
turned a declared ledger back into a draft by deleting three things, got ten credential
shapes past the scrubber, and closed over an audit saying "A3 is not covered".

  python3 harness/tests/test_readiness_r2.py
    -> "ok: the second review's findings stay fixed", exit 0
"""
import importlib.util, json, os, pathlib, re, subprocess, sys, tempfile, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _ledgerkit import (ENGINE, HARNESS, STOP, blocked, check, declared, file_check, finish,
                        forge_tick, guard, led, make_repo, stop)

ROOT = HARNESS.parent
CLEAN = {k: v for k, v in os.environ.items()
         if k not in ("LEDGER_DIR", "CLAUDE_SESSION_ID", "CLAUDE_CODE_SESSION_ID",
                      "CLAUDE_PROJECT_DIR", "LEDGER_STOP_GATE_ACTIVE")}


def eng(cwd, *args, **env):
    return subprocess.run([sys.executable, str(ENGINE), "--session", "t", *args], cwd=str(cwd),
                          capture_output=True, text=True, env={**CLEAN, **env}, timeout=300)


def one(tmp, name):
    root = make_repo(pathlib.Path(tmp) / name)
    return root, declared(root, [("PROVE", "the release file exists", file_check("release.txt"))])


with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)

    # 1a. A renamed LEDGER_DIR no longer moves the checks into a decoy folder.
    root, path = one(tmp, "decoy")
    decoy = tmp / "decoy-folder"
    decoy.mkdir()
    (decoy / "release.txt").write_text("decoy")
    r = eng(decoy, "--file", str(path), "run", LEDGER_DIR="x")
    check("run with LEDGER_DIR renamed judges the repo, not the caller's folder", r.returncode != 0, r.stdout)
    r = eng(decoy, "--file", str(path), "close", LEDGER_DIR="x")
    check("close with LEDGER_DIR renamed refuses", r.returncode != 0 and path.exists(), r.stdout)

    # 1b. A fake bash first on PATH is not the shell checks run in.
    root, path = one(tmp, "fakebash")
    fake = tmp / "fakebin"
    fake.mkdir()
    (fake / "bash").write_text("#!/bin/sh\nexit 0\n")
    (fake / "bash").chmod(0o755)
    if os.name != "nt":
        r = eng(root, "run", PATH=f"{fake}{os.pathsep}{os.environ['PATH']}")
        check("a fake bash first on PATH does not pass a check", r.returncode != 0, r.stdout)

    # 1c. A ledger closed as met is not judged again: the re-judge added for this finding
    # blocked honest work (BOOTSTRAP's proof ledger, other tasks' point in time checks),
    # so a close in a doctored environment is a documented limit (LEDGER.md section 2).
    root, path = one(tmp, "reclose")
    (root / "release.txt").write_text("v1")
    eng(root, "run")
    r = eng(root, "close")
    check("an honest close succeeds", r.returncode == 0, r.stdout + r.stderr)
    (root / "release.txt").unlink()
    check("a closed ledger whose work later changed does not block unrelated work",
          not blocked(stop(root)), stop(root))

    # 2. No recursion: a stop gate nested in a stop gate's check allows at once, the outer
    # gate marks its status run, and a timed out check's whole process group dies.
    root = make_repo(tmp / "nested")
    (root / "seen.txt").write_text("")
    probe = f"{sys.executable} -c \"import os;open('seen.txt','a').write(os.environ.get('LEDGER_STOP_GATE_ACTIVE','-'))\""
    declared(root, [("HOLD", "the probe runs", probe)])
    eng(root, "run")
    (root / "seen.txt").write_text("")
    stop(root)
    check("the stop gate marks the status run it starts", "1" in (root / "seen.txt").read_text(),
          (root / "seen.txt").read_text())
    res = subprocess.run([sys.executable, str(STOP)], input=json.dumps({"session_id": "t", "cwd": str(root)}),
                         capture_output=True, text=True, cwd=str(root), timeout=60,
                         env={**CLEAN, "LEDGER_ENGINE": str(ENGINE), "LEDGER_STOP_GATE_ACTIVE": "1"})
    check("a stop gate started inside a stop gate's check allows at once", res.stdout.strip() == "", res.stdout)
    kit = (HARNESS / "tests" / "_ledgerkit.py").read_text()
    check("the test kit never hands CLAUDE_PROJECT_DIR to a hook", kit.count('"CLAUDE_PROJECT_DIR"') >= 2)
    spec = importlib.util.spec_from_file_location("ledger_engine", ENGINE)
    eng_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(eng_mod)
    pidfile = tmp / "grandchild.pid"

    class G:
        shell = "bash"
        check = (f"{sys.executable} -c \"import subprocess,sys,time;"
                 f"p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(120)']);"
                 f"open(r'{pidfile}','w').write(str(p.pid));time.sleep(120)\"")
        expect = None
    if os.name != "nt":
        ok, detail, why = eng_mod.run_check(G, timeout=3)
        time.sleep(1)
        pid = int(pidfile.read_text()) if pidfile.exists() else None
        alive = pid is not None and subprocess.run(["kill", "-0", str(pid)], capture_output=True).returncode == 0
        check("a timed out check's grandchild is killed too", why == "timeout" and pid and not alive, (why, pid, alive))

    # 3. Nothing in the owner's profile runs before a check.
    root, path = one(tmp, "profile")
    home = tmp / "home"
    home.mkdir()
    for f in (".bash_profile", ".bashrc", ".profile"):
        (home / f).write_text("test() { return 0; }\n[ () { return 0; }\n")
    (home / "env.sh").write_text("test() { return 0; }\n")
    root2 = make_repo(tmp / "profile2")
    declared(root2, [("PROVE", "the release file exists", "test -f release.txt")])
    r = eng(root2, "run", HOME=str(home), BASH_ENV=str(home / "env.sh"), ENV=str(home / "env.sh"))
    check("a profile or BASH_ENV redefining `test` does not pass a check", r.returncode != 0, r.stdout)

    # 4. Stripping the Lock line, every BASELINE and the declare log line is still broken.
    root, path = one(tmp, "strip")
    forge_tick(path, "G1")
    t = path.read_text()
    t = re.sub(r"(?m)^Lock: .*$", "Lock: open", t)
    t = re.sub(r"(?m)^\s+BASELINE:.*\n", "", t)
    t = re.sub(r"(?m)^\S+ \S+ declared \d+ gates?, lock .*\n", "", t)
    path.write_text(t)
    check("a declared ledger stripped back to a draft still blocks the stop gate", blocked(stop(root)), stop(root))
    r = eng(root, "--force", "open", "--title", "again")
    check("and --force open still refuses it", r.returncode != 0 and path.exists(), r.stdout + r.stderr)

    # 6. An audit naming a gap in plain words is a gaps verdict. Since round 9 a verdict
    # must open with COVERED or GAPS FOUND, so the plain words follow a COVERED head.
    root, path = one(tmp, "audit")
    (root / "release.txt").write_text("v1")
    eng(root, "run")
    eng(root, "audit", "subagent", "COVERED: A3 (rename the file) is not covered by any gate")
    r = eng(root, "close")
    check("close refuses when the audit says an ask is not covered", r.returncode != 0 and path.exists(), r.stdout)

    # Guard: interpreters behind env/command, and code fed through a here-document.
    root, path = one(tmp, "guard")
    for cmd in ["env python3 -c \"open('.ledger/t.md','a').write('x')\"",
                "command python3 -c \"open('.ledger/t.md','a').write('x')\"",
                "python3 - <<'EOF'\nopen('.ledger/t.md','a').write('x')\nEOF"]:
        check(f"guard refuses: {cmd.splitlines()[0]}", guard(root, "Bash", {"command": cmd}))
    check("guard allows a heredoc that only mentions the folder to cat",
          not guard(root, "Bash", {"command": "cat <<'EOF'\nsee .ledger/t.md\nEOF"}))

    # NIT 9: map before declare is a normal step, not a failure.
    root = make_repo(tmp / "map")
    (root / "p.txt").write_text("build the release file\n")
    eng(root, "open", "--title", "m", "--prompt-file", "p.txt")
    lp = root / ".ledger" / "t.md"
    lp.write_text(lp.read_text().replace("-->\n\n## Asks", "-->\n- [ ] G1 JUDGE: done\n\n## Asks", 1))
    r = eng(root, "map", "A1", "G1")
    check("map before declare exits 0", r.returncode == 0, r.stdout + r.stderr)
    r = eng(root, "evidence", "G1", "already done")
    check("evidence before declare is refused", r.returncode != 0, r.stdout + r.stderr)

# 5. Ten more credential shapes, and prose that must survive.
sys.path.insert(0, str(HARNESS))
from history import scrub
for s, secret in [("redis-cli -a Hunter2pw", "Hunter2pw"),
                  ("123456789:" + "AAEhBOweik6ad9r_QXMENQjcrGbqCr4K-Ew", "AAEhBOweik6ad9r"),
                  ("machine api.example.com login alice password Hunter2pw", "Hunter2pw"),
                  ("the password for the db is Hunter2pw", "Hunter2pw"),
                  ("wget --http-password Hunter2pw https://x", "Hunter2pw"),
                  ("htpasswd -b .htpasswd alice Hunter2pw", "Hunter2pw"),
                  ("$c = ConvertTo-SecureString 'Hunter2pw' -AsPlainText -Force", "Hunter2pw"),
                  ("echo Hunter2pw | docker login --password-stdin", "Hunter2pw"),
                  ("https://AbCdEfGhIjKl0123@gitlab.example.com/o/r.git", "AbCdEfGhIjKl0123"),
                  ("call (415) 555-0132", "555-0132")]:
    check(f"scrubbed: {s}", secret not in scrub(s), scrub(s))
for s in ["on 2026-10-28 at 10:11 ran 3 tests in 12.5s", "the token is not in the archive",
          "see https://github.com/o/r"]:
    check(f"prose survives: {s}", scrub(s) == s, scrub(s))

# Docs.
ledger_md = (HARNESS / "LEDGER.md").read_text()
check("LEDGER.md has no empty code fence", "```\n```" not in ledger_md)
check("LEDGER.md names a doctored close as a limit", "run `close` in a doctored environment" in ledger_md)
sec = ROOT / "SECURITY.md"
if sec.exists():
    t = sec.read_text()
    check("SECURITY.md keeps every What counts bullet in its list",
          t.index("- Anything that sends vault content") < t.index("Out of scope"))
readme = (ROOT / "README.md").read_text()
if "## What it does not stop" in readme:
    check("README names the six block release", "six blocks in a row" in readme)
boot = ROOT / "BOOTSTRAP.md"
if boot.exists():
    t = boot.read_text()
    check("BOOTSTRAP records the real interpreter path, not a shim", "print(sys.executable)" in t)
    check("BOOTSTRAP says the hook snippets merge into one hooks object", "merged into one `\"hooks\"` object" in t)

finish("the second review's findings stay fixed")
