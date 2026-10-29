# Capabilities: Gemini CLI

What this engine can and cannot do. Descriptive only, per contract section 8: no preferences, no rules, nothing about the owner.

Verified: 2026-10-27, gemini 0.46.0, macOS, from the installed CLI's `--help`, the vendor's hook documentation, and running this adapter's files by hand. NOT yet proven end to end: a logged in fresh session answering a question only the vault knows (BOOTSTRAP phase 4, step 5). Re-verify on your own version.

## Provides

· **Entry points.** A global instructions file, `~/.gemini/GEMINI.md`. Installed on the source machine.
· **Hooks.** `SessionStart` in `~/.gemini/settings.json` (`hooks.SessionStart[].hooks[]`, `type: command`, timeouts in milliseconds). Its output takes the same shape as Claude Code's (`hookSpecificOutput.additionalContext`, optional `systemMessage`): injected as the first turn interactively, prepended to the prompt headless. `adapters/gemini/hooks/session-start.py` uses the shared core and was run by hand on the source machine (it loads the vault). Advisory only: it never blocks startup.
· **Headless runs.** `gemini -p <prompt>`, with `--approval-mode auto_edit` (approves file edits, asks for other tools), read from `gemini --help`. `review-job.sh` uses exactly these. `--include-directories` adds folders, like `--add-dir`.
· **Login.** A headless run on the source machine exited asking for an auth method: the owner must log in once (never the agent).
· **Blocked for personal accounts, observed 2026-10-27:** after updating to 0.65.0, sign-in failed with "This client is no longer supported for Gemini Code Assist for individuals", pointing to Antigravity. API key and paid Code Assist users may still work.
· **Note.** Google's docs say Gemini CLI was replaced by Antigravity CLI for unpaid and Google One users on 2026-06-18; check which one the owner has.
· **Subagents.** Not established here.
· **Model per subagent.** Not established here.
· **Usage readout.** None found for the agent: ask the owner whether they are on a plan with limits, and pay per token users read their provider console.

## What the protocol asks for, and what satisfies it here

| Protocol requirement | Mechanism here | When absent, the protocol falls back to |
| --- | --- | --- |
| SOUL and IDENTITY are in context every session (`CONTRACT.md` §1) | see Entry points and Hooks above | the loader file, and an agent that has not read the core files says so before substantial work |
| A turn may not end while the ledger says otherwise | not established (hook events beyond SessionStart unchecked) | advisory: paste `ledger.py status` into every report |
| The weekly review job runs unattended on this engine | `review-job.sh` sets `AGENT_CMD`; run with `MESOSPHERE_ADAPTER=gemini` | review by hand |
| The eval runner never sees ground truth | `blind.py` | the same on every engine |
| The ask coverage audit is performed by a party that did not do the work (`LEDGER.md` §6) | isolated subagents not established here | a human audit, recorded as `Audit: human` |
| The right model for each job: model per subagent (`BOOTSTRAP.md` §3) | not established here | everything runs on the session model, in smaller batches, with usage checked between them |
