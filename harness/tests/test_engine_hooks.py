#!/usr/bin/env python3
"""The Gemini CLI and Cursor session start hooks inject the vault, through the shared core.

Each hook is run as its engine would run it, against a throwaway vault (or the real
one inside the vault repo), and must put SOUL, IDENTITY, INDEX and the contract in
the field its engine reads: hookSpecificOutput.additionalContext for Gemini,
additional_context for Cursor. A missing vault must say it was NOT loaded.

  python3 harness/tests/test_engine_hooks.py
    -> "ok: engine hooks", exit 0
"""
import json, os, pathlib, subprocess, sys, tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _vault import vault_root  # noqa: E402

ADAPTERS = HERE.parent / "adapters"
HOOKS = {"gemini": lambda o: o["hookSpecificOutput"]["additionalContext"],
         "cursor": lambda o: o["additional_context"]}
fails = []


def check(name, ok, detail=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}")
    if not ok:
        fails.append(f"{name}: {detail}")


def run(engine, vault):
    env = dict(os.environ, MESOSPHERE_DIR=str(vault))
    r = subprocess.run([sys.executable, str(ADAPTERS / engine / "hooks" / "session-start.py")],
                       input=json.dumps({"source": "startup", "hook_event_name": "SessionStart"}),
                       capture_output=True, text=True, env=env)
    return r.returncode, r.stdout


root = vault_root()
for engine, field in HOOKS.items():
    rc, out = run(engine, root)
    try:
        ctx = field(json.loads(out))
    except (ValueError, KeyError):
        ctx = ""
    check(f"{engine}: exits 0", rc == 0, out[:200])
    check(f"{engine}: stdout is ASCII JSON", out.isascii(), "non-ASCII byte")
    check(f"{engine}: injects all four core files",
          all(f"===== {n} =====" in ctx for n in ("SOUL.md", "IDENTITY.md", "INDEX.md", "harness/CONTRACT.md")), ctx[:200])
    with tempfile.TemporaryDirectory() as empty:
        rc, out = run(engine, pathlib.Path(empty) / "nowhere")
        check(f"{engine}: a missing vault still exits 0 and says NOT loaded", rc == 0 and "NOT loaded" in out, out[:200])

if fails:
    print("\nFAIL\n  " + "\n  ".join(fails))
    sys.exit(1)
print("ok: engine hooks")
