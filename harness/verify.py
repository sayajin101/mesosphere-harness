#!/usr/bin/env python3
"""Vault integrity gate. Run from the vault root: python3 harness/verify.py

Checks the invariants in OPERATING.md and the write rules in harness/CONTRACT.md.
Exits non-zero on any failure so agents, hooks and the weekly review job can gate on it.

Optional: --diff <ref> also audits the working tree against a git ref for
changes an agent is never allowed to make (tier 1, raw/, status: fields).
"""
import re, sys, subprocess, pathlib, argparse

VALID_STATUS = {"mined-unverified", "draft", "interviewed", "signed"}
VALID_TYPE = {"heuristic", "taste", "voice", "value", "decision", "person", "skill", "episode"}
TIER2 = ("heuristics", "taste", "voice", "people", "decisions", "skills", "episodic")
PROTECTED = ("SOUL.md", "IDENTITY.md")

fail = []
warn = []


def notes():
    for p in sorted(pathlib.Path(".").rglob("*.md")):
        # .ledger holds live task ledgers: machine-local working state, gitignored,
        # carrying raw command output. It is not vault content and must not be linted,
        # or an open ledger fails the vault gate for quoting a tool's own dashes.
        if {".git", ".obsidian", ".ledger"} & set(p.parts):
            continue
        yield p


def frontmatter(lines):
    """Return (start, end) line indices of the YAML block, or None."""
    if not lines or lines[0].strip() != "---":
        return None
    try:
        return 0, lines.index("---", 1)
    except ValueError:
        return None


def sources_block(lines, fm):
    start = next((i for i in range(fm[0] + 1, fm[1]) if re.match(r"^sources:\s*$", lines[i])), None)
    if start is None:
        return []
    out, i = [], start + 1
    while i < fm[1] and re.match(r"^\s+-", lines[i]):
        out.append((i, lines[i]))
        i += 1
    return out


def check_frontmatter_and_sources():
    by_base = {}
    for p in notes():
        by_base.setdefault(p.stem, p)

    for p in notes():
        lines = p.read_text(encoding="utf-8", errors="replace").split("\n")
        fm = frontmatter(lines)
        rel = p.as_posix()  # str() is raw\x.md on Windows, so raw/ tests missed it (round 14)

        if fm is None:
            if rel.startswith(TIER2) or rel in PROTECTED:
                fail.append(f"{rel}: tier 1/2 page has no YAML frontmatter (SCHEMA.md requires it)")
            continue

        head = "\n".join(lines[fm[0] + 1:fm[1]])
        m = re.search(r"^status:\s*(\S+)", head, re.M)
        if not m:
            fail.append(f"{rel}: no status: field")
        elif m.group(1) not in VALID_STATUS:
            fail.append(f"{rel}: status '{m.group(1)}' is not one of {sorted(VALID_STATUS)}")

        m = re.search(r"^type:\s*(\S+)", head, re.M)
        if m and m.group(1) not in VALID_TYPE and "|" not in head.split("type:")[1][:60]:
            fail.append(f"{rel}: type '{m.group(1)}' is not one of {sorted(VALID_TYPE)}")

        for ln, raw in sources_block(lines, fm):
            v = raw.strip()[2:].strip()
            if v.startswith("[["):
                fail.append(f"{rel}:{ln+1}: unquoted wikilink in YAML, parses as a nested list: {v}")
            elif v.startswith('"[['):
                if not v.endswith(']]"'):
                    fail.append(f"{rel}:{ln+1}: malformed wikilink source: {v}")
                else:
                    tgt = v[3:-3]
                    if not pathlib.Path(tgt).exists():
                        fail.append(f"{rel}:{ln+1}: source target does not exist: {tgt}")
            else:
                # An entry may be a bare path, or prose with one or more paths embedded
                # ("episodic/foo.md (the digest committed earlier today)"). Validate every
                # path-like token so a mixed entry is not silently unchecked. Report one
                # line once, however many paths it carries, so a long list stays readable.
                loose = []
                for tok in re.findall(r"[\w./-]+\.md", v):
                    if "*" in tok or "<" in tok:
                        continue
                    if pathlib.Path(tok).exists():
                        loose.append(tok)
                    elif "/" not in tok and tok[:-3] in by_base:
                        # bare filename shorthand that resolves to exactly one note
                        loose.append(f"{tok} (shorthand for {by_base[tok[:-3]]})")
                    else:
                        fail.append(f"{rel}:{ln+1}: source path does not exist: {tok}")
                if loose and not rel.startswith("raw/"):
                    kind = "a plain path, not a wikilink" if len(loose) == 1 and loose[0] == v \
                           else f"{len(loose)} path{'s' if len(loose) > 1 else ''} in prose, not a wikilink"
                    warn.append(f"{rel}:{ln+1}: source is {kind}: {', '.join(loose[:3])}"
                                + (" ..." if len(loose) > 3 else ""))


