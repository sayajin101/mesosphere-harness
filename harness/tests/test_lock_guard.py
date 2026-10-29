"""Exercise lock-guard.py without putting its trigger strings in a shell command."""
import json, pathlib, subprocess, sys

# Resolved from this file, never hardcoded: a Windows path here made the test fail on
# the Mac for a reason that had nothing to do with the guard.
import tempfile
ROOT = pathlib.Path(__file__).resolve().parents[2]
GUARD = str(ROOT / "harness" / "adapters" / "claude-code" / "hooks" / "lock-guard.py")
# The guard only denies writes while some ledger in the directory is locked, so the test
# builds its own locked ledger in a throwaway directory. Pointing it at the real vault
# made the result depend on whether a live ledger happened to be locked at that moment.
_TMP = tempfile.TemporaryDirectory()
CWD = _TMP.name
(pathlib.Path(CWD) / ".ledger").mkdir()
(pathlib.Path(CWD) / ".ledger" / "capabilities.md").write_text("# Ledger: test\nLock: sha256:0000000000000000\n")
LED = ".ledger/capabilities.md"

cases = [
    ("read with sed -n", f"sed -n 1,5p {LED}", False),
    ("read with cat", f"cat {LED}", False),
    ("read with grep", f"grep Lock {LED}", False),
    ("in-place sed", f"sed -i s/a/b/ {LED}", True),
    ("append redirect", f"echo x >" + f"> {LED}", True),
    ("remove", f"rm {LED}", True),
    ("stderr redirect is not a write", f"grep Lock {LED} 2>" + "&1", False),
    ("the engine itself", "python harness/ledger.py --session capabilities status", False),
    # Real false positives from 2026-10-27: the folder was only MENTIONED while the
    # write went elsewhere, and both commands were refused.
    ("a read filter names the folder, the write is elsewhere",
     "grep -rn old heuristics | grep -v .ledger ; sed -i s/a/b/ notes.md", False),
    ("a here-document mentions the folder, the redirect is elsewhere",
     "cat >" + "> notes.md <<'EOF'\nsee the .ledger/ folder, -> details\nEOF", False),
    ("a pipeline reads the ledger and tees elsewhere", f"cat {LED} | tee out.txt", False),
    # Still writes into the ledger folder, however the command is dressed.
    ("copy into the ledger", f"cp x.md {LED}", True),
    ("a redirect into the ledger after another command", f"cat notes.md ; echo x >" + f" {LED}", True),
    ("tee into the ledger", f"echo x | tee {LED}", True),
    ("move into the ledger folder", "mv draft.md .ledger/", True),
    # Found 2026-10-28 by a readiness review: any command that merely MENTIONED
    # ledger.py was waved through, so a sed with a ledger.py comment could tick a box.
    ("a forged ledger.py mention", f"sed -i s/x/y/ {LED} # ledger.py", True),
]

fails = []
for name, command, expect_deny in cases:
    payload = json.dumps({"tool_name": "Bash", "cwd": CWD, "tool_input": {"command": command}})
    res = subprocess.run([sys.executable, GUARD], input=payload, capture_output=True, text=True)
    denied = "permissionDecision" in res.stdout and "deny" in res.stdout
    if denied != expect_deny:
        fails.append(f"{name}: expected {'deny' if expect_deny else 'allow'}, got "
                     f"{'deny' if denied else 'allow'}")
    else:
        print(f"  ok  {name}: {'denied' if denied else 'allowed'}")

if fails:
    for f in fails:
        print(f"FAIL {f}")
    sys.exit(1)
print("guard: reads allowed, writes denied, mentions elsewhere allowed, forged ledger.py mention denied")
