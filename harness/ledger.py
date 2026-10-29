#!/usr/bin/env python3
"""Task completion ledger, phase 1. Run from the repo root:

  python harness/ledger.py open --title "seven voice pages" --prompt-file prompt.txt
  python harness/ledger.py declare          # lints gates, runs baselines, writes the lock
  python harness/ledger.py --force declare --gates-file F   # add gates to a declared contract
  python harness/ledger.py map A3 "G2, G5"  # remap an ask after declare
  python harness/ledger.py run              # executes CHECK lines, flips boxes, records evidence
  python harness/ledger.py status [--json]  # re-runs ticked checks; 0 = all met, 1 = unmet, 2 = error, 3 = lock broken
  python harness/ledger.py evidence G3 "the deciding proof for a JUDGE gate"
  python harness/ledger.py abandon G2 "reason this gate is genuinely impossible"
  python harness/ledger.py close [--archive-to episodic]

Protocol: harness/LEDGER.md. Nothing here calls a model. Every decision this
file makes is a string comparison or a subprocess exit code, which is the
entire point: the agent doing the work is not the party that decides it is done.

Live ledgers live in .ledger/ (gitignore it). They are working state carrying
raw command output, so they never enter the vault; `close` writes a scrubbed
summary to episodic/ instead.
"""
import argparse, hashlib, json, os, re, shlex, shutil, subprocess, sys, pathlib, signal, time
from datetime import datetime, timezone

CLASSES = ("PROVE", "HOLD", "JUDGE")
NOOP_CMDS = {"echo", "true", ":", "printf", "cat", "yes", "type"}
DEFAULT_TIMEOUT = 120

GATE_RE = re.compile(r"^- \[( |x|X)\] (G\d+) (" + "|".join(CLASSES) + r"): (.*)$")
ATTR_RE = re.compile(r"^\s+(CHECK|EXPECT|SHELL|TIMEOUT|BASELINE|EVIDENCE|ABANDON|VERDICT):\s?(.*)$")
ASK_RE = re.compile(r'^(A\d+) "(.*)" -> (.*)$')
LOCK_RE = re.compile(r"^Lock: (\S+)\s*$")
AUDIT_RE = re.compile(r"^Audit:\s*(.*)$")
#   subagent / human   a verdict was actually reached, so the ledger may close
#   awaiting-human     the agent has asked and is waiting. This unblocks the TURN, so the
#                      agent can end it in order to ask, and still blocks the CLOSE. Without
#                      this state the human fallback deadlocks: the wall holds the turn
#                      until an audit exists, and the audit cannot exist until the human is
#                      asked, which requires ending the turn. Found on 2026-08-22, one
#                      minute after building the wall it deadlocked against.
#   awaiting-subagent  dispatched and not yet returned. Same reason: an async auditor
#                      returns after the turn it was dispatched in, so the wall must let
#                      that turn end or the audit can never arrive. Third instance of one
#                      mistake on 2026-08-22: a requirement whose satisfaction needs the
#                      turn to end cannot be enforced by refusing to end the turn.
AUDIT_BY = ("subagent", "human", "awaiting-human", "awaiting-subagent")
AUDIT_FINAL = ("subagent", "human")

# Deterministic ask enumeration. Over-generates on purpose: dismissing a
# candidate costs one cheap line, missing a real ask is the failure this exists
# to catch.
ASK_VERBS = re.compile(
    r"\b(add|write|draft|create|make|build|fix|update|remove|delete|check|verify|run|test|"
    r"document|refactor|rename|move|ensure|keep|use|explain|list|review|clean|split|merge|"
    r"port|wire|install|commit|push|dont|don't|never|also|must|should|implement|change|deploy|"
    r"publish|release|bump|tag|replace|set|configure|upgrade|migrate|revert|rewrite|send|"
    r"open|close|mine|interview|sign|prove|copy|backup|archive)\b", re.I)


def now():
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")


def write_lf(path, text):
    """LF on every machine. write_text translates newlines to CRLF on Windows, so every
    ledger and summary written on Windows carried CRLF until 2026-09-29. Rule: LF line
    endings, always."""
    pathlib.Path(path).write_bytes(text.replace("\r\n", "\n").encode("utf-8"))


def die(msg, code=2):
    print(f"ledger: {msg}", file=sys.stderr)
    sys.exit(code)


# ---------------------------------------------------------------- file layout

def find_ledger_dir(start, name=None):
    """The ledger folder that governs `start`: the nearest one found walking up, never
    past the repository root. Until 2026-10-28 every caller joined `.ledger` onto the
    current folder, so after `cd subdir` the stop gate saw no ledger and allowed, and the
    guard let a write into the root ledger through. An absolute LEDGER_DIR wins."""
    name = name or os.environ.get("LEDGER_DIR") or ".ledger"
    if os.path.isabs(name):
        return pathlib.Path(name)
    start = pathlib.Path(start).resolve()
    # An empty folder never wins: on 2026-10-28 a review hid the root ledger from the
    # stop gate with one `mkdir sub/.ledger`. Any .git marks a checkout's root, a .git
    # file included: a worktree nested in the repo is its own checkout, and walking past
    # it put the worktree's ledger, and its checks, in the main checkout (round 5). The
    # stop gate also reads the project folder's ledger, so a submodule hides nothing.
    empty, root = None, None
    for folder in (start, *start.parents):
        if (folder / name).is_dir():
            if any((folder / name).glob("*.md")):
                return folder / name
            empty = empty or folder / name
        if (folder / ".git").exists():
            root = folder
            break
    # A new ledger belongs at the repository root, where the stop gate looks from any
    # folder: one opened in a subfolder went unenforced once the agent cd'd back up
    # (round 4 review). Outside a repository, the folder the command runs in.
    return empty or (root or start) / name


def ledger_dir(args):
    return pathlib.Path(args.dir) if args.dir else find_ledger_dir(os.getcwd())


def one_line(name, text):
    """Free text lands on one line of the ledger. A newline in it writes raw lines into
    the file: on 2026-10-28 a review forged a PROVE pass with one `evidence` call that
    carried a fake ticked gate and a comment opener hiding the real one. So every free
    text argument is refused if it holds a line break of any kind."""
    if re.search(r"[\r\n\x0b\x0c\x1c-\x1e\x85  ]", text or ""):
        die(f"{name} must be one line: it holds a line break, which would write raw lines "
            "into the ledger")
    return text


def ledger_path(args):
    if args.file:
        return pathlib.Path(args.file)
    d = ledger_dir(args)
    sid = args.session or os.environ.get("CLAUDE_SESSION_ID") or os.environ.get("CLAUDE_CODE_SESSION_ID") or "session"
    exact = d / f"{sid}.md"
    # A session named on the command line means that ledger and no other. Falling back
    # to the only other ledger in the folder let `--session a abandon G2` abandon
    # session b's G2 once a's own ledger had closed (round 9 review).
    if exact.exists() or args.session:
        return exact
    found = sorted(d.glob("*.md")) if d.exists() else []
    if not found:
        return exact
    if len(found) == 1:
        # The implicit id changes after /clear; the one ledger here is still this work's.
        print(f"ledger: no {exact.name}, using the only ledger here, {found[0]}", file=sys.stderr)
        return found[0]
    die(f"{len(found)} ledgers in {d}; pass --session or --file")


# ------------------------------------------------------------------- parsing

class Gate:
    def __init__(self, line_no, checked, gid, cls, outcome):
        self.line_no, self.checked, self.id, self.cls, self.outcome = line_no, checked, gid, cls, outcome
        self.check = self.expect = self.shell = self.baseline = self.timeout = None
        self.evidence = self.abandon = self.verdict = None
        self.attr_lines = {}
        self.dupes = []       # attribute names seen twice: only a hand edit does that
        self.recheck = None   # (ok, detail) once its CHECK has been re-run by verify()

    @property
    def evidence_ok(self):
        if not self.evidence or re.fullmatch(r"pending", self.evidence.strip(), re.I):
            return False
        # "pending: owner has not signed" says the judgement is not in yet (round 19).
        # JUDGE only: a check's output may well begin "Pending migrations: 0".
        return not (self.cls == "JUDGE" and re.match(r"pending\b", self.evidence.strip(), re.I))

    @property
    def forced(self):
        return self.cls != "JUDGE" and (self.evidence or "").startswith("FORCED")

    @property
    def met(self):
        if self.abandon:
            return True
        if not (self.checked and self.evidence_ok):
            return False
        # A tick is a claim, not a proof. Once verify() has re-run the CHECK, its result
        # is what counts, so a box ticked by hand over a failing check stays unmet.
        return self.recheck is None or self.recheck[0]

    def unmet_reason(self):
        if not self.checked:
            return "unchecked"
        if not self.evidence_ok:
            return "checked but EVIDENCE still pending"
        if self.recheck is not None and not self.recheck[0]:
            return f"ticked, but its CHECK fails when re-run: {self.recheck[1]}"
        return None

    def frozen_repr(self):
        """Exactly the fields the lock covers. The checkbox, EVIDENCE, ABANDON and
        VERDICT are deliberately absent: those are what work is allowed to change."""
        # TIMEOUT joins only when present, so every lock written before it existed holds.
        return "|".join([self.id, self.cls, self.outcome.strip(), self.check or "",
                         self.expect or "", self.shell or "", self.baseline or ""]
                        + ([f"timeout={self.timeout}"] if self.timeout else []))

    def limit(self, timeout):
        """Seconds this check may run: the caller's, or more if declare recorded more. A
        gate declared with --timeout 300 timed out under a plain `run` or `status` at the
        default 120, while the stop gate, with its own large budget, passed it (round 12)."""
        try:
            return max(timeout, int(self.timeout or 0))
        except ValueError:
            return timeout


