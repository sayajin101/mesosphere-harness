#!/usr/bin/env python3
"""Prove blind.py hides the answers and score.py refuses bad runs.

Read-only with respect to the repo: everything is written to a temp directory.

  python eval-template/tests/test_blind_score.py
    -> "ok: blind and score", exit 0
"""
import json, pathlib, subprocess, sys, tempfile

HERE = pathlib.Path(__file__).resolve().parents[1]
BLIND, SCORE = HERE / "blind.py", HERE / "score.py"
EXAMPLE = HERE / "scenarios" / "scenarios.json"
fails = []


def check(name, ok, detail=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}")
    if not ok:
        fails.append(f"{name}: {detail}")


def run(*args):
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True)


with tempfile.TemporaryDirectory() as d:
    d = pathlib.Path(d)
    out, key = d / "blind.json", d / "key.json"
    r = run(BLIND, EXAMPLE, "--out", out, "--key", key, "--seed", "3")
    check("blind writes a set and a key", r.returncode == 0 and out.is_file() and key.is_file(), r.stdout + r.stderr)
    blinded = json.loads(out.read_text())
    keymap = json.loads(key.read_text())
    original = {s["id"]: s for s in json.loads(EXAMPLE.read_text())}
    text = out.read_text()
    check("no ground truth reaches the runner",
          all(w not in text for w in ("ground_truth", "reasoning", "contamination_check", "example-0")), text[:200])
    check("every record holds only bid, situation and options",
          all(set(b) == {"bid", "situation", "options"} for b in blinded), str(blinded[0].keys()))
    ok = True
    for b in blinded:
        src = original[keymap[b["bid"]]["id"]]
        perm = keymap[b["bid"]]["option_map"]
        ok &= [src["options"][p] for p in perm] == b["options"]
    check("the key maps every shown option back to the original", ok)

    r = run(BLIND, "--selfcheck", EXAMPLE)
    check("selfcheck passes the clean example", r.returncode == 0 and ", 0 ground truth fields leaked" in r.stdout, r.stdout)
    check("selfcheck prints counts, not scenario text", "slow database" not in r.stdout, r.stdout)

    leaky = json.loads(EXAMPLE.read_text())
    leaky[0]["situation"] += " " + leaky[0]["ground_truth"]["quote"]
    lp = d / "leaky.json"
    lp.write_text(json.dumps(leaky))
    r = run(BLIND, "--selfcheck", lp)
    check("a scenario that quotes its own answer is caught", r.returncode == 1 and ", 1 ground truth fields leaked" in r.stdout, r.stdout)
    r = run(BLIND, lp, "--out", d / "x.json", "--key", d / "y.json")
    check("a leaking set is never written", r.returncode == 1 and not (d / "x.json").exists(), r.stdout + r.stderr)
    r = run(BLIND, EXAMPLE, "--out", EXAMPLE, "--key", d / "k.json")
    check("blind refuses to overwrite the scenario file", r.returncode != 0, r.stdout + r.stderr)

    r = run(SCORE, "--selftest")
    check("score selftest passes", r.returncode == 0 and r.stdout.strip() == "score selftest ok", r.stdout)
    sp = d / "scores.json"
    sp.write_text(json.dumps([{"id": "example-01", "decision_match": 1, "grounding": 1, "style": 0, "note": ""}]))
    r = run(SCORE, sp, "--scenarios", EXAMPLE)
    check("score refuses a run that skipped a scenario", r.returncode == 1 and "REFUSED" in r.stdout, r.stdout)

if fails:
    print("\nFAIL\n  " + "\n  ".join(fails))
    sys.exit(1)
print("ok: blind and score")