def strip_code(text):
    """Remove fenced blocks and inline code so documentation examples are not read as content."""
    out, infence = [], False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            infence = not infence
            continue
        out.append("" if infence else re.sub(r"`[^`]*`", "", line))
    return "\n".join(out)


def check_links():
    by_base = {}
    for p in notes():
        by_base.setdefault(p.stem, p)
    for p in notes():
        for raw in re.findall(r"\[\[([^\]|#]+)", strip_code(p.read_text(encoding="utf-8", errors="replace"))):
            raw = raw.strip()
            if "<" in raw or ">" in raw:      # SCHEMA.md placeholders
                continue
            cand = pathlib.Path(raw if raw.endswith(".md") else raw + ".md")
            if not cand.exists() and raw not in by_base:
                warn.append(f"{p}: unresolved wikilink [[{raw}]]")


def check_line_endings():
    """LF only, on disk, whatever wrote the file. .gitattributes normalises on commit,
    but a CRLF working copy still shows as modified with an empty diff and makes every
    commit print a warning. Found 2026-09-29: the ledger engine wrote CRLF on Windows,
    and an old note was rewritten with CRLF by something never identified."""
    for p in notes():
        try:
            p.read_bytes().decode("utf-8")
        except UnicodeDecodeError as e:
            # Reported, not a crash: the other checks read on with a replacement character
            # (round 20 review: one bad byte crashed the whole linter).
            fail.append(f"{p.as_posix()}: not valid UTF-8 (byte {e.start}); re-save it as UTF-8")
        if b"\r\n" in p.read_bytes():
            fail.append(f"{p.as_posix()}: CRLF line endings on disk. The vault is LF only; "
                        f"convert it (the content is unchanged, only the endings)")


def check_dashes():
    for p in notes():
        # raw/ is immutable verbatim evidence (documents, transcripts). Its dashes are the
        # source's, not the vault's prose, and no agent may edit them anyway.
        if p.as_posix().startswith("raw/"):  # as_posix: str() has backslashes on Windows
            continue
        infence = False
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").split("\n"), 1):
            if line.lstrip().startswith("```"):
                infence = not infence
                continue
            if infence or line.strip() == "---":
                continue
            if re.fullmatch(r"[|\s:-]+", line):             # markdown table separator row
                continue
            stripped = re.sub(r"`[^`]*`", "", line)          # ignore inline code
            stripped = re.sub(r"https?://\S+", "", stripped)  # ignore urls
            stripped = re.sub(r"--[a-z][a-z0-9-]*", "", stripped)  # cli long flags are identifiers
            for bad, name in (("\u2014", "em-dash"), ("\u2013", "en-dash"), ("--", "double-hyphen")):
                if bad in stripped:
                    fail.append(f"{p}:{i}: {name} in prose (banned by OPERATING.md)")


def check_diff(ref):
    try:
        changed = subprocess.run(["git", "diff", "--name-only", ref], capture_output=True,
                                 text=True, check=True).stdout.split()
    except subprocess.CalledProcessError:
        fail.append(f"cannot diff against '{ref}'")
        return
    for f in changed:
        if f in PROTECTED:
            fail.append(f"{f}: tier 1 modified. Only the owner edits SOUL.md and IDENTITY.md (contract 3.3)")
        if f.startswith("raw/"):
            fail.append(f"{f}: raw/ is immutable evidence and was modified (contract 3.3)")
    # A new page legitimately introduces a status: line. Only flag a status that CHANGED,
    # which means the same file's diff carries both a removed and an added status line.
    added = set(subprocess.run(["git", "diff", "--name-only", "--diff-filter=A", ref],
                               capture_output=True, text=True).stdout.split())
    for f in changed:
        if f in added or not f.endswith(".md"):
            continue
        d = subprocess.run(["git", "diff", ref, "--", f], capture_output=True, text=True).stdout
        old = re.findall(r"^-status:\s*(\S+)", d, re.M)
        new = re.findall(r"^\+status:\s*(\S+)", d, re.M)
        if old and new and old != new:
            # SCHEMA.md reserves only `signed` for the owner, and contract 3.2 permits agent drafts and
            # enrichments on tier 2 provided they never set `signed`. So a move TO signed is a hard
            # failure; any other status change is legal and only worth surfacing for review.
            if new[0] == "signed":
                fail.append(f"{f}: status changed {old[0]} -> signed. Only the owner sets signed (SCHEMA.md, contract 3.2)")
            else:
                warn.append(f"{f}: status changed {old[0]} -> {new[0]}; permitted under contract 3.2, confirm it was intended")


