#!/usr/bin/env python3
"""The ninth readiness review's honest-use findings stay fixed.

An audit verdict summarised in the agent's own words ("1 gap: A2 has no gate") read as
clean and let the ledger close; an ask mapped by hand to a gate that does not exist
counted as covered; `--session a` acted on session b's ledger once a's had closed; prose
passwords ("password for prod: x") survived the scrubber; and a PROVE gate red only
because its interpreter was missing looked like an honest red.

  python3 harness/tests/test_readiness_r9.py
    -> "ok: the ninth review's findings stay fixed", exit 0
"""
import json, os, pathlib, re, subprocess, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _ledgerkit import ENGINE, HARNESS, check, file_check, finish, make_repo

ROOT = HARNESS.parent
CLEAN = {k: v for k, v in os.environ.items()
         if k not in ("LEDGER_DIR", "CLAUDE_SESSION_ID", "CLAUDE_CODE_SESSION_ID",
                      "CLAUDE_PROJECT_DIR", "LEDGER_STOP_GATE_ACTIVE", "LEDGER_DEPTH")}
EM = chr(8212)


def eng(cwd, *args, session="t"):
    return subprocess.run([sys.executable, str(ENGINE), "--session", session, *args], cwd=str(cwd),
                          capture_output=True, text=True, env=CLEAN, timeout=300)


def draft(root, gates, mapping, session="t", title="kit",
          prompt="build the release file for the next build\n", crlf=False):
    """Open a ledger and write `gates` (lines) and every ask mapped to `mapping`."""
    (root / "p.txt").write_text(prompt, encoding="utf-8")
    eng(root, "open", "--title", title, "--prompt-file", "p.txt", session=session)
    path = root / ".ledger" / f"{session}.md"
    text = path.read_text(encoding="utf-8").replace(
        "-->\n\n## Asks", "-->\n" + "\n".join(gates) + "\n\n## Asks", 1)
    text = re.sub(r"(?m)^(A\d+ .*) -> \?$", lambda m: f"{m.group(1)} -> {mapping}", text)
    path.write_bytes(text.replace("\n", "\r\n").encode() if crlf else text.encode())
    return path


GATE = ["- [ ] G1 PROVE: the release file exists", f"      CHECK: {file_check('release.txt')}"]

