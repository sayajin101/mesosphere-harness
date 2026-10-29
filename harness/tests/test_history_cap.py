#!/usr/bin/env python3
"""max_chars is a true cap: no extract is longer, whatever the first message's size.

Until 2026-10-28 the first message was always kept whole, so a 999,999 character
message passed a 1,000 character cap. An oversized message is now cut to fit and
marked, and the checkpoint still moves past it so the next run is not stuck on it.

  python3 harness/tests/test_history_cap.py
    -> "ok: the cap holds", exit 0
"""
import json, os, pathlib, subprocess, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _ledgerkit import check, finish

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "history.py"


def entry(ts, content):
    return json.dumps({"type": "user", "timestamp": ts,
                       "message": {"role": "user", "content": content}})


def run(d, msgs, cap):
    proj = d / "projects" / "-repo"
    proj.mkdir(parents=True, exist_ok=True)
    f = proj / "s1.jsonl"
    f.write_text("\n".join(entry(f"2026-10-28T10:{i:02d}:00Z", m) for i, m in enumerate(msgs)) + "\n")
    os.utime(f, (1924992000, 1924992000))
    cfg = d / "mining.json"
    cfg.write_text(json.dumps({"every_days": 30, "max_chars": cap, "workdir": str(d / "work"),
                               "start_from": "2026-10-27",
                               "sources": [{"type": "claude-code", "path": str(d / "projects")}]}))
    r = subprocess.run([sys.executable, str(SCRIPT), "--config", str(cfg), "--now",
                        "2026-10-29T00:00:00Z", "--force"], capture_output=True, text=True)
    rows = [json.loads(x) for p in (d / "work").glob("new-*.jsonl") for x in p.read_text().splitlines()]
    state = json.loads((d / "work" / "state.json").read_text()) if (d / "work" / "state.json").exists() else {}
    return r.stdout.strip(), rows, state


with tempfile.TemporaryDirectory() as tmp:
    out, rows, state = run(pathlib.Path(tmp), ["word " * 200_000], 1000)
    total = sum(len(r["text"]) for r in rows)
    check("a giant first message is cut to the cap", rows and total <= 1000, f"{total} chars: {out}")
    check("the cut is marked", rows and "cut" in rows[0]["text"][-40:], rows[0]["text"][-60:] if rows else "")
    check("the checkpoint moves past it", state.get("since", "").startswith("2026-10-28T10:00"), state)

with tempfile.TemporaryDirectory() as tmp:
    out, rows, state = run(pathlib.Path(tmp), ["said by the owner " * 35, "also said by the owner " * 30], 1000)
    total = sum(len(r["text"]) for r in rows)
    check("two messages that overflow together stop at the first", len(rows) == 1 and total <= 1000,
          f"{len(rows)} rows, {total} chars")
    check("the run says it was capped", "capped" in out, out)

finish("the cap holds")
