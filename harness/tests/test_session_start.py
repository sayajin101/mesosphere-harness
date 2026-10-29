"""Exercise session-start.py: it must inject the core vault files, and say so loudly when it cannot."""
import json, pathlib, subprocess, sys, tempfile, os

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _vault import vault_root
ROOT = vault_root()
HOOK = str(ROOT / "harness" / "adapters" / "claude-code" / "hooks" / "session-start.py")
CORE = {"SOUL.md": "# SOUL", "IDENTITY.md": "# IDENTITY", "INDEX.md": "# Index",
        "harness/CONTRACT.md": "Harness Contract"}


def run(source, env_extra=None):
    env = dict(os.environ)
    env["MESOSPHERE_DIR"] = str(ROOT)
    env.update(env_extra or {})
    payload = json.dumps({"hook_event_name": "SessionStart", "source": source})
    return subprocess.run([sys.executable, HOOK], input=payload, capture_output=True,
                          text=True, encoding="utf-8", env=env)


fails = []


def check(name, ok, detail=""):
    if ok:
        print(f"  ok  {name}")
    else:
        fails.append(f"{name}: {detail}")


for source in ("startup", "resume", "clear", "compact"):
    res = run(source)
    check(f"{source}: exits 0", res.returncode == 0, res.stderr[-300:])
    # Windows decodes a hook's stdout with the locale codec; ASCII-only JSON survives any codec.
    check(f"{source}: stdout is ASCII-only JSON", res.stdout.isascii(), "non-ASCII byte on stdout")
    try:
        out = json.loads(res.stdout)
    except json.JSONDecodeError:
        check(f"{source}: stdout parses as JSON", False, res.stdout[:200])
        continue
    spec = out.get("hookSpecificOutput", {})
    check(f"{source}: event name", spec.get("hookEventName") == "SessionStart", str(spec)[:200])
    ctx = spec.get("additionalContext", "")
    for name, heading in CORE.items():
        check(f"{source}: injects {name} in full", heading in ctx
              and (ROOT / name).read_text(encoding="utf-8").strip()[-80:] in ctx, "missing or cut")

with tempfile.TemporaryDirectory() as empty:
    res = run("startup", {"MESOSPHERE_DIR": str(pathlib.Path(empty) / "no-vault-here")})
    check("missing vault: still exits 0, never blocks a session", res.returncode == 0, res.stderr[-300:])
    try:
        out = json.loads(res.stdout)
    except json.JSONDecodeError:
        out = {}
    check("missing vault: the model is told it was NOT loaded",
          "NOT loaded" in out.get("hookSpecificOutput", {}).get("additionalContext", ""), res.stdout[:200])
    check("missing vault: the user sees a warning", "NOT loaded" in out.get("systemMessage", ""), res.stdout[:200])

if fails:
    print("\nFAIL")
    for f in fails:
        print("  " + f)
    sys.exit(1)
print(f"\nPASS: session-start hook, {len(CORE)} core files, 4 sources, missing-vault path")
