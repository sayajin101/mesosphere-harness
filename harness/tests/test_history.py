#!/usr/bin/env python3
"""history.py hands the agent only the owner's NEW words, scrubbed, capped, on cadence.

Read-only with respect to the repo: every case builds a throwaway history and workdir.

  python3 harness/tests/test_history.py
    -> "ok: history", exit 0
"""
import json, os, pathlib, subprocess, sys, tempfile

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "history.py"
fails = []


def check(name, ok, detail=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}")
    if not ok:
        fails.append(f"{name}: {detail}")


def entry(ts, content, **extra):
    return json.dumps({"type": "user", "timestamp": ts, "message": {"role": "user", "content": content}, **extra})


def setup(d, max_chars=100000, every=30):
    proj = d / "projects" / "-repo"
    (proj / "s1" / "subagents").mkdir(parents=True)
    lines = [
        entry("2026-09-01T10:00:00Z", "an old message from before the start date, long enough"),
        entry("2026-10-28T10:00:00Z", "i prefer correctness over speed, every single time"),
        entry("2026-10-28T10:05:00Z", "ok"),
        entry("2026-10-28T10:06:00Z", [{"type": "tool_result", "content": "someone else's data"}]),
        entry("2026-10-28T10:07:00Z", "<task-notification>harness noise, not the owner</task-notification>"),
        entry("2026-10-28T10:08:00Z", "Stop hook feedback: this turn cannot end yet, harness text"),
        entry("2026-10-28T10:09:00Z", "a sidechain prompt written by an agent, not the owner", isSidechain=True),
        entry("2026-10-28T10:10:00Z", [{"type": "text", "text": "my key is sk-ant-" + "a" * 30 + " please keep it"}]),
        entry("2026-10-28T10:11:00Z", "call me on +1 202 555 0123 about the release"),
    ]
    (proj / "s1.jsonl").write_text("\n".join(lines) + "\n")
    (proj / "s1" / "subagents" / "agent-x.jsonl").write_text(entry("2026-10-28T11:00:00Z", "a subagent brief that the owner never typed") + "\n")
    cfg = {"every_days": every, "max_chars": max_chars, "workdir": str(d / "work"),
           "start_from": "2026-10-27", "sources": [{"type": "claude-code", "path": str(d / "projects")}]}
    (d / "mining.json").write_text(json.dumps(cfg))
    touch(d)
    return d / "mining.json"


def touch(d):
    """Real files carry today's mtime; these messages are dated ahead of it, so the
    fixture's mtimes are set past them, as they would be on a machine living in that time."""
    for f in (d / "projects").rglob("*.jsonl"):
        os.utime(f, (1924992000, 1924992000))  # 2031-01-01


def run(cfg, *args, now="2026-10-29T00:00:00Z"):
    r = subprocess.run([sys.executable, str(SCRIPT), "--config", str(cfg), "--now", now, *args],
                       capture_output=True, text=True)
    return r.returncode, r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""


with tempfile.TemporaryDirectory() as tmp:
    d = pathlib.Path(tmp)
    rc, line = run(d / "missing.json")
    check("no config means not configured", rc == 0 and line == "mining: not configured", line)

    cfg = setup(d)
    rc, line = run(cfg, "--dry-run")
    check("a dry run reports counts", rc == 0 and line.startswith("mining: dry run, nothing written: 3 new messages"), line)
    check("a dry run writes nothing", not (d / "work").exists())

    rc, line = run(cfg)
    out = sorted((d / "work").glob("new-*.jsonl"))
    rows = [json.loads(x) for x in out[0].read_text().splitlines()] if out else []
    texts = " | ".join(r["text"] for r in rows)
    check("a real run writes an extract outside the history", rc == 0 and len(out) == 1, line)
    check("only the owner's new messages", len(rows) == 3, texts)
    check("older than the start date is skipped", "old message" not in texts, texts)
    check("short, tool result, harness and sidechain lines are skipped",
          not any(w in texts for w in ("someone else", "harness", "sidechain", "subagent")), texts)
    check("keys are scrubbed", "sk-ant" not in texts and "[REDACTED]" in texts, texts)
    check("phone numbers are scrubbed", "555 0123" not in texts, texts)
    check("each row names its source", all(r["source"] == "claude-code" for r in rows), rows)

    rc, line = run(cfg, now="2026-11-05T00:00:00Z")
    check("inside the cadence it is not due", line == "mining: not due until 2026-11-28", line)

    rc, line = run(cfg, now="2026-11-30T00:00:00Z")
    check("after the cadence nothing new means 0", line == "mining: 0 new messages", line)

    proj = d / "projects" / "-repo" / "s1.jsonl"
    with proj.open("a") as fh:
        fh.write(entry("2026-12-01T09:00:00Z", "a brand new thought from december about pricing") + "\n")
    touch(d)
    rc, line = run(cfg, "--force", now="2026-12-02T00:00:00Z")
    check("the checkpoint picks up only what is new", line.startswith("mining: 1 new messages"), line)