class Ledger:
    def __init__(self, path, text=None):
        self.path = pathlib.Path(path)
        if text is None and not self.path.exists():
            die(f"no ledger at {self.path}; run `open` first")
        # From text when an amendment is assembled in memory, so a refused one never
        # touches the file.
        # A stray byte must not crash the judge: on 2026-10-28 one invalid UTF-8 byte in
        # the Log made status fail, and the stop gate read the failure as "allow".
        self.lines = (text if text is not None else
                      self.path.read_bytes().decode("utf-8", "replace")).replace("\r\n", "\n").split("\n")
        self.gates, self.asks, self.lock_line, self.lock = [], [], -1, None
        self.audit, self.audit_line = None, -1
        cur, commented, prompt, fence = None, False, False, None
        for i, line in enumerate(self.lines):
            # The stored prompt is what was asked, never contract: a prompt quoting a
            # ledger used to parse as gates and asks (2026-10-28 readiness review). Inside
            # its fence even a `## ` heading is prompt text.
            if prompt and fence is None and re.fullmatch(r"`{3,}", line.strip()):
                fence = line.strip()
                continue
            if prompt and fence is not None:
                if line.strip() == fence:
                    fence = None
                continue
            if line.startswith("## "):
                prompt = line.strip() == "## Prompt"
            if prompt:
                continue
            # Commented regions are documentation, including the example gate the
            # template ships with. They must never parse as content.
            if commented:
                commented = "-->" not in line
                continue
            if line.lstrip().startswith("<!--") and "-->" not in line:
                commented, cur = True, None
                continue
            m = LOCK_RE.match(line)
            if m and self.lock is None:
                self.lock, self.lock_line = m.group(1), i
                continue
            a = AUDIT_RE.match(line)
            if a and self.audit is None:
                self.audit, self.audit_line = a.group(1).strip(), i
                continue
            g = GATE_RE.match(line)
            if g:
                cur = Gate(i, g.group(1).lower() == "x", g.group(2), g.group(3), g.group(4))
                self.gates.append(cur)
                continue
            a = ATTR_RE.match(line) if cur else None
            if a:
                key = a.group(1).lower()
                if key in cur.attr_lines:
                    cur.dupes.append(a.group(1))
                setattr(cur, key, a.group(2).strip())
                cur.attr_lines[key] = i
                continue
            k = ASK_RE.match(line)
            if k:
                self.asks.append((i, k.group(1), k.group(2), k.group(3).strip()))
            if line.startswith("#"):
                cur = None

    # --- writing

    def save(self):
        write_lf(self.path, "\n".join(self.lines))

    def _shift(self, anchor):
        for g in self.gates:
            if g.line_no > anchor:
                g.line_no += 1
            g.attr_lines = {k: (v + 1 if v > anchor else v) for k, v in g.attr_lines.items()}
        self.asks = [(i + 1 if i > anchor else i, a, t, m) for i, a, t, m in self.asks]
        if self.lock_line > anchor:
            self.lock_line += 1
        if self.audit_line > anchor:
            self.audit_line += 1

    def log(self, msg):
        try:
            idx = self.lines.index("## Log")
        except ValueError:
            self.lines += ["", "## Log"]
            idx = len(self.lines) - 1
        end = len(self.lines)
        while end > idx + 1 and not self.lines[end - 1].strip():
            end -= 1
        self.lines.insert(end, f"{now()} {msg}")
        self._shift(end - 1)

    def set_attr(self, gate, key, value):
        # Store exactly what the parser will read back, which strips attribute lines.
        # A value ending in a space (a check's output cut at 200 characters, just after
        # a word) otherwise differs from its own file by one space, and the lock computed
        # over it reports BROKEN on a file nobody touched. Found 2026-10-13.
        value = str(value).strip()
        line = f"      {key.upper()}: {value}"
        if key in gate.attr_lines:
            self.lines[gate.attr_lines[key]] = line
        else:
            anchor = max([gate.line_no] + list(gate.attr_lines.values()))
            self.lines.insert(anchor + 1, line)
            self._shift(anchor)
            gate.attr_lines[key] = anchor + 1
        setattr(gate, key, value)

    def check_box(self, gate):
        self.lines[gate.line_no] = self.lines[gate.line_no].replace("- [ ]", "- [x]", 1)
        gate.checked = True

    def uncheck_box(self, gate):
        self.lines[gate.line_no] = re.sub(r"^- \[[xX]\]", "- [ ]", self.lines[gate.line_no], count=1)
        gate.checked = False

    # --- the lock

    def raw_prompt(self):
        """The prompt as given, stored fenced under ## Prompt at open time. Kept verbatim
        because an auditor must see what was asked, not a paraphrase of it."""
        try:
            start = self.lines.index("## Prompt")
        except ValueError:
            return ""
        body, fence = [], None
        for line in self.lines[start + 1:]:
            if fence is None:
                if re.fullmatch(r"`{3,}", line.strip()):
                    fence = line.strip()
                elif line.startswith("## "):
                    break
                continue
            if line.strip() == fence:
                break
            body.append(line)
        return "\n".join(body).strip()

    @property
    def audit_done(self):
        """The coverage audit: has a party that did not do the work confirmed that the
        gates cover every ask? Deliberately not part of the lock, since it is recorded
        after the contract is frozen."""
        return bool(self.audit) and not re.fullmatch(r"pending", self.audit, re.I)

    @property
    def audit_final(self):
        """A verdict actually reached, as opposed to one being waited on. Closing needs
        this; ending a turn only needs audit_done."""
        return self.audit_done and self.audit.split(":", 1)[0].strip() in AUDIT_FINAL

    def computed_lock(self):
        # Gates AND ask texts. Freezing gates alone left a hole: an agent could delete
        # an ask line to make an unmapped ask disappear, which is silent scope narrowing
        # by exactly the route section 6 forbids. Ask MAPPINGS stay free, since deciding
        # which gate covers an ask is the work. Adding a genuinely new ask mid task is
        # therefore a deliberate `declare --force`, which lands in the log.
        blob = "\n".join(g.frozen_repr() for g in self.gates)
        blob += "\n#asks\n" + "\n".join(f"{aid}|{text}" for _, aid, text, _ in self.asks)
        return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]

    def log_lines(self):
        """The Log section only: a prompt quoting a ledger carries lines that look like
        log entries, and they made a fresh draft read as declared (round 5)."""
        try:
            return self.lines[len(self.lines) - 1 - self.lines[::-1].index("## Log"):]
        except ValueError:
            return []

    @property
    def declared(self):
        """Declared is read from everything declare leaves behind, not the Lock line alone.
        Until 2026-10-28 rewriting that one line to `open`, or deleting it, turned a
        failing declared ledger into a draft: status exited 0, the stop gate skipped it
        and close archived a success, with no hash to recompute."""
        # Plus two marks no draft carries: the sidecar declare writes beside the ledger,
        # and a recorded audit verdict (`audit` refuses a draft). Stripping the Lock line,
        # every BASELINE and the log entry still left a forged draft (round 2 review).
        return (self.lock not in (None, "open")
                or any(g.baseline for g in self.gates)
                or any(re.match(r"^\S+ \S+ declared \d+ gates?, lock ", l) for l in self.log_lines())
                or self.path.with_suffix(".declared").exists()
                or self.audit_done)

    @property
    def root(self):
        """The folder every CHECK runs in: the one holding the ledger folder, which is
        where the stop gate runs them too. A ledger kept elsewhere with --file has no
        such folder, so its checks run where the caller stands, as they always did."""
        folder = self.path.resolve().parent
        names = {".ledger", pathlib.Path(os.environ.get("LEDGER_DIR") or ".ledger").name}
        if folder.name == "closed" and folder.parent.name in names:
            return folder.parent.parent
        # `.ledger` always counts, whatever LEDGER_DIR says: renaming it in the caller's
        # environment moved every check into a decoy folder (round 2 review).
        return folder.parent if folder.name in names else None

    def lock_state(self):
        if self.lock in (None, "open"):
            return "broken" if self.declared else "open"
        # A repeated attribute line is never written by the engine. Parsed last wins, so
        # a second CHECK under a gate could replace the frozen one without changing what
        # the lock reads; treat it as the hand edit it is.
        if any(g.dupes for g in self.gates):
            return "broken"
        return "intact" if self.lock == self.computed_lock() else "broken"

    @property
    def relocked(self):
        return any(re.match(r"^\S+ \S+ RELOCKED ", l) for l in self.lines)

    def verify(self, timeout=DEFAULT_TIMEOUT):
        """Re-run the CHECK of every ticked PROVE and HOLD gate that is not abandoned.

        The file is not trusted. Until 2026-10-28 a box ticked and an EVIDENCE line
        written by any means (a python one liner, a newline smuggled into `evidence`)
        read as met, because the lock covers what a gate means and not whether it was
        met. Now status, close and the stop gate ask the system again, so a forged tick
        counts for nothing. An unticked gate is unmet whatever its check says, so only
        ticked gates need the run: the verdict is the same as running every check."""
        ran = 0
        # A deadline from the caller (the stop gate's budget) as wall clock seconds: past
        # it, a check is not started and counts as failing, so the engine always returns
        # before its caller gives up on it.
        deadline = float(os.environ.get("LEDGER_DEADLINE") or 0)
        for g in self.gates:
            if g.abandon or g.cls == "JUDGE" or not g.check or not g.checked:
                continue
            if lint(g):
                g.recheck = (False, "its CHECK no longer passes lint: " + "; ".join(lint(g)))
                continue
            limit = g.limit(timeout)
            if deadline:
                left = deadline - time.time()
                if left < 1:
                    g.recheck = (False, "not run: the caller's time budget ran out")
                    continue
                limit = min(limit, left)
            ok, detail, why = run_check(g, limit, self.root)
            g.recheck = (ok, detail if ok else f"{why}: {detail}")
            ran += 1
        return ran

    def write_lock(self):
        value = self.computed_lock()
        if self.lock_line >= 0:
            self.lines[self.lock_line] = f"Lock: {value}"
        else:
            self.lines.insert(1, f"Lock: {value}")
            self._shift(0)
            self.lock_line = 1
        self.lock = value