# The selftest runs on EVERY verify.py invocation, because a check behind an
# opt-in flag is an instruction to remember to call it, and an instruction is
# read by the same process that decides whether it was followed. That is the form
# contract section 9 exists to replace with a mechanism.
# The mutation test is 92s against the selftest's 14s, so it waits for a flag.
#
# Each machine runs its own OS's suites: zsh on macOS, Windows PowerShell on win32
# (so the Windows wrapper's fixes have a permanent guard too). Anywhere else neither applies and the check says so.
WRAPPER_BASE = "harness/review-job"
WRAPPER_SUITES = {
    "darwin": {"dir": "macos", "default": ("selftest.sh",),
               "full": ("selftest.sh", "mutationtest.sh"),
               "argv": lambda s: ["zsh", str(s)]},
    "win32": {"dir": "windows", "default": ("selftest.ps1",),
              "full": ("selftest.ps1", "mutationtest.ps1"),
              "argv": lambda s: ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(s)]},
}
# The Windows mutation test runs a dozen copies of a selftest that starts seven
# powershell.exe processes at about 6s each, so it takes minutes, not seconds.
WRAPPER_TIMEOUT = {"mutationtest.ps1": 3600}


def check_wrappers(d, full):
    """Run the review job's own test suites as a standing check.

    These live in a ledger's HOLD gates otherwise, and a HOLD gate dies when its
    ledger closes, so the claim "the wrapper tests are green" had no permanent
    home. Found 2026-08-24, when a closed ledger took its regression guards with it.

    Deliberately NOT wired into either wrapper itself: each selftest's end to end
    cases invoke its wrapper, so a self check there would recurse without end.
    """
    spec = WRAPPER_SUITES.get(sys.platform)
    if spec is None:
        warn.append(f"{WRAPPER_BASE}: no wrapper suites for {sys.platform}, so none were run. "
                    f"Not evidence that they pass")
        return
    d = d or f"{WRAPPER_BASE}/{spec['dir']}"
    base = pathlib.Path(d)
    if not base.is_dir():
        fail.append(f"{d}: wrapper directory not found, so the suites were not run. "
                    f"An unreadable suite is not a passing suite")
        return
    for suite in spec["full"] if full else spec["default"]:
        script = base / suite
        if not script.is_file():
            fail.append(f"{script}: wrapper suite missing, so it did not pass. "
                        f"Absent and green are different facts")
            continue
        limit = WRAPPER_TIMEOUT.get(suite, 300)
        try:
            r = subprocess.run(spec["argv"](script), capture_output=True, text=True,
                               timeout=limit, errors="replace")
        except subprocess.TimeoutExpired:
            fail.append(f"{script}: timed out after {limit}s, which is not a pass")
            continue
        except OSError as e:
            fail.append(f"{script}: could not be executed: {e}")
            continue
        if r.returncode != 0:
            last = [l for l in (r.stdout + r.stderr).splitlines() if l.strip()]
            why = last[-1] if last else "no output"
            fail.append(f"{script}: exit {r.returncode}: {why}")
        else:
            warn.append(f"{script}: passed")


OUTCOMES = "episodic/lesson-outcomes.md"
OUTCOME_VALUES = {"added", "rejected", "parked", "waiting"}
PAGE_DIRS = ("heuristics", "taste", "voice", "people", "decisions", "skills")
# Rows decided before the marker convention existed carry no marker on their page,
# so the page side of the check starts on the day the convention began.
MARKER_FROM = ""  # set to a YYYY-MM-DD to exempt rows decided before you adopted markers
MARKER = re.compile(r"Approved by the owner (\d{4}-\d{2}-\d{2})\.")


