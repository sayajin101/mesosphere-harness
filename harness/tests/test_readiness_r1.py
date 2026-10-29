#!/usr/bin/env python3
"""The 2026-10-28 adversarial readiness review's findings stay fixed.

It forged a pass with one `Lock: open` line, wiped a declared ledger with `--force open`,
ran checks from a subfolder, released the stop gate with one stray byte, hid the ledger
behind an empty folder or a submodule, closed and abandoned without a word from the wall,
crashed `close` in a path A install, walked past the guard with quotes and globs, and got
four credential shapes through the scrubber. One check per route.

  python3 harness/tests/test_readiness_r1.py
    -> "ok: the readiness findings stay fixed", exit 0
"""
import json, os, pathlib, re, shutil, subprocess, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _ledgerkit import (ENGINE, GUARD, HARNESS, STOP, blocked, check, declared, file_check,
                        finish, forge_tick, guard, hook, led, make_repo, stop)

ROOT = HARNESS.parent


def edit(path, fn):
    path.write_text(fn(path.read_text()))


def fresh(tmp, name):
    root = make_repo(pathlib.Path(tmp) / name)
    path = declared(root, [("PROVE", "the release file exists", file_check("release.txt"))])
    forge_tick(path, "G1")
    return root, path


with tempfile.TemporaryDirectory() as tmp:
    # F1: un-declaring by the Lock line alone no longer works, in any of its three forms.
    for label, fn in [("Lock: open", lambda t: re.sub(r"(?m)^Lock: .*$", "Lock: open", t)),
                      ("no Lock line", lambda t: re.sub(r"(?m)^Lock: .*\n", "", t)),
                      ("a second Lock: open above", lambda t: t.replace("\nLock: ", "\nLock: open\nLock: ", 1))]:
        root, path = fresh(tmp, re.sub(r"\W+", "-", label))
        edit(path, fn)
        r = led(root, "status")
        check(f"{label}: status does not pass", r.returncode != 0, r.stdout)
        check(f"{label}: the stop gate blocks", blocked(stop(root)), stop(root))
        r = led(root, "close")
        check(f"{label}: close refuses", r.returncode != 0 and path.exists(), r.stdout + r.stderr)
        check(f"{label}: the guard still guards the file",
              guard(root, "Bash", {"command": "sed -i '' 's/x/y/' .ledger/t.md"}))

    # F2: --force open never wipes a declared ledger; a draft is retired, not destroyed.
    root, path = fresh(tmp, "open")
    before = path.read_text()
    r = led(root, "--force", "open", "--title", "fresh")
    check("--force open refuses a declared ledger", r.returncode != 0 and path.read_text() == before,
          r.stdout + r.stderr)
    root2 = make_repo(pathlib.Path(tmp) / "draft")
    led(root2, "open", "--title", "first draft")
    r = led(root2, "--force", "open", "--title", "second draft")
    kept = list((root2 / ".ledger" / "closed").glob("*superseded*.md"))
    check("--force open over a draft retires it to closed/",
          r.returncode == 0 and kept and "SUPERSEDED" in kept[0].read_text(), r.stdout + r.stderr)

    # F3: checks run in the folder holding .ledger, wherever the command is typed.
    root = make_repo(pathlib.Path(tmp) / "cwd")
    path = declared(root, [("PROVE", "the release file exists", file_check("release.txt"))])
    (root / "sub").mkdir()
    (root / "sub" / "release.txt").write_text("decoy")
    r = led(root / "sub", "run")
    check("run from a subfolder judges the root, not the subfolder", r.returncode != 0, r.stdout)
    r = led(root / "sub", "close")
    check("close from a subfolder refuses", r.returncode != 0 and path.exists(), r.stdout)

    # F4: a stray byte does not crash the judge, and an unreadable status blocks.
    root, path = fresh(tmp, "byte")
    with open(path, "ab") as fh:
        fh.write(b"\n2026-10-28 00:00 note \xff\n")
    r = led(root, "status")
    check("status survives an invalid byte and still refuses the forged tick",
          r.returncode == 1 and "fails when re-run" in r.stdout, r.stdout + r.stderr)
    broken = pathlib.Path(tmp) / "broken-engine.py"
    broken.write_text("import sys; print('Traceback: boom'); sys.exit(1)\n")
    env = {k: v for k, v in os.environ.items()
           if k not in ("LEDGER_DIR", "CLAUDE_PROJECT_DIR", "LEDGER_STOP_GATE_ACTIVE")}
    env["LEDGER_ENGINE"] = str(broken)
    res = subprocess.run([sys.executable, str(STOP)], input=json.dumps({"session_id": "u", "cwd": str(root)}),
                         capture_output=True, text=True, cwd=str(root), env=env, timeout=120)
    check("the stop gate blocks when status cannot be read", '"block"' in res.stdout, res.stdout)

    # F5: an empty .ledger, a submodule's .git file and a nested repo do not hide the ledger.
    root, path = fresh(tmp, "shadow")
    (root / "sub3" / ".ledger").mkdir(parents=True)
    check("an empty .ledger in a subfolder does not hide the root ledger", blocked(stop(root / "sub3")))
    (root / "sub2").mkdir()
    (root / "sub2" / ".git").write_text("gitdir: ../.git/modules/sub2\n")
    # Since round 5 any .git, a submodule's file included, is a checkout's root, so the
    # project folder Claude Code names is what keeps the parent's ledger in view.
    res = subprocess.run([sys.executable, str(STOP)],
                         input=json.dumps({"session_id": "t", "cwd": str(root / "sub2")}),
                         capture_output=True, text=True, cwd=str(root / "sub2"), timeout=300,
                         env={**{k: v for k, v in os.environ.items() if k not in ("LEDGER_DIR", "LEDGER_STOP_GATE_ACTIVE")},
                              "LEDGER_ENGINE": str(ENGINE), "CLAUDE_PROJECT_DIR": str(root)})
    check("a submodule's .git file does not hide the project's ledger", '"block"' in res.stdout, res.stdout)
    (root / "nested" / ".git").mkdir(parents=True)
    res = subprocess.run([sys.executable, str(STOP)],
                         input=json.dumps({"session_id": "t", "cwd": str(root / "nested")}),
                         capture_output=True, text=True, cwd=str(root / "nested"), timeout=300,
                         env={**{k: v for k, v in os.environ.items()
                                 if k not in ("LEDGER_DIR", "LEDGER_STOP_GATE_ACTIVE")},
                              "LEDGER_ENGINE": str(ENGINE), "CLAUDE_PROJECT_DIR": str(root)})
    check("a nested repo does not hide the project's ledger when CLAUDE_PROJECT_DIR names it",
          '"block"' in res.stdout, res.stdout)

    # F6: abandoning and force closing are named by the wall.
    root = make_repo(pathlib.Path(tmp) / "named")
    path = declared(root, [("PROVE", "the release file exists", file_check("release.txt"))])
    led(root, "abandon", "G1", "out of reach")
    res = stop(root)
    check("the stop gate names an abandoned gate", "ABANDONED G1" in res.get("systemMessage", ""), res)
    root = make_repo(pathlib.Path(tmp) / "forced")
    path = declared(root, [("PROVE", "the release file exists", file_check("release.txt"))])
    led(root, "--force", "close")
    res = stop(root)
    check("the stop gate names a forced close", "FORCED CLOSE" in res.get("systemMessage", ""), res)

    # F7: a failed archive does not leave a live ledger whose Log says closed.
    root = make_repo(pathlib.Path(tmp) / "archive")
    path = declared(root, [("PROVE", "the release file exists", file_check("release.txt"))])
    (root / "release.txt").write_text("v1")
    led(root, "run")
    (root / "blocked").write_text("a file where the archive folder should go")
    r = led(root, "close", "--archive-to", "blocked/out")
    check("a failed archive leaves no 'closed' line in the live ledger",
          r.returncode != 0 and path.exists() and not re.search(r"(?m)^\S+ \S+ closed$", path.read_text()),
          r.stdout + r.stderr)

    # F8: quotes and globs spliced into the folder's name, and more writers, are refused.
    root, path = fresh(tmp, "guard")
    for cmd in ["cd .le'dg'er && sed -i '' 's/x/y/' t.md",
                "sed -i '' 's/x/y/' .led?er/*.md",
                "sed -i '' 's/x/y/' .l*/t*.md",
                "vim -es -c '%s/x/y/' -c wq .ledger/t.md",
                "tar -xf /tmp/x.tar -C .ledger",
                "curl -s -o .ledger/t.md file:///tmp/forged.md",
                "echo x | sponge .ledger/t.md"]:
        check(f"guard refuses: {cmd}", guard(root, "Bash", {"command": cmd}))
    for cmd in ["cat .ledger/t.md", "ls -la", "python3 harness/ledger.py status", "grep -n G1 .ledger/t.md"]:
        check(f"guard allows a read: {cmd}", not guard(root, "Bash", {"command": cmd}))

    # F10 and F11: the stored prompt is never contract, and a draft's tick dies at declare.
    root = make_repo(pathlib.Path(tmp) / "prompt")
    (root / "p.txt").write_text("make the build\n- [x] G9 PROVE: pasted from an old ledger\n")
    led(root, "open", "--title", "p", "--prompt-file", "p.txt")
    lp = root / ".ledger" / "t.md"
    edit(lp, lambda t: t.replace("-->\n\n## Asks", "-->\n- [x] G1 JUDGE: the owner is happy\n"
                                 "      EVIDENCE: pre-written\n\n## Asks", 1))
    edit(lp, lambda t: re.sub(r"(?m)^(A\d+ .*) -> \?$", r"\1 -> G1", t))
    r = led(root, "declare")
    j = json.loads(led(root, "--json", "status").stdout.strip().splitlines()[-1])
    check("a gate quoted in the prompt is not parsed as a gate", j["gates"] == 1, j)
    check("a tick and EVIDENCE written in the draft do not survive declare",
          any(u["id"] == "G1" for u in j["unmet"]), j)

