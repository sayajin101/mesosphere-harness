#!/usr/bin/env python3
"""The documentation fixes from the 2026-10-28 readiness review stay fixed.

Docs are what a stranger's agent follows, so a stale claim is a bug: it told agents the
lock catches a forged edit (it did not), that one ledger per folder is the rule (the stop
gate enforced something else), and that Cursor runs the review job (it refuses). Each
check below is one finding. Parts that need a file this repo does not ship are skipped.

  python3 harness/tests/test_doc_fixes.py
    -> "ok: docs match the code", exit 0
"""
import pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _ledgerkit import check, finish

ROOT = pathlib.Path(__file__).resolve().parents[2]
H = ROOT / "harness"


def text(rel):
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else None


STALE = ["lock catches such an edit", "detects the edit after the fact", "single open ledger",
         "any command invoking `ledger.py` is allowed", "reliably know its own session id",
         "`harness/review-job/prompt.md` beside this file", "review job can run on this engine"]
docs = [p for p in H.rglob("*") if p.suffix in (".md", ".py") and "tests" not in p.parts]
for phrase in STALE:
    hits = [str(p.relative_to(ROOT)) for p in docs if phrase.lower() in p.read_text(encoding="utf-8").lower()]
    check(f"stale claim gone: {phrase}", not hits, hits)

prompt = text("harness/review-job/prompt.md")
check("review prompt reports company facts as counts only, twice",
      prompt.count("REPORT THE COUNT ONLY") == 2 and '"route to moon" items instead' not in prompt)

ledger = text("harness/LEDGER.md")
check("LEDGER.md states the audit limit", "cannot prove it" in ledger and "audit human" in ledger)
check("LEDGER.md states the forging limit", "recompute" in ledger and "not a sandbox" in ledger)
check("LEDGER.md states the lookup rule once", ledger.count("Which ledgers are enforced, the one rule") == 1)
check("LEDGER.md says close scrubs with history.py", "scrubbed by `history.py`" in ledger)

cursor = text("harness/adapters/cursor/CAPABILITIES.md")
check("cursor CAPABILITIES says the review job is not supported",
      "not supported" in cursor and "_ADAPTER=cursor" not in cursor)

boot = text("BOOTSTRAP.md")
if boot is not None:
    check("BOOTSTRAP: the private remote gate is HOLD with an anchored EXPECT",
          "`HOLD: the remote is private`" in boot and "`EXPECT: /^PRIVATE$/`" in boot
          and "`PROVE: the remote is private`" not in boot)
    check("BOOTSTRAP: an advisory branch for engines without hooks, proven by status exiting 1",
          "Advisory branch" in boot and "exits 1" in boot)
    check("BOOTSTRAP: the scrub gate plants and removes a canary", "canary" in boot and "delete the canary" in boot)
    check("BOOTSTRAP: the usage readout points at the Usage readout line",
          not re.search(r"usage readout if it has one \(its `CAPABILITIES.md`, row \"model per subagent\"\)", boot))
    done = boot.split("## When you are done", 1)[-1]
    check("BOOTSTRAP: When you are done carries the finish-line rule", "hunt for what is left" in done)
    contract = text("harness/CONTRACT.md")
    nine = contract.split("## 9.", 1)[-1].split("\n## ", 1)[0]
    check("CONTRACT section 9 carries the finish-line rule", "hunt for what is left" in nine.lower())
    readme = text("README.md")
    check("README states what the ledger does not stop", "## What it does not stop" in readme)

finish("docs match the code")