# ------------------------------------------------------------ check execution

def windows_bash():
    """Git Bash on Windows, or None. Never WSL's launcher, which runs checks in Linux,
    where the owner's Windows paths and tools are not (round 5). Searched whether or
    not `bash` is on PATH: Git's installer default puts only `Git\\cmd` there, and
    without WSL the search never ran, so `test -f` was declared under cmd.exe and could
    never pass (round 10 review)."""
    exe = shutil.which("bash")
    if exe and not re.search(r"\\(System32|WindowsApps)\\", exe, re.I):
        return exe
    git = shutil.which("git.exe")
    tries = [os.environ.get("CLAUDE_CODE_GIT_BASH_PATH")]
    tries += [os.path.join(os.path.dirname(os.path.dirname(git)), "bin", "bash.exe")] if git else []
    tries += [os.path.join(b, "Git", "bin", "bash.exe") for b in
              (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"),
               os.path.join(os.environ.get("LOCALAPPDATA") or "", "Programs")) if b]
    return next((x for x in tries if x and os.path.isfile(x)), None)


def resolve_shell(requested):
    """Return (name, argv prefix). Explicit beats implicit: the shell that ran a
    check is frozen into its gate, so a check written under Git Bash cannot
    silently re-run under cmd.exe on the next machine and fail for the wrong
    reason."""
    if requested in (None, "", "auto"):
        if os.name == "nt":
            requested = "bash" if windows_bash() else "cmd"
        else:
            requested = "bash" if shutil.which("bash") else "sh"
    if requested == "none":
        return "none", None
    # The system's own shell before PATH's: a fake `bash` first on PATH forged every
    # check (round 2 review). Windows has no fixed place, so it keeps the PATH lookup.
    fixed = [f"/bin/{requested}", f"/usr/bin/{requested}"] if os.name != "nt" else []
    exe = next((f for f in fixed if os.access(f, os.X_OK)), None) or \
        shutil.which("cmd.exe" if requested == "cmd" else requested)
    if os.name == "nt" and requested == "bash":
        exe = windows_bash()
    if not exe:
        return requested, None
    if requested == "bash":
        # Not a login shell: `-l` ran ~/.bash_profile first, where one line redefining
        # `test` forged status, close and the stop gate (round 2 review). Git Bash on
        # Windows keeps `-l`, which is what puts its tools on PATH there.
        return "bash", [exe, "-lc"] if os.name == "nt" else [exe, "--noprofile", "--norc", "-c"]
    if requested == "cmd":
        return "cmd", [exe, "/c"]
    return requested, [exe, "-c"]


MAX_DEPTH = 3


def run_check(gate, timeout=DEFAULT_TIMEOUT, cwd=None):
    """Execute one CHECK, in the ledger's repo folder. Returns (ok, tail, detail).
    Until 2026-10-28 it ran wherever the caller stood, so `run` from a subfolder could
    tick and archive a gate the stop gate, at the root, saw failing."""
    if int(os.environ.get("LEDGER_DEPTH") or 0) >= MAX_DEPTH:
        return False, f"not run: checks nested {MAX_DEPTH} deep, a check is calling the ledger", "nested"
    name, prefix = resolve_shell(gate.shell)
    if prefix is None and name != "none":
        return False, f"shell '{name}' not found on this machine", "shell-missing"
    try:
        argv = shlex.split(gate.check) if name == "none" else prefix + [gate.check]
        if name == "cmd":
            # A list goes through list2cmdline, which writes \" that cmd.exe never undoes,
            # so a quoted CHECK failed for the wrong reason; cmd takes the line as written.
            argv = f'"{prefix[0]}" /c {gate.check}'
        # Its own process group, so a timeout kills everything the check started, not
        # only the shell: orphans of timed out checks kept forking on 2026-10-28.
        # No startup files by the back door either: BASH_ENV and ENV name a file a
        # non-interactive shell sources before the check.
        # Exported functions too: `test() { return 0; }; export -f test` reached every
        # check as BASH_FUNC_test%% and passed it (round 3 review).
        env = {k: v for k, v in os.environ.items()
               if k not in ("BASH_ENV", "ENV", "SHELLOPTS", "PS4") and not k.startswith("BASH_FUNC_")}
        if os.name == "nt":
            # Git Bash runs as a login shell there, and an MSYS2 style profile moves a
            # login shell to HOME unless this is set; checks run in the ledger's root.
            env["CHERE_INVOKING"] = "1"
        # A check that runs `ledger.py status` on its own ledger would re-run itself
        # without end; each level is counted, and past a few none starts (round 4).
        env["LEDGER_DEPTH"] = str(int(os.environ.get("LEDGER_DEPTH") or 0) + 1)
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", cwd=str(cwd) if cwd else None,
                                env=env, start_new_session=os.name != "nt")
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                if os.name != "nt":
                    os.killpg(proc.pid, signal.SIGKILL)
                else:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                                   capture_output=True)
            except OSError:
                pass
            proc.kill()
            proc.communicate()
            return False, f"timed out after {int(timeout)}s", "timeout"
        res = subprocess.CompletedProcess(argv, proc.returncode, stdout, stderr)
    except OSError as e:
        return False, str(e), "oserror"
    out = f"{res.stdout or ''}\n{res.stderr or ''}"
    ok = expect_matches(gate.expect, out) if gate.expect else res.returncode == 0
    return ok, tail(out), f"exit {res.returncode}"


def expect_matches(expect, output):
    rx = re.fullmatch(r"/(.+)/([a-z]*)", expect)
    if rx:
        try:
            # MULTILINE so ^ and $ anchor to each line. The output is stdout, a newline and
            # stderr, so a clean `0` from grep arrives as "0\n\n", and without this flag
            # /^0$/ could never match it: twelve correct gates stayed red on 2026-09-02.
            flags = re.M | (re.I if "i" in rx.group(2) else 0)
            return re.search(rx.group(1), output, flags) is not None
        except re.error:
            return False
    return expect in output


def tail(output, limit=200):
    parts = [s.strip() for s in output.split("\n") if s.strip()]
    return (" | ".join(parts[-2:]) or "(no output)")[:limit]


# ------------------------------------------------------------------- commands

def cmd_open(args):
    d = ledger_dir(args)
    d.mkdir(parents=True, exist_ok=True)
    sid = args.session or os.environ.get("CLAUDE_SESSION_ID") or os.environ.get("CLAUDE_CODE_SESSION_ID") or "session"
    path = pathlib.Path(args.file) if args.file else d / f"{sid}.md"
    if args.file and path.resolve().parent.name not in {".ledger", d.name}:
        # The stop gate and the guard look only in .ledger folders (round 14 review).
        print(f"ledger: WARNING: {path} is not in a .ledger folder, so the stop gate and the "
              "write guard will never see it: this ledger is advisory only", file=sys.stderr)
    if path.exists():
        # Never over a declared ledger, --force or not: until 2026-10-28 `--force open`
        # replaced one with a blank draft through the engine path the guard allows, and
        # the contract, its audit and its log vanished. A draft may be replaced, but it
        # is retired to closed/ first, so even that leaves a trace.
        old = Ledger(path)
        if old.declared:
            # It is usually another task's: name this one, never close that one (round 20).
            die(f"{path} holds a declared ledger, most likely another task's. Open yours under "
                "its own name with `--session <new id>`; close that one only when its own work "
                "is done")
        if not args.force:
            die(f"{path} already exists; pass --force to replace the draft")
        closed = path.parent / "closed"
        closed.mkdir(parents=True, exist_ok=True)
        old.log("SUPERSEDED: replaced by `--force open` before it was declared")
        old.save()
        path.replace(closed / f"{path.stem}-superseded-{datetime.now().strftime('%H%M%S')}.md")

    prompt = ""
    if args.prompt_file:
        prompt = read_input(args.prompt_file)
    elif args.prompt:
        prompt = args.prompt

    asks = enumerate_asks(prompt)
    body = [
        f"# Ledger: {args.title}",
        "Lock: open",
        "Audit: pending",
        f"Session: {sid}",
        f"Opened: {now()}",
        "",
        "## Contract",
        "<!-- Frozen by `declare`. After that only the checkbox, EVIDENCE, ABANDON and",
        "     VERDICT lines may change. Editing an outcome, CHECK, EXPECT, SHELL or",
        "     BASELINE breaks the lock and the Stop gate refuses to end the turn.",
        "",
        "- [ ] G1 PROVE: <outcome, stated so a stranger could judge it>",
        "      CHECK: <command that fails right now and passes when the work is done>",
        "      EXPECT: <substring, or /regex/, or omit to decide on exit code; an EXPECT replaces the exit code>",
        "-->",
        "",
        "## Asks",
        "<!-- Enumerated from the raw prompt by the harness, not by the agent. Every ask",
        "     needs a mapping: '-> G1' or '-> none: why this is out of scope'. -->",
    ]
    body += [f'{aid} "{text}" -> ?' for aid, text in asks] or \
        [f"<!-- {'no candidate asks found in the prompt: add any by hand' if prompt.strip() else 'no prompt supplied'} -->"]
    # The prompt is kept verbatim, because the coverage auditor must see what was asked
    # rather than the enumerator's reading of it, and because an enumerated ask list is
    # evidence of what the harness understood, not of what was said.
    if prompt.strip():
        # A fence longer than any backtick run in the prompt, so a prompt quoting code or
        # carrying its own headings stays whole (round 4 review: a `## ` line cut it).
        fence = "`" * max(3, 1 + max((len(r) for r in re.findall(r"`+", prompt)), default=0))
        body += ["", "## Prompt", fence, prompt.strip(), fence]
    body += ["", "## Log", f"{now()} opened, {len(asks)} candidate asks enumerated", ""]
    write_lf(path, "\n".join(body))
    print(f"{path}: opened with {len(asks)} candidate asks")
    print("Next: write the gates under ## Contract, map every ask, then run `declare`.")
    return 0


