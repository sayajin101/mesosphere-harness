#!/usr/bin/env python3
"""The vendor neutral core of the every-session vault load (contract section 1).

What to inject (SOUL, IDENTITY, INDEX, CONTRACT in full), what to say when the vault
cannot be read, and the optional review reminder all live here, so every engine's
session start hook builds the same context. An engine's adapter only wraps the
result in that engine's own output format: Claude Code's hook prints the JSON its
SessionStart event expects; another engine's hook prints whatever its own expects,
or a plain loader (a global instructions file) points the agent at the same files.
"""
import json, os, pathlib, re, time
from datetime import date

CORE = ("SOUL.md", "IDENTITY.md", "INDEX.md", "harness/CONTRACT.md")


def loaded_context(root, source):
    parts = [
        f"VAULT LOADED BY THE SESSIONSTART HOOK (source: {source}). The persona vault at "
        f"{root.as_posix()} is injected below, in full, so the load cannot be skipped. SOUL and "
        "IDENTITY are always in context. INDEX is a map: pull its pages just in time from that "
        "path. CONTRACT is obeyed exactly, including the task ledger for substantial work and "
        "the dash rule. Do not re-read these four files; they are already here."
    ]
    for rel in CORE:
        # A stray byte must not stop the whole vault loading (round 9 review).
        text = (root / rel).read_text(encoding="utf-8", errors="replace").strip()
        parts.append(f"===== {rel} =====\n{text}")
    return "\n\n".join(parts)


def missing_context(root, missing):
    return (f"VAULT NOT loaded: the SessionStart hook could not read {', '.join(missing)} under "
            f"{root.as_posix()}. The owner's persona, red lines and contract are NOT in context. "
            "Tell the owner before doing substantial work, and load the vault by hand if it exists "
            "elsewhere on this machine.")


def outstanding(root):
    """What is waiting on the owner: unarchived digests, unverified pages, waiting lessons."""
    digests = sorted(re.match(r"review-digest-(\d{4}-\d{2}-\d{2})", p.name).group(1)
                     for p in (root / "episodic").glob("review-digest-*.md")
                     if re.match(r"review-digest-\d{4}-\d{2}-\d{2}", p.name))
    unverified = 0
    for d in ("heuristics", "taste", "voice", "people", "decisions", "skills"):
        for p in (root / d).rglob("*.md"):
            # One stray byte in one page must not silence the reminder (round 19).
            if re.search(r"^status:\s*mined-unverified\s*$", p.read_text(encoding="utf-8", errors="replace"), re.M):
                unverified += 1
    waiting = 0
    tracker = root / "episodic" / "lesson-outcomes.md"
    if tracker.is_file():
        for line in tracker.read_text(encoding="utf-8", errors="replace").split("\n"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if line.startswith("| L-") and len(cells) == 7 and cells[3] == "waiting" \
                    and cells[0] != "L-example":
                waiting += 1
    return digests, unverified, waiting


def reminder(root, source, now=None):
    """Return the reminder line, or None. Writes the throttle state only when it fires."""
    try:
        cfg_path = root / "review-reminders.json"
        if source != "startup" or not cfg_path.is_file():
            return None
        cfg = json.loads(cfg_path.read_text(encoding="utf-8-sig"))  # a BOM must not switch reminders off
        after_days = int(cfg.get("remind_after_days", 7))
        every_hours = float(cfg.get("at_most_every_hours", 24))
        now = time.time() if now is None else now
        state = root / ".reminder-state"
        if state.is_file():
            last = float(state.read_text(encoding="utf-8").strip() or 0)
            if now - last < every_hours * 3600:
                return None
        digests, unverified, waiting = outstanding(root)
        if not digests:
            return None
        oldest = digests[0]
        age = (date.fromtimestamp(now) - date.fromisoformat(oldest)).days
        if age < after_days:
            return None
        state.write_text(str(int(now)), encoding="utf-8")
        return (f"Review waiting: {len(digests)} digest(s), oldest {oldest} ({age} days), "
                f"{unverified} unverified page(s), {waiting} waiting lesson(s). "
                "Ask this session to walk you through the oldest digest.")
    except Exception:
        return None
