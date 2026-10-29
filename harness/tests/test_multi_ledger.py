#!/usr/bin/env python3
"""Proves the Stop gate enforces every open ledger, not just a single one.

The hook looks a ledger up by session id and falls back when the name does not match.
That fallback used to require exactly one open ledger, so opening a second silently
switched the wall off: no exact match, count not one, hook allowed. A wall that
disappears when a second task starts is worse than no wall, because nobody notices.

Read-only: temp ledgers, ledger.py and the hook, invoked with a synthetic payload. It
never touches the real .ledger directory.

  python harness/tests/test_multi_ledger.py
    -> "ok: all open ledgers enforced", exit 0
"""
import json, pathlib, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
ENGINE = ROOT / "ledger.py"
HOOK = ROOT / "adapters" / "claude-code" / "hooks" / "stop-gate.py"

fails = []


def make(dirpath, name, gate_outcome, satisfied):
    """Write a declared ledger whose single gate is met or unmet as asked."""
    path = dirpath / f"{name}.md"
    py = pathlib.Path(sys.executable).as_posix()  # `python` is not on every PATH (not on the Mac)
    check = f'"{py}" -c "import sys; sys.exit(0)"' if satisfied else \
            f'"{py}" -c "import sys; sys.exit(1)"'
    path.write_text(
        f"# Ledger: {name}\nLock: open\nAudit: pending\nSession: {name}\n"
        f"Opened: 2026-01-01 00:00\n\n## Contract\n\n"
        f"- [ ] G1 PROVE: {gate_outcome}\n      CHECK: {check}\n\n"
        f"## Asks\nA1 \"do {name}\" -> G1\n\n## Log\n2026-01-01 00:00 opened\n",
        encoding="utf-8")
    return path


def hook_says(cwd, session):
    payload = json.dumps({"session_id": session, "cwd": str(cwd)})
    env_res = subprocess.run([sys.executable, str(HOOK)], input=payload,
                             capture_output=True, text=True, timeout=60,
                             cwd=str(cwd), env={**{k: v for k, v in __import__("os").environ.items()
                                                   if k not in ("CLAUDE_PROJECT_DIR",
                                                                "LEDGER_STOP_GATE_ACTIVE")},
                                                "LEDGER_ENGINE": str(ENGINE)})
    out = env_res.stdout.strip()
    if not out:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {"raw": out}


with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    led = root / ".ledger"
    led.mkdir()

    # Two ledgers, both declared. The first is fully satisfiable, the second is not.
    a = make(led, "alpha", "alpha is done", satisfied=True)
    b = make(led, "beta", "beta is NOT done", satisfied=False)
    for p in (a, b):
        subprocess.run([sys.executable, str(ENGINE), "--file", str(p), "declare"],
                       capture_output=True, text=True, timeout=60, cwd=tmp)
    # Satisfy and audit alpha completely, so only beta should hold the turn.
    subprocess.run([sys.executable, str(ENGINE), "--file", str(a), "run"],
                   capture_output=True, text=True, timeout=60, cwd=tmp)
    subprocess.run([sys.executable, str(ENGINE), "--file", str(a), "audit", "human", "covered"],
                   capture_output=True, text=True, timeout=60, cwd=tmp)

    # The session id matches neither file, which is the case that used to go silent.
    verdict = hook_says(root, "some-unrelated-session-id")
    if verdict is None:
        fails.append("the hook allowed the turn with two open ledgers, one of them unmet. "
                     "This is the silent-wall regression.")
    else:
        reason = verdict.get("reason", "")
        if verdict.get("decision") != "block":
            fails.append(f"expected a block, got {verdict}")
        if "beta" not in reason:
            fails.append(f"the block does not name the unmet ledger: {reason[:200]}")
        if "alpha" in reason and "beta is NOT done" not in reason:
            fails.append("the block cites the satisfied ledger instead of the unmet one")

    # With every ledger satisfied and audited, the turn is released.
    subprocess.run([sys.executable, str(ENGINE), "--file", str(b), "abandon", "G1", "test"],
                   capture_output=True, text=True, timeout=60, cwd=tmp)
    subprocess.run([sys.executable, str(ENGINE), "--file", str(b), "audit", "human", "covered"],
                   capture_output=True, text=True, timeout=60, cwd=tmp)
    verdict = hook_says(root, "some-unrelated-session-id")
    # Settled means allowed. An abandoned gate is named in a note, never a block.
    if verdict is not None and (verdict.get("decision") == "block"
                                or "ABANDONED G1" not in verdict.get("systemMessage", "")):
        fails.append(f"the hook still blocked once every ledger was settled: {verdict}")

if fails:
    for f in fails:
        print(f"FAIL: {f}")
    sys.exit(1)
print("ok: all open ledgers enforced (an unmet second ledger still blocks, and the turn "
      "is released only when every open ledger is settled)")
sys.exit(0)
