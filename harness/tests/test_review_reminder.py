#!/usr/bin/env python3
"""The session start hook reminds the owner about outstanding reviews, on their cadence.

Off unless review-reminders.json exists. Fires only on a fresh session, only when the
oldest unarchived digest has waited remind_after_days, and at most once every
at_most_every_hours. A broken config must never stop the vault loading.

Read-only with respect to the repo: every case builds its own throwaway vault.

  python3 harness/tests/test_review_reminder.py
    -> "ok: review reminders", exit 0
"""
import json, os, pathlib, shutil, subprocess, sys, tempfile
from datetime import date, timedelta

HERE = pathlib.Path(__file__).resolve().parent
HOOK = HERE.parent / "adapters" / "claude-code" / "hooks" / "session-start.py"
fails = []


def check(name, ok, detail=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}")
    if not ok:
        fails.append(f"{name}: {detail}")


def vault(tmp, digest_ages=(30,), config=None, archived=(), unverified=1, waiting=1):
    v = pathlib.Path(tmp) / "v"
    if v.exists():
        shutil.rmtree(v)
    (v / "harness").mkdir(parents=True)
    (v / "episodic" / "archive").mkdir(parents=True)
    (v / "heuristics").mkdir()
    for name in ("SOUL.md", "IDENTITY.md", "INDEX.md"):
        (v / name).write_text(f"# {name}\n")
    (v / "harness" / "CONTRACT.md").write_text("# Harness Contract\n")
    for age in digest_ages:
        d = (date.today() - timedelta(days=age)).isoformat()
        (v / "episodic" / f"review-digest-{d}.md").write_text("digest\n")
    for age in archived:
        d = (date.today() - timedelta(days=age)).isoformat()
        (v / "episodic" / "archive" / f"review-digest-{d}.md").write_text("old\n")
    for i in range(unverified):
        (v / "heuristics" / f"p{i}.md").write_text("---\nstatus: mined-unverified\n---\n# p\n")
    rows = "".join(f"| L-w{i} | a lesson | digest | waiting | | | |\n" for i in range(waiting))
    (v / "episodic" / "lesson-outcomes.md").write_text(
        "| L-example | x | bootstrap | waiting | | | |\n" + rows)
    if config is not None:
        (v / "review-reminders.json").write_text(config if isinstance(config, str) else json.dumps(config))
    return v


def hook(v, source="startup"):
    env = dict(os.environ, MESOSPHERE_DIR=str(v))
    r = subprocess.run([sys.executable, str(HOOK)], input=json.dumps({"source": source}),
                       capture_output=True, text=True, env=env)
    out = json.loads(r.stdout) if r.stdout.strip() else {}
    return r.returncode, out.get("systemMessage", ""), out.get("hookSpecificOutput", {}).get("additionalContext", "")


CFG = {"remind_after_days": 7, "at_most_every_hours": 24}
with tempfile.TemporaryDirectory() as tmp:
    rc, msg, ctx = hook(vault(tmp, config=None))
    check("no config means no reminder", rc == 0 and msg == "" and "REVIEW REMINDER" not in ctx, msg)

    v = vault(tmp, digest_ages=(30, 3), config=CFG, unverified=2, waiting=1)
    rc, msg, ctx = hook(v)
    check("an old digest triggers a reminder", "Review waiting: 2 digest(s)" in msg and "(30 days)" in msg, msg)
    check("unverified pages are counted", "2 unverified page(s)" in msg, msg)
    check("waiting lessons are counted, the template row is not", "1 waiting lesson(s)" in msg, msg)
    check("the agent is told too", "REVIEW REMINDER" in ctx and "# SOUL.md" in ctx, ctx[-300:])
    check("the vault still loads in full", "===== SOUL.md =====" in ctx, ctx[:200])
    check("the reminder time is recorded", (v / ".reminder-state").is_file())
    check("output stays ASCII", (msg + ctx).isascii())

    rc, msg, _ = hook(v)
    check("a second session inside the window stays quiet", msg == "", msg)

    (v / ".reminder-state").unlink()
    rc, msg, _ = hook(v, source="resume")
    check("resume and compact never remind", msg == "", msg)

    rc, msg, _ = hook(vault(tmp, digest_ages=(2,), config=CFG))
    check("a digest younger than the threshold stays quiet", msg == "", msg)

    rc, msg, _ = hook(vault(tmp, digest_ages=(), archived=(40,), config=CFG))
    check("an archived digest counts as reviewed", msg == "", msg)

    v = vault(tmp, config={"remind_after_days": 7, "at_most_every_hours": 0})
    hook(v)
    rc, msg, _ = hook(v)
    check("at_most_every_hours 0 reminds every fresh session", "Review waiting" in msg, msg)

    rc, msg, ctx = hook(vault(tmp, config="{not json"))
    check("a broken config never stops the vault loading", rc == 0 and "===== SOUL.md =====" in ctx and msg == "", msg)

if fails:
    print("\nFAIL\n  " + "\n  ".join(fails))
    sys.exit(1)
print("ok: review reminders")
