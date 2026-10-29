#!/usr/bin/env python3
"""Claude Code Stop hook for the task ledger.

Refuses to let a turn end while the session's ledger has unmet gates, unmapped
asks, or a broken lock. Costs zero tokens: it shells out to ledger.py, which
only compares strings and exit codes.

Wire it (confirm the field names against the current hooks reference):

  "hooks": {
    "Stop": [{"hooks": [{"type": "command", "timeout": 900,
              "command": "python3 \"/ABS/PATH/TO/REPO/harness/adapters/claude-code/hooks/stop-gate.py\""}]}]
  }

Not SubagentStop: a subagent is not bound by its parent's ledger, and wired there it
held the coverage auditor over its own audit. If an older install wires it, the hook
allows a subagent's stop at once.

Use python3 (python on native Windows, where python3 usually does not exist), and an
absolute path to this file, quoted: a missing interpreter exits 127, which Claude Code
treats as non blocking, so the wall fails open without a word, and an unquoted path with
a space in it makes Python exit 2, which Claude Code reads as a block on every stop. The hook finds
ledger.py by its position (harness/adapters/claude-code/hooks/ -> harness/), so copy the
harness folder with its layout intact.

The timeout is long because the wall does not trust the ledger file: `status`
re-runs the CHECK of every ticked gate, so a turn ends only when the system itself
still passes. Keep checks fast; a check past its own bound counts as failing.

Lookup, the one rule (LEDGER.md section 9): the ledger folder is the nearest `.ledger`
holding a ledger, found walking up from the working folder and stopping at the
repository root, plus the project folder's own `.ledger` when Claude Code names it in
CLAUDE_PROJECT_DIR. EVERY open ledger in them is enforced, whoever opened it. Silent
exit 0 when there is none. Finished ledgers move to `.ledger/closed/` on close, so they
never capture a session.
"""
import hashlib, json, os, pathlib, re, subprocess, sys, time

MAX_BLOCKS = 6  # release rather than trap: see the progress guard below


def read_payload():
    try:
        return json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")
    except (json.JSONDecodeError, OSError):
        return {}


def allow(message=None):
    if message:
        print(json.dumps({"systemMessage": message}))
    sys.exit(0)


def block(reason):
    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(0)


payload = read_payload()

# The scheduled review job is exempt from the ledger (contract 9.6): its wrapper
# bounds it to one digest. But it runs in the same clone as interactive sessions, and
# this hook enforces every open ledger there, so on 2026-09-29 another session's
# ledgers blocked the job six times and its run took 75 minutes instead of about 13.
# Both wrappers export this marker to the claude they launch; exactly "1" exempts.
if os.environ.get("MESOSPHERE_REVIEW_JOB") == "1":
    allow()

# A stop gate started by a check that another stop gate is re-running is not a turn
# ending, and judging there recurses: on 2026-10-28 a check ran the test suite, whose
# tests started the stop gate, which re-ran the check, until about 2,600 processes
# exhausted the machine. The outer gate marks its status run; an inner one allows.
if os.environ.get("LEDGER_STOP_GATE_ACTIVE") == "1":
    allow()

# A subagent is not the party the ledger binds. Blocking SubagentStop held the blind
# coverage auditor over the very audit it was writing, told helpers to work the parent's
# gates, and spent the parent's six block release (round 4 review). The parent's own
# Stop is the wall.
if payload.get("hook_event_name") == "SubagentStop":
    allow()

cwd = pathlib.Path(payload.get("cwd") or os.getcwd())
session = payload.get("session_id") or os.environ.get("CLAUDE_SESSION_ID") or "session"

engine = pathlib.Path(os.environ.get("LEDGER_ENGINE") or
                      pathlib.Path(__file__).resolve().parents[3] / "ledger.py")


def find_ledger_dir(start):
    """Same walk as ledger.py's: until 2026-10-28 this joined .ledger onto the payload's
    cwd, so after `cd subdir` the wall saw no ledger and let the turn end. An empty
    folder never wins (one `mkdir` hid the root ledger), and any .git, a worktree's or
    submodule's file included, is a checkout's root; CLAUDE_PROJECT_DIR covers the rest."""
    name = os.environ.get("LEDGER_DIR") or ".ledger"
    if os.path.isabs(name):
        return pathlib.Path(name)
    start = start.resolve()
    for folder in (start, *start.parents):
        if (folder / name).is_dir() and any((folder / name).glob("*.md")):
            return folder / name
        if (folder / ".git").exists():
            break
    return start / name


# The walk from where the agent stands, and the project's own folder, which a nested
# `git init` cannot hide (2026-10-28 readiness review).
ledger_dirs = []
for start in (cwd, os.environ.get("CLAUDE_PROJECT_DIR")):
    d = find_ledger_dir(pathlib.Path(start)).resolve() if start else None
    if d and d not in ledger_dirs:
        ledger_dirs.append(d)
