#!/usr/bin/env python3
"""Cursor sessionStart hook: inject the vault into every agent chat.

Cursor's sessionStart takes {"additional_context": "..."} on stdout and adds it to the
conversation's initial system context. It is fire and forget: the agent loop does not
wait for it, so prove on the machine that the context actually arrives. Reuses the
vendor neutral core in harness/session_context.py.

Register it in ~/.cursor/hooks.json (user level; paths are relative to ~/.cursor/
unless absolute):

  {"version": 1, "hooks": {"sessionStart": [{"command":
      "python3 /ABS/PATH/TO/VAULT/harness/adapters/cursor/hooks/session-start.py"}]}}
"""
import json, os, pathlib, sys

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[3]))
from session_context import CORE, loaded_context, missing_context, reminder  # noqa: E402


def main():
    try:
        sys.stdin.buffer.read()
    except OSError:
        pass
    root = pathlib.Path(os.environ.get("MESOSPHERE_DIR") or HERE.parents[4])
    missing = [rel for rel in CORE if not (root / rel).is_file()]
    if missing:
        context = missing_context(root, missing)
    else:
        context = loaded_context(root, "startup")
        nudge = reminder(root, "startup")
        if nudge:
            context += "\n\nREVIEW REMINDER: " + nudge
    sys.stdout.write(json.dumps({"additional_context": context}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
