#!/usr/bin/env python3
"""Strip the answers from the scenario set before any runner sees it.

The runner must never see ground truth, and the party that prepares the blind set
should not be a model deciding what to leave out. This script does it
mechanically: it keeps only the situation and the options, shuffles option order,
gives each scenario a neutral id, and writes the mapping to a separate key file
that only the judge step reads.

  python3 blind.py scenarios/scenarios.json --out blind.json --key key.json [--seed 7]
  python3 blind.py --selfcheck scenarios/scenarios.json

--selfcheck writes nothing and prints counts only, never scenario text:
  "30 scenarios blinded, 0 ground truth fields leaked"   exit 0
  "30 scenarios blinded, 2 ground truth fields leaked"   exit 1

A leak is either a field other than situation and options reaching the blind
record, or a ground truth quote appearing word for word inside the situation or
an option, which means the scenario itself gives its answer away.
"""
import argparse, json, pathlib, random, sys

KEEP = ("situation", "options")
QUOTE_MIN = 25  # shorter quotes collide with ordinary phrasing


def load(path):
    data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise SystemExit(f"{path}: expected a non empty JSON array of scenarios")
    for i, s in enumerate(data):
        missing = [k for k in ("id", "situation", "options", "ground_truth") if k not in s]
        if missing:
            raise SystemExit(f"{path}: scenario {i} is missing {', '.join(missing)}")
        if not isinstance(s["options"], list) or len(s["options"]) < 2:
            raise SystemExit(f"{path}: scenario {s['id']} needs at least two options")
    ids = [s["id"] for s in data]
    if len(ids) != len(set(ids)):
        raise SystemExit(f"{path}: duplicate scenario ids")
    return data


def blind(scenarios, seed):
    rng = random.Random(seed)
    order = list(range(len(scenarios)))
    rng.shuffle(order)
    blinded, key = [], {}
    for n, idx in enumerate(order, 1):
        s = scenarios[idx]
        perm = list(range(len(s["options"])))
        rng.shuffle(perm)
        bid = f"S{n:02d}"
        blinded.append({"bid": bid, "situation": s["situation"],
                        "options": [s["options"][p] for p in perm]})
        # key[bid]["option_map"][shown_position] = original_position
        key[bid] = {"id": s["id"], "option_map": perm}
    return blinded, key


def leaks(scenarios, blinded):
    count = 0
    by_situation = {b["situation"]: b for b in blinded}
    for s in scenarios:
        b = by_situation.get(s["situation"])
        if b is None:
            count += 1
            continue
        count += len([k for k in b if k not in KEEP + ("bid",)])
        gt = s.get("ground_truth") or {}
        quote = (gt.get("quote") or "").strip().lower()
        if len(quote) >= QUOTE_MIN:
            shown = " ".join([b["situation"], *b["options"]]).lower()
            if quote in shown:
                count += 1
    return count


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("scenarios")
    ap.add_argument("--out")
    ap.add_argument("--key")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()

    scenarios = load(a.scenarios)
    blinded, key = blind(scenarios, a.seed)
    leaked = leaks(scenarios, blinded)
    print(f"{len(blinded)} scenarios blinded, {leaked} ground truth fields leaked")
    if a.selfcheck:
        return 1 if leaked else 0
    if leaked:
        print("refusing to write a blind set that leaks its answers", file=sys.stderr)
        return 1
    if not a.out or not a.key:
        ap.error("--out and --key are required unless --selfcheck")
    src = pathlib.Path(a.scenarios).resolve()
    for target in (a.out, a.key):
        if pathlib.Path(target).resolve() == src:
            ap.error("refusing to overwrite the scenario file")
    pathlib.Path(a.out).write_text(json.dumps(blinded, indent=2) + "\n", encoding="utf-8")
    pathlib.Path(a.key).write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
    print(f"blind set: {a.out}  key (judge only): {a.key}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
