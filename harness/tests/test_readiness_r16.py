#!/usr/bin/env python3
"""The sixteenth readiness review's findings stay fixed.

SHOULD FIX: scrub() kept a credential's name when an earlier rule had already redacted
its value ("token: [REDACTED]"), which BOOTSTRAP's frozen scrub gate counts; history.py
mined Claude Code compaction summaries, model-written, as the owner's own words; and on
Windows a hook decoding stdin with the code page crashed on one byte and failed open.
NITs: the guard refused a real engine call whose evidence said "install"; same day
extracts overwrote each other; a missing scores file printed a traceback; a prompt with
no asks read "no prompt supplied"; two scrubber shapes; and five doc lines.

  python3 harness/tests/test_readiness_r16.py
    -> "ok: the sixteenth review's findings stay fixed", exit 0
"""
import json, os, pathlib, re, subprocess, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _ledgerkit import ENGINE, GUARD, HARNESS, HOOKS, STOP, check, declared, file_check, finish, make_repo

ROOT = HARNESS.parent
CLEAN = {k: v for k, v in os.environ.items()
         if k not in ("LEDGER_DIR", "CLAUDE_SESSION_ID", "CLAUDE_CODE_SESSION_ID",
                      "CLAUDE_PROJECT_DIR", "LEDGER_STOP_GATE_ACTIVE", "LEDGER_DEPTH")}
sys.path.insert(0, str(HARNESS))
import history
from history import scrub

# SHOULD FIX 1: after scrub(), BOOTSTRAP's gate pattern finds nothing, prefixed values included.
GATE = r"""["']?(password|passwd|secret|token|api_?key)["']?\s*[:=]\s*\S+"""
ghp = "ghp" + "_" + "abcdefghijklmnopqrstuvwxyz123456"
sk = "sk" + "-" + "abcdefghijklmnopqrstuvwx"
for s in (f"token: {ghp}", f"secret: {sk}", f'"token": "{ghp}"', '{"password": "canary-not-a-real-secret"}'):
    check(f"the scrub gate finds nothing after scrub(): {s[:24]}", re.search(GATE, scrub(s)) is None, scrub(s))

# SHOULD FIX 2: a compaction summary is not the owner's words.
summary = {"type": "user", "isCompactSummary": True, "isVisibleInTranscriptOnly": True,
           "message": {"content": "This session is being continued from a previous conversation. Summary: ..."}}
check("a compaction summary is skipped", history.owner_text(summary) is None)
bare = {"type": "user", "message": {"content": "This session is being continued from a previous conversation that ran out of context."}}
check("its opening line is skipped even without the flags", history.owner_text(bare) is None)
check("an ordinary owner message still counts",
      history.owner_text({"type": "user", "message": {"content": "keep commits small"}}) == "keep commits small")

with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)

    # SHOULD FIX 3: a byte the Windows code page cannot decode does not crash a hook.
    root = make_repo(tmp / "bytes")
    payload = json.dumps({"session_id": "t", "cwd": str(root), "hook_event_name": "Stop",
                          "transcript_path": "C:\\Users\\\u00c1lvaro\\t.jsonl"}, ensure_ascii=False).encode("utf-8")
    env = {**CLEAN, "PYTHONIOENCODING": "cp1252", "LEDGER_ENGINE": str(ENGINE)}
    for hook in (STOP, GUARD, HOOKS / "session-start.py"):
        r = subprocess.run([sys.executable, str(hook)], input=payload, capture_output=True,
                           cwd=str(root), env=env, timeout=120)
        check(f"{hook.name} reads a UTF-8 payload under a cp1252 locale",
              r.returncode == 0 and b"Traceback" not in r.stderr, r.stderr[-300:])

    # NIT: a real engine call is allowed whatever its evidence text says.
    root = make_repo(tmp / "guard")
    declared(root, [("PROVE", "the release file exists", file_check("release.txt"))])
    cmd = f'{sys.executable} {ENGINE} --file .ledger/t.md evidence G1 "owner ran the install and approved"'
    res = subprocess.run([sys.executable, str(GUARD)], input=json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": str(root)}),
        capture_output=True, text=True, cwd=str(root), env={**CLEAN, "LEDGER_ENGINE": str(ENGINE)}, timeout=60)
    check("the guard allows an engine call whose evidence mentions an install", '"deny"' not in res.stdout, res.stdout)
    res = subprocess.run([sys.executable, str(GUARD)], input=json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": "touch .ledger/t.md"}, "cwd": str(root)}),
        capture_output=True, text=True, cwd=str(root), env={**CLEAN, "LEDGER_ENGINE": str(ENGINE)}, timeout=60)
    check("and still refuses a real write into the folder", '"deny"' in res.stdout, res.stdout)

    # NIT: a prompt with no asks says so, not "no prompt supplied".
    root = make_repo(tmp / "noasks")
    (root / "p.txt").write_text("hello there\n")
    subprocess.run([sys.executable, str(ENGINE), "--session", "t", "open", "--title", "x", "--prompt-file", "p.txt"],
                   cwd=str(root), capture_output=True, env=CLEAN, timeout=60)
    body = (root / ".ledger" / "t.md").read_text()
    check("a prompt with no asks is not called missing", "no prompt supplied" not in body and "no candidate asks" in body)

    # NIT: a missing scores file is a refusal, not a traceback.
    score = ROOT / "eval-template" / "score.py"
    if score.exists():
        r = subprocess.run([sys.executable, str(score), str(tmp / "none.json")], capture_output=True, text=True, timeout=60)
        check("score.py refuses a missing scores file in one line",
              "REFUSED" in r.stdout + r.stderr and "Traceback" not in r.stderr, r.stdout + r.stderr)

# NIT: two more scrubber shapes.
jwt = "eyJ" + "hbGciOiJub25lIn0.eyJzdWIiOiIxMjM0NTY3ODkwIn0."
for s, secret in [("set the api secret to qwErTy12345AsdfG", "qwErTy"), (f"jwt {jwt}", "eyJzdWIi")]:
    check(f"scrubbed: {s[:30]}", secret not in scrub(s), scrub(s))
check("survives: set the timeout to 30", scrub("set the timeout to 30") == "set the timeout to 30")

# NIT: a second extract the same day gets its own name.
src = (HARNESS / "history.py").read_text(encoding="utf-8")
check("history.py names a second same-day extract apart", "%H%M%S" in src and "if out.exists()" in src)

# Docs.
ledger_md = (HARNESS / "LEDGER.md").read_text(encoding="utf-8")
check("LEDGER.md says a CHECK names version-managed tools by absolute path", "names its tools by absolute path" in ledger_md)
boot = ROOT / "BOOTSTRAP.md"
if boot.exists():
    b = boot.read_text(encoding="utf-8")
    check("BOOTSTRAP says the wall proof may block this session too", "audit awaiting-human" in b and "never satisfy G1 yourself" in b)
    check("BOOTSTRAP's checkpoint no longer collides with state.json", "mining-checkpoint.json" in b)
    check("BOOTSTRAP lists the phases as list items", "each written as a `- ` list item" in b)
    check("BOOTSTRAP names every plist placeholder", "__PYTHON__" in b and "__VAULT__" in b)

finish("the sixteenth review's findings stay fixed")
