#!/usr/bin/env python3
"""The seventeenth readiness review's findings stay fixed.

SHOULD FIX: history.py mined the weekly review job's own headless prompt, about ten
thousand characters a run, as the owner's typed words.
NITs: accepted next-prompt suggestions were mined as typed; the stop gate said nothing
while an audit was awaited; "not missing" and **VERDICT: COVERED** were misread; the guard
missed a quoted interpreter path; the Windows mining line could lose a non-ASCII path;
.NET appSettings values survived the scrubber; and two BOOTSTRAP lines.

  python3 harness/tests/test_readiness_r17.py
    -> "ok: the seventeenth review's findings stay fixed", exit 0
"""
import datetime, json, os, pathlib, re, subprocess, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _ledgerkit import ENGINE, GUARD, HARNESS, check, declared, file_check, finish, make_repo, stop

ROOT = HARNESS.parent
CLEAN = {k: v for k, v in os.environ.items()
         if k not in ("LEDGER_DIR", "CLAUDE_SESSION_ID", "CLAUDE_CODE_SESSION_ID",
                      "CLAUDE_PROJECT_DIR", "LEDGER_STOP_GATE_ACTIVE", "LEDGER_DEPTH")}
sys.path.insert(0, str(HARNESS))
import history, ledger

with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)

    # SHOULD FIX: the review job's prompt, as Claude Code records a headless run, is not mined.
    prompt = (HARNESS / "review-job" / "prompt.md").read_text(encoding="utf-8")
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    proj = tmp / "projects" / "vault"
    proj.mkdir(parents=True)
    rows = [{"type": "user", "entrypoint": "sdk-cli", "timestamp": ts, "message": {"content": prompt}},
            {"type": "user", "timestamp": ts, "message": {"content": prompt}},
            {"type": "user", "promptSource": "suggestion_accepted", "timestamp": ts, "message": {"content": "yes, do that next"}},
            {"type": "user", "timestamp": ts, "message": {"content": "keep commits small and reversible"}}]
    (proj / "s.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
    got = [t for _, t, _ in history.claude_code(str(tmp / "projects"), since)]
    check("the review prompt is never mined, flagged or not", not any("scheduled weekly" in t for t in got), [t[:60] for t in got])
    check("an accepted suggestion is not mined as typed", "yes, do that next" not in got, got)
    check("the owner's own message still is", got == ["keep commits small and reversible"], got)

    # NIT: an awaited audit is named at the stop, never silent.
    root = make_repo(tmp / "await")
    declared(root, [("PROVE", "the release file exists", file_check("release.txt"))], audit=False)
    (root / "release.txt").write_text("v1")
    subprocess.run([sys.executable, str(ENGINE), "--session", "t", "run"], cwd=str(root), capture_output=True, env=CLEAN)
    subprocess.run([sys.executable, str(ENGINE), "--session", "t", "audit", "awaiting-subagent", "dispatched"],
                   cwd=str(root), capture_output=True, env=CLEAN)
    res = stop(root, session="s")
    check("the stop gate names an awaited audit", "AUDIT AWAITING" in json.dumps(res), res)

    # NIT: the guard knows a quoted interpreter path as the engine.
    root = make_repo(tmp / "quoted")
    declared(root, [("PROVE", "the release file exists", file_check("release.txt"))])
    cmd = f'"{sys.executable}" {ENGINE} --file .ledger/t.md evidence G1 "install verified"'
    r = subprocess.run([sys.executable, str(GUARD)], input=json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": str(root)}),
        capture_output=True, text=True, cwd=str(root), env=CLEAN, timeout=60)
    check("a quoted interpreter path running the engine is allowed", '"deny"' not in r.stdout, r.stdout)

# NIT: verdict wording.
check("'not missing anything' reads as covered",
      not ledger.audit_found_gaps("subagent: COVERED: every ask is gated; the A1 ask is not missing anything"))
check("'A3 is not covered' still reads as gaps", ledger.audit_found_gaps("subagent: COVERED: A3 is not covered"))
check("a markdown bold verdict line is a verdict", ledger.VERDICT_HEAD.match("**VERDICT: COVERED**") is not None)

# NIT: .NET appSettings.
out = history.scrub('<add key="ApiKey" value="AbCd1234EfGh5678" />')
check("an appSettings secret value is scrubbed", "AbCd1234" not in out, out)

# NIT: the Windows mining call runs in UTF-8.
ps1 = (HARNESS / "review-job" / "windows" / "run-review.ps1").read_bytes()
check("run-review.ps1 sets UTF-8 for the mining call", b"PYTHONIOENCODING = 'utf-8'" in ps1)
check("run-review.ps1 stays CRLF", b"\n" not in ps1.replace(b"\r\n", b""))

# NIT: BOOTSTRAP lines.
boot = ROOT / "BOOTSTRAP.md"
if boot.exists():
    b = boot.read_text(encoding="utf-8")
    check("BOOTSTRAP says the reminder shows only when a digest is waiting", "with no digest waiting it shows nothing" in b)
    check("BOOTSTRAP says to scrub each message before writing its line", "scrub each message's text, then write its line" in b)

finish("the seventeenth review's findings stay fixed")