def read_input(path, strict=False):
    """A prompt or gates file, whatever wrote it. Windows PowerShell 5.1's `>` and
    `Out-File` write UTF-16; read as UTF-8 that came through with a NUL between every
    letter, enumerated zero asks and declared silently (round 8 review)."""
    raw = pathlib.Path(path).read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    try:
        text = raw.decode("utf-8-sig", errors="strict" if strict else "replace")
    except UnicodeDecodeError as exc:
        die(f"{path} is not UTF-8 ({exc.reason} at byte {exc.start}); save it as UTF-8")
    if "\x00" in text:
        die(f"{path} holds NUL bytes, so it is not UTF-8 text; save it as UTF-8 "
            "(in PowerShell: Set-Content -Encoding utf8)")
    return text


def enumerate_asks(prompt):
    if not prompt.strip():
        return []
    segments = []
    for raw in prompt.split("\n"):
        line = raw.strip()
        if not line:
            continue
        # "1) push. 2) keep it. 3) approved" is three asks on one line. Splitting on an
        # inline enumeration marker first is what stops it collapsing into one, which it
        # did on 2026-08-22, taking a four part instruction down to one truncated ask.
        #
        # A piece that came from an explicit list marker is structural: the author
        # numbered it, so it is an item however terse. "push" is one word and a whole
        # instruction. Free prose still needs three words to count, or every stray
        # clause becomes an ask.
        pieces = re.split(r"\s+(?=\d{1,2}[.)]\s)", line)
        for piece in pieces:
            marked = re.match(r"^([-*+]|\d{1,2}[.)])\s+(.*)$", piece.strip())
            structural = bool(marked) or len(pieces) > 1
            body = marked.group(2) if marked else piece.strip()
            if not body:
                continue
            for s in re.split(
                    r"(?<=[.!?;])\s+|\s+(?:and also|then also|and then|also,)\s+", body):
                if s:
                    segments.append((s, structural))
    asks, seen = [], set()
    for seg, structural in segments:
        text = re.sub(r"\s+", " ", seg).strip(" .,;:")
        if len(text) > 120:
            # Visible truncation. A silently clipped ask reads as the whole ask.
            text = text[:120] + " [truncated]"
        # A list item the author wrote is an ask whatever its verb; prose needs a known
        # verb and two words ("Refactor auth.py"), round 15 review.
        if not structural and (len(text.split()) < 2 or not ASK_VERBS.search(text)):
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        # No cap. One used to stop at 14 without a word, and items 15 onward never
        # became asks for declare or the stop gate to see (round 8 review).
        asks.append((f"A{len(asks) + 1}", text.replace('"', "'")))
    return asks


def lint(gate):
    """Static refusals, applied before anything is executed."""
    bad = []
    if gate.cls == "JUDGE":
        if gate.check:
            bad.append("a JUDGE gate must not carry a CHECK; if a command can prove it, make it PROVE")
        return bad
    if not gate.check:
        return [f"a {gate.cls} gate needs a CHECK line"]
    first = pathlib.PurePath(gate.check.strip().split()[0].lower()).name
    if first in NOOP_CMDS:
        bad.append(f"CHECK starts with '{first}', which cannot fail for the right reason")
    # grep -c prints 0 and exits 1 when nothing matches. With no EXPECT the gate is
    # judged on exit code, so a gate whose passing state is a zero count can never pass.
    if (not gate.expect and re.search(r"\bgrep\b[^|;&]*\s-[a-zA-Z]*c", gate.check)
            and not re.search(r"\|\|\s*true\b", gate.check)):
        bad.append("CHECK uses grep -c with no EXPECT, so it is judged on exit code, and grep "
                   "exits 1 on a zero count; add an EXPECT such as /^\\s*0\\s*$/ and '|| true'")
    # An EXPECT replaces the exit code. A bare success word then passes a failing run:
    # pytest prints "1 failed, 4 passed" and exits 1, and EXPECT /passed/ matched it, so
    # the gate was met over failing tests (round 21 review). Anchor it to the line that
    # only a full pass prints, or drop EXPECT and let the exit code judge.
    if gate.expect and re.fullmatch(r"/?\s*(?:passed|pass|passing|ok|okay|success|successful|succeeded|"
                                    r"done|green|complete|completed|all good)\s*/?[a-z]*", gate.expect.strip(), re.I):
        bad.append(f"EXPECT '{gate.expect.strip()}' is a bare success word, which a failing run also "
                   "prints (\"1 failed, 4 passed\"); an EXPECT replaces the exit code, so anchor it "
                   "to the line only a full pass prints, or drop EXPECT and judge on exit code")
    # With no EXPECT a check is judged on exit code, and `|| true` makes that 0 for ever:
    # a HOLD gate refused for a red baseline, given the suffix, guarded nothing (round 13).
    if not gate.expect and re.search(r"(?:\|\||;)\s*(?:true|:|exit\s+0)\s*$", gate.check):
        bad.append("CHECK ends in a suffix that forces exit 0 ('|| true' or the like), so with no "
                   "EXPECT it can never fail; add an EXPECT the passing output must match, or drop it")
    if gate.expect:
        needle = gate.expect.strip("/").strip()
        # As a whole word: `EXPECT: /ok/` is not a tautology because the CHECK runs
        # tests/hooks_test.py (round 8 and 10 reviews).
        if needle and re.search(r"(?<!\w)" + re.escape(needle.lower()) + r"(?!\w)", gate.check.lower()):
            bad.append(f"EXPECT '{needle}' appears inside its own CHECK, so the check is a tautology")
    bad += lint_mangled(gate)
    return bad


def lint_mangled(gate):
    """Refuse a gate that an escaping layer has mangled on its way into the file.

    On 2026-10-27 five gates were written through a Python string that was not raw:
    \\1 became a control character, \\n became a real newline that split a CHECK and
    two EXPECTs across lines, and doubled backslashes collapsed into regex escapes.
    All five were red at declaration for the wrong reason, which the red first rule
    cannot tell from the right one, so they surfaced only after the work was done,
    when a corrected PROVE gate is refused as vacuous. Each refusal below is aimed at
    one of those shapes. Found while running the harness (2026-10).
    """
    bad = []
    for name, value in (("outcome", gate.outcome), ("CHECK", gate.check), ("EXPECT", gate.expect)):
        ctl = sorted({f"0x{ord(c):02x}" for c in value or "" if (ord(c) < 32 and c != "\t") or ord(c) == 127})
        if ctl:
            bad.append(f"{name} holds control character(s) {', '.join(ctl)}, the mark of an escape "
                       f"such as \\1 collapsed on the way in; write the gate with a plain editor")
    if gate.expect and gate.expect.strip().startswith("/"):
        rx = re.fullmatch(r"/(.+)/([a-z]*)", gate.expect.strip())
        if not rx:
            bad.append("EXPECT opens a regex with / but never closes it, so it would be matched as "
                       "literal text; a newline may have split it across lines")
        else:
            try:
                re.compile(rx.group(1))
            except re.error as e:
                bad.append(f"EXPECT regex does not compile ({e}), so it could never match; "
                           f"a doubled backslash may have collapsed into an escape")
    # Quotes are only checked for POSIX shells: cmd.exe has no single quotes, so an
    # apostrophe there is text, not an opening quote.
    if gate.check and (gate.shell or "auto") in ("bash", "sh", "auto", "none"):
        try:
            shlex.split(gate.check)
        except ValueError as e:
            bad.append(f"CHECK has an unclosed quote ({e}), so the shell cannot run it as written; "
                       f"a newline may have split it across lines")
    return bad


