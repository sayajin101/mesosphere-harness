#!/usr/bin/env python3
"""Claude Code PreToolUse hook: nothing edits a ledger except ledger.py.

The lock makes a mid task contract change detectable. This makes it hard, which
matters because the failure being designed against is an agent quietly bringing
the contract down to meet the work. Every legal mutation has a subcommand, and
subcommands enforce the rules; a direct write bypasses all of them.

Wire it (confirm the field names against the current hooks reference):

  "hooks": {
    "PreToolUse": [{"matcher": "Write|Edit|MultiEdit|NotebookEdit|Bash",
                    "hooks": [{"type": "command", "timeout": 10,
                    "command": "python3 \"/ABS/PATH/TO/REPO/harness/adapters/claude-code/hooks/lock-guard.py\""}]}]
  }

python on native Windows. Keep the harness folder layout intact when copying.
"""
import fnmatch, json, os, pathlib, re, sys

ADVICE = ("Ledger files are written only by ledger.py, which is what keeps the frozen "
          "contract honest. Use `run` to execute checks, `evidence` for a JUDGE gate, "
          "`abandon` to surrender a gate on the record, `map <ask> \"<gates>\"` to remap an "
          "ask, or `--force declare --gates-file F` with the new gates in a file OUTSIDE the "
          "ledger directory to amend the contract deliberately and visibly.")


def allow():
    sys.exit(0)