ledger_dir = ledger_dirs[0]

# Every open ledger, always. Until 2026-10-28 an exact session match was enforced ALONE,
# and ledger.py names a new ledger by session id, so any session that opened a small
# ledger of its own silenced a long running one beside it. Enforcing only a single open
# ledger before 2026-08-22 had the same effect from the other side.
targets = sorted(p for d in ledger_dirs if d.is_dir() for p in d.glob("*.md"))

# A ledger closed with --force over unmet work is named for a day after the close, so a
# forced close is never silent. Only the engine's own Log line counts, never the phrase
# anywhere in the file. A ledger closed as met is not judged again: an earlier version
# re-ran closed ledgers to catch a close forged in a doctored environment, and it blocked
# honest work instead (another task's point in time checks, BOOTSTRAP's own proof
# ledger), so that route is a documented limit rather than a check (LEDGER.md section 2).
forced_closes = []
for d in ledger_dirs:
    for p in sorted((d / "closed").glob("*.md")) if (d / "closed").is_dir() else []:
        try:
            if time.time() - p.stat().st_mtime < 86400 and re.search(
                    r"(?m)^\d{4}-\d\d-\d\d \d\d:\d\d FORCED close over: ",
                    p.read_bytes().decode("utf-8", "replace")):
                forced_closes.append(p.name)
        except OSError:
            pass

FORCED_NOTE = [f"  FORCED CLOSE {name}: closed over unmet work with --force. Say so in the report."
               for name in forced_closes]
if not targets:
    # The last ledger closed: its block count is history (round 12 review: it stayed).
    for d in ledger_dirs:
        try:
            (d / f"{session}.state.json").unlink()
        except OSError:
            pass
    allow("ledger:\n" + "\n".join(FORCED_NOTE) if FORCED_NOTE else None)
if not engine.exists():
    # Ledgers to enforce and no judge to ask: fail closed, never silently (round 6).
    block(f"ledger: {len(targets)} ledger(s) in force, but the engine is missing at {engine}. "
          "Restore harness/ledger.py beside the hooks, or set LEDGER_ENGINE to it.")

STATUS_TIMEOUT = int(os.environ.get("LEDGER_STOP_TIMEOUT") or 840)
# One budget for the whole hook, not one per ledger: two slow ledgers at 840s each
# outran the 900s hook timeout, and a hook that times out lets the turn end (round 3).
DEADLINE = time.monotonic() + STATUS_TIMEOUT