def check_outcomes(path):
    """The record of what happened to each suggested lesson must agree with the pages.

    Without it every digest re-proposes lessons already decided. An absent or empty
    tracker fails rather than passing, because "no rows read" and "nothing to
    check" print the same zero, and the gate itself once had no zero count guard.
    """
    p = pathlib.Path(path)
    if not p.is_file():
        fail.append(f"{path}: lesson tracker not found, so no outcome was checked. "
                    f"An absent record is not an empty one")
        return
    rows, seen = [], set()
    for ln, line in enumerate(p.read_text(encoding="utf-8", errors="replace").split("\n"), 1):
        if not line.startswith("| L-"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 7:
            fail.append(f"{path}:{ln}: expected 7 columns, found {len(cells)}")
            continue
        lid, _lesson, _raised, outcome, where, decided, _record = cells
        if lid in seen:
            fail.append(f"{path}:{ln}: duplicate id {lid}")
        seen.add(lid)
        if outcome not in OUTCOME_VALUES:
            fail.append(f"{path}:{ln}: outcome '{outcome}' is not one of {sorted(OUTCOME_VALUES)}")
            continue
        page = where.strip("`")
        if outcome == "added":
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", decided):
                fail.append(f"{path}:{ln}: {lid} is added but has no decided date")
                continue
            if not page or not pathlib.Path(page).is_file():
                fail.append(f"{path}:{ln}: {lid} is added to '{page}', which does not exist")
                continue
        rows.append((ln, lid, outcome, page, decided))
    if not rows:
        fail.append(f"{path}: no lesson rows could be read, so no outcome was checked")
        return

    claimed = {}
    for ln, lid, outcome, page, decided in rows:
        if outcome == "added" and decided >= MARKER_FROM:
            claimed.setdefault((page, decided), []).append(lid)
    found = {}
    for d in PAGE_DIRS:
        for f in sorted(pathlib.Path(d).rglob("*.md")):
            for date in MARKER.findall(f.read_text(encoding="utf-8", errors="replace")):
                # as_posix, not str: tracker rows name pages with forward slashes, and str()
                # gives backslashes on Windows, so no key matched there and every row failed.
                found[(f.as_posix(), date)] = found.get((f.as_posix(), date), 0) + 1
    for key, ids in sorted(claimed.items()):
        have = found.get(key, 0)
        if have < len(ids):
            fail.append(f"{key[0]}: tracker says {len(ids)} lessons were added on {key[1]} "
                        f"but the page carries {have} approval markers for that date ({', '.join(ids)})")
    for key, have in sorted(found.items()):
        want = len(claimed.get(key, []))
        if have > want:
            warn.append(f"{key[0]}: {have} approval markers dated {key[1]} but the tracker records "
                        f"{want}, so a lesson landed without a row in {path}")


def main():
    # Notes are UTF-8 on every platform. Read with the Windows code page, a curly quote
    # crashed verify and an em dash slipped past the dash rule as mojibake (round 8).
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--diff", metavar="REF", help="also audit the working tree against a git ref")
    ap.add_argument("--wrappers-full", "--wrappers", action="store_true",
                    help="also run the slow mutation test, not just the selftest")
    ap.add_argument("--no-wrappers", action="store_true",
                    help="skip the wrapper suites entirely; use only when you know why")
    ap.add_argument("--outcomes", metavar="FILE", default=OUTCOMES,
                    help="the lesson tracker to check; overridable so the check can be proven to refuse")
    ap.add_argument("--wrappers-dir", metavar="DIR", default=None,
                    help="where this OS's suites live (default: its review-job directory); "
                         "overridable so the check can be proven to refuse")
    a = ap.parse_args()

    check_frontmatter_and_sources()
    check_links()
    check_dashes()
    check_line_endings()
    check_outcomes(a.outcomes)
    if a.diff:
        check_diff(a.diff)
    if not a.no_wrappers:
        check_wrappers(a.wrappers_dir, a.wrappers_full)

    n = len(list(notes()))
    for w in warn:
        print(f"warn  {w}")
    for f in fail:
        print(f"FAIL  {f}")
    print(f"\n{n} notes checked, {len(fail)} failures, {len(warn)} warnings")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
