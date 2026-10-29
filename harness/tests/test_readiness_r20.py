#!/usr/bin/env python3
"""The twentieth readiness review's findings stay fixed.

SHOULD FIX: BOOTSTRAP had the canary deleted from the raw extract alone, which turned its
own line count gate red for good; the hook wiring snippets left the script path unquoted,
so a path with a space made Python exit 2, which Claude Code reads as a block on every
tool call and stop; and `open` over another task's declared ledger told the agent to close
that ledger instead of naming its own.
NITs: one transcript under two project folders was mined twice; one bad byte crashed
verify.py; "COVERED: A2 needs no gate" read as gaps; and three BOOTSTRAP lines.

  python3 harness/tests/test_readiness_r20.py
    -> "ok: the twentieth review's findings stay fixed", exit 0
"""
import datetime, json, os, pathlib, re, shutil, subprocess, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _ledgerkit import ENGINE, HARNESS, check, declared, file_check, finish, make_repo

ROOT = HARNESS.parent
CLEAN = {k: v for k, v in os.environ.items()
         if k not in ("LEDGER_DIR", "CLAUDE_SESSION_ID", "CLAUDE_CODE_SESSION_ID",
                      "CLAUDE_PROJECT_DIR", "LEDGER_STOP_GATE_ACTIVE", "LEDGER_DEPTH")}
sys.path.insert(0, str(HARNESS))
import history, ledger

with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)

    # SHOULD FIX 2: the documented wiring works from a path with a space in it.
    spaced = tmp / "My Vault"
    shutil.copytree(HARNESS, spaced / "harness", ignore=shutil.ignore_patterns("__pycache__", "tests"))
    repo = make_repo(tmp / "repo")
    for hook in ("stop-gate", "lock-guard"):
        doc = (HARNESS / "adapters" / "claude-code" / "hooks" / f"{hook}.py").read_text(encoding="utf-8")
        m = re.search(r'"command": "((?:[^"\\]|\\.)*)"', doc)
        cmd = json.loads('"' + m.group(1) + '"') if m else ""
        cmd = re.sub(r"/ABS/PATH/TO/\w+", str(spaced), cmd).replace("python3", sys.executable, 1)
        payload = {"session_id": "t", "cwd": str(repo), "hook_event_name": "Stop",
                   "tool_name": "Bash", "tool_input": {"command": "ls"}}
        r = subprocess.run(["/bin/bash", "-c", cmd], input=json.dumps(payload), capture_output=True,
                           text=True, cwd=str(repo), env=CLEAN, timeout=120)
        check(f"the {hook} wiring snippet starts from a path with a space", r.returncode == 0, (cmd, r.stderr[-200:]))

    # SHOULD FIX 3: open over another task's declared ledger points at --session.
    root = make_repo(tmp / "second")
    declared(root, [("PROVE", "the release file exists", file_check("release.txt"))], session="session")
    (root / "p2.txt").write_text("build the notes file for the next build\n")
    r = subprocess.run([sys.executable, str(ENGINE), "--session", "session", "open", "--title", "two",
                        "--prompt-file", "p2.txt"], cwd=str(root), capture_output=True, text=True, env=CLEAN)
    check("open over a declared ledger leads with --session, not with closing it",
          r.returncode != 0 and "--session <new id>" in r.stderr and "--force close" not in r.stderr, r.stderr)

    # NIT: one transcript under two project folders is mined once.
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    line = json.dumps({"type": "user", "timestamp": ts, "message": {"content": "keep commits small and reversible"}})
    for folder in ("a", "b"):
        (tmp / "projects" / folder).mkdir(parents=True)
        (tmp / "projects" / folder / "s.jsonl").write_text(line + "\n")
    cfg = {"every_days": 0, "workdir": str(tmp / "work"), "start_from": "2020-01-01",
           "sources": [{"type": "claude-code", "path": str(tmp / "projects")}]}
    (tmp / "mining.json").write_text(json.dumps(cfg))
    subprocess.run([sys.executable, str(HARNESS / "history.py"), "--config", str(tmp / "mining.json")],
                   capture_output=True, text=True, timeout=120)
    got = [json.loads(l)["text"] for f in (tmp / "work").glob("new-*.jsonl") for l in f.read_text().splitlines() if l]
    check("a message found under two project folders is mined once", got == ["keep commits small and reversible"], got)

    # NIT: one bad byte is a reported failure, not a crash.
    vault = tmp / "vault"
    (vault / "heuristics").mkdir(parents=True)
    (vault / "heuristics" / "odd.md").write_bytes(b"caf\xe9 au lait\n")
    probe = (f"import sys; sys.path.insert(0, {str(HARNESS)!r}); import verify; "
             "verify.check_line_endings(); verify.check_dashes(); verify.check_links(); print('FAILS', verify.fail)")
    r = subprocess.run([sys.executable, "-c", probe], cwd=str(vault), capture_output=True, text=True, timeout=60)
    check("verify reports a non UTF-8 note instead of crashing",
          "not valid UTF-8" in r.stdout and "Traceback" not in r.stderr, r.stdout + r.stderr[-300:])

check("'COVERED: A2 needs no gate' reads as covered", not ledger.audit_found_gaps("subagent: COVERED: A2 needs no gate"))
check("'COVERED: A3 has no gate' still reads as gaps", ledger.audit_found_gaps("subagent: COVERED: A3 has no gate"))

caps = (HARNESS / "adapters" / "claude-code" / "CAPABILITIES.md").read_text(encoding="utf-8")
check("CAPABILITIES says an unquoted path with a space blocks everything", "exit 2" in caps)
boot = ROOT / "BOOTSTRAP.md"
if boot.exists():
    b = boot.read_text(encoding="utf-8")
    check("BOOTSTRAP deletes the canary from both extracts", "delete the canary line from both the raw and the scrubbed extract" in b)
    check("BOOTSTRAP quotes hook paths on every OS", "in double quotes on every OS" in b)
    check("BOOTSTRAP records the awaited audit after declare", "once you have declared the gate below" in b)
    check("BOOTSTRAP keeps CLAUDE.local.md out of git locally", "keep it out of git with `.git/info/exclude`" in b)
    check("BOOTSTRAP says which adapters have no hooks folder", "Codex and Antigravity have none" in b)

finish("the twentieth review's findings stay fixed")