def cmd_declare(args):
    if getattr(args, "gates_file", None):
        return cmd_amend(args)
    led = Ledger(ledger_path(args))
    if not led.gates:
        die("no gates found under ## Contract. A gate written inside the template's "
            "<!-- --> comment is ignored: put it below the comment's closing -->")
    if led.lock_state() == "intact" and not args.force:
        die("already declared; pass --force to re-declare, which rewrites the lock")
    if led.lock_state() == "broken" and not args.force:
        die("LOCK BROKEN: the frozen contract changed after declare. Restore it, or "
            "re-declare deliberately with `declare --force` and say so in your report.", 3)
    # Nothing is met before the contract exists. A tick or EVIDENCE written into the
    # draft used to survive declare, so a JUDGE gate could be met at the moment it was
    # frozen (2026-10-28 readiness review). A re-declare keeps what the work earned.
    if not led.declared:
        given_up = [g.id for g in led.gates if g.abandon]
        if given_up:
            die(f"{', '.join(given_up)} carry ABANDON in the draft: a gate is given up after "
                "declare, out loud, never frozen surrendered; delete the line (round 14 review)")
        for g in led.gates:
            if g.checked:
                led.uncheck_box(g)
            if g.evidence:
                led.set_attr(g, "evidence", "pending")

    ids = [g.id for g in led.gates]
    if len(set(ids)) != len(ids):
        die(f"duplicate gate ids: {sorted({i for i in ids if ids.count(i) > 1})}")
    dupes = [f"{g.id} {', '.join(g.dupes)}" for g in led.gates if g.dupes]
    if dupes:
        die(f"repeated attribute lines (only the last would count): {'; '.join(dupes)}")

    refused, declared = [], 0
    for g in led.gates:
        problems = lint(g)
        if problems:
            refused += [f"{g.id}: {p}" for p in problems]
            continue
        if g.cls == "JUDGE":
            led.set_attr(g, "baseline", "n/a, manual gate")
            if not g.evidence:
                led.set_attr(g, "evidence", "pending")
            declared += 1
            print(f"  DECLARED {g.id} JUDGE: {g.outcome}")
            continue

        name, _ = resolve_shell(g.shell)
        led.set_attr(g, "shell", name)
        if args.timeout > DEFAULT_TIMEOUT:
            led.set_attr(g, "timeout", args.timeout)
        ok, detail, why = run_check(g, g.limit(args.timeout), led.root)
        if why in ("shell-missing", "oserror", "timeout", "nested"):
            # A timed out baseline is not a red one: it proves nothing either way, so a
            # PROVE gate locked on it was never shown to fail (round 6 review).
            refused.append(f"{g.id}: baseline could not run ({detail}). {could_not_run(why)}")
            continue
        if g.cls == "PROVE" and ok:
            refused.append(f"{g.id}: baseline already PASSES, so this gate proves nothing. "
                           "Sharpen it, or make it HOLD if it is a regression guard.")
            continue
        if g.cls == "HOLD" and not ok:
            refused.append(f"{g.id}: baseline already FAILS, so it cannot be held. "
                           f"Make it PROVE. ({detail})")
            continue
        led.set_attr(g, "baseline", f"{'pass' if ok else 'fail'} at {now()}: {detail}")
        if not g.evidence:
            led.set_attr(g, "evidence", "pending")
        declared += 1
        print(f"  DECLARED {g.id} {g.cls} (baseline {'green' if ok else 'red'}): {g.outcome}")
        if not ok:
            red_note(g, detail)

    if refused:
        print("\nREFUSED, nothing was locked:")
        for r in refused:
            print(f"  {r}")
        # The loop above already rewrote SHELL, BASELINE and EVIDENCE on the gates that
        # passed their checks. Saving those would change frozen fields under an intact
        # lock, so a refused `declare --force` used to break the very contract it left
        # alone (2026-09-28). Reload from disk and record only the refusal.
        led = Ledger(led.path)
        led.log(f"declare refused {len(refused)} gate(s)")
        led.save()
        return 2

    unmapped = unmapped_asks(led)
    if unmapped:
        print(f"\nREFUSED: {len(unmapped)} ask(s) with no mapping to an existing gate: {', '.join(unmapped)}")
        print("  Map each to a gate ('-> G2') or dismiss it explicitly ('-> none: <reason>').")
        return 2

    # An audit judged the contract it was shown. A re-declare changes that contract, so
    # the old verdict no longer applies to it: reset it rather than let a verdict about a
    # previous contract close this one, or a stale gaps verdict strand it.
    if args.force and led.audit_done and led.audit_line >= 0:
        led.lines[led.audit_line] = "Audit: pending"
        led.audit = "pending"
        led.log("coverage audit reset to pending: the contract changed after it was recorded")
    led.write_lock()
    led.log(f"declared {declared} gates, lock {led.lock}")
    led.save()
    write_lf(led.path.with_suffix(".declared"), f"{led.lock}\n")
    print(f"\nLOCKED {led.lock} over {declared} gate{'s' if declared != 1 else ''}. "
          "The contract is now frozen.")
    return 0


def cmd_amend(args):
    """Add gates to a declared contract: `declare --force --gates-file F`.

    Until 2026-09-29 the guard named `declare --force` as the way to amend a contract
    and blocked the edit that command needed, so the sanctioned path was unreachable.
    Now the new gates arrive in a file outside the ledger directory and the engine,
    still the only writer, appends them. Only the NEW gates run baselines: the old
    ones keep theirs, because once the work is done a met PROVE gate's baseline would
    pass and be refused as vacuous. Everything is checked in memory first, so a
    refused amendment leaves the ledger byte for byte as it was.
    """
    path = ledger_path(args)
    led = Ledger(path)
    if not args.force:
        die("adding gates changes a frozen contract, so it is deliberate: pass --force")
    state = led.lock_state()
    if state != "intact":
        die(f"an amendment needs an intact lock (this one is {state}); "
            "declare the ledger first, or restore it", 3 if state == "broken" else 2)
    src = pathlib.Path(args.gates_file).resolve()
    if src.parent == path.resolve().parent:
        die("the gates file must live outside the ledger directory, which only the engine writes")
    if not src.is_file():
        die(f"no gates file at {src}")
    new_text = read_input(src, strict=True).replace("\r\n", "\n").strip("\n")
    # A gates file holds gates and nothing else. Until 2026-10-28 attribute lines before
    # its first gate attached to the LAST EXISTING gate, so `CHECK: test -d .` silently
    # replaced a frozen check, and the amendment re-locked over it. Lines of any other
    # kind (an ask, a Lock or Audit line, a comment opener) could reshape the file too.
    body = [l for l in new_text.split("\n") if l.strip()]
    if not body or not GATE_RE.match(body[0]):
        die("a gates file must open with a gate line ('- [ ] G7 PROVE: ...'); attribute "
            "lines before the first gate would attach to an existing gate")
    stray = [l for l in body if not GATE_RE.match(l) and not ATTR_RE.match(l)]
    if stray:
        die(f"a gates file may hold only gate and attribute lines, not: {stray[0][:80]}")
    probe = Ledger(path, text="## Contract\n" + new_text + "\n")
    if not probe.gates:
        die(f"no gates found in {src}")
    dupes = [f"{g.id} {', '.join(g.dupes)}" for g in probe.gates if g.dupes]
    if dupes:
        die(f"repeated attribute lines in the gates file: {'; '.join(dupes)}")
    if any(g.checked or g.evidence or g.abandon or g.baseline for g in probe.gates):
        die("new gates arrive unticked, with no EVIDENCE, ABANDON or BASELINE: the engine "
            "writes those")
    old_ids = {g.id for g in led.gates}
    new_ids = [g.id for g in probe.gates]
    clash = sorted(set(new_ids) & old_ids) + sorted({i for i in new_ids if new_ids.count(i) > 1})
    if clash:
        die(f"gate ids already in use or repeated: {', '.join(clash)}")
    if "## Asks" not in led.lines:
        die("no ## Asks section to insert the gates before")
    at = led.lines.index("## Asks")
    while at > 0 and not led.lines[at - 1].strip():
        at -= 1
    amended = Ledger(path, text="\n".join(led.lines[:at] + new_text.split("\n") + led.lines[at:]))
    refused = []
    for g in amended.gates:
        if g.id not in new_ids:
            continue
        problems = lint(g)
        if problems:
            refused += [f"{g.id}: {x}" for x in problems]
            continue
        if g.cls == "JUDGE":
            amended.set_attr(g, "baseline", "n/a, manual gate")
            amended.set_attr(g, "evidence", "pending")
            print(f"  ADDED {g.id} JUDGE: {g.outcome}")
            continue
        name, _ = resolve_shell(g.shell)
        amended.set_attr(g, "shell", name)
        if args.timeout > DEFAULT_TIMEOUT:
            amended.set_attr(g, "timeout", args.timeout)
        ok, detail, why = run_check(g, g.limit(args.timeout), led.root)
        if why in ("shell-missing", "oserror", "timeout", "nested"):
            refused.append(f"{g.id}: baseline could not run ({detail}). {could_not_run(why)}")
        elif g.cls == "PROVE" and ok:
            refused.append(f"{g.id}: baseline already PASSES, so this gate proves nothing")
        elif g.cls == "HOLD" and not ok:
            refused.append(f"{g.id}: baseline already FAILS, so it cannot be held ({detail})")
        else:
            amended.set_attr(g, "baseline", f"{'pass' if ok else 'fail'} at {now()}: {detail}")
            amended.set_attr(g, "evidence", "pending")
            print(f"  ADDED {g.id} {g.cls} (baseline {'green' if ok else 'red'}): {g.outcome}")
            if not ok:
                red_note(g, detail)
    if refused:
        print("REFUSED, the ledger was not changed:")
        for r in refused:
            print(f"  {r}")
        return 2
    # Baselines can take minutes. If anything was recorded meanwhile, stop rather than
    # write over it: the same lost update this release fixes in `run`.
    if Ledger(path).lines != led.lines:
        die("the ledger changed while the amendment was being checked; run it again")
    # Last line of defence: every gate that existed before must come out exactly as it
    # went in, frozen fields, box, evidence and all, and so must the asks.
    def shape(g):
        return (g.frozen_repr(), g.checked, g.evidence, g.abandon, g.verdict, tuple(g.dupes))
    old = {g.id: shape(g) for g in led.gates}
    new = {g.id: shape(g) for g in amended.gates if g.id in old}
    touched = sorted(i for i in old if old[i] != new.get(i))
    if touched or [a[1:3] for a in led.asks] != [a[1:3] for a in amended.asks]:
        die(f"the amendment would change existing content ({', '.join(touched) or 'the asks'}); "
            "refused, the ledger was not changed")
    before = amended.lock
    amended.write_lock()
    if amended.audit_done and amended.audit_line >= 0:
        amended.lines[amended.audit_line] = "Audit: pending"
        amended.audit = "pending"
        amended.log("coverage audit reset to pending: the contract changed after it was recorded")
    amended.log(f"AMENDED: added {', '.join(new_ids)} from {src.name}, lock {before} -> {amended.lock}")
    amended.save()
    print(f"\nAMENDED: {', '.join(new_ids)} added, lock {amended.lock}. Map the asks they "
          "cover with `map`, and get the audit redone: it judged the old contract.")
    return 0


