#!/usr/bin/env python3
"""close runs history.scrub over everything it archives, evidence included.

LEDGER.md promised a scrubbed summary, but until 2026-10-28 close only replaced dashes,
so a credential in a check's output went into episodic/ verbatim.

  python3 harness/tests/test_close_scrub.py
    -> "ok: the archive is scrubbed", exit 0
"""
import pathlib, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _ledgerkit import check, declared, finish, led, make_repo

TOKEN = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2"

with tempfile.TemporaryDirectory() as tmp:
    root = make_repo(tmp)
    declared(root, [("JUDGE", "the release notes read well", None)])
    led(root, "evidence", "G1", f"read them; the log also printed token={TOKEN} by mistake")
    r = led(root, "close", "--archive-to", "episodic")
    out = list((root / "episodic").glob("*.md"))
    text = out[0].read_text() if out else ""
    check("close archived the ledger", r.returncode == 0 and out, r.stdout + r.stderr)
    check("the token is not in the archive", TOKEN not in text and "A1b2C3d4" not in text, text)
    check("the redaction is marked", "[REDACTED]" in text, text)
    check("ordinary evidence survives", "read them" in text, text)

finish("the archive is scrubbed")
