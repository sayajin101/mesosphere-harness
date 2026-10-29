#!/usr/bin/env python3
"""Extract the owner's NEW chat messages since the last run, scrubbed, for mining.

Initial mining reads the whole history once. After that, this runs on the owner's
cadence (monthly by default) so the vault keeps learning from chats instead of
freezing at setup. It is a plain script on purpose: an unattended agent run cannot
approve a command that writes files, so the job's wrapper runs this BEFORE the agent
starts and hands the agent the one line this prints.

  python3 harness/history.py --config mining.json            # extract if due
  python3 harness/history.py --config mining.json --dry-run  # counts only, writes nothing
  python3 harness/history.py --config mining.json --force    # ignore the cadence once

mining.json, at the vault root (machine paths may use ~):

  {"every_days": 30,                  # cadence; the owner chooses it
   "max_chars": 400000,               # cap per run, about 100k tokens; the rest waits
   "workdir": "~/persona-mining",      # OUTSIDE every repo; extracts and state live here
   "start_from": "2026-10-27",        # first run reads from here (the initial mining date)
   "sources": [
     {"type": "claude-code", "path": "~/.claude/projects"},
     {"type": "command", "name": "cursor", "command": ["python3", "~/persona-mining/extractors/cursor.py"]}
   ]}

A "command" source is an extractor the owner's agent wrote at setup for a tool this
script does not read natively. It receives the cut-off time in HISTORY_SINCE (ISO 8601)
and prints JSON lines {"ts": ISO 8601, "text": "..."}: only the owner's own words.

The last line printed is the one the agent receives, always starting "mining:":
  mining: not configured | not due until <date> | 0 new messages
  mining: <n> new messages (<chars> chars, ~<tokens> tokens) from <sources> in <file>[; capped, the rest waits for the next run]
  mining: FAILED: <reason>

Standard library only. Never reads anything but the configured history; never writes
inside a repo; never records a checkpoint on a dry run or a failure.
"""
import argparse, json, os, pathlib, re, subprocess, sys
from datetime import datetime, timedelta, timezone

CUT = " [cut: longer than max_chars]"
MIN_CHARS = 20   # "ok", "yes", "continue" say little about a person
# Owner-role entries that are really the harness talking, not the owner typing.
NOT_THE_OWNER = re.compile(
    r"^\s*(<|Stop hook feedback|Another Claude session sent|\[SYSTEM NOTIFICATION|"
    r"\[Request interrupted|Caveat: The messages below|This session is being continued from a previous conversation|"
    r"You are running .{0,80}?scheduled weekly)")
SECRET_NAMES = (r"password|passwd|passphrase|passcode|pwd|pw|pass|secret|token|api[_-]?key|"
                r"access[_-]?key|private[_-]?key|client[_-]?secret|credentials?|auth|pin|key")