def cmd_map(args):
    """Remap an ask. Mappings were always meant to stay free after declare, since
    deciding which gate covers an ask is the work, but with the guard blocking every
    direct write there was no way to change one. The target must name gates that
    exist, or be an explicit `none: <reason>` dismissal."""
    led = Ledger(ledger_path(args))
    hit = [a for a in led.asks if a[1] == args.ask]
    if not hit:
        die(f"no ask {args.ask}")
    target = args.target.strip()
    if target.startswith("->"):
        target = target[2:].strip()
    if not target:
        die("an empty mapping maps nothing")
    if not re.match(r"none:\s*\S", target, re.I):
        ids = {g.id for g in led.gates}
        named = re.findall(r"G\d+", target)
        missing = [x for x in named if x not in ids]
        if not named or missing:
            die(f"the target must name existing gates or be 'none: <reason>'; unknown: "
                f"{', '.join(missing) or target}")
    line_no, aid, text, _ = hit[0]
    led.lines[line_no] = f'{aid} "{text}" -> {target}'
    led.log(f"{aid} mapped -> {target}")
    led.save()
    print(f"  {aid} -> {target}")
    led = Ledger(led.path)  # report what was saved, not the copy parsed before
    code = report(led, args)
    # Mapping a draft is a normal step before declare, so it is not a failure exit.
    return 0 if led.lock_state() == "open" else code


def cmd_brief(args):
    """Emit the coverage auditor's brief, and nothing else.

    Blindness is the mechanism that stops the audit being a rubber stamp, so it should
    not depend on an agent assembling the brief by hand and remembering to leave its own
    work out. This prints the raw prompt, the enumerated asks and the gate titles. It
    cannot print evidence, baselines, checks, the log or the diff, because it never reads
    them into the output at all. Hand the output to the auditor verbatim.

    Added 2026-08-22 because the first real coverage audit found exactly this gap: the
    protocol required blindness and nothing enforced it.
    """
    led = Ledger(ledger_path(args))
    out = ["=== WHAT WAS ASKED (raw, as given) ==="]
    prompt = led.raw_prompt()
    out.append(prompt if prompt else "(no raw prompt stored on this ledger)")
    out.append("")
    out.append("=== THE ASKS THE HARNESS ENUMERATED ===")
    out += [f'{aid} "{text}"' for _, aid, text, _ in led.asks] or ["(none)"]
    out.append("")
    out.append("=== WHAT THE GATES CLAIM TO COVER (titles only) ===")
    out += [f"{g.id} {g.cls}: {g.outcome}" for g in led.gates] or ["(none)"]
    out.append("")
    out.append("=== YOUR TASK ===")
    out.append("Name any ask, or clearly implied part of an ask, that no gate covers. "
               "Do not read files and do not inspect the work: you are comparing what was "
               "asked against what the gates claim, nothing more. Answer with VERDICT: "
               "COVERED or VERDICT: GAPS FOUND, then one line per uncovered ask.")
    print("\n".join(out))
    return 0


def cmd_audit(args):
    """Record the coverage audit: did the gates cover every ask that was actually made?

    The engine makes no model calls, so it cannot perform this itself, and the party
    that did the work must not be the party that judges its own coverage. So this
    command only records a verdict reached elsewhere: by a subagent given nothing but
    the raw prompt and the gate titles, or by a human. Which mechanism is available is
    an adapter question (CAPABILITIES.md), never a protocol one.
    """
    led = Ledger(ledger_path(args))
    if args.by not in AUDIT_BY:
        die(f"audit --by must be one of {list(AUDIT_BY)}, not '{args.by}'")
    if led.lock_state() == "open":
        die("nothing to audit yet: the contract is not declared, so the ask coverage "
            "it would be audited against is not frozen")
    # A verdict reached is recorded in the auditor's own words, which open with COVERED
    # or GAPS FOUND (the brief asks for exactly that). A summary such as "1 gap: A2 has
    # no gate" read as clean and let the ledger close (round 9 review).
    if args.by in AUDIT_FINAL and not VERDICT_HEAD.match(args.verdict):
        die("a verdict opens with COVERED or GAPS FOUND (optionally after 'VERDICT:'): "
            "paste the auditor's verdict line itself, then any detail after a colon")
    value = f"{args.by}: {args.verdict.strip()}"
    old = led.audit if led.audit_done and led.audit != value else None
    if led.audit_line >= 0:
        led.lines[led.audit_line] = f"Audit: {value}"
    else:
        led.lines.insert(1, f"Audit: {value}")
        led._shift(0)
    led.audit = value
    # The verdict itself goes in the log, and the one it replaced: an audit re-recorded
    # from GAPS FOUND to COVERED used to leave two identical log lines (round 6).
    led.log(f"coverage audit recorded by {args.by}: {args.verdict.strip()}"
            + (f" (replacing {old})" if old else ""))
    led.save()
    print(f"  audit recorded ({args.by})")
    return report(led, args)


def cmd_relock(args):
    """Recompute the lock without re-running baselines.

    Narrow purpose: the freeze algorithm itself changed under an open ledger. Not for
    contract changes, which are `declare --force`. The distinction matters because
    `declare --force` re-runs baselines, and once the work is done a PROVE gate's
    baseline passes and is correctly refused as vacuous, so an algorithm change would
    otherwise strand a ledger that has nothing wrong with it. Requires --force and
    says loudly what it did, because a command that rewrites a lock is exactly the
    thing an agent should not be able to reach for quietly.
    """
    led = Ledger(ledger_path(args))
    if not args.force:
        die("relock rewrites the lock over the CURRENT contract without re-running "
            "baselines. If you changed a gate, use `declare --force` instead. If the "
            "freeze algorithm changed, pass --force and say so in your report.")
    before = led.lock
    led.write_lock()
    led.log(f"RELOCKED {before} -> {led.lock}, baselines not re-run, reason: {args.reason}")
    led.save()
    print(f"RELOCKED {before} -> {led.lock}. Baselines were NOT re-run. "
          "This belongs in your report.")
    return report(led, args)


def cmd_run(args):
    led = Ledger(ledger_path(args))
    state = led.lock_state()
    if state == "open":
        die("not declared yet; run `declare` first")
    if state == "broken":
        die("LOCK BROKEN: the frozen contract changed after declare. Restore it, or "
            "re-declare deliberately with `declare --force` and say so in your report.", 3)

    # A HOLD gate is a regression guard, so it runs on EVERY run, met or not: one that
    # only ran until it first passed proved the system was clean once, early, and never
    # again. Found 2026-10-27 by an independent review that broke the vault after the
    # guard went green and watched status keep reporting it met.
    # Every PROVE gate runs too, met or not, for the reason status re-runs them: a tick in
    # the file is a claim, and a met gate whose check now fails is unticked on the record.
    ran, passed, regressed, results = 0, {}, {}, {}
    for g in led.gates:
        if g.abandon or g.cls == "JUDGE" or not g.check:
            continue
        ok, detail, why = run_check(g, g.limit(args.timeout), led.root)
        results[g.id] = (ok, detail if ok else f"{why}: {detail}")
        ran += 1
        if ok:
            # A silent check produces no output, and "(no output)" is not evidence: it
            # tells a later reader nothing about what was actually verified. Record the
            # exit status and the command that earned it instead.
            passed[g.id] = detail if detail != "(no output)" else f"{why}, silent check: {g.check}"
            print(f"  PASS {g.id}: {g.outcome}")
        else:
            print(f"  FAIL {g.id}: {g.outcome}\n       {why}: {detail}")
            regressed[g.id] = f"REGRESSED at {now()}: {why}: {detail}"

    # Reload before writing. Checks can take many minutes, and saving the copy loaded
    # at the start erased anything recorded meanwhile: on 2026-09-29 an audit written
    # during a twenty minute run vanished, log line and all. Only this run's own
    # results are applied, to whatever the ledger says now.
    led = Ledger(ledger_path(args))
    if led.lock_state() != "intact":
        die("the contract changed while the checks ran, so their results were not recorded. "
            "Run again against the current contract.", 3)
    for g in led.gates:
        if g.id in passed and not g.abandon:
            # A met gate that passes again gets this run's output: a HOLD gate's evidence
            # stayed the first run's ("ALL 32 PASSED") into the archive (round 12).
            if not g.checked:
                led.check_box(g)
            led.set_attr(g, "evidence", passed[g.id])
        elif g.id in regressed and not g.abandon and g.checked:
            led.uncheck_box(g)
            led.set_attr(g, "evidence", regressed[g.id])
    led.log(f"run executed {ran} check(s)")
    led.save()
    for g in led.gates:
        if g.id in results and g.checked:
            g.recheck = results[g.id]
    return report(led, args, rechecked=len(results))


def cmd_evidence(args):
    led = Ledger(ledger_path(args))
    if led.lock_state() == "open":
        die("nothing can be met before the contract is declared; run `declare` first")
    g = next((x for x in led.gates if x.id == args.gate), None)
    if not g:
        die(f"no gate {args.gate}")
    if g.cls != "JUDGE" and not args.force:
        die(f"{g.id} is a {g.cls} gate, so its evidence comes from its CHECK. "
            "Pass --force only if you can say why that is wrong.")
    text = args.text.strip()
    if g.cls != "JUDGE":
        # A forced pass on a provable gate is an override, never a pass: stamp it, log
        # it, and name it in every status report (found 2026-10-28).
        text = "FORCED (not proven by its CHECK): " + text
    led.set_attr(g, "evidence", text)
    if not g.checked:
        led.check_box(g)
    led.log(f"{g.id} evidence recorded by hand" + (", FORCED" if g.cls != "JUDGE" else ""))
    led.save()
    print(f"  {g.id}: evidence recorded")
    return report(led, args)


def cmd_abandon(args):
    led = Ledger(ledger_path(args))
    if led.lock_state() == "open":
        # A draft gate is edited or deleted, not surrendered: an ABANDON written now
        # survived declare, so a gate could be frozen already given up (round 14 review).
        die("nothing to abandon before the contract is declared: delete or rewrite the draft gate")
    g = next((x for x in led.gates if x.id == args.gate), None)
    if not g:
        die(f"no gate {args.gate}")
    led.set_attr(g, "abandon", f"{args.reason.strip()} ({now()})")
    led.log(f"{g.id} ABANDONED: {args.reason.strip()}")
    led.save()
    print(f"  {g.id}: abandoned. This belongs in your report and in the closing summary.")
    return report(led, args)


