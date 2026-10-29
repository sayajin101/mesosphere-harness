"""Shared helpers for the ledger tests: build a real declared ledger in a temp folder
with ledger.py itself, and drive the engine and the hooks against it.

Not a test (run_all.py runs test_*.py only). Everything happens in temp folders.
"""
import json, os, pathlib, subprocess, sys

HARNESS = pathlib.Path(__file__).resolve().parents[1]
ENGINE = HARNESS / "ledger.py"
HOOKS = HARNESS / "adapters" / "claude-code" / "hooks"
STOP = HOOKS / "stop-gate.py"
GUARD = HOOKS / "lock-guard.py"
PY = pathlib.Path(sys.executable).as_posix()

fails = []


def check(name, ok, detail=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}")
    if not ok:
        fails.append(f"{name}: {str(detail)[-600:]}")


def finish(label):
    if fails:
        print("\nFAIL\n  " + "\n  ".join(fails))
        sys.exit(1)
    print(f"ok: {label}")


def file_check(name):
    """A CHECK that passes exactly while `name` exists in the ledger's repo folder."""
    return f"{PY} -c \"import pathlib,sys;sys.exit(not pathlib.Path('{name}').exists())\""


def led(cwd, *args, session="t"):
    env = {k: v for k, v in os.environ.items() if k not in ("LEDGER_DIR", "CLAUDE_SESSION_ID",
                                                             "CLAUDE_CODE_SESSION_ID",
                                                             "CLAUDE_PROJECT_DIR",
                                                             "LEDGER_STOP_GATE_ACTIVE")}
    return subprocess.run([sys.executable, str(ENGINE), "--session", session, *args],
                          cwd=str(cwd), capture_output=True, text=True, env=env, timeout=300)


def make_repo(root):
    root = pathlib.Path(root)
    (root / ".git").mkdir(parents=True, exist_ok=True)  # marks the repo root for the walk up
    return root


def declared(root, gates, session="t", audit=True):
    """Open, write `gates` (list of (cls, outcome, check or None)), map the one ask to
    all of them, declare, and record a covering audit. Returns the ledger path."""
    root = pathlib.Path(root)
    (root / "prompt.txt").write_text("build the release file for the next build\n")
    r = led(root, "open", "--title", "kit", "--prompt-file", "prompt.txt", session=session)
    assert r.returncode == 0, r.stderr
    path = root / ".ledger" / f"{session}.md"
    body = []
    for i, (cls, outcome, chk) in enumerate(gates, 1):
        body.append(f"- [ ] G{i} {cls}: {outcome}")
        if chk:
            body.append(f"      CHECK: {chk}")
    ids = ", ".join(f"G{i}" for i in range(1, len(gates) + 1))
    text = path.read_text().replace("-->\n\n## Asks", "-->\n" + "\n".join(body) + "\n\n## Asks", 1)
    text = "\n".join(l[:-1] + ids if l.startswith("A") and l.endswith("-> ?") else l
                     for l in text.split("\n"))
    path.write_text(text)
    r = led(root, "declare", session=session)
    assert r.returncode == 0, r.stdout + r.stderr
    if audit:
        r = led(root, "audit", "subagent", "COVERED", session=session)
    return path


def forge_tick(path, gid, evidence="all good"):
    """What the readiness review did with a python one liner: tick the box and write an
    EVIDENCE line, leaving every frozen field, and so the lock, untouched."""
    lines = path.read_text().split("\n")
    out, cur = [], None
    for l in lines:
        if l.startswith(f"- [ ] {gid} "):
            l, cur = l.replace("- [ ]", "- [x]", 1), gid
        elif l.startswith("- ["):
            cur = None
        if cur and l.strip().startswith("EVIDENCE:"):
            l = f"      EVIDENCE: {evidence}"
        out.append(l)
    path.write_text("\n".join(out))


def hook(script, payload, cwd):
    env = dict(os.environ, LEDGER_ENGINE=str(ENGINE))
    # CLAUDE_PROJECT_DIR would make a test's stop gate enforce the owner's real ledger,
    # whose checks run this suite, which starts the stop gate again: on 2026-10-28 that
    # loop forked about 2,600 processes. Every hook here sees the temp repo only.
    for k in ("LEDGER_DIR", "MESOSPHERE_REVIEW_JOB", "CLAUDE_PROJECT_DIR", "LEDGER_STOP_GATE_ACTIVE"):
        env.pop(k, None)
    r = subprocess.run([sys.executable, str(script)], input=json.dumps(payload),
                       capture_output=True, text=True, cwd=str(cwd), env=env, timeout=300)
    out = r.stdout.strip()
    try:
        return json.loads(out) if out else {}
    except json.JSONDecodeError:
        return {"raw": out}


def stop(cwd, session="t"):
    return hook(STOP, {"session_id": session, "cwd": str(cwd)}, cwd)


def blocked(res):
    return res.get("decision") == "block"


def guard(cwd, tool, tool_input):
    res = hook(GUARD, {"tool_name": tool, "tool_input": tool_input, "cwd": str(cwd)}, cwd)
    return (res.get("hookSpecificOutput") or {}).get("permissionDecision") == "deny"