# A value: quoted (up to its closing quote, escaped JSON quotes too) or bare (up to
# whitespace or a closing bracket).
VALUE = r"""(?:\\?"[^"\n]*"|\\?'[^'\n]*'|[^\s,;}\]]+)"""
SCRUB = [
    # Prefixed keys and tokens, live and test: OpenAI and Stripe (sk-, sk_, pk_, rk_,
    # whsec_), GitHub, GitLab (personal, runner, trigger), npm, Slack (xoxa/b/p/r/s, xapp-),
    # AWS, Google API and OAuth.
    re.compile(r"\b(sk-|sk_|pk_|rk_|whsec_|ghp_|gho_|ghs_|ghu_|ghr_|github_pat_|glpat-|glrt-|glptt-|npm_|"
               r"xox[abposr]-|xapp-|AKIA|ASIA|AIza|GOCSPX-|sq0atp-|sq0csp-|dckr_pat_)[A-Za-z0-9_\-]{12,}"),
    # Google OAuth access tokens carry dots and dashes after their prefix.
    re.compile(r"\bya29\.[A-Za-z0-9_.\-]{12,}"),
    # JWTs, and private key blocks of every kind, PGP's "PRIVATE KEY BLOCK" included.
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}(?:\.[A-Za-z0-9_-]*)?"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY[A-Z ]*-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY[A-Z ]*-----"),
    # A key pasted without its END line goes to the end of the text (round 18).
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY[A-Z ]*-----[\s\S]*\Z"),
    # "use the token 2f9a8b7c6d5e4f3a2b1c": a hex value named as a secret, no = sign.
    re.compile(r"(?i)\b(?:token|key|secret)\s+(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{16,}\b"),
    # Passwords in URLs: scheme://user:secret@host, and scheme://:secret@host (redis).
    re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://[^/\s:@]*:)[^@\s]+@"),
    # Authorization headers: Basic, Bearer, Token or any scheme, whatever the length.
    re.compile(r"(?i)\bauthorization\s*[:=]\s*\S+(\s+\S+)?"),
    re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/\-]{8,}=*"),
    # Command line passwords: --password X, --password=X, mysql -pX (attached).
    re.compile(r"(?i)--(" + SECRET_NAMES + r")(?:=|\s+)" + VALUE),
    (re.compile(r"(?i)\b((?:mysql|mariadb)\w*\b[^\n]*?\s)-p(?!\s)\S+"),
     lambda m: m.group(1) + "-p[REDACTED]"),
    # More command lines (2026-10-28 readiness review): curl -u user:pass and wget
    # --user, sshpass -p and docker login -p (spaced), and cookie header values.
    (re.compile(r"(?i)\b((?:curl|wget)\b[^\n]*?\s(?:-u|--user)(?:=|\s+))(\S+?:)\S+"),
     lambda m: m.group(1) + m.group(2) + "[REDACTED]"),
    (re.compile(r"(?i)\b((?:sshpass|docker\s+login|podman\s+login|helm\s+registry\s+login)\b"
                r"[^\n]*?\s-p\s*)(\S+)"),
     lambda m: m.group(1) + "[REDACTED]"),
    # Round 8: az login -p, sqlplus user/pass@db, and a YAML block scalar's next line.
    (re.compile(r"(?i)\b(az\s+login\b[^\n]*?\s-p\s+)(\"[^\"]*\"|'[^']*'|\S+)"),
     lambda m: m.group(1) + "[REDACTED]"),
    (re.compile(r"(?i)\b(sqlplus\s+(?:-\w+\s+)*[^\s/@-][^\s/@]*/)[^\s@]+"),
     lambda m: m.group(1) + "[REDACTED]"),
    (re.compile(r"(?im)^(\s*[\w-]*(?:password|passphrase|secret|token)[\w-]*\s*:\s*[|>][-+]?[ \t]*\n)[ \t]+\S[^\n]*"),
     lambda m: m.group(1) + "  [REDACTED]"),
    (re.compile(r"(?i)\b((?:set-)?cookie\s*:\s*)[^\n]+"), lambda m: m.group(1) + "[REDACTED]"),
    # Round 2: redis-cli -a, wget and curl password flags, htpasswd -b, a .netrc line,
    # PowerShell's SecureString from plain text, a password piped into --password-stdin,
    # a Telegram bot token, and a bare token used as a URL's user name.
    (re.compile(r"(?i)\b(redis-cli\b[^\n]*?\s-a\s+)(\S+)"), lambda m: m.group(1) + "[REDACTED]"),
    (re.compile(r"(?i)(--(?:http|proxy|ftp)-?password(?:=|\s+))(\S+)"), lambda m: m.group(1) + "[REDACTED]"),
    (re.compile(r"(?i)\b(htpasswd\b[^\n]*?\s-\w*b\w*\s+\S+\s+\S+\s+)(\S+)"),
     lambda m: m.group(1) + "[REDACTED]"),
    (re.compile(r"(?i)\b(machine\s+\S+\s+login\s+\S+\s+password\s+)(\S+)"),
     lambda m: m.group(1) + "[REDACTED]"),
    (re.compile(r"(?i)(ConvertTo-SecureString\s+(?:-String\s+)?)(\"[^\"]*\"|'[^']*'|\S+)"),
     lambda m: m.group(1) + "[REDACTED]"),
    (re.compile(r"(?i)\b(echo|printf)\s+(\S+)(\s*\|[^\n]*--password-stdin)"),
     lambda m: m.group(1) + " [REDACTED]" + m.group(3)),
    re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b"),
    # Round 6: SendGrid keys, Azure AD client secrets, Google refresh tokens.
    re.compile(r"\bSG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?<![A-Za-z0-9_~.-])[A-Za-z0-9_~.-]{3}\dQ~[A-Za-z0-9_~.-]{30,40}"),
    re.compile(r"(?<![\w/])1//0[A-Za-z0-9_-]{20,}"),
    # Round 3: Discord bot tokens, and the signature of an Azure SAS URL.
    re.compile(r"\b[MNO][A-Za-z\d_-]{23,27}\.[A-Za-z\d_-]{6}\.[A-Za-z\d_-]{27,}"),
    # Round 8: a Discord webhook's token, which the base64 rule cut apart at its - and _.
    (re.compile(r"(?i)(discord(?:app)?\.com/api/webhooks/\d+/)[\w-]+"), lambda m: m.group(1) + "[REDACTED]"),
    (re.compile(r"(?i)\b(sig=)[A-Za-z0-9%+/=]{16,}"), lambda m: m.group(1) + "[REDACTED]"),
    (re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[A-Za-z0-9_\-]{16,}@"), lambda m: m.group(1) + "[REDACTED]@"),
    # Round 4: user:password@host with no scheme in front.
    (re.compile(r"(?<![\w/:@])([\w.-]{1,64}):([^\s@:/]{4,})@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*)"),
     lambda m: m.group(1) + ":[REDACTED]@" + m.group(3)),
    # .NET appSettings: <add key="ApiKey" value="..."/> keeps its value under a key
    # attribute that names the secret (round 17 review).
    (re.compile(r"(?i)(<add\b[^>]*\b(?:key|name)\s*=\s*\"[^\"]*(?:pass|secret|token|key|pwd)[^\"]*\"[^>]*?\bvalue\s*=\s*\")[^\"]*"),
     lambda m: m.group(1) + "[REDACTED]"),
    # A password or passphrase given a value runs to the end of the line, so every word
    # of a multi word passphrase goes; a quoted value is left to the rule below (round 5: three of four words survived).
    # Round 9: also after a short qualifier ("password for the staging db: x").
    re.compile(r"(?i)\b(password|passphrase|passwd)(?:\s+(?:for|of|on|to)\s+[^\n:=]{1,40}?)?"
               r"(\s*[:=]\s*)(?![\"'])[^\n]+"),
    # NAME=value and name: value for anything named like a secret, prefixed environment
    # names (OPENAI_API_KEY) and quoted JSON or YAML keys ("password": "x") included, at
    # any value length: a four character PIN is still a PIN.
    # Escaped JSON too (\"password\":\"x\", as secret managers print it), and the name
    # anywhere in an identifier (DB_PASSWORD_PROD), round 7. No optional quote before
    # VALUE: one there ate the opening quote, so "correct horse battery staple" lost
    # only its first word (round 8).
    # A value an earlier rule already redacted is taken whole, name and all: stopping
    # short of it left a stray "]" (round 14), and refusing it kept "token: [REDACTED]",
    # which BOOTSTRAP's scrub gate counts as a credential (round 16).
    re.compile(r"(?i)(?:\\?[\"'])?\b[A-Z0-9_]*(" + SECRET_NAMES + r")(?:_[A-Z0-9]+)*\b(?:\\?[\"'])?\s*[:=]\s*"
               r"(?:\[REDACTED\]|" + VALUE + ")"),
    # Said in prose: "my password is hunter2", "the pin was 4821". Only words that name a
    # secret outright: "the token is not in the archive" is a sentence, not a leak.
    re.compile(r"(?i)\b(password|passphrase|passcode|pin|pwd?|api[ _-]?key)(?:\s+(?:for|of|to)\s+[^\n]{1,40}?)?"
               r"(?:\s+(?:is|was|=|-|should\s+be|will\s+be|to)|\s*:)\s*:?\s*(?:\"[^\"\n]*\"|'[^'\n]*'|(?!not\b)\S+)"),
    # "login with password x", "use the passphrase x" (round 9).
    re.compile(r"(?i)\b(?:with|using|use)\s+(?:the\s+|a\s+|my\s+)?(?:password|passphrase|pwd?)\s+(?!(?:is|was|manager|field|policy|reset|prompt)\b)\S+"),
    # Round 21: "token <value>" with a token shaped value, and openssl, unzip and 7z
    # password flags.
    re.compile(r"(?i)\btoken\s+(?=[\w\-]*\d)(?=[\w\-]*[A-Za-z])[\w\-]{16,}"),
    (re.compile(r"(?i)\b((?:openssl|unzip|7z|7za)\b[^\n]*?\s-(?:k|P|p|passin\s+pass:|passout\s+pass:)\s*)(\S+)"),
     lambda m: m.group(1) + "[REDACTED]"),
    # "use secret abc123XYZ" (round 19): a token shaped value after the word.
    re.compile(r"(?i)\b(?:with|using|use)\s+(?:the\s+|a\s+|my\s+)?(?:secret|token)\s+(?=\S*\d)\S{6,}"),
    # "user admin password Winter2026": the bare word, then a value with a digit or a
    # symbol in it, so "password reset flow" and "password manager" are left alone (round 10).
    re.compile(r"(?i)\b(?:password|passwd|passphrase|pwd)\s+(?!(?:is|was|for|of|on|to|and|or|the|a|an|"
               r"reset|manager|field|policy|prompt|change|hash|hashing|login|auth|rules?|length|"
               r"strength|form|input|box|protected|less|based|via|in|from|with|stored|store|check|"
               r"validation|expired?|must|should|will|can)\b)(?=\S*[0-9!@#$%^&*])\S{4,}"),
    # Round 12: "the token is X" with a token shaped value (so "the token is not in the
    # archive" stays), "set DB_PASS to X", and "login admin / P@ssw0rd123".
    re.compile(r"(?i)\b(?:secret|token)\s+(?:is|was)\s+(?!(?:not|in|the|a|an|stored|missing|valid|"
               r"invalid|expired|set|now|still|being|kept|rotated|revoked)\b)(?=\S*\d)\S{6,}"),
    # Round 14: "creds are admin/hunter22", and a UUID shaped key named as one.
    (re.compile(r"(?i)\b((?:creds?|credentials)\s+(?:are|is|was|were|:)?\s*[^\s/]+/)\S+"),
     lambda m: m.group(1) + "[REDACTED]"),
    (re.compile(r"(?i)\b(key|token|secret)\b([^\n]{0,20}?)\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"),
     lambda m: m.group(1) + m.group(2) + "[REDACTED]"),
    (re.compile(r"(?i)\b(set\s+(?:the\s+|my\s+)?(?:[A-Z0-9_]+\s+)?[A-Z0-9_]*(?:PASS|PASSWORD|PASSWD|PWD|SECRET|TOKEN|API_?KEY)[A-Z0-9_]*\s+to\s+)\S+"),
     lambda m: m.group(1) + "[REDACTED]"),
    (re.compile(r"(?i)\b((?:login|user(?:name)?|creds?|credentials)\s*:?\s+\S+\s*/\s*)(?=\S*[A-Za-z])(?=\S*[0-9!@#$%^&*])\S{4,}"),
     lambda m: m.group(1) + "[REDACTED]"),
    # Round 13: "the api key 9a8b7c..." with no verb, "here's the secret X", and
    # "username admin pass X".
    re.compile(r"(?i)\bapi[ _-]?key\s+(?=[A-Za-z0-9_\-]*\d)[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)\bhere(?:'s|\s+is)\s+(?:the|my|your|our)\s+(?:secret|token|password|passphrase|"
               r"api[ _-]?key|key)\s*:?\s+(?=\S*[0-9!@#$%^&*])\S+"),
    (re.compile(r"(?i)\b((?:user(?:name)?|login)\s+\S+\s+(?:pass|pw|pwd)\s+)(?=\S*[0-9!@#$%^&*])\S+"),
     lambda m: m.group(1) + "[REDACTED]"),
    # Long hex in either case, and long base64 runs (AWS secret keys are 40).
    re.compile(r"(?i)\b[0-9a-f]{32,}\b"),
    re.compile(r"(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{32,}={0,2}(?![A-Za-z0-9+/])"),
    # And base64url (round 8), which splits at - and _ under the rule above. Mixed case
    # and a digit, so a long snake_case name or a dated slug is left alone.
    re.compile(r"(?<![\w-])(?=[\w-]*\d)(?=[\w-]*[A-Z])(?=[\w-]*[a-z])[A-Za-z0-9_-]{40,}(?![\w-])"),
    # Phone numbers: an international prefix, a grouped local number, or a UK mobile
    # (07xxx xxxxxx). Written so dates (2026-10-28) and times (10:11) are never touched.
    re.compile(r"(?<![\w:/-])\+\d{1,3}[\s.-]?\(?\d{1,4}\)?(?:[\s.-]?\d{2,4}){2,4}(?![\w:-])"),
    re.compile(r"(?<![\w:/-])\(?0\d{2,3}\)?[\s.]\d{3}[\s.]\d{3,4}(?![\w:-])"),
    re.compile(r"(?<![\w:/-])07\d{3}\s?\d{3}\s?\d{3}(?![\w:-])"),
    # A ten digit local number written without spaces, as in 0123456789.
    re.compile(r"(?<![\w:/.-])0[1-9]\d{8}(?![\w:-])"),
    # North American: (415) 555-0132, 415-555-0132, 415.555.0132.
    re.compile(r"(?<![\w:/-])\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?![\w:-])"),
]
# Card numbers and national ID numbers (13 digits, as South Africa's): 13 to 19 digits,
# spaced or dashed, redacted only when the Luhn check passes, so order numbers and
# timestamps mostly survive.
DIGIT_RUN = re.compile(r"(?<![\d-])\d(?:[ -]?\d){12,18}(?![\d-])")