def summarise(led):
    met = [g for g in led.gates if g.met and not g.abandon]
    abandoned = [g for g in led.gates if g.abandon]
    unmet = [g for g in led.gates if not g.met]
    return met, abandoned, unmet, unmapped_asks(led)


def could_not_run(why):
    return {"timeout": "A slow check needs a larger --timeout (seconds per check, default 120).",
            "shell-missing": "No shell to run it: install bash (Git Bash on Windows).",
            "nested": "A check that runs the ledger itself has hit the depth limit."
            }.get(why, "The check could not be started; see the error above.")


MISSING_CMD = re.compile(r"exit (?:126|127|9009)\b|command not found|is not recognized", re.I)


def red_note(g, detail):
    """Why a baseline is red, printed. A gate red only because its interpreter is
    missing (a Windows `python` stub) can never go green, and `(baseline red)` alone
    looked like the honest red it is not (round 9 review)."""
    print(f"      red because: {detail[:200]}")
    if MISSING_CMD.search(detail):
        print(f"      WARNING: {g.id} is red because a command was not found, not because the "
              "work is missing. It will never pass: fix the CHECK and declare again.")


def unmapped_asks(led):
    """Asks with no real mapping: none at all, a dismissal with no reason, or a gate id
    the contract does not hold. A hand written `A2 -> G2` with no G2 counted as mapped,
    so the ask was dropped without a word (round 9 review)."""
    ids = {g.id for g in led.gates}
    out = []
    for _, aid, _, target in led.asks:
        target = target.strip()
        if re.match(r"none:\s*\S", target, re.I):
            continue
        named = re.findall(r"\bG\d+\b", target)
        if not named or any(x not in ids for x in named):
            out.append(aid)
    return out


def report(led, args, rechecked=None):
    """rechecked: how many checks were re-run for this report, or None when they were
    not (a `map` or `audit` reply). Only a re-run report can be trusted on what is met,
    which is why status, close and the stop gate always re-run."""
    met, abandoned, unmet, unmapped = summarise(led)
    state = led.lock_state()
    # Only a declared ledger owes an audit: nothing is committed to before the lock.
    audit_pending = state != "open" and not led.audit_done
    # An auditor that found gaps has said the contract misses something asked: that is
    # not done, and status said "1/1 met" over it (round 7 review).
    audit_gaps = state != "open" and led.audit_final and audit_found_gaps(led.audit)
    forced = [g.id for g in led.gates if g.forced]
    if getattr(args, "json", False):
        print(json.dumps({
            "path": str(led.path), "lock": state, "gates": len(led.gates), "met": len(met),
            "abandoned": [g.id for g in abandoned],
            "unmet": [{"id": g.id, "cls": g.cls, "why": g.unmet_reason(), "outcome": g.outcome}
                      for g in unmet],
            "unmapped_asks": unmapped,
            "audit": ("pending" if audit_pending else "n/a" if state == "open"
                      else "gaps" if audit_gaps
                      else "recorded" if led.audit_final
                      else led.audit.split(":", 1)[0].strip()),
            "forced": forced, "relocked": led.relocked, "rechecked": rechecked,
        }))
    else:
        for g in unmet:
            print(f"  UNMET {g.id} {g.cls} ({g.unmet_reason()}): {g.outcome}")
        for gid in forced:
            print(f"  FORCED {gid}: evidence written by hand with --force, not by its CHECK. "
                  "It counts only while its CHECK passes. Say so in the report.")
        if led.relocked:
            print("  RELOCKED: the lock was rewritten with `relock --force`, without re-running "
                  "baselines. Say so in the report.")
        if rechecked is None and state == "intact":
            print("  (checks not re-run for this reply; `status` re-runs them)")
        for aid in unmapped:
            print(f"  UNMAPPED {aid}: this ask is not covered by any gate")
        if audit_gaps:
            print(f"  AUDIT GAPS: {led.audit}. Add gates for the gap with `--force declare "
                  "--gates-file F` and audit again, or carry it into a follow up ledger and "
                  "`--force close` naming where it went.")
        if audit_pending:
            print("  AUDIT PENDING: no coverage audit recorded. A party that did not do the "
                  "work must confirm the gates cover every ask.")
        elif state != "open" and not led.audit_final:
            print(f"  AUDIT {led.audit.split(chr(58))[0].upper()}: the turn may end so the "
                  "verdict can be obtained, but this ledger cannot close until it is recorded.")
        tally = f"{len(met)}/{len(led.gates)} met"
        if abandoned:
            tally += f", {len(abandoned)} abandoned"
        print(f"{led.path}: {tally}, lock {state}")
    if state == "broken":
        return 3
    # A verdict still awaited lets the TURN end (the stop gate reads --json for that),
    # but the work is not done: status exited 0 over it, so "status must exit 0, then
    # close" passed on a ledger close then refused (round 11 review).
    awaiting = state != "open" and led.audit_done and not led.audit_final
    return 0 if not (unmet or unmapped or audit_pending or audit_gaps or awaiting) else 1


def cmd_status(args):
    led = Ledger(ledger_path(args))
    # Whatever the lock says: a broken or tampered ledger is still re-checked, so its
    # report never shows a forged tick as met.
    ran = led.verify(args.timeout)
    return report(led, args, rechecked=ran)


DASHES = ((chr(8212), ", "), (chr(8211), " to "), (" -- ", " "), ("--", " "))


def scrub(text, dashes=True):
    """What leaves .ledger for the vault is scrubbed twice: credentials and personal
    numbers by history.py's scrubber (the summary used to promise this and only replaced
    dashes, 2026-10-28), then the dashes the vault bans in prose (contract 3.5)."""
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    try:
        from history import scrub as scrub_secrets
    finally:
        sys.path.pop(0)
    text = scrub_secrets(text)
    if dashes:
        text = re.sub(r"\s*[\u2014\u2013]\s*", lambda m: ", " if m.group(0).strip() == chr(8212) else " to ", text)
    for bad, good in (DASHES if dashes else ()):
        text = text.replace(bad, good)
    return text


NEGATED_GAP = re.compile(r"\b(?:no|nothing|none|not\s+one|not)\b[^,.;:]{0,30}?"
                         r"\b(?:missing|uncovered|lacks?|gaps?|unmapped)\b", re.I)
GAP_WORD = re.compile(r"\bnot\s+(?:covered|mapped|gated)\b|\buncovered\b|\bno\s+gate\b|\blacks?\b"
                      r"|\bmissing\b|\bgaps?\b|\bunmapped\b", re.I)


def covered_but_gap(detail):
    """The detail after a COVERED head contradicts it only when it says so outright: an
    `except`, or a clause naming an ask (A3) as uncovered. Any gap word anywhere made
    "COVERED: nothing missing" a gap (round 10 review), and before that "COVERED except
    A3" read as clean (round 9)."""
    detail = NEGATED_GAP.sub(" ", detail)
    # A dismissed ask is the mapping working as designed, not a gap (round 12 review).
    detail = re.sub(r"\bno\s+gate\s+(?:is\s+)?(?:needed|required|necessary)\b|\bneeds?\s+no\s+gate\b", " ", detail, flags=re.I)
    # "except A2, dismissed as out of scope" names a dismissal, not a gap (round 19).
    if re.search(r"\bexcept\b|\bbut\s+(?:not\s+)?A\d+\b", detail, re.I) and not re.search(r"\bdismiss", detail, re.I):
        return True
    return any(re.search(r"\bA\d+\b", c) and GAP_WORD.search(c) and not re.search(r"\bdismiss", c, re.I)
               for c in re.split(r"[,.;]|\band\b", detail))


# Markdown emphasis around the line is not part of it: auditors write **VERDICT: COVERED**.
VERDICT_HEAD = re.compile(r"\s*[*_`]*\s*(?:verdict\s*:\s*)?[*_`]*\s*(covered|gaps\s+found)\b", re.I)


def audit_found_gaps(audit):
    """True only when the verdict says gaps were found. The old test matched the bare
    word, so "no gaps", "gaps closed" or "two gaps, both covered" refused a close the
    auditor had cleared, and the only way out was to reword the verdict."""
    verdict = audit.split(":", 1)[1] if ":" in audit else audit
    # The brief asks for a structured verdict, and that is read literally, except that
    # COVERED followed by a named gap ("COVERED except A3") is a gap (round 9 review).
    head = VERDICT_HEAD.match(verdict)
    if head:
        if head.group(1).lower() != "covered":
            return True
        return covered_but_gap(verdict[head.end():])
    # Free text: a gap named in plain words is a gap ("A3 is not covered" read as clean
    # because it contains the word covered, round 2), but "no gaps found" is not one
    # (round 6: it matched "gaps found" and refused a clean close).
    text = re.sub(r"\bno\s+(?:uncovered\s+)?gaps?(?:\s+found)?\b", " ", verdict, flags=re.I)
    if re.search(r"\bgaps?\s+found\b|\bnot\s+(?:covered|mapped|gated)\b|\bno\s+gate\s+(?:covers|names)\b"
                 r"|(?<!no )(?<!nothing in the prompt is )\buncovered\b|\bmissing\b", text, re.I):
        return True
    if re.search(r"\bexcept\b|\bgaps?\b|\blacks?\b", text, re.I):
        return True
    if re.search(r"\bcovered\b|\bno\s+gaps?\b", verdict, re.I):
        return False
    # Free text that says neither is not a verdict of coverage: fail closed.
    return True


