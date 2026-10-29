# Capabilities: Claude Code

What this engine can and cannot do, as observed when this template was extracted. Re-verify every line on your own machines before relying on it. Declared under contract section 8, which permits an adapter to state vendor-specific limits and forbids it from adding persona content, preferences or rules.

**This file is descriptive only.** It never says what the owner wants, never says which mechanism to prefer, and never carries a rule. If a line here starts sounding like a decision, it belongs in `harness/CONTRACT.md` or in a protocol page instead. Every normative sentence below is a citation of one of those, not a new rule.

**It is also weather, not atmosphere.** This is the highest churn file in the harness: hooks, skills and subagents all arrived after the vault was written, and any of them can change shape without notice. Verified at extraction time on Windows and macOS, and not guaranteed to hold after that. Re-verify on your own version. Contract section 8 is what forbids anything outside an adapter from depending on a line in here, and `harness/ENGINEERING.md` rule 2 is why anything that does depend on one proves it first rather than trusting it.

## Provides

· **Entry points.** A vendor-neutral pointer in the vault root `CLAUDE.md`, plus `AGENTS.md` for the cross-vendor convention, plus a user-level `~/.claude/CLAUDE.md` per machine. Session-start instructions are honoured.
· **Hooks.** Shell commands the engine runs at lifecycle points, receiving a JSON payload on stdin and answering on stdout. In use here: `Stop`, `PreToolUse` (vault sessions), and `SessionStart` (user level, every session on the machine, since 2026-10-07). Also available: `PostToolUse`, `UserPromptSubmit`, `SessionEnd`, `PreCompact`, `Notification`. A `SessionStart` hook can inject text into the model's context through `hookSpecificOutput.additionalContext` and show the user a line through `systemMessage`. A `Stop` hook can refuse to let a turn end; a `PreToolUse` hook can deny a tool call before it runs. Payload field names and response shapes move between versions, so confirm them against the current reference rather than against these files.
· **Subagents.** A task can be dispatched to a fresh agent with its own context, given only the brief it is handed. It cannot see the parent transcript, and siblings cannot see each other. That isolation is the capability, not the parallelism.
· **Skills.** Named, on-demand instruction bundles the agent can invoke, including as slash commands.
· **Model per subagent.** A subagent can be given its own model (the Agent tool's model option; a workflow script's per agent `model` and `effort`). Fast tier: the Haiku or Sonnet family at low effort; strong tier: the Opus family; the session model handles orchestration. Usage is visible to the owner in the app or with `/usage`; check it before and after any fan out. Confirm the option names against the current reference, since they move.
· **Usage readout.** The desktop app gives the agent the plan's usage windows (a 5 hour limit, weekly across all models, weekly per model) with percent used and reset time, plus the session's own context window; in the CLI the owner sees the same with `/usage`. A headless run has no one to ask, so it relies on the mining cap (`max_chars`) instead. Verified 2026-10-27 on macOS, desktop app.
· **Headless runs.** `claude -p` with the prompt as the last command line argument (not stdin), a permission mode, and `--add-dir` to widen read access. This is how the weekly review job runs.
· **Settings layering.** Project `.claude/settings.json` tracked, `.claude/settings.local.json` untracked. Machine-specific absolute paths go in the local file so they never reach git.
· **The session id is in the Bash environment.** `CLAUDE_CODE_SESSION_ID` is set for every shell the agent runs, so `ledger.py open` names the ledger after the session without being told. Lookup no longer depends on it: the stop gate enforces every open ledger in the folder (`LEDGER.md` section 9).

## Does not provide

· **A hook cannot spawn a subagent.** A hook is a shell command with no access to the agent's tools. It can require that an agent did something, by refusing to let the turn end, but it cannot do that thing itself.
· **A headless run cannot grant an interactive approval.** Observed 2026-08-22: the review job could not run `verify.py` because the call needed an approval a non-interactive run cannot give, so its digest correctly quoted no integrity number and labelled it unverified.
· **A hook that cannot start fails open, or blocks everything.** A missing interpreter exits 127, which Claude Code treats as non blocking, so the wall falls silently. A script path Python cannot open (a wrong path, or a path with a space left unquoted) makes Python exit 2, which Claude Code reads as a block: every tool call and every turn end is refused, the settings edit that would fix it included, with no six block release. Quote the script path in the command on every OS. Once running, `stop-gate.py` fails closed: a missing engine, a status it cannot read and one that does not finish in time all block, and it releases only after six blocks with nothing changed, saying so. Prove the wall after wiring (`harness/ENGINEERING.md` rule 1).
· **A headless run cannot log itself in.** `claude -p` rides on the CLI's stored OAuth session, which can expire, and only an interactive login restores it. Observed on Windows: the scheduled review job ran, printed `Failed to authenticate: OAuth session expired and could not be refreshed`, exited 1, and its wrapper correctly recorded `failed` and committed nothing.
· **A settings change can reach a running session, but do not count on it.** Observed 2026-10-27 on macOS: ledger hooks added to the project's `.claude/settings.local.json` mid session fired in that same session on its next turn end. Whether user level settings are picked up mid session was not observed either way, and older versions read hook wiring only at session start. So still prove a new hook in a fresh session. The hook script's own contents are read per invocation, so editing the script takes effect immediately.

## Platform limits observed on the source machines

Not vendor facts, but they shape what a check or a job may rely on here.

· `python3` does not exist on native Windows. `python` and `py` do.
· `powershell -File script.ps1 -Unknown` **runs the script anyway** unless the script declares `[CmdletBinding()]`. A bare `param()` block does not refuse the argument. This turned a read-only check into two full runs of a live job on 2026-08-22.
· A PowerShell parameter binding refusal still exits 0, so anything checking for a refusal must match output, not exit status.
· Git Bash rewrites a leading slash in an argument into a path, so `taskkill /PID` needs doubled slashes.

## What the protocol asks for, and what satisfies it here

Requirements are quoted from the protocol pages; this table only maps them onto mechanisms and records the fallback each protocol already specifies for when the mechanism is absent.

| Protocol requirement | Mechanism here | When absent, the protocol falls back to |
| --- | --- | --- |
| A turn may not end while the ledger says otherwise (`LEDGER.md` §9) | `Stop` hook | the ledger is advisory, and the agent pastes its full status into the report so a human sees the same refusal |
| Nothing edits a declared ledger but the engine (`LEDGER.md` §9) | `PreToolUse` hook | status, close and the stop gate re-run every ticked gate's CHECK, so a box ticked by any route the guard misses still counts for nothing; a changed outcome or CHECK breaks the lock |
| The ask coverage audit is performed by a party that did not do the work (`LEDGER.md` §6) | a subagent given only the raw prompt and the gate titles | a human audit, recorded as `Audit: human`, per the same section |
| The review digest's independent reads should not wait on each other | three concurrent subagents, merged by one writer | reading them in any order, since the sequence was never load-bearing |
| SOUL and IDENTITY are always in context, INDEX is the map, and the core is re-read after compaction (`CONTRACT.md` §1) | a user-level `SessionStart` hook (`startup`, `resume`, `clear`, `compact`) that injects SOUL, IDENTITY, INDEX and CONTRACT in full | the loader instruction in `~/.claude/CLAUDE.md`, which an agent can skip without anything noticing, so an agent that has not read the core files says so before substantial work |

## Sources

- `harness/CONTRACT.md` · section 8 permits this file and bounds what it may contain, section 4 is why the contract must not depend on it
- `harness/LEDGER.md` · the requirements in the table above, quoted rather than restated
- `harness/ENGINEERING.md` · the fail-open consequence named in the limits section