def frozen(path):
    """A ledger is protected only once declare has locked it. Before that the
    contract is still being written, and the agent has to be able to write it.
    Declared is read the way ledger.py reads it, from a lock value, a BASELINE line or
    the declare entry in the Log: until 2026-10-28 one `Lock: open` line unguarded it."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    # Never the stored prompt: one quoting a ledger made a fresh draft read as declared.
    text = re.sub(r"\n## Prompt\n[\s\S]*?(?=\n## Log\n|\Z)", "\n", text)
    lock = re.search(r"^Lock:[ \t]*(\S*)", text, re.M)
    return bool((lock and lock.group(1) not in ("", "open"))
                or re.search(r"^\s+BASELINE:", text, re.M)
                or re.search(r"^\S+ \S+ declared \d+ gates?, lock ", text, re.M))


def any_frozen(directory):
    try:
        return any(frozen(p) for p in directory.glob("*.md"))
    except OSError:
        return False


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))
    sys.exit(0)


try:
    payload = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")
except (json.JSONDecodeError, OSError):
    allow()

tool = payload.get("tool_name", "")
inp = payload.get("tool_input") or {}
cwd = pathlib.Path(payload.get("cwd") or os.getcwd())
ENGINE = pathlib.Path(os.environ.get("LEDGER_ENGINE") or
                      pathlib.Path(__file__).resolve().parents[3] / "ledger.py").resolve()


def find_ledger_dir(start):
    """Same walk as ledger.py's: the nearest .ledger holding a ledger, up from the
    working folder, never past a checkout's root (any .git, a worktree's file included). Joining .ledger onto the cwd, as this did until 2026-10-28, let
    `cd subdir` walk a write past the guard."""
    name = os.environ.get("LEDGER_DIR") or ".ledger"
    if os.path.isabs(name):
        return pathlib.Path(name)
    start = start.resolve()
    for folder in (start, *start.parents):
        if (folder / name).is_dir() and any((folder / name).glob("*.md")):
            return folder / name
        if (folder / ".git").exists():
            break
    return start / name


# Guarded: the walk from the working folder and the project's own ledger folder, the
# same pair the stop gate enforces.
ledger_dirs = []
for start in (cwd, os.environ.get("CLAUDE_PROJECT_DIR")):
    d = find_ledger_dir(pathlib.Path(start)).resolve() if start else None
    if d and d not in ledger_dirs:
        ledger_dirs.append(d)

if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
    target = inp.get("file_path") or inp.get("notebook_path") or ""
    if not target:
        allow()
    try:
        resolved = (cwd / target).resolve()
    except OSError:
        allow()
    for ledger_dir in ledger_dirs:
        if not (resolved == ledger_dir or ledger_dir in resolved.parents):
            continue
        if frozen(resolved):
            deny(f"{tool} into a declared ledger is blocked: {resolved.name} is locked. {ADVICE}")
        # Beside a declared ledger, the only file a tool may write is a draft: the stop
        # gate's state file and declare's sidecar steer the wall, and pre-filling the
        # state file's verified list let a forged close through (round 3 review).
        if any_frozen(ledger_dir) and not (resolved.suffix == ".md" and resolved.parent == ledger_dir):
            deny(f"{tool} into a ledger folder is blocked: only ledger.py writes {resolved.name}. {ADVICE}")
    allow()

if tool == "Bash":
    command = inp.get("command") or ""
    # Defence in depth, and only that. The wall is the re-run: status, close and the stop
    # gate re-run every ticked gate's CHECK, so a box ticked by any route this guard
    # misses still counts for nothing. This guard exists to make the honest path the easy
    # one, not to sandbox a shell, which a regex cannot do. Reads stay allowed: a writer
    # is a destructive or in-place command, a redirect, or an interpreter running inline
    # code. The list was widened on 2026-10-28 after a review walked past it with perl,
    # dd, ln, install, rsync, ed, `cd .ledger && sed -i`, python -c and a folder name
    # assembled in a variable.
    writers = re.compile(
        r"\b(tee|cp|mv|rm|truncate|dd|ln|install|rsync|ed|ex|touch|patch|unlink|shred|"
        r"sponge|tar|unzip|vim?|nvim|nano|emacs|curl|wget)\b"
        r"|\bsed\b[^|;&]*\s(-[a-zA-Z]*i|--in-place)"
        r"|\bg?awk\b[^|;&]*-i\s*inplace"
        r"|\b(Set-Content|Add-Content|Out-File|Remove-Item|Move-Item|Copy-Item|New-Item)\b", re.I)
    # An interpreter given the folder's name may write to it however its code is spelled.
    interp = re.compile(r"^\s*(?:\S+=\S*\s+)*(?:(?:env|command|exec|nohup|time|sudo)\s+(?:-\S+\s+)*)*"
                        # A quoted or backslash path counts too: "C:/Program Files/.../python.exe"
                        # (round 17 review).
                        r"(?:\"[^\"]*[/\\]|\S*[/\\])?(python[\d.]*|py|node|deno|ruby|perl|php|"
                        r"pwsh|powershell|osascript|bash|sh|zsh|dash|ksh|fish)(?:\.exe)?\"?(?![\w.-])(.*)$", re.I)
    redirect = re.compile(r"(?<![0-9&])>>?(?!&)\s*(\S+)")
    names_rx = re.compile("|".join([r"\.ledger\b"] + [
        re.escape(d.name) + r"([/\\]|\b)|" + re.escape(str(d)) for d in ledger_dirs]), re.I)

    def names(text):
        """Whether text names a ledger folder, however it is spelled: quotes spliced
        into the name (`.le'dg'er`) and glob patterns (`.led?er`, `.l*`) both count
        (2026-10-28 readiness review)."""
        plain = re.sub(r"[\"'\\]", "", text)
        if names_rx.search(text) or names_rx.search(plain):
            return True
        for tok in re.split(r"[\s()`=$<>]+", plain):
            if re.search(r"[*?\[]", tok):
                for part in re.split(r"[/\\]", tok):
                    if re.search(r"[*?\[]", part) and any(
                            fnmatch.fnmatch(d.name, part) for d in ledger_dirs) \
                            and part.startswith("."):
                        return True
        return False

    def strip_heredocs(text):
        """A here-document body is data handed to a command, never a command or a target,
        so the folder's name inside one is a mention, not a write."""
        out, lines, i = [], text.split("\n"), 0
        while i < len(lines):
            out.append(lines[i])
            m = re.search(r"<<-?\s*(['\"]?)(\w+)\1", lines[i])
            i += 1
            if m:
                while i < len(lines) and lines[i].strip() != m.group(2):
                    i += 1
                i += 1
        return "\n".join(out)

    def pieces(text):
        """Split into simple commands on ; | && || and newlines, but never inside quotes:
        `python3 -c "a; open('.ledger/x')"` is one command, not two harmless halves."""
        out, cur, quote, i = [], [], None, 0
        while i < len(text):
            c = text[i]
            if quote:
                cur.append(c)
                if c == quote:
                    quote = None
                elif c == "\\" and quote == '"' and i + 1 < len(text):
                    cur.append(text[i + 1])
                    i += 1
            elif c in "'\"":
                quote = c
                cur.append(c)
            elif c in ";|\n" or text.startswith("&&", i):
                out.append("".join(cur))
                cur = []
                if text.startswith(("&&", "||"), i):
                    i += 1
            else:
                cur.append(c)
            i += 1
        out.append("".join(cur))
        return out

    def expand(text, env):
        return re.sub(r"\$\{?([A-Za-z_]\w*)\}?",
                      lambda m: env.get(m.group(1), os.environ.get(m.group(1), m.group(0))), text)

    def inside(folder):
        return any(folder == d or d in folder.parents for d in ledger_dirs)

    def engine_call(rest):
        """A real call to this repo's ledger.py: the engine writes the folder, by design."""
        toks = rest.split()
        skip = False
        for tok in toks:
            tok = tok.strip("'\"")
            if skip:
                skip = False
                continue
            if tok in ("-X", "-W"):          # python -X utf8 ledger.py: the value is not the script
                skip = True
                continue
            if tok.startswith("-"):
                continue
            try:
                return (here / os.path.expanduser(tok)).resolve() == ENGINE
            except OSError:
                return False
        return False

    # Judge each simple command on its own, with variables from earlier assignments
    # expanded and the folder followed through cd, so a read that merely names the folder
    # passes and a write is refused however its target is spelled.
    if any(any_frozen(d) for d in ledger_dirs):
        # An interpreter fed a here-document runs that body as code, so there the body
        # is a command after all: `python3 - <<EOF` naming the folder is a write
        # (round 2 review).
        for m in re.finditer(r"(?m)^(.*)<<-?\s*(['\"]?)(\w+)\2.*\n([\s\S]*?)^\s*\3\s*$", command):
            if interp.match(m.group(1).split("|")[-1]) and names(m.group(4)):
                deny(f"That command feeds code naming a declared ledger's folder to an "
                     f"interpreter. {ADVICE}")
        env, here = {}, cwd.resolve()
        for piece in pieces(strip_heredocs(command)):
            for m in re.finditer(r"(?:^|\s)(?:export\s+)?([A-Za-z_]\w*)=(\"[^\"]*\"|'[^']*'|\S*)", piece):
                env[m.group(1)] = expand(m.group(2).strip("'\""), env)
            text = expand(piece, env)
            cd = re.match(r"\s*(?:cd|pushd|Set-Location|sl)\s+(\S+)", text, re.I)
            if cd:
                try:
                    # Quotes spliced into the name are still that name: `cd .le'dg'er`.
                    here = (here / os.path.expanduser(re.sub(r"[\"'\\]", "", cd.group(1)))).resolve()
                except OSError:
                    pass
                continue
            # `git clean -x` or `-X` deletes ignored files, and .ledger is ignored: the whole
            # record vanished with no trace (round 3 review).
            # Only as the command itself: a commit message that mentions it is text.
            if re.match(r"\s*(?:\S+=\S*\s+)*(?:\S*/)?git\s+(?:-C\s+\S+\s+)?clean\b[^|;&]*\s-\w*[xX]", text):
                deny(f"git clean with -x or -X deletes the ignored ledger folder. {ADVICE}")
            # `git stash --all` (or -a) takes ignored files too, the ledger folder with them.
            if re.match(r"\s*(?:\S+=\S*\s+)*(?:\S*/)?git\s+(?:-C\s+\S+\s+)?stash\b[^|;&]*\s(?:--all|-a)\b", text):
                deny(f"git stash --all stashes the ignored ledger folder away. {ADVICE}")
            within = inside(here)
            targets = [m.group(1) for m in redirect.finditer(text)]
            it = interp.match(text)
            # A real call to the engine is allowed whatever its free text says: "owner ran
            # the install" in an evidence line is not an install (round 16 review).
            engine = bool(it) and engine_call(it.group(2))
            if any(names(x) or within for x in targets) \
                    or (not engine and (writers.search(text) or it) and (names(text) or within)):
                deny(f"That command looks like it writes into a directory holding a "
                     f"declared ledger. {ADVICE}")

allow()