with tempfile.TemporaryDirectory() as tmp:
    d = pathlib.Path(tmp)
    cfg = setup(d, max_chars=60)
    rc, line = run(cfg)
    check("a cap stops the run and says so", "capped, the rest waits" in line and line.startswith("mining: 1 new messages"), line)
    rc, line = run(cfg, "--force", now="2026-10-29T01:00:00Z")
    check("a capped run resumes where it stopped", line.startswith("mining: 1 new messages") and "capped" in line, line)

with tempfile.TemporaryDirectory() as tmp:
    d = pathlib.Path(tmp)
    ext = d / "ext.py"
    ext.write_text("import json,os\nprint(json.dumps({'ts':'2026-10-28T12:00:00Z','text':'from another tool, owner words here'}))\n"
                   "print(json.dumps({'ts':'2026-01-01T00:00:00Z','text':'too old to count at all here'}))\n")
    cfg = {"every_days": 30, "max_chars": 100000, "workdir": str(d / "work"), "start_from": "2026-10-27",
           "sources": [{"type": "command", "name": "cursor", "command": [sys.executable, str(ext)]}]}
    (d / "m.json").write_text(json.dumps(cfg))
    rc, line = run(d / "m.json")
    check("a command source is read and filtered by date", line.startswith("mining: 1 new messages") and "cursor" in line, line)
    (d / "m.json").write_text(json.dumps(dict(cfg, sources=[{"type": "claude-code", "path": str(d / "nope")}])))
    rc, line = run(d / "m.json", "--force")
    check("a missing source fails loudly with one line", rc == 1 and line.startswith("mining: FAILED:"), line)


# Secret shapes a readiness review slipped past the first scrubber (2026-10-28), and
# text that must survive untouched.
SHAPES = {
    "aws secret": "aws_secret wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY here",
    "url password": "db is postgres://admin:Sup3rS3cret!@db.example.com:5432/app",
    "env key": "export OPENAI_API_KEY=abcdef1234567890 now",
    "upper hex": "hash ABCDEF0123456789ABCDEF0123456789ABCD end",
    "base64": "blob QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVowMTIzNDU2Nzg5YWJj end",
    # Assembled at run time, so a host's secret scanner sees no live-looking key here.
    "live key": "key rk_" + "live_51Habcdefghijklmnop end",
}
SECRETS = ["wJalrXUtnFEMI", "Sup3rS3cret", "abcdef1234567890", "ABCDEF0123456789ABCDEF",
           "QUJDREVGR0hJSktM", "rk_" + "live_51H"]
spec = __import__("importlib.util").util.spec_from_file_location("history", SCRIPT)
hist = __import__("importlib.util").util.module_from_spec(spec)
spec.loader.exec_module(hist)
for name, text in SHAPES.items():
    out = hist.scrub(text)
    check(f"scrubs {name}", not any(s in out for s in SECRETS) and "[REDACTED]" in out, out)
for keep in ("we shipped it on 2026-10-28 at 10:11, ticket 4521",
             "version 1.4.8 of the CLI, port 8080, 3 of 12 tasks"):
    check(f"leaves ordinary text alone: {keep[:30]}", hist.scrub(keep) == keep, hist.scrub(keep))

if fails:
    print("\nFAIL\n  " + "\n  ".join(fails))
    sys.exit(1)
print("ok: history (secret shapes)")