def luhn(digits):
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch) * (2 if i % 2 else 1)
        total += n - 9 if n > 9 else n
    return total % 10 == 0


def scrub(text):
    for rx in SCRUB:
        rx, repl = rx if isinstance(rx, tuple) else (rx, "[REDACTED]")
        text = rx.sub(repl, text)
    return DIGIT_RUN.sub(lambda m: "[REDACTED]" if luhn(re.sub(r"\D", "", m.group(0)))
                         else m.group(0), text)


def parse_ts(s):
    # Python 3.9 parses a fraction of exactly 3 or 6 digits only, and dropped the rest
    # of the messages without a word: pad or cut it to 6 (round 14 review).
    s = re.sub(r"(\.\d+)", lambda m: "." + (m.group(1)[1:] + "000000")[:6], str(s), count=1)
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def owner_text(entry):
    """The owner's typed words in one Claude Code transcript line, or None."""
    if entry.get("type") != "user" or entry.get("isSidechain") or entry.get("isMeta"):
        return None
    # A compaction summary is typed by the model, not the owner, and paraphrases tool
    # output, other people's data included (round 16 review).
    if entry.get("isCompactSummary") or entry.get("isVisibleInTranscriptOnly"):
        return None
    # A headless run's prompt (the weekly review job's own, about 10k characters) is a
    # script, and an accepted next-prompt suggestion was worded by the model: neither
    # is the owner typing (round 17 review).
    if entry.get("entrypoint") == "sdk-cli" or entry.get("promptSource") in ("suggestion_accepted", "system"):
        return None
    # The class, not one more case: any origin marker that is not the human is not the
    # owner typing. An agent-started session's brief carries turnOrigin "sdk", a harness
    # notice origin.kind "task-notification" (round 18). Typed messages carry "human" or
    # neither field, so none are lost.
    origin = entry.get("origin")
    kind = origin.get("kind") if isinstance(origin, dict) else origin
    if entry.get("turnOrigin") not in (None, "human") or kind not in (None, "human"):
        return None
    content = (entry.get("message") or {}).get("content")
    # Context blocks the desktop app puts in front of what was typed are not the owner's
    # words, but what follows them is: strip them first (round 21 review).
    harness_block = re.compile(r"<(artifact-view-context|system-reminder|ide_selection|ide_opened_file)\b[^>]*>[\s\S]*?</\1>")
    if isinstance(content, str):
        content = harness_block.sub("", content).lstrip()
    elif isinstance(content, list):
        content = [dict(p, text=harness_block.sub("", p.get("text", "")).lstrip())
                   if isinstance(p, dict) and p.get("type") == "text" else p for p in content]
    if isinstance(content, list):
        if any(isinstance(p, dict) and p.get("type") == "tool_result" for p in content):
            return None
        # Block by block: one harness block in front (a system reminder) used to drop
        # the owner's own words after it (round 19 review).
        content = "\n".join(p.get("text", "") for p in content
                            if isinstance(p, dict) and p.get("type") == "text"
                            and not NOT_THE_OWNER.match(p.get("text", "")))
    if not isinstance(content, str) or NOT_THE_OWNER.match(content):
        return None
    # A paste is someone else's text: Claude Code stores it after what was typed,
    # wrapped in <pasted_content>, and a pasted Slack thread is colleagues' words.
    # Keep only what came before it, and drop any harness block left inside (round 19).
    content = re.split(r"<pasted_content\b", content, maxsplit=1)[0]
    content = re.sub(r"<system-reminder>[\s\S]*?</system-reminder>", "", content)
    return content.strip() or None


