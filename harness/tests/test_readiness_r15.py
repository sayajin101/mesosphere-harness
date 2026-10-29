#!/usr/bin/env python3
"""The fifteenth readiness review's findings stay fixed.

SHOULD FIX: BOOTSTRAP's phase 1 scrub gate counts `"password": "[REDACTED]"`, so an agent
that wrote its own key-keeping scrubber could never turn the gate green. BOOTSTRAP now
says to scrub with the shipped scrub(), which removes name and value together.
NITs: list items with an unlisted verb, and two word imperatives, were dropped as asks;
an extractor's or a check's output was decoded with the locale codec; BOOTSTRAP gave no
suite runtime, mixed its interpreter wording, and added the remote gates before the
ledger existed; and a worktree's missing hooks went unmentioned.

  python3 harness/tests/test_readiness_r15.py
    -> "ok: the fifteenth review's findings stay fixed", exit 0
"""
import pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _ledgerkit import HARNESS, check, finish

ROOT = HARNESS.parent
sys.path.insert(0, str(HARNESS))
import ledger
from history import scrub

# The SHOULD FIX: the gate's own pattern finds nothing in what scrub() leaves of the canary.
GATE = r"""["']?(password|passwd|secret|token|api_?key)["']?\s*[:=]\s*\S+"""
canary = '{"password": "canary-not-a-real-secret"}'
check("the phase 1 gate pattern finds nothing after scrub() of the canary",
      re.search(GATE, scrub(canary)) is None, scrub(canary))
boot = ROOT / "BOOTSTRAP.md"
if boot.exists():
    b = boot.read_text(encoding="utf-8")
    check("BOOTSTRAP's gate pattern is the one tested here", GATE in b)
    check("BOOTSTRAP scrubs with the shipped scrub(), not a scrubber of the agent's own",
          "from history import scrub" in b and "never a scrubber of your own" in b)
    check("BOOTSTRAP gives the suite's runtime", "about three minutes" in b)
    check("BOOTSTRAP names the profile's Python for hook commands", "which `python3` stands for" in b)
    step4 = b.split("4. Open the setup ledger inside the vault.")[1].split("### Phase 1")[0]
    check("the remote gates are listed where the setup ledger is opened",
          "`HOLD: the remote is private` gates from step 2" in step4)

# NIT: every list item is an ask, and a two word imperative in prose is one.
asks = [t for _, t in ledger.enumerate_asks("Can you:\n- bump the version\n- tag the release\n- write release notes\n")]
check("three listed items give three asks, whatever their verbs", len(asks) == 3, asks)
asks = [t for _, t in ledger.enumerate_asks("Refactor auth.py; keep the public API stable; don't touch the database layer\n")]
check("a two word imperative is an ask", any(a.lower().startswith("refactor") for a in asks), asks)

# NIT: subprocess output is decoded as UTF-8 whatever the locale.
src = (HARNESS / "history.py").read_text(encoding="utf-8")
call = re.search(r"out = subprocess\.run\(cmd,[^)]*\)", src, re.S)
check("history.py decodes an extractor's output as UTF-8",
      call is not None and 'encoding="utf-8"' in call.group(0), call.group(0) if call else src[:0])
led = (HARNESS / "ledger.py").read_text(encoding="utf-8")
popen = re.search(r"proc = subprocess\.Popen\(argv,[^)]*\)", led, re.S)
check("ledger.py decodes a check's output as UTF-8",
      popen is not None and 'encoding="utf-8"' in popen.group(0))

# NIT: worktrees.
readme = (HARNESS / "adapters" / "claude-code" / "README.md").read_text(encoding="utf-8")
check("the Claude Code adapter README warns that a worktree may carry no hooks", "worktree" in readme)

finish("the fifteenth review's findings stay fixed")
