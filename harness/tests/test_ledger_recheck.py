#!/usr/bin/env python3
"""A forged tick counts for nothing: status, close and the stop gate re-run the checks.

On 2026-10-28 a readiness review ticked a PROVE gate's box and wrote its EVIDENCE line
with a python one liner. The lock covers what a gate means, not whether it was met, so
the lock stayed intact, status exited 0, the stop gate let the turn end and close
archived the ledger as met. The fix stops trusting the file: every ticked PROVE and
HOLD gate that is not abandoned has its CHECK re-run, and only the re-run counts.

  python3 harness/tests/test_ledger_recheck.py
    -> "ok: a forged tick is ignored", exit 0
"""
import json, pathlib, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _ledgerkit import (blocked, check, declared, file_check, finish, forge_tick, led,
                        make_repo, stop)

with tempfile.TemporaryDirectory() as tmp:
    root = make_repo(tmp)
    (root / "config.txt").write_text("x")  # a HOLD gate must pass at declare
    path = declared(root, [("PROVE", "the release file exists", file_check("release.txt")),
                           ("HOLD", "the config file is still there", file_check("config.txt")),
                           ("PROVE", "an impossible extra", file_check("never.txt"))])
    led(root, "abandon", "G3", "out of scope, on the record")
    led(root, "run")

    forge_tick(path, "G1")
    r = led(root, "status")
    check("status refuses a forged tick", r.returncode == 1, r.stdout + r.stderr)
    check("status says the re-run failed", "fails when re-run" in r.stdout, r.stdout)
    j = json.loads(led(root, "--json", "status").stdout.strip().splitlines()[-1])
    check("status --json counts the forged gate unmet",
          any(u["id"] == "G1" for u in j["unmet"]) and j["rechecked"] >= 1, j)
    check("an abandoned gate is not re-run and does not block",
          not any(u["id"] == "G3" for u in j["unmet"]), j)
    check("the stop gate blocks a forged tick", blocked(stop(root)), stop(root))
    r = led(root, "close")
    check("close refuses a forged tick", r.returncode != 0 and path.exists(), r.stdout + r.stderr)

    # The real thing satisfies it.
    (root / "release.txt").write_text("v1")
    r = led(root, "status")
    check("a ticked gate whose check passes is met", r.returncode == 0, r.stdout + r.stderr)
    check("the stop gate allows once the checks really pass", not blocked(stop(root)), stop(root))

    # A regression after the tick is caught without anyone running `run`.
    (root / "release.txt").unlink()
    r = led(root, "status")
    check("status catches a PROVE regression with no run", r.returncode == 1, r.stdout)
    (root / "release.txt").write_text("v1")
    (root / "config.txt").unlink()
    r = led(root, "status")
    check("status catches a HOLD regression with no run", r.returncode == 1 and "G2" in r.stdout,
          r.stdout)

finish("a forged tick is ignored")
