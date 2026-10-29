# Adapter: Claude Code

Wiring for Anthropic's Claude Code. The protocol it wires lives in `harness/CONTRACT.md` and `harness/LEDGER.md`; this adapter only maps Claude Code's native mechanisms onto it, per contract section 8.

## Entry points

· Vault root `CLAUDE.md` points sessions opened inside the vault at `harness/CONTRACT.md`.
· Vault root `AGENTS.md` carries the same pointer for any tool reading the cross-vendor convention.
· For sessions opened OUTSIDE the vault (any project repo), the hook is a small pointer block, NEVER placed in a company repo's shared CLAUDE.md (colleagues' agents read that; the persona is the owner's alone):
  · Per project: a `CLAUDE.local.md` beside the repo's CLAUDE.md (auto-read by Claude Code, kept out of git) containing: read SOUL.md and IDENTITY.md in full, read INDEX.md as a map and pull pages just-in-time, obey harness/CONTRACT.md, plus one line naming the company context.
  · Global: the same block once in `~/.claude/CLAUDE.md` (per machine, with that machine's clone path), making every session on the machine wear the vault. Install after SOUL and IDENTITY are signed (before signing, tier 1 loads as provisional per the contract).
· Claude Code's auto-memory lives in `~/.claude/projects/*/memory/`; anything person-level discovered there should be promoted into the vault per SCHEMA.md, not duplicated.

## The vault load (contract section 1)

The loader block in `~/.claude/CLAUDE.md` is an instruction, read by the same process that decides whether to follow it. Sessions have been observed skipping it, then asserting things the vault plainly contradicts, running substantial work with no ledger, and breaking write rules. So the load is made observable rather than trusted:

· `hooks/session-start.py` on **SessionStart**, matcher `startup|resume|clear|compact`: injects SOUL.md, IDENTITY.md, INDEX.md and harness/CONTRACT.md in full as `additionalContext`. `compact` is in the matcher because contract section 1.4 asks for a re-read after compaction. It finds the vault from its own path (or `MESOSPHERE_DIR`), so no machine path lives in the vault.
· It never blocks a session. A missing vault exits 0 and says, to the model through `additionalContext` and to the user through `systemMessage`, that the persona was NOT loaded, because a silent hook looks exactly like one that worked.
· Its stdout is ASCII-only JSON, because Windows decodes a hook's stdout with the locale codec.
· Cost: roughly the size of those four files in tokens at every session start. Keep SOUL and IDENTITY short.

Wire it in the **user-level** `~/.claude/settings.json`, because it must reach every repo on the machine. That file is per machine, so the absolute clone path never reaches git. `harness/tests/test_session_start.py` covers all four sources and the missing-vault path. A settings change only reaches sessions started after it, so prove the hook with a fresh session, not the one that installed it.

## The task completion ledger (contract section 9)

Two hooks, both in `hooks/`:

· `stop-gate.py` on **Stop** (not SubagentStop: a subagent is not bound by its parent's ledger): refuses to end a turn while any open ledger has an unmet gate, an unmapped ask, a missing audit, or a broken lock. It re-runs the CHECK of every ticked gate rather than trusting the box, so give it a long hook timeout (900 seconds, as in the wiring at the top of `hooks/stop-gate.py`) and keep checks fast. No model calls: a file scan, the checks, and an exit code. Releases rather than traps: after six consecutive blocks with no change to the ledger it allows the stop and says so. It allows at once when `MESOSPHERE_REVIEW_JOB=1` is set, which the review job wrappers export for the claude they launch: contract 9.6 exempts that job, and without the marker an interactive session's open ledgers can hold the job hostage.
· `lock-guard.py` on **PreToolUse** (`Write|Edit|MultiEdit|NotebookEdit|Bash`): denies direct writes into `.ledger/`, so every mutation goes through a subcommand that enforces the rules. Reads are always allowed, and so is a real call to this repo's `ledger.py`. A shell command is refused when it writes into the folder by any route the guard recognises: a redirect, an in place editor, a copy or link, an interpreter running inline code that names the folder, or a write after `cd .ledger`. The guard is defence in depth, not a sandbox: the wall is the stop gate, which re-runs the checks.

Wire them in the vault's `.claude/settings.local.json`, deliberately not the tracked `settings.json`: the entries carry this machine's absolute path, and settings.local.json is gitignored so that path never lands in the repo. Each hook file carries its own wiring snippet in its docstring. On native Windows the interpreter is usually `python`, not `python3`. A git worktree is its own checkout and does not share the main checkout's untracked `settings.local.json`: if you work in worktrees (the desktop app makes them for parallel sessions), check that the hooks are wired there too, by proving the wall in a worktree session, or a ledger opened there is advisory without a word.

If you want the ledger enforced in other repos too (not only inside the vault), copy `harness/ledger.py` and `harness/history.py` into it (`close` scrubs its archive with `history.py`), wire the same two hooks in that repo's `.claude/settings.local.json`, and run `ledger.py` from that repo's root, so its `.ledger/` lives there.

Lookup follows the one rule in `LEDGER.md` section 9: the nearest `.ledger` holding a ledger, walking up from the working folder, plus the project folder's own (`CLAUDE_PROJECT_DIR`), and every open ledger in them enforced, whoever opened it. `ledger.py close` retires the live file to `.ledger/closed/`, which keeps a finished task from becoming a wall in front of unrelated work later.

**Prove the wall, do not assume it.** A hook command whose interpreter is missing exits non zero, which Claude Code treats as non blocking, so it looks exactly like a hook that approved (`harness/ENGINEERING.md` rule 1); one whose script path Python cannot open (unquoted, with a space in it) exits 2, which Claude Code reads as a block on everything. Quote the script path. After wiring, open a ledger with one gate that cannot pass, try to end the turn, and confirm you are refused. Hook payload field names move with the vendor, so confirm them against the current hooks reference rather than trusting these files.

## The weekly review job

The job itself is vendor neutral since 2026-10-27 and lives in `harness/review-job/`; this adapter supplies only `review-job.sh`, which tells the wrapper how Claude Code runs headless (`AGENT_CMD`). Everything below about the wrappers applies to any engine.

A scheduled headless run (macOS: a launchd job built from `review-job/macos/local.mesosphere-review.plist.template`; Windows: Task Scheduler running `review-job/windows/run-review.ps1`) that pulls the vault, sweeps `episodic/` and the machine's fresh `~/.claude` auto-memories, and writes exactly one `episodic/review-digest-<date>.md` with ready-to-approve promotion drafts, contradictions, staleness flags, and housekeeping, then commits and pushes. It may write ONLY that digest file; tiers 1 and 2 stay owner-gated.

**The prompt lives here, and every job reads it from the vault clone at run time.** `harness/review-job/prompt.md` is the single copy. A job must never keep its own copy elsewhere, because that copy drifts silently. If the file is missing at run time the job fails loudly rather than falling back. With more than one machine, stagger the weekday so digests do not collide.

Five things the wrapper has to get right, every one of them learned by getting it wrong:

· **Make sure the run can actually read the auto-memory path, and check rather than assume.** Whether a headless run can reach `~/.claude/projects/*/memory/` is machine-specific: on one Windows machine the Read tool was denied while `ls` and `cat` on the identical files succeeded, so that job passes `--add-dir`; on macOS it was not needed. Grant it only where the run genuinely cannot read the path. The sweep must use `find -L`: a memory store belonging to a repo the owner owns is a symlink into that repo (contract section 5), and a bare `find -type d -name memory` neither matches it nor complains.
· **Stage by pattern, and know which kind of empty you are looking at.** Commit `episodic/review-digest-*.md` rather than one exact filename. A digest written but not staged is a hard failure; neither written nor staged is a quiet week.
· **Prove the run happened, because the scheduler will not tell you.** The job writes an inflight marker at start and clears it only when an outcome has been written to a status file, and the next run reports any marker it finds as a killed predecessor.
· **The execution bound is not symmetric between platforms.** Task Scheduler has an execution time limit; launchd has none, so the macOS wrapper carries its own wall clock watchdog. The Windows wrapper carries one too, set just under the scheduler's limit, because a scheduler kill records no outcome of its own.
· **Refuse arguments, and scope the commit.** A shell script with no argument parsing runs its body anyway, exactly as `powershell -File` does without `[CmdletBinding()]`, so the refusal is the first statement in the wrapper, ahead of anything with a side effect. The commit carries the pathspec too, so a concurrent interactive session's staged work never lands under a digest message.

Deployment details, env overrides and the self tests are in `review-job/README.md`.

## What this engine can and cannot do

Declared in `CAPABILITIES.md` beside this file, per contract section 8. Descriptive only, and the most disposable file in the harness. Nothing outside an adapter may depend on a capability, so that page also records the fallback for each requirement it satisfies.

Nothing in this adapter adds persona content or modifies contract rules.