def claude_code(path, since):
    root = pathlib.Path(os.path.expanduser(path))
    if not root.is_dir():
        raise RuntimeError(f"claude-code path not found: {root}")
    for f in sorted(root.rglob("*.jsonl")):
        if "subagents" in f.parts:            # prompts written by an agent, not the owner
            continue
        if datetime.fromtimestamp(f.stat().st_mtime, timezone.utc) < since:
            continue
        with f.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = parse_ts(entry.get("timestamp", ""))
                text = owner_text(entry)
                if ts and text and ts >= since:
                    yield ts, text, f.stem


def command(src, since):
    cmd = [os.path.expanduser(c) for c in src["command"]]
    env = dict(os.environ, HISTORY_SINCE=since.isoformat())
    # UTF-8 whatever the locale: cp1252 on Windows failed on emoji bytes (round 15).
    out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                         env=env, timeout=600)
    if out.returncode != 0:
        raise RuntimeError(f"extractor {src.get('name', cmd[0])} exited {out.returncode}: {out.stderr.strip()[:200]}")
    for line in out.stdout.splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = parse_ts(row.get("ts", ""))
        if ts and ts >= since and isinstance(row.get("text"), str):
            yield ts, row["text"].strip(), src.get("name", "command")


def main():
    ap = argparse.ArgumentParser(description="Extract the owner's new chat messages for mining.")
    ap.add_argument("--config", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--now", help=argparse.SUPPRESS)  # tests only
    a = ap.parse_args()

    cfg_path = pathlib.Path(a.config)
    if not cfg_path.is_file():
        print("mining: not configured")
        return 0
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8-sig"))  # a BOM from Notepad is fine
        every = timedelta(days=float(cfg.get("every_days", 30)))
        cap = int(cfg.get("max_chars", 400000))
        work = pathlib.Path(os.path.expanduser(cfg["workdir"]))
        sources = cfg["sources"]
        now = parse_ts(a.now) if a.now else datetime.now(timezone.utc)
        state_path = work / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
        since = parse_ts(state.get("since") or cfg.get("start_from") or now.isoformat())
        last = parse_ts(state["last_run"]) if state.get("last_run") else None
        if last and now - last < every and not a.force:
            print(f"mining: not due until {(last + every).date().isoformat()}")
            return 0

        rows = []
        for src in sources:
            kind = src.get("type")
            gen = claude_code(src["path"], since) if kind == "claude-code" else \
                command(src, since) if kind == "command" else None
            if gen is None:
                raise RuntimeError(f"unknown source type {kind!r}")
            name = src.get("name", kind)
            rows += [(ts, name, sid, text) for ts, text, sid in gen if len(text) >= MIN_CHARS]
        rows.sort(key=lambda r: r[0])
        # One transcript can sit under two project folders: the same message, twice
        # (round 20 review found a fifth of an extract duplicated). Keep the first.
        seen, unique = set(), []
        for r in rows:
            if (r[0], r[3]) not in seen:
                seen.add((r[0], r[3]))
                unique.append(r)
        rows = unique
        # Sources read ts >= since, and the checkpoint counts how many messages at that
        # exact stamp were already taken: with ts > since, a cap between two messages
        # sharing a stamp lost the second for good (round 18 review).
        taken = int(state.get("taken_at_since") or 0) if state.get("since") else 0
        at_since = [r for r in rows if r[0] == since]
        rows = at_since[taken:] + [r for r in rows if r[0] != since]

        # A true cap. Until 2026-10-28 the first message was always kept whole, so one
        # 999,999 character paste sailed past a 1,000 character cap. A message longer than
        # the whole cap is cut to fit, marked, and counts as read; otherwise the run stops
        # at the first message that would overflow and the rest waits.
        kept, chars = [], 0
        for r in rows:
            clean = scrub(r[3])
            if len(clean) > cap:
                clean = clean[:max(0, cap - len(CUT))] + CUT[:cap]
            if chars + len(clean) > cap:
                break
            kept.append((r[0], r[1], r[2], clean))
            chars += len(clean)
        capped = len(kept) < len(rows)
        names = sorted({r[1] for r in kept})

        if not kept:
            if not a.dry_run:
                work.mkdir(parents=True, exist_ok=True)
                state_path.write_text(json.dumps({"since": since.isoformat(), "taken_at_since": taken,
                                                  "last_run": now.isoformat()}), encoding="utf-8")
            print("mining: 0 new messages")
            return 0
        out = work / f"new-{now.date().isoformat()}.jsonl"
        if out.exists():
            # A second run the same day kept the first's checkpoint and replaced its
            # extract, so those messages were never mined (round 16 review).
            out = work / f"new-{now.date().isoformat()}-{now.strftime('%H%M%S')}.jsonl"
        summary = (f"{len(kept)} new messages ({chars} chars, ~{chars // 4} tokens) from "
                   f"{', '.join(names)}")
        if a.dry_run:
            print(f"mining: dry run, nothing written: {summary}" + ("; would cap" if capped else ""))
            return 0
        work.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as fh:
            for ts, name, sid, text in kept:
                fh.write(json.dumps({"ts": ts.isoformat(), "source": name, "session": sid, "text": text}) + "\n")
        # The checkpoint moves only past what was actually written, so a capped run
        # resumes exactly where it stopped instead of skipping the remainder.
        last_ts = kept[-1][0]
        at_last = sum(1 for k in kept if k[0] == last_ts) + (taken if last_ts == since else 0)
        state_path.write_text(json.dumps({"since": last_ts.isoformat(), "taken_at_since": at_last,
                                          "last_run": now.isoformat()}), encoding="utf-8")
        print(f"mining: {summary} in {out}" + ("; capped, the rest waits for the next run" if capped else ""))
        return 0
    except Exception as exc:  # the wrapper must get a line it can hand on, never a traceback
        print(f"mining: FAILED: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
