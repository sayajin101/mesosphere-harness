#!/usr/bin/env python3
"""Claude Code SessionStart hook: make the vault load observable instead of trusted.

Injects SOUL.md, IDENTITY.md, INDEX.md and harness/CONTRACT.md in full as
additionalContext, so a session wears the vault whether or not it follows the
loader instruction in ~/.claude/CLAUDE.md. A session on 2026-10-07 skipped that
instruction and then asserted a hardware fact about the owner's machine that the
vault plainly contradicted, ran substantial work with no ledger, and broke the
write rules. Nothing noticed, because an instruction is not observable.

Wire it in the USER-level settings (it applies to every repo on the machine), with
that machine's clone path, and confirm the field names against the current hooks
reference:

  "hooks": {
    "SessionStart": [{"matcher": "startup|resume|clear|compact",
                      "hooks": [{"type": "command", "timeout": 15,
                        "command": "python3 \"<clone>/harness/adapters/claude-code/hooks/session-start.py\""}]}]
  }

`compact` is in the matcher because contract section 1.4 asks for a re-read after
compaction. The vault is located from this file's own path, or MESOSPHERE_DIR when set.
A missing vault never blocks a session: it exits 0 and says, to the model and to the
user, that the persona was NOT loaded, because a silent hook looks exactly like one
that worked.

Review reminders (optional, off unless the owner opts in): when the vault root holds
review-reminders.json, a fresh session (source "startup") counts what is waiting on
the owner and, if the oldest unarchived review digest is at least remind_after_days
old, tells them, at most once every at_most_every_hours. A digest counts as reviewed
once it is moved to episodic/archive/. The last reminder time lives in .reminder-state
at the vault root, which is gitignored. Example config:

  {"remind_after_days": 7, "at_most_every_hours": 24}

Any error in the reminder is swallowed: a reminder must never stop the vault loading.
"""
import json, os, pathlib, sys

# The context itself is built by the vendor neutral core in harness/session_context.py;
# this hook only wraps it in the JSON Claude Code's SessionStart event expects.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))
from session_context import CORE, loaded_context, missing_context, reminder  # noqa: E402

def vault_root():
    override = os.environ.get("MESOSPHERE_DIR")
    return pathlib.Path(override) if override else pathlib.Path(__file__).resolve().parents[4]


def source_of_payload():
    try:
        return json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}").get("source", "unknown")
    except (json.JSONDecodeError, OSError, AttributeError):
        return "unknown"


def emit(context, warning=None):
    out = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}
    if warning:
        out["systemMessage"] = warning
    # ASCII-only: Windows decodes a hook's stdout with the locale codec, which mangles UTF-8.
    sys.stdout.write(json.dumps(out, ensure_ascii=True))


def main():
    source = source_of_payload()
    root = vault_root()
    missing = [rel for rel in CORE if not (root / rel).is_file()]
    if missing:
        emit(missing_context(root, missing),
             f"Vault NOT loaded: vault files missing under {root.as_posix()}")
        return 0
    try:
        context = loaded_context(root, source)
        nudge = reminder(root, source)
        if nudge:
            context += ("\n\nREVIEW REMINDER: " + nudge + " Mention this to the owner once, then "
                        "offer to go through the oldest digest item by item; never decide for them.")
        emit(context, nudge)
    except OSError as exc:
        emit(missing_context(root, [str(exc)]), "Vault NOT loaded: the vault could not be read")
    return 0


if __name__ == "__main__":
    sys.exit(main())
