#!/usr/bin/env python3
"""The eighteenth readiness review's findings stay fixed.

SHOULD FIX: history.py mined user-role entries the owner never typed: the brief of a
session an agent started (turnOrigin "sdk") and a harness notice (origin.kind
"task-notification"). Closed as a class: any origin marker that is not the human.
NITs: a BOM in mining.json or review-reminders.json; a cap between two messages with one
timestamp lost the second; a hex value named as a token, and a private key pasted
without its END line, survived; cmd.exe mangled a quoted CHECK; and two BOOTSTRAP lines.

  python3 harness/tests/test_readiness_r18.py
    -> "ok: the eighteenth review's findings stay fixed", exit 0
"""
import json, os, pathlib, subprocess, sys, tempfile, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _ledgerkit import HARNESS, check, finish

ROOT = HARNESS.parent
sys.path.insert(0, str(HARNESS))
import history, ledger, session_context

H = history.owner_text
check("an agent-started session's brief is not the owner's words",
      H({"type": "user", "turnOrigin": "sdk", "origin": None,
         "message": {"content": "Background (from the session that started this one): build it"}}) is None)
check("a harness task notification is not the owner's words",
      H({"type": "user", "origin": {"kind": "task-notification"}, "promptSource": "system",
         "message": {"content": "Background agent finished its work"}}) is None)
check("a desktop message marked human still counts",
      H({"type": "user", "turnOrigin": "human", "origin": {"kind": "human"},
         "message": {"content": "typed by the owner"}}) == "typed by the owner")
check("an older message with no origin fields still counts",
      H({"type": "user", "message": {"content": "older format message"}}) == "older format message")

with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)

    # A BOM in review-reminders.json does not switch the reminder off.
    vault = tmp / "vault"
    (vault / "episodic").mkdir(parents=True)
    (vault / "episodic" / "review-digest-2026-01-01.md").write_text("# digest\n")
    (vault / "review-reminders.json").write_bytes(
        b"\xef\xbb\xbf" + json.dumps({"remind_after_days": 0, "at_most_every_hours": 0}).encode())
    check("a BOM in review-reminders.json keeps the reminder on",
          session_context.reminder(vault, "startup", now=time.time()) is not None)

    # A BOM in mining.json, and a cap between two messages with one timestamp.
    work = tmp / "work"
    ext = tmp / "ext.py"
    stamp = "2026-10-20T10:00:00+00:00"
    ext.write_text("import json\n" + "".join(
        f"print(json.dumps({{'ts': {stamp!r}, 'text': {('message number %d, long enough to count' % n)!r}}}))\n"
        for n in (1, 2, 3)))
    cfg = {"every_days": 0, "max_chars": 90, "workdir": str(work), "start_from": "2026-10-01",
           "sources": [{"type": "command", "name": "ext", "command": [sys.executable, str(ext)]}]}
    (tmp / "mining.json").write_bytes(b"\xef\xbb\xbf" + json.dumps(cfg).encode())
    r = subprocess.run([sys.executable, str(HARNESS / "history.py"), "--config", str(tmp / "mining.json"),
                        "--now", "2026-10-29T00:00:00+00:00"], capture_output=True, text=True, timeout=120)
    check("a BOM in mining.json is read", r.stdout.startswith("mining:") and "FAILED" not in r.stdout, r.stdout + r.stderr)
    mined = []
    for _ in range(4):
        subprocess.run([sys.executable, str(HARNESS / "history.py"), "--config", str(tmp / "mining.json"),
                        "--now", "2026-10-29T00:00:00+00:00", "--force"], capture_output=True, text=True, timeout=120)
    for f in sorted(work.glob("new-*.jsonl")):
        mined += [json.loads(l)["text"] for l in f.read_text().splitlines() if l.strip()]
    check("every message sharing a timestamp across a cap is mined in the end",
          sorted(set(mined)) == ["message number %d, long enough to count" % n for n in (1, 2, 3)], mined)

# Two scrubber shapes.
out = history.scrub("use the token 2f9a8b7c6d5e4f3a2b1c")
check("a hex value named as a token is scrubbed", "2f9a8b7c" not in out, out)
key = "-----BEGIN OPENSSH " + "PRIVATE KEY-----\nb3BlbnNzaC1rZXktdjEAAAAA\nQyNTUxOQAAACD"
out = history.scrub(key)
check("a private key without its END line is scrubbed whole", "QyNTUxOQ" not in out and "BEGIN" not in out, out)
check("survives: the key idea is simple", history.scrub("the key idea is simple") == "the key idea is simple")

# cmd.exe gets the CHECK as written, quotes intact.
probe = f"""
import sys
sys.path.insert(0, {str(HARNESS)!r})
import ledger
seen = []
class Fake:
    def __init__(self, argv, **kw):
        seen.append(argv)
        raise OSError("stop here")
ledger.os.name = "nt"
ledger.windows_bash = lambda: None
ledger.shutil.which = lambda n: "C:/Windows/System32/cmd.exe" if n == "cmd.exe" else None
ledger.subprocess.Popen = Fake
g = ledger.Gate(0, False, "G1", "PROVE", "x")
g.check, g.shell = 'findstr "foo" file.txt', "cmd"
ledger.run_check(g, 5, None)
print(repr(seen[0]) if seen else "none")
"""
r = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, timeout=60)
check("cmd.exe receives the quoted CHECK as written", '/c findstr "foo" file.txt' in r.stdout and '\\\\"' not in r.stdout,
      r.stdout + r.stderr)

boot = ROOT / "BOOTSTRAP.md"
if boot.exists():
    b = boot.read_text(encoding="utf-8")
    check("BOOTSTRAP copies the template's dotfiles", "dotfiles included" in b)
    check("BOOTSTRAP says the reminder proof needs a waiting digest", "The line shows only while a digest is waiting" in b)

finish("the eighteenth review's findings stay fixed")