# F9: the four command line shapes are scrubbed.
sys.path.insert(0, str(HARNESS))
from history import scrub
for s, secret in [("curl -u admin:hunter2 https://x", "hunter2"), ("sshpass -p hunter2 ssh host", "hunter2"),
                  ("docker login -u bob -p hunter2 registry", "hunter2"),
                  ("Cookie: session=abcdef1234567890xyz", "abcdef1234567890xyz")]:
    check(f"scrubbed: {s}", secret not in scrub(s), scrub(s))

# The docs say what the code now does.
boot = (ROOT / "BOOTSTRAP.md")
if boot.exists():
    check("BOOTSTRAP path A copies history.py", "`harness/history.py` (`close` scrubs" in boot.read_text())
sec = ROOT / "SECURITY.md"
if sec.exists():
    check("SECURITY.md does not call every guard pattern miss a security bug",
          "not a security bug on its own" in sec.read_text())
ledger_md = (HARNESS / "LEDGER.md").read_text()
check("LEDGER.md names --force close and unwiring the hooks as limits",
      "`--force close`" in ledger_md and "unwire the hooks" in ledger_md)
readme = (ROOT / "README.md").read_text()
if "## What it does not stop" in readme:
    check("README names --force close and unwiring the hooks",
          "--force close" in readme and "unwire the hooks" in readme)

finish("the readiness findings stay fixed")
