#!/usr/bin/env python3
"""The eighth readiness review's honest-use findings stay fixed.

On Windows an arrow in a gate outcome crashed declare before it locked, and verify read
notes in the code page, so a curly quote crashed it and an em dash slipped past the dash
rule. A quoted passphrase kept every word but its first, base64url tokens survived, the
ask list stopped at 14 without a word, a second archive with the same title replaced the
first, and a UTF-16 prompt file opened with zero asks.

  python3 harness/tests/test_readiness_r8.py
    -> "ok: the eighth review's findings stay fixed", exit 0
"""
import json, os, pathlib, re, subprocess, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _ledgerkit import ENGINE, HARNESS, check, file_check, finish, led, make_repo

CLEAN = {k: v for k, v in os.environ.items()
         if k not in ("LEDGER_DIR", "CLAUDE_SESSION_ID", "CLAUDE_CODE_SESSION_ID",
                      "CLAUDE_PROJECT_DIR", "LEDGER_STOP_GATE_ACTIVE", "LEDGER_DEPTH")}


def eng(cwd, *args, **env):
    return subprocess.run([sys.executable, str(ENGINE), "--session", "t", *args], cwd=str(cwd),
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env={**CLEAN, **env}, timeout=300)


def draft(root, outcome, chk, prompt="build the release file for the next build\n"):
    """Open a ledger, write one gate, map every ask to it. Not declared."""
    (root / "prompt.txt").write_text(prompt, encoding="utf-8")
    eng(root, "open", "--title", "kit", "--prompt-file", "prompt.txt")
    path = root / ".ledger" / "t.md"
    text = path.read_text(encoding="utf-8").replace(
        "-->\n\n## Asks", f"-->\n- [ ] G1 PROVE: {outcome}\n      CHECK: {chk}\n\n## Asks", 1)
    path.write_text(re.sub(r"(?m)^(A\d+ .*) -> \?$", r"\1 -> G1", text), encoding="utf-8")
    return path


with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)

    # F1: a character outside the Windows code page never crashes the engine.
    root = make_repo(tmp / "cp1252")
    path = draft(root, "the p\u00e1gina \u2192 menu file exists", file_check("menu.txt"))
    win = {"PYTHONIOENCODING": "cp1252"}
    r = eng(root, "declare", **win)
    check("declare under cp1252 with an arrow in an outcome locks the ledger",
          r.returncode == 0 and "Traceback" not in r.stderr
          and not path.read_text(encoding="utf-8").split("\n")[1].startswith("Lock: open"),
          r.stdout + r.stderr)
    for cmd in ("status", "brief", "run"):
        r = eng(root, cmd, **win)
        check(f"{cmd} under cp1252 does not crash", "Traceback" not in r.stderr, r.stderr[-400:])

    # F4: no silent cap on the asks.
    root = make_repo(tmp / "cap")
    lines = "\n".join(f"{n}. update the page number {n} with its new sources" for n in range(1, 19))
    (root / "p.txt").write_text("Please do all of these:\n" + lines + "\n", encoding="utf-8")
    eng(root, "open", "--title", "cap", "--prompt-file", "p.txt")
    asks = re.findall(r"(?m)^A\d+ ", (root / ".ledger" / "t.md").read_text(encoding="utf-8"))
    check("an 18 item prompt yields 18 asks", len(asks) == 18, len(asks))

    # F6: a UTF-16 prompt file (PowerShell 5.1 `>`) enumerates its asks.
    root = make_repo(tmp / "u16")
    text = "1. add the export button\r\n2. fix the login redirect\r\n3. keep the tests green\r\n"
    (root / "p16.txt").write_bytes(text.encode("utf-16"))
    r = eng(root, "open", "--title", "u16", "--prompt-file", "p16.txt")
    body = (root / ".ledger" / "t.md").read_text(encoding="utf-8")
    check("a UTF-16 prompt file opens with its three asks",
          len(re.findall(r"(?m)^A\d+ ", body)) == 3 and "\x00" not in body, r.stdout + r.stderr)
    root = make_repo(tmp / "nul")
    (root / "p.txt").write_bytes(text.encode("utf-16-le"))
    r = eng(root, "open", "--title", "nul", "--prompt-file", "p.txt")
    check("a prompt file full of NULs is refused, not opened empty",
          r.returncode != 0 and not (root / ".ledger" / "t.md").exists(), r.stdout + r.stderr)

    # F6, the gates file: a UTF-16 amendment is read, not a traceback.
    root = make_repo(tmp / "amend16")
    draft(root, "the release file exists", file_check("release.txt"))
    eng(root, "declare")
    (tmp / "more16.txt").write_bytes(
        f"- [ ] G2 PROVE: the notes file exists\n      CHECK: {file_check('notes.txt')}\n".encode("utf-16"))
    r = eng(root, "--force", "declare", "--gates-file", str(tmp / "more16.txt"))
    check("a UTF-16 gates file amends the contract",
          r.returncode == 0 and "G2 PROVE" in (root / ".ledger" / "t.md").read_text(encoding="utf-8"),
          r.stdout + r.stderr)

    # F5 and N7: a second archive with the same title keeps the first, and --archive-to
    # resolves from the ledger's root, not the folder close was typed in.
    root = make_repo(tmp / "archive")
    (root / "sub").mkdir()
    for n in (1, 2):
        draft(root, "the release file exists", file_check("release.txt"))
        eng(root, "declare")
        (root / "release.txt").write_text(f"v{n}")
        eng(root, "run")
        eng(root, "evidence", "G1", f"release run {n}")
        eng(root, "audit", "subagent", "COVERED")
        r = eng(root / "sub", "close", "--archive-to", "episodic")
        (root / "release.txt").unlink()
    kept = sorted((root / "episodic").glob("*.md")) if (root / "episodic").is_dir() else []
    check("two same-day closes with one title keep two archives", len(kept) == 2,
          [p.name for p in kept] + [r.stdout + r.stderr])
    check("--archive-to from a subfolder lands at the ledger's root",
          not (root / "sub" / "episodic").exists(), list((root / "sub").iterdir()))

    # N6: the JSON audit label says which party is awaited.
    root = make_repo(tmp / "label")
    draft(root, "the release file exists", file_check("release.txt"))
    eng(root, "declare")
    eng(root, "audit", "awaiting-subagent", "dispatched")
    j = json.loads(eng(root, "--json", "status").stdout.strip().splitlines()[-1])
    check("status --json names an awaited subagent as such", j["audit"] == "awaiting-subagent", j)

    # F2: verify reads notes as UTF-8 whatever the locale says.
    vault = tmp / "vault"
    (vault / "heuristics").mkdir(parents=True)
    (vault / "heuristics" / "t.md").write_text(
        "She said, \u201cship it\u201d, \u2014 then left.\n", encoding="utf-8")
    code = (f"import sys; sys.path.insert(0, {str(HARNESS)!r}); import verify; "
            "verify.check_dashes(); verify.check_links(); print('FAILS', verify.fail)")
    env = {**CLEAN, "LC_ALL": "en_US.ISO8859-1", "LANG": "en_US.ISO8859-1", "PYTHONUTF8": "0"}
    env.pop("PYTHONIOENCODING", None)
    r = subprocess.run([sys.executable, "-c", code], cwd=str(vault), capture_output=True,
                       text=True, env=env, timeout=60)
    check("verify under a non UTF-8 locale still catches the em dash",
          "em-dash" in r.stdout and "Traceback" not in r.stderr, r.stdout + r.stderr)

