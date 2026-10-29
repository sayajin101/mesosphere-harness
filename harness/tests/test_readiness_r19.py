#!/usr/bin/env python3
"""The nineteenth readiness review's findings stay fixed.

SHOULD FIX: history.py mined pasted text, a Slack thread with colleagues' names say, as
the owner's own words; and BOOTSTRAP's phase 1 canary was not shaped like a message, so
"scrub each message's text" could leave an empty scrubbed file that passed the gate.
NITs: JUDGE evidence "pending: ..." counted as met; a quoted passphrase after "is" kept
all but its first word, and "use secret X" survived; a message whose first block was a
harness reminder was dropped whole; "except A2, dismissed" read as a gap; SECURITY.md
assumed private reporting is on; and one stray byte in a page silenced the reminder.

  python3 harness/tests/test_readiness_r19.py
    -> "ok: the nineteenth review's findings stay fixed", exit 0
"""
import json, os, pathlib, re, subprocess, sys, tempfile, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _ledgerkit import HARNESS, check, finish

ROOT = HARNESS.parent
sys.path.insert(0, str(HARNESS))
import history, ledger, session_context

H = history.owner_text
paste = 'look at this thread\n<pasted_content id="p1">Jane Doe: we ship Friday\nBob Roe: no we do not</pasted_content>'
out = H({"type": "user", "message": {"content": paste}})
check("a paste is not mined as the owner's words", out == "look at this thread", out)
out = H({"type": "user", "message": {"content": [
    {"type": "text", "text": "<system-reminder>harness note</system-reminder>"},
    {"type": "text", "text": "my own words after the reminder"}]}})
check("a harness block in front no longer drops the owner's words", out == "my own words after the reminder", out)
check("a message that is only a paste yields nothing",
      H({"type": "user", "message": {"content": '<pasted_content id="p2">someone else</pasted_content>'}}) is None)

# The canary BOOTSTRAP plants is a message, and scrub() of its text clears the gate.
GATE = r"""["']?(password|passwd|secret|token|api_?key)["']?\s*[:=]\s*\S+"""
boot = ROOT / "BOOTSTRAP.md"
if boot.exists():
    b = boot.read_text(encoding="utf-8")
    m = re.search(r"`(\{\"ts\": [^`]*canary-not-a-real-secret[^`]*\})`", b)
    check("BOOTSTRAP's canary is a message line with a text field", m is not None and "text" in json.loads(m.group(1)))
    if m:
        raw = json.loads(m.group(1))
        check("the canary is red on the raw line", re.search(GATE, json.dumps(raw)) is not None)
        clean = json.dumps({**raw, "text": history.scrub(raw["text"])})
        check("and green once its text is scrubbed", re.search(GATE, clean) is None, clean)
    check("BOOTSTRAP adds a gate that the scrubbed extract keeps every message",
          "HOLD: the scrubbed extract keeps every message" in b)

# NITs.
g = ledger.Gate(0, True, "G1", "JUDGE", "the owner signed")
g.evidence = "pending: owner has not signed"
check("JUDGE evidence that begins 'pending' is not met", not g.evidence_ok)
h = ledger.Gate(0, True, "G2", "HOLD", "no migrations wait")
h.evidence = "Pending migrations: 0"
check("a check's output that begins 'Pending' still counts", h.evidence_ok)
for s, secret in [('my password is "correct horse battery"', "battery"), ("use secret abc123XYZ", "abc123")]:
    check(f"scrubbed: {s}", secret not in history.scrub(s), history.scrub(s))
check("COVERED except a dismissed ask reads as covered",
      not ledger.audit_found_gaps("subagent: COVERED except A2, dismissed as out of scope"))
check("COVERED except an uncovered ask still reads as gaps",
      ledger.audit_found_gaps("subagent: COVERED except A3, which no gate covers"))
sec = ROOT / "SECURITY.md"
if sec.exists():
    check("SECURITY.md says what to do when private reporting is off", "If that button is missing" in sec.read_text())

with tempfile.TemporaryDirectory() as tmp:
    vault = pathlib.Path(tmp)
    (vault / "episodic").mkdir()
    (vault / "heuristics").mkdir()
    (vault / "episodic" / "review-digest-2026-01-01.md").write_text("# digest\n")
    (vault / "heuristics" / "odd.md").write_bytes(b"---\nstatus: mined-unverified\n---\ncaf\xe9\n")
    (vault / "review-reminders.json").write_text(json.dumps({"remind_after_days": 0, "at_most_every_hours": 0}))
    check("a page with a stray byte does not silence the reminder",
          session_context.reminder(vault, "startup", now=time.time()) is not None)

finish("the nineteenth review's findings stay fixed")