with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)

    # 1: a verdict must open with COVERED or GAPS FOUND, and COVERED naming a gap is gaps.
    root = make_repo(tmp / "audit")
    path = draft(root, GATE, "G1")
    eng(root, "declare")
    (root / "release.txt").write_text("v1")
    eng(root, "run")
    r = eng(root, "audit", "subagent", "1 gap: A2 (changelog entry) has no gate")
    check("a free text verdict is refused at record time", r.returncode != 0, r.stdout + r.stderr)
    r = eng(root, "close")
    check("and the ledger does not close on it", r.returncode != 0 and path.exists(), r.stdout)
    eng(root, "audit", "subagent", "COVERED except A2, which no gate covers")
    r = eng(root, "status")
    check("COVERED followed by a named gap reads as gaps", r.returncode == 1, r.stdout)
    r = eng(root, "close")
    check("close refuses over it", r.returncode != 0 and path.exists(), r.stdout)
    r = eng(root, "audit", "subagent", "COVERED: every ask has a gate, no gaps found")
    r = eng(root, "close")
    check("a clean COVERED still closes", r.returncode == 0 and not path.exists(), r.stdout + r.stderr)

    # 2: an ask mapped to a gate that does not exist is unmapped.
    root = make_repo(tmp / "ghost")
    draft(root, GATE, "G2")
    r = eng(root, "declare")
    check("declare refuses an ask mapped to a gate that does not exist",
          r.returncode != 0 and "A1" in r.stdout, r.stdout)
    root = make_repo(tmp / "noreason")
    draft(root, GATE, "none")
    r = eng(root, "declare")
    check("declare refuses a dismissal with no reason", r.returncode != 0, r.stdout)

    # 3: an explicit --session never lands on another session's ledger.
    root = make_repo(tmp / "sessions")
    draft(root, GATE + ["- [ ] G2 PROVE: the notes file exists", f"      CHECK: {file_check('notes.txt')}"],
          "G1, G2", session="b")
    eng(root, "declare", session="b")
    r = eng(root, "abandon", "G2", "not needed for my task", session="a")
    b = (root / ".ledger" / "b.md").read_text(encoding="utf-8")
    check("--session a with no a.md does not abandon session b's G2",
          r.returncode != 0 and not re.search(r"(?m)^\s+ABANDON:", b) and "G2: abandoned" not in r.stdout,
          r.stdout + r.stderr)

    # 5: a red baseline is explained, and a missing command is called out.
    root = make_repo(tmp / "stub")
    draft(root, ["- [ ] G1 PROVE: the proof file exists",
                 "      CHECK: pythonstub-not-installed -c \"import sys; sys.exit(1)\""], "G1")
    r = eng(root, "declare")
    check("declare warns that a baseline is red only because a command was not found",
          "WARNING" in r.stdout and "not found" in r.stdout, r.stdout)

    # NIT: a CRLF draft declares on the first try.
    root = make_repo(tmp / "crlf")
    draft(root, GATE, "G1", crlf=True)
    r = eng(root, "declare")
    check("a draft saved with CRLF declares", r.returncode == 0, r.stdout + r.stderr)

    # NIT: an em dash in a title archives as ", " with no stray spaces.
    root = make_repo(tmp / "title")
    draft(root, GATE, "G1", title=f"voice page {EM} first")
    eng(root, "declare")
    (root / "release.txt").write_text("v1")
    eng(root, "run")
    eng(root, "audit", "subagent", "COVERED")
    eng(root, "close", "--archive-to", "episodic")
    arch = "".join(p.read_text(encoding="utf-8") for p in (root / "episodic").glob("*.md"))
    check("the archived title reads 'voice page, first'", "# Ledger: voice page, first" in arch, arch[:400])

    # NIT: a core file that is not UTF-8 still loads the vault.
    vault = tmp / "vault"
    (vault / "harness").mkdir(parents=True)
    for rel in ("SOUL.md", "IDENTITY.md", "INDEX.md", "harness/CONTRACT.md"):
        (vault / rel).write_text("# page\n", encoding="utf-8")
    (vault / "SOUL.md").write_bytes(b"# Soul\ncaf\xe9 latin-1 byte\n")
    sys.path.insert(0, str(HARNESS))
    import session_context
    try:
        ctx = session_context.loaded_context(vault, "startup")
        ok = "latin-1 byte" in ctx
    except ValueError as exc:
        ok, ctx = False, repr(exc)
    check("a core file with a stray byte still loads", ok, ctx[-300:])

# 4: the prose shapes people actually type.
from history import scrub
for s, secret in [("password for the staging db: Hunter22!", "Hunter22"),
                  ("the password for prod: Hunter22!", "Hunter22"),
                  ("Password for root - Hunter22", "Hunter22"),
                  ("pw for wifi: Hunter22", "Hunter22"),
                  ("login with password Hunter22", "Hunter22"),
                  ("set the password to Hunter22", "Hunter22"),
                  ("the db password should be Hunter22", "Hunter22"),
                  ("passphrase for the key: blue river stone", "stone")]:
    check(f"scrubbed: {s}", secret not in scrub(s), scrub(s))
for s in ["password-protected zip", "the password field is required", "use a password manager",
          "the password for the user must be reset", "the token is not in the archive"]:
    check(f"survives: {s}", scrub(s) == s, scrub(s))

# 5, the doc: BOOTSTRAP's proof gate uses one check that works on every platform.
boot = ROOT / "BOOTSTRAP.md"
if boot.exists():
    check("BOOTSTRAP's proof gate no longer calls a bare `python`",
          "CHECK: python -c" not in boot.read_text(encoding="utf-8"))

finish("the ninth review's findings stay fixed")
