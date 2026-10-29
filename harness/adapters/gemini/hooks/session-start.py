#!/usr/bin/env python3
"""Gemini CLI SessionStart hook: inject the vault into every session.

Gemini CLI's SessionStart output takes the same shape as Claude Code's
(hookSpecificOutput.additionalContext, plus an optional systemMessage), so this
reuses the vendor neutral core in harness/session_context.py. Gemini injects the
context as the first turn interactively and prepends it to the prompt headless.

Register it in ~/.gemini/settings.json (timeouts are in milliseconds there):

  "hooks": {"SessionStart": [{"hooks": [{"type": "command", "timeout": 15000,
      "name": "vault-load", "command": "python3 /ABS/PATH/TO/VAULT/harness/adapters/gemini/hooks/session-start.py"}]}]}

Never blocks a session: Gemini treats SessionStart as advisory.
"""
import json, os, pathlib, sys

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[3]))
from session_context import CORE, loaded_context, missing_context, reminder  # noqa: E402


def main():
    try:
        source = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}").get("source", "unknown")
    except (json.JSONDecodeError, OSError, AttributeError):
        source = "unknown"
    root = pathlib.Path(os.environ.get("MESOSPHERE_DIR") or HERE.parents[4])
    missing = [rel for rel in CORE if not (root / rel).is_file()]
    out = {"hookSpecificOutput": {"hookEventName": "SessionStart"}}
    if missing:
        out["hookSpecificOutput"]["additionalContext"] = missing_context(root, missing)
        out["systemMessage"] = f"Vault NOT loaded: files missing under {root.as_posix()}"
    else:
        context = loaded_context(root, source)
        nudge = reminder(root, source)
        if nudge:
            context += "\n\nREVIEW REMINDER: " + nudge
            out["systemMessage"] = nudge
        out["hookSpecificOutput"]["additionalContext"] = context
    sys.stdout.write(json.dumps(out, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