def cmd_close(args):
    led = Ledger(ledger_path(args))
    if led.path.resolve().parent.name == "closed":
        die(f"{led.path} is already closed")
    if led.lock_state() == "open":
        # Never declared, so nothing in it was committed to: throwing it away is tidying,
        # not a forced close. The only route used to be `--force close`, which printed
        # FORCED CLOSE in every session for a day over a harmless cleanup (round 13).
        closed = led.path.parent / "closed"
        closed.mkdir(parents=True, exist_ok=True)
        led.log("DISCARDED: closed before it was ever declared, so nothing in it was committed to")
        led.save()
        dest = closed / f"{led.path.stem}-discarded-{datetime.now().strftime('%H%M%S')}.md"
        led.path.replace(dest)
        for side in (led.path.with_suffix(".state.json"), led.path.with_suffix(".declared")):
            if side.exists():
                side.unlink()
        print(f"{led.path}: discarded, never declared. Not archived. Moved to {dest}.")
        return 0
    ran = led.verify(args.timeout)
    met, abandoned, unmet, unmapped = summarise(led)
    if (unmet or unmapped or not led.audit_final) and not args.force:
        print("REFUSED to close:")
        return max(1, report(led, args, rechecked=ran))
    # An audit that found gaps is not a formality to be filed. The gap cannot be gated
    # into THIS contract, since the freeze exists precisely so gates are not retrofitted
    # to match what was built, so it must be carried into a successor ledger. Closing over
    # a gaps verdict without saying where it went is the silent narrowing this whole file
    # exists to prevent, so it requires --force and a stated destination.
    if led.audit_final and audit_found_gaps(led.audit) and not args.force:
        print("REFUSED to close: the coverage audit found gaps.\n"
              f"  {led.audit}\n"
              "  A gap cannot be gated into a frozen contract. Carry it into a follow up "
              "ledger, then close this one with --force: the log records it as FORCED over "
              "the gaps verdict, and your report says where the gap went.")
        return 1
    # The record keeps what close itself just saw, not what the first run saw (round 12).
    for g in led.gates:
        if g.recheck and g.recheck[0] and g.recheck[1] != "(no output)":
            led.set_attr(g, "evidence", g.recheck[1])
    if led.lock_state() == "broken" and not args.force:
        die("LOCK BROKEN; close refused. Explain the amendment first.", 3)

    # A forced close is an override, so the log names exactly what it overrode.
    overridden = ([f"unmet {', '.join(g.id for g in unmet)}"] if unmet else []) + \
                 ([f"unmapped {', '.join(unmapped)}"] if unmapped else []) + \
                 ([f"audit {led.audit or 'missing'}"] if not led.audit_final else []) + \
                 ([f"a gaps verdict ({led.audit})"] if led.audit_final and audit_found_gaps(led.audit) else []) + \
                 ([f"lock {led.lock_state()}"] if led.lock_state() == "broken" else [])
    closing = f"FORCED close over: {'; '.join(overridden)}" if overridden else "closed"

    def retire():
        """Move the live ledger out of the lookup path. A finished ledger left in
        place would capture the next session in this directory, which is how a
        stale gate file turns into a wall in front of unrelated work."""
        closed = led.path.parent / "closed"
        closed.mkdir(parents=True, exist_ok=True)
        # The close is logged only now, once nothing can fail: a crash while archiving
        # used to leave a live ledger whose Log already said "closed" (2026-10-28).
        led.log(closing)
        led.save()
        dest = closed / led.path.name
        if dest.exists():
            dest = closed / f"{led.path.stem}-{datetime.now().strftime('%H%M%S')}.md"
        led.path.replace(dest)
        for side in (led.path.with_suffix(".state.json"), led.path.with_suffix(".declared")):
            if side.exists():
                side.unlink()
        return dest

    if not args.archive_to:
        dest = retire()
        print((f"FORCED close over: {'; '.join(overridden)}\n" if overridden else "") +
              f"{led.path}: closed, {len(met)} met, {len(abandoned)} abandoned. "
              f"Not archived. Live file retired to {dest}.")
        return 0

    out_dir = pathlib.Path(args.archive_to)
    if not out_dir.is_absolute() and led.root:
        # From the ledger's root, where its checks run, not wherever close was typed.
        out_dir = led.root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    title = led.lines[0].removeprefix("# Ledger:").strip()
    # From the scrubbed title: a secret in a title used to land in the archive's file name.
    slug = re.sub(r"[^a-z0-9]+", "-", scrub(title).lower()).strip("-") or "task"
    day = datetime.now().strftime("%Y-%m-%d")
    out = out_dir / f"{day}-ledger-{slug}.md"
    if out.exists():
        # A follow up ledger often keeps the title; its archive used to replace the
        # first one's record without a word (round 8 review).
        out = out_dir / f"{day}-ledger-{slug}-{datetime.now().strftime('%H%M%S')}.md"
        n = 2
        while out.exists():
            out = out_dir / f"{day}-ledger-{slug}-{datetime.now().strftime('%H%M%S')}-{n}.md"
            n += 1
    lines = [
        "---", "type: episode", "status: draft",
        "scope: one completed task, harness enforcement record",
        "confidence: high", f"updated: {day}",
        "sources:", "  - a task ledger closed by the harness", "---", "",
        f"# Ledger: {scrub(title)}", "",
        f"Closed {now()}. {len(met)} gates met, {len(abandoned)} abandoned, "
        f"{len(led.gates)} declared. Lock {led.lock_state()}.", "",
        # The audit goes in the record too: a gap it named must not vanish with the file.
        f"Audit: {scrub(led.audit or 'none recorded')}", "",
        *([f"Closed with --force over: {scrub('; '.join(overridden))}", ""] if overridden else []),
        "## Gates", "",
    ]
    for g in led.gates:
        mark = "abandoned" if g.abandon else ("met" if g.met else "UNMET")
        lines.append(f"- {g.id} {g.cls} ({mark}): {scrub(g.outcome)}")
        if g.abandon:
            lines.append(f"  - surrendered: {scrub(g.abandon)}")
    lines += ["", "## Evidence", "",
              "```", *[f"{g.id}: {scrub(g.evidence, dashes=False)}" for g in led.gates if g.evidence], "```", ""]
    if abandoned:
        lines += ["## Lesson stubs (contract 6.1)", ""]
        lines += [f"- {g.id} was surrendered: {scrub(g.abandon)}. Worth a lesson note?"
                  for g in abandoned]
        lines.append("")
    lines += ["Protocol: [[harness/CONTRACT.md]]", ""]
    write_lf(out, "\n".join(lines))
    dest = retire()
    print((f"FORCED close over: {'; '.join(overridden)}\n" if overridden else "") +
          f"{led.path}: closed. Archived to {out}, live file retired to {dest}")
    print("Read the Evidence block before committing: it is command output, scrubbed of the "
          "credential shapes history.py knows, so still check it for anything else that must "
          "never enter the vault (contract 3.4).")
    return 0


GLOBAL_VALUE_FLAGS = ("--dir", "--file", "--session", "--timeout")
GLOBAL_BOOL_FLAGS = ("--json", "--force")


def hoist_globals(argv):
    """Accept global flags on either side of the subcommand. argparse puts them
    before it; humans and hooks write them after it, and being told 'unrecognized
    argument' for `status --json` is exactly the kind of friction that gets a
    discipline tool abandoned."""
    head, rest, i = [], [], 0
    while i < len(argv):
        a = argv[i]
        if a in GLOBAL_BOOL_FLAGS:
            head.append(a)
        elif a in GLOBAL_VALUE_FLAGS and i + 1 < len(argv):
            head += [a, argv[i + 1]]
            i += 1
        elif a.split("=")[0] in GLOBAL_VALUE_FLAGS and "=" in a:
            head.append(a)
        else:
            rest.append(a)
        i += 1
    return head + rest


def main():
    # A Windows pipe takes the console code page, where an arrow in a gate outcome
    # crashed declare before it locked (round 8 review). Escape what cannot be shown.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    ap = argparse.ArgumentParser(prog="ledger", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", help="ledger directory (default .ledger, or $LEDGER_DIR)")
    ap.add_argument("--file", help="explicit ledger path, overrides --dir and --session")
    ap.add_argument("--session", help="session id, which names the ledger file")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="seconds per check")
    ap.add_argument("--json", action="store_true", help="machine readable status")
    ap.add_argument("--force", action="store_true", help="override a refusal, deliberately")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("open")
    p.set_defaults(fn=cmd_open)
    p.add_argument("--title", required=True)
    p.add_argument("--prompt-file")
    p.add_argument("--prompt")
    for name, fn in (("run", cmd_run), ("status", cmd_status)):
        sub.add_parser(name).set_defaults(fn=fn)
    p = sub.add_parser("declare")
    p.set_defaults(fn=cmd_declare)
    p.add_argument("--gates-file", help="with --force: append these gates to a declared "
                   "contract, baselining only them (the file must live outside the ledger dir)")
    p = sub.add_parser("map")
    p.set_defaults(fn=cmd_map)
    p.add_argument("ask")
    p.add_argument("target", help="gate ids, e.g. 'G1, G4', or 'none: <reason>'")
    p = sub.add_parser("evidence")
    p.set_defaults(fn=cmd_evidence)
    p.add_argument("gate")
    p.add_argument("text")
    p = sub.add_parser("abandon")
    p.set_defaults(fn=cmd_abandon)
    p.add_argument("gate")
    p.add_argument("reason")
    sub.add_parser("brief").set_defaults(fn=cmd_brief)
    p = sub.add_parser("audit")
    p.set_defaults(fn=cmd_audit)
    p.add_argument("by", choices=list(AUDIT_BY))
    p.add_argument("verdict")
    p = sub.add_parser("relock")
    p.set_defaults(fn=cmd_relock)
    p.add_argument("reason")
    p = sub.add_parser("close")
    p.set_defaults(fn=cmd_close)
    p.add_argument("--archive-to")

    args = ap.parse_args(hoist_globals(sys.argv[1:]))
    for name in ("title", "text", "reason", "verdict", "target", "ask", "gate"):
        if isinstance(getattr(args, name, None), str):
            one_line(name, getattr(args, name))
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
