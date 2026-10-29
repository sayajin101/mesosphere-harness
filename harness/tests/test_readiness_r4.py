#!/usr/bin/env python3
"""The fourth readiness review's honest-use findings stay fixed.

The stop gate blocked subagents over their parent's ledger, a ledger opened from a
subfolder went unenforced at the root, a `## ` heading in the prompt cut what the blind
auditor saw, `close` on a closed ledger hid it one folder deeper, a check calling the
ledger recursed without bound, and a few common credential shapes got through. The rest
of that review, deliberate forgery with a shell, is a documented class of limit.

  python3 harness/tests/test_readiness_r4.py
    -> "ok: the fourth review's findings stay fixed", exit 0
"""
import json, os, pathlib, re, subprocess, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _ledgerkit import (ENGINE, HARNESS, STOP, blocked, check, declared, file_check, finish,
                        forge_tick, led, make_repo, stop)

ROOT = HARNESS.parent
CLEAN = {k: v for k, v in os.environ.items()
         if k not in ("LEDGER_DIR", "CLAUDE_SESSION_ID", "CLAUDE_CODE_SESSION_ID",
                      "CLAUDE_PROJECT_DIR", "LEDGER_STOP_GATE_ACTIVE", "LEDGER_DEPTH")}


def eng(cwd, *args, **env):
    return subprocess.run([sys.executable, str(ENGINE), "--session", "t", *args], cwd=str(cwd),
                          capture_output=True, text=True, env={**CLEAN, **env}, timeout=300)


with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)

    # F9: a subagent's stop is never blocked by its parent's ledger.
    root = make_repo(tmp / "sub")
    declared(root, [("PROVE", "the release file exists", file_check("release.txt"))])
    res = subprocess.run([sys.executable, str(STOP)],
                         input=json.dumps({"session_id": "t", "cwd": str(root), "hook_event_name": "SubagentStop"}),
                         capture_output=True, text=True, cwd=str(root), timeout=120,
                         env={**CLEAN, "LEDGER_ENGINE": str(ENGINE)})
    check("SubagentStop is allowed over an unmet parent ledger", res.stdout.strip() == "", res.stdout)
    check("Stop still blocks over the same ledger", blocked(stop(root)))
    check("the hook's wiring no longer names SubagentStop as a target",
          '"SubagentStop": [{' not in (HARNESS / "adapters/claude-code/hooks/stop-gate.py").read_text())

    # F4: a ledger opened from a subfolder lives at the repository root.
    root = make_repo(tmp / "subfolder")
    (root / "deep" / "er").mkdir(parents=True)
    (root / "deep" / "er" / "p.txt").write_text("build the release file\n")
    r = eng(root / "deep" / "er", "open", "--title", "s", "--prompt-file", "p.txt")
    check("open from a subfolder creates the ledger at the repo root",
          (root / ".ledger" / "t.md").exists() and not (root / "deep" / "er" / ".ledger").exists(),
          r.stdout + r.stderr)

    # F5: the stored prompt stays whole, headings and code fences included, and none of it
    # parses as contract.
    root = make_repo(tmp / "prompt")
    prompt = ("make the build\n\n## Details\n- [ ] G9 PROVE: pasted gate\n"
              "```\ncode with ## inside\n```\nlast line of the prompt\n")
    (root / "p.txt").write_text(prompt)
    eng(root, "open", "--title", "p", "--prompt-file", "p.txt")
    lp = root / ".ledger" / "t.md"
    lp.write_text(lp.read_text().replace("-->\n\n## Asks", "-->\n- [ ] G1 JUDGE: done\n\n## Asks", 1))
    lp.write_text(re.sub(r"(?m)^(A\d+ .*) -> \?$", r"\1 -> G1", lp.read_text()))
    eng(root, "declare")
    brief = eng(root, "brief").stdout
    check("the brief carries the whole prompt, past a ## heading and a code fence",
          "last line of the prompt" in brief and "## Details" in brief, brief[-400:])
    j = json.loads(eng(root, "--json", "status").stdout.strip().splitlines()[-1])
    check("nothing in the prompt parses as a gate", j["gates"] == 1, j)

    # F2: close refuses a ledger that is already closed.
    root = make_repo(tmp / "reclose")
    path = declared(root, [("PROVE", "the release file exists", file_check("release.txt"))])
    (root / "release.txt").write_text("v1")
    eng(root, "run")
    eng(root, "close")
    done = next((root / ".ledger" / "closed").glob("*.md"))
    r = eng(root, "--file", str(done), "close")
    check("close on an already closed ledger is refused",
          r.returncode != 0 and done.exists() and not (done.parent / "closed").exists(), r.stdout + r.stderr)

    # F7: a check that calls the ledger cannot recurse without bound.
    root = make_repo(tmp / "recurse")
    path = declared(root, [("PROVE", "the status of this very ledger", f"{sys.executable} {ENGINE} --session t status")])
    forge_tick(path, "G1")
    r = eng(root, "--timeout", "60", "status")
    check("a check that runs the ledger's own status stops at the depth limit",
          r.returncode == 1 and "Traceback" not in r.stdout + r.stderr, (r.stdout + r.stderr)[-300:])

    # F1 (cheap part): SHELLOPTS and PS4 never reach a check.
    root = make_repo(tmp / "shellopts")
    declared(root, [("PROVE", "the release file exists", "test -f release.txt")])
    r = eng(root, "run", SHELLOPTS="noexec")
    check("SHELLOPTS=noexec does not pass a check", r.returncode != 0, r.stdout)

    # F8: the archive's file name comes from the scrubbed title.
    root = make_repo(tmp / "title")
    (root / "p.txt").write_text("ship it\n")
    eng(root, "open", "--title", "deploy with password=Hunter2pw", "--prompt-file", "p.txt")
    lp = root / ".ledger" / "t.md"
    lp.write_text(lp.read_text().replace("-->\n\n## Asks", "-->\n- [ ] G1 JUDGE: shipped\n\n## Asks", 1))
    lp.write_text(re.sub(r"(?m)^(A\d+ .*) -> \?$", r"\1 -> G1", lp.read_text()))
    eng(root, "declare")
    eng(root, "evidence", "G1", "shipped by hand")
    eng(root, "audit", "subagent", "COVERED")
    eng(root, "close", "--archive-to", "arch")
    names = [p.name for p in (root / "arch").glob("*.md")]
    check("no secret in the archive's file name", names and not any("hunter2pw" in n.lower() for n in names), names)

sys.path.insert(0, str(HARNESS))
from history import scrub
for s, secret in [("ssh admin:Hunter2Pass@db.example.com", "Hunter2Pass"), ("call 0123456789", "0123456789")]:
    check(f"scrubbed: {s}", secret not in scrub(s), scrub(s))
for s in ["git@github.com:org/repo.git", "pip install a==1.2.3", "at 10:11:12 on 2026-10-29"]:
    check(f"survives: {s}", scrub(s) == s, scrub(s))

# The limits are stated as a class, honestly, in every doc a reader meets first.
ledger_md = (HARNESS / "LEDGER.md").read_text()
check("LEDGER.md states the forgery class and that listing it is a losing game",
      "listing them all is a losing game" in ledger_md)
readme = (ROOT / "README.md").read_text()
if "## What it does not stop" in readme:
    check("README states the forgery class", "Anything that can run shell commands as the owner can forge a pass" in readme)
sec = ROOT / "SECURITY.md"
if sec.exists():
    check("SECURITY.md scopes reports to honest-use bugs", "an honest agent, one not trying to cheat" in sec.read_text())

finish("the fourth review's findings stay fixed")