def status_of(path):
    try:
        left = DEADLINE - time.monotonic()
        if left < 5:
            return "timeout"
        # The engine gets a wall clock deadline of its own and stops starting checks at
        # it, so it returns before this timeout fires: killing the engine here would
        # orphan the check it was running, which kept a suite running after a stop.
        res = subprocess.run([sys.executable, str(engine), "--file", str(path),
                              # No per check cap below the budget: the deadline already
                              # bounds the whole run, and a two minute suite is a fair check.
                              "--timeout", str(max(1, int(left - 3))),
                              "--json", "status"],
                             env={**os.environ, "LEDGER_STOP_GATE_ACTIVE": "1",
                                  "LEDGER_DEADLINE": str(time.time() + left - 3)},
                             capture_output=True, text=True, timeout=left + 30,
                             cwd=str(path.parent.parent))
    except subprocess.TimeoutExpired:
        return "timeout"
    except OSError:
        return None
    try:
        return json.loads(res.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return None

lines, unreadable, blocking = list(FORCED_NOTE), [], False
# What is outstanding, not the files' bytes: `ledger.py run`, the very command the block
# message asks for, adds a Log line every time, so a byte digest changed at every block
# and the six block release never fired for an agent doing as told (round 12 review).
progress = []
for target in targets:
    state = status_of(target)
    progress.append([target.name, state if not isinstance(state, dict) else
                     [state.get(k) for k in ("lock", "gates", "met", "abandoned", "unmapped_asks", "audit")]
                     + [sorted(g["id"] for g in state.get("unmet") or [])]])
    label = f"[{target.name}] " if len(targets) > 1 else ""
    if state == "timeout":
        # Fail closed: re-running the checks is the whole defence against a forged tick,
        # so a status that could not finish proves nothing was met.
        blocking = True
        lines.append(f"  {label}status did not finish within {STATUS_TIMEOUT}s while re-running "
                     "its checks, so nothing it claims is proven. Make the slow CHECK faster.")
        continue
    if state is None:
        unreadable.append(target.name)
        continue
    # Drafting is not a commitment. Until `declare` freezes the contract there is nothing
    # to enforce, and enforcing a draft traps the session for the crime of having started
    # to write gates. Same rule as the PreToolUse guard: free until frozen.
    if state["lock"] == "open":
        # Not enforced, on purpose (LEDGER.md section 7), but never silent: a drifting
        # agent that never declares must not read the quiet as a pass (round 5).
        if state.get("gates"):
            lines.append(f"  {label}DRAFT {target.name}: {state['gates']} gate(s) written but never "
                         "declared, so nothing in it is enforced. Run `ledger.py declare`.")
        continue
    for gid in state.get("abandoned") or []:
        lines.append(f"  {label}ABANDONED {gid}: surrendered, not met. Say so in the report.")
    for gid in state.get("forced") or []:
        lines.append(f"  {label}FORCED {gid}: evidence written by hand with --force, not by its "
                     "CHECK. Say so in the report.")
    if state.get("relocked"):
        lines.append(f"  {label}RELOCKED: the lock was rewritten without re-running baselines. "
                     "Say so in the report.")
    if state["lock"] == "broken":
        blocking = True
        lines.append(f"  {label}LOCK BROKEN: the frozen contract was edited after declare, so "
                     "the record of what was asked no longer matches what is being delivered. "
                     "Restore the gate lines, or re-declare with `declare --force` and say so.")
        continue
    if state.get("audit") in ("awaiting-human", "awaiting-subagent"):
        # The turn may end so the verdict can come, but never in silence: a verdict that
        # never arrives left a ledger that can never close looking like a pass (round 17).
        lines.append(f"  {label}AUDIT AWAITING ({state['audit']}): {target.name} cannot close "
                     "until a verdict is recorded with `ledger.py audit subagent|human`.")
    unmet, unmapped = state["unmet"], state["unmapped_asks"]
    audit_pending = state.get("audit") == "pending"
    audit_gaps = state.get("audit") == "gaps"
    if not unmet and not unmapped and not audit_pending and not audit_gaps:
        continue
    blocking = True
    for g in unmet[:5]:
        lines.append(f"  {label}{g['id']} {g['cls']} ({g['why']}): {g['outcome']}")
    if len(unmet) > 5:
        lines.append(f"  {label}and {len(unmet) - 5} more")
    for aid in unmapped[:5]:
        lines.append(f"  {label}{aid}: an ask from the original prompt that no gate covers")
    if audit_gaps:
        lines.append(f"  {label}the coverage audit found gaps. Add gates for them with "
                     "`--force declare --gates-file F` and audit again, or carry them into a "
                     "follow up ledger and `--force close`.")
    if audit_pending:
        lines.append(f"  {label}no coverage audit recorded. Run `ledger.py brief`, hand its "
                     "output verbatim to a subagent and nothing else, never your transcript, "
                     "and record its verdict line with `ledger.py audit subagent \"COVERED|GAPS FOUND: ...\"`. "
                     "If subagents are unavailable, ask the owner and record `audit human \"COVERED: ...\"`.")

# Fail closed. A ledger whose status cannot be read proves nothing was met, and until
# 2026-10-28 one stray byte in a Log released the wall here ("not blocking"). The
# progress guard below still releases a session that genuinely cannot fix it.
if unreadable:
    blocking = True
    lines.append(f"  could not read status for {', '.join(unreadable)}: run `ledger.py status` "
                 "on it and repair what it reports")

state_dir = next((d for d in ledger_dirs if d.is_dir() and any(d.glob("*.md"))), ledger_dir)
state_file = state_dir / f"{session}.state.json"
if not blocking:
    try:
        state_file.unlink()  # nothing outstanding, so no block count to keep
    except OSError:
        pass
    allow("ledger:\n" + "\n".join(lines) if lines else None)

# Progress guard. Blocking is only useful while the ledger is still moving; a
# stuck agent gets released rather than trapped, and Claude Code force releases
# after its own consecutive-block limit as well.
digest = hashlib.sha256(json.dumps(progress, sort_keys=True).encode()).hexdigest()[:16]
# In a folder that exists: aimed at a missing one, the write failed silently, the count
# never rose, and the six block release never fired (round 5).
try:
    seen = json.loads(state_file.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    seen = {}
blocks = seen.get("blocks", 0) + 1 if seen.get("digest") == digest else 1
try:
    state_file.write_text(json.dumps({"digest": digest, "blocks": blocks}), encoding="utf-8")
except OSError:
    pass

if blocks > MAX_BLOCKS:
    allow(f"ledger: releasing after {MAX_BLOCKS} blocks with no change to any open ledger. "
          f"{len(lines)} item(s) still outstanding. Say so in the report.")

block("ledger: this turn cannot end yet.\n" + "\n".join(lines) + "\n"
      "Work the next unmet gate, then `ledger.py run` to execute its CHECK. A JUDGE gate "
      "needs `ledger.py evidence <id> \"<proof>\"`. An ask with no gate must be mapped or "
      "explicitly dismissed. If a gate is genuinely impossible, "
      "`ledger.py abandon <id> \"<reason>\"` and report it. Done means the ledger says so.")