# F3: quoted passphrases, base64url tokens, and the smaller shapes from the same review.
sys.path.insert(0, str(HARNESS))
from history import scrub
for s, secret in [
        ('{"password": "correct horse battery staple"}', "battery"),
        ('PASSWORD="correct horse battery staple"', "battery"),
        ('wifi_password: "correct horse battery staple"', "battery"),
        ("secret = 'correct horse battery staple'", "battery"),
        ('DB_PASS="correct horse battery staple"', "battery"),
        ('{\\"password\\":\\"Hunter2 pass phrase\\"}', "phrase"),
        ("https://discord.com/api/webhooks/1234567890123456789/Xy-7aB_c9dEfGhIj-"
         + "KlMnOpQr_StUvWxYz0-12345678_AbCdEfGhIjK-LmNoPqRsTuV", "KlMnOpQr"),
        ("token Ab3dEf-Gh1jKl_Mn0pQr-St9vWx_Yz2bCd-Ef4hIj_Kl5", "Gh1jKl"),
        ("az login -u me -p 'Winter2026!'", "Winter2026"),
        ("sqlplus scott/Tiger123!@orcl", "Tiger123"),
        ("the pw for the router is Winter2026", "Winter2026"),
        ("password: |\n  Winter2026!\nnext: 1", "Winter2026")]:
    check(f"scrubbed: {s[:50]}", secret not in scrub(s), scrub(s))
for s in ["test_readiness_r1_and_a_very_long_snake_case_name_x",
          "2026-10-29-ledger-tidy-the-docs-and-other-things-here",
          "pip install a==1.2.3", "git@github.com:org/repo.git", "the token is not in the archive"]:
    check(f"survives: {s}", scrub(s) == s, scrub(s))

# The privacy review's catch: ENGINEERING.md no longer says the stop gate fails open on a
# missing engine, a timeout or unreadable output.
eng_md = (HARNESS / "ENGINEERING.md").read_text(encoding="utf-8")
check("ENGINEERING.md says the stop gate fails closed when it cannot get an answer",
      "allows the turn on every error path" not in eng_md and "fails closed instead" in eng_md)

finish("the eighth review's findings stay fixed")
