#!/usr/bin/env python3
"""Proves the ask enumerator splits an inline numbered list instead of collapsing it.

Read-only: imports enumerate_asks and calls it. No files, no subprocesses.

  python harness/tests/test_ask_enumeration.py
    -> "ok: inline lists split", exit 0
    -> "FAIL: ...", exit 1

Paid for on 2026-08-22: The owner answered four questions in one line, as a numbered list with no line
breaks, and the
enumerator returned a single ask, truncated mid sentence. Four instructions became one,
which is precisely the partial compliance failure the ledger exists to catch.
"""
import importlib.util, pathlib, sys

spec = importlib.util.spec_from_file_location(
    "ledger", pathlib.Path(__file__).resolve().parents[1] / "ledger.py")
ledger = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ledger)

fails = []


def check(name, condition, detail):
    if not condition:
        fails.append(f"{name}: {detail}")


# The shape of the prompt that broke it: four answers in one line.
asks = ledger.enumerate_asks(
    "1) push it, 2) keep the old one 3) approved 4) if it belongs in the harness "
    "then move it there")
texts = [t for _, t in asks]
check("inline list splits", len(asks) >= 3,
      f"expected at least 3 asks from a four part inline list, got {len(asks)}: {texts}")
check("push survives", any("push" in t for t in texts), f"no ask mentions push: {texts}")
check("keep survives", any("keep" in t for t in texts), f"no ask mentions keep: {texts}")
check("harness survives", any("harness" in t for t in texts), f"no ask mentions harness: {texts}")

# Markdown bullets still work, one ask each.
bullets = ledger.enumerate_asks("- add the loader\n- write its tests\n- keep the linter clean")
check("bullets split", len(bullets) == 3, f"expected 3 asks from 3 bullets, got {len(bullets)}")

# Sentences on one line still split.
sentences = ledger.enumerate_asks("Add a config loader. Also write tests for it.")
check("sentences split", len(sentences) >= 2,
      f"expected 2 asks from 2 sentences, got {len(sentences)}: {[t for _, t in sentences]}")

# Ids are sequential and unique, since a mapping refers to them.
ids = [a for a, _ in ledger.enumerate_asks("1) one thing. 2) another thing. 3) a third thing")]
check("ids sequential", ids == [f"A{i + 1}" for i in range(len(ids))], f"ids are {ids}")

# Truncation is visible rather than silent.
long_ask = ledger.enumerate_asks("please add " + ("a very long requirement " * 12))
check("truncation is marked",
      not long_ask or all(len(t) <= 140 and (len(t) < 130 or t.endswith("[truncated]"))
                          for _, t in long_ask),
      f"a clipped ask must say so: {[t for _, t in long_ask]}")

# Noise without a verb is still dropped, so the signal stays readable.
noise = ledger.enumerate_asks("hi there\nthanks!\nok")
check("noise dropped", len(noise) == 0, f"expected no asks from pleasantries, got {noise}")

if fails:
    for f in fails:
        print(f"FAIL: {f}")
    sys.exit(1)
print("ok: inline lists split (and bullets, sentences, ids, visible truncation, noise dropped)")
sys.exit(0)
