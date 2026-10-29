#!/usr/bin/env python3
"""Proves `ledger.py brief` emits the auditor's brief and nothing that would sight it.

Blindness is the mechanism that stops a coverage audit being a rubber stamp. Before
this existed the brief was assembled by hand, so the constraint was a rule the agent
could forget. Now the engine emits it, and this test asserts what it must not contain:
evidence, baselines, check commands, the log.

Read-only: a temp ledger and ledger.py.

  python harness/tests/test_audit_brief.py
    -> "ok: brief is blind", exit 0
"""
import pathlib, subprocess, sys, tempfile

ENGINE = pathlib.Path(__file__).resolve().parents[1] / "ledger.py"
RAW = "please add the loader and also keep the linter clean"

fails = []


def run(path, *args, cwd=None):
    res = subprocess.run([sys.executable, str(ENGINE), "--file", str(path), *args],
                         capture_output=True, text=True, timeout=60, cwd=cwd)
    return res.returncode, (res.stdout or "") + (res.stderr or "")


with tempfile.TemporaryDirectory() as tmp:
    d = pathlib.Path(tmp)
    path = d / "brief.md"
    code, out = subprocess.run(
        [sys.executable, str(ENGINE), "--file", str(path), "open",
         "--title", "brief test", "--prompt", RAW],
        capture_output=True, text=True, timeout=60, cwd=tmp).returncode, ""

    text = path.read_text(encoding="utf-8")
    if "## Prompt" not in text or RAW not in text:
        fails.append("open did not store the raw prompt verbatim, so an auditor would only "
                     "ever see the enumerator's reading of it")

    # Give it a gate carrying a check, an expect, a baseline and evidence: precisely the
    # things the brief must not leak.
    text = text.replace("## Asks", (
        "- [x] G1 PROVE: the loader exists\n"
        "      CHECK: SECRET_CHECK_COMMAND\n"
        "      EXPECT: SECRET_EXPECT\n"
        "      BASELINE: SECRET_BASELINE\n"
        "      EVIDENCE: SECRET_EVIDENCE\n\n## Asks"))
    text = text.replace("-> ?", "-> G1")
    path.write_text(text, encoding="utf-8")

    code, out = run(path, "brief", cwd=tmp)
    if code != 0:
        fails.append(f"brief exited {code}: {out.strip()[:200]}")

    must_contain = [RAW, "G1", "the loader exists", "WHAT WAS ASKED", "titles only"]
    for needle in must_contain:
        if needle not in out:
            fails.append(f"brief omitted something the auditor needs: {needle!r}")

    must_not_contain = ["SECRET_CHECK_COMMAND", "SECRET_EXPECT", "SECRET_BASELINE",
                        "SECRET_EVIDENCE"]
    for needle in must_not_contain:
        if needle in out:
            fails.append(f"brief leaked {needle!r}, which sights the auditor on the work")

    # A checked box must not leak either: whether a gate passed is not the auditor's business.
    if "[x]" in out:
        fails.append("brief leaked checkbox state, which tells the auditor what was completed")

if fails:
    for f in fails:
        print(f"FAIL: {f}")
    sys.exit(1)
print("ok: brief is blind (raw prompt, asks and gate titles only; no check, baseline, "
      "evidence or checkbox state)")
sys.exit(0)
