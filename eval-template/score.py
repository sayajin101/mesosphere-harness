#!/usr/bin/env python3
"""Total the judge's verdicts and compare them with the incumbent, mechanically.

The judge is a model, because deciding whether an answer matches a real decision
needs judgment. Adding the numbers up, noticing a scenario the judge skipped, and
deciding whether the incumbent held do not, so a script does them.

  python3 score.py runs/2026-11-01-scores.json
  python3 score.py runs/NEW-scores.json --scenarios scenarios/scenarios.json --incumbent runs/OLD-scores.json
  python3 score.py --selftest

A scores file is a JSON array, one entry per scenario:
  {"id": "...", "decision_match": 0 | 0.5 | 1, "grounding": 0 | 1, "style": 0 | 1, "note": "..."}

Refuses (exit 1) on: a value outside its scale, a duplicate id, and, with
--scenarios, any active scenario left unscored or any score for a scenario that
is not in the set. A run that quietly skips its hardest scenarios would otherwise
score higher than one that answered everything.
"""
import argparse, json, pathlib, sys, tempfile

SCALES = {"decision_match": (0, 0.5, 1), "grounding": (0, 1), "style": (0, 1)}


class Invalid(Exception):
    pass


def load_scores(path):
    # A refusal, not a traceback: a missing file is phase 6's expected red baseline.
    try:
        data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise Invalid(f"{path}: no such scores file yet")
    except (OSError, ValueError) as e:
        raise Invalid(f"{path}: unreadable scores file ({e})")
    if not isinstance(data, list) or not data:
        raise Invalid(f"{path}: expected a non empty JSON array of scores")
    seen = set()
    for i, row in enumerate(data):
        sid = row.get("id")
        if not sid:
            raise Invalid(f"{path}: entry {i} has no id")
        if sid in seen:
            raise Invalid(f"{path}: duplicate id {sid}")
        seen.add(sid)
        for field, scale in SCALES.items():
            if row.get(field) not in scale:
                raise Invalid(f"{path}: {sid} {field}={row.get(field)!r} is not one of {scale}")
    return data


def mean(rows, field):
    return round(sum(r[field] for r in rows) / len(rows), 3)


def summarise(rows):
    return {f: mean(rows, f) for f in SCALES}


def coverage(rows, scenarios_path):
    active = {s["id"] for s in json.loads(pathlib.Path(scenarios_path).read_text(encoding="utf-8"))}
    scored = {r["id"] for r in rows}
    missing, extra = sorted(active - scored), sorted(scored - active)
    if missing or extra:
        raise Invalid(f"coverage: {len(missing)} unscored {missing[:10]}, "
                      f"{len(extra)} not in the set {extra[:10]}")
    return len(active)


def compare(new, old):
    head_new, head_old = mean(new, "decision_match"), mean(old, "decision_match")
    verdict = "beaten" if head_new > head_old else "held" if head_new == head_old else "lost"
    common = {r["id"] for r in new} & {r["id"] for r in old}
    line = f"incumbent {head_old}, this run {head_new}: incumbent {verdict}"
    if common:
        n = [r for r in new if r["id"] in common]
        o = [r for r in old if r["id"] in common]
        line += (f"; on the {len(common)} scenarios both runs scored: "
                 f"{mean(n, 'decision_match')} vs {mean(o, 'decision_match')}")
    return verdict, line


def report(path, scenarios=None, incumbent=None):
    rows = load_scores(path)
    out = []
    if scenarios:
        out.append(f"coverage: all {coverage(rows, scenarios)} active scenarios scored once")
    s = summarise(rows)
    out.append(f"headline decision_match {s['decision_match']} over {len(rows)} scenarios "
               f"(grounding {s['grounding']}, style {s['style']})")
    misses = [r["id"] for r in rows if r["decision_match"] < 1]
    out.append(f"misses: {len(misses)} {misses}")
    if incumbent:
        out.append(compare(rows, load_scores(incumbent))[1])
    return out


def selftest():
    def write(d, name, obj):
        p = pathlib.Path(d) / name
        p.write_text(json.dumps(obj), encoding="utf-8")
        return str(p)

    def refuses(fn):
        try:
            fn()
        except Invalid:
            return True
        return False

    row = lambda i, dm, g=1, st=1: {"id": i, "decision_match": dm, "grounding": g, "style": st, "note": ""}
    with tempfile.TemporaryDirectory() as d:
        sc = write(d, "scenarios.json", [{"id": "a"}, {"id": "b"}, {"id": "c"}])
        good = write(d, "new.json", [row("a", 1), row("b", 0.5), row("c", 0, 0, 0)])
        old = write(d, "old.json", [row("a", 1), row("b", 0), row("c", 0)])
        lines = report(good, sc, old)
        checks = [
            ("headline is the mean decision_match", "headline decision_match 0.5 over 3" in lines[1]),
            ("misses are listed", "misses: 2" in lines[2]),
            ("a better run beats the incumbent", "incumbent beaten" in lines[3]),
            ("equal runs hold", compare(load_scores(old), load_scores(old))[0] == "held"),
            ("a worse run loses", compare(load_scores(old), load_scores(good))[0] == "lost"),
            ("an unscored scenario is refused",
             refuses(lambda: report(write(d, "skip.json", [row("a", 1), row("b", 1)]), sc))),
            ("a score outside the scale is refused",
             refuses(lambda: load_scores(write(d, "bad.json", [row("a", 0.7)])))),
            ("a duplicate id is refused",
             refuses(lambda: load_scores(write(d, "dup.json", [row("a", 1), row("a", 1)])))),
            ("an empty scores file is refused", refuses(lambda: load_scores(write(d, "empty.json", [])))),
        ]
    failed = [name for name, ok in checks if not ok]
    if failed:
        print("score selftest FAILED: " + "; ".join(failed))
        return 1
    print("score selftest ok")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("scores", nargs="?")
    ap.add_argument("--scenarios", help="the active scenario set, to prove every one was scored")
    ap.add_argument("--incumbent", help="the scores file of the run to beat")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.scores:
        ap.error("a scores file is required unless --selftest")
    try:
        for line in report(a.scores, a.scenarios, a.incumbent):
            print(line)
    except Invalid as e:
        print(f"REFUSED: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
