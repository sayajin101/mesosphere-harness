# Capabilities: Cursor agent CLI

What this engine can and cannot do. Descriptive only, per contract section 8: no preferences, no rules, nothing about the owner.

Verified: 2026-10-27, cursor-agent 2026.01.23-916f423, macOS, from the installed CLI's `--help`, the vendor's hook documentation, and running this adapter's files by hand. Proven end to end 2026-10-27: a logged in fresh session answered a question only the vault knows. Re-verify on your own version.

## Provides

· **Entry points.** User rules live in the Cursor app (Customize, Rules); a forum report says the CLI has no global rules file, only a repo's AGENTS.md. So the hook below is the main mechanism.
· **Hooks.** `sessionStart` in `~/.cursor/hooks.json` (`{"version": 1, "hooks": {"sessionStart": [{"command": ...}]}}`), returning `{"additional_context": ...}` on stdout. Fire and forget: the agent loop does not wait for it. Cursor's docs do not say whether the CLI fires it; it does: proven 2026-10-27 on macOS, a fresh `cursor-agent -p` session in an unrelated folder, told not to read any file, answered from the injected SOUL. `adapters/cursor/hooks/session-start.py` uses the shared core and was run by hand on the source machine (it loads the vault).
· **Headless runs.** `cursor-agent -p <prompt>`, with `--force` (allows commands unless explicitly denied), read from `cursor-agent --help`. Because `--force` allows any command, the weekly review job is not supported on this engine: `review-job.sh` and `review-job.ps1` refuse.
· **Login.** Not confirmed on the source machine; the owner logs in once (never the agent).
· **Subagents.** Not established here.
· **Model per subagent.** Not established here.
· **Usage readout.** None found for the agent: ask the owner whether they are on a plan with limits, and pay per token users read their provider console.

## What the protocol asks for, and what satisfies it here

| Protocol requirement | Mechanism here | When absent, the protocol falls back to |
| --- | --- | --- |
| SOUL and IDENTITY are in context every session (`CONTRACT.md` §1) | see Entry points and Hooks above | the loader file, and an agent that has not read the core files says so before substantial work |
| A turn may not end while the ledger says otherwise | `stop` hook exists in Cursor hooks; not wired or proven here | advisory: paste `ledger.py status` into every report |
| The weekly review job runs unattended | not supported: the only headless write mode allows any command, and the job reads untrusted mined text, so both adapter files refuse | run the review job with another engine, or review by hand |
| The eval runner never sees ground truth | `blind.py` | the same on every engine |
| The ask coverage audit is performed by a party that did not do the work (`LEDGER.md` §6) | isolated subagents not established here | a human audit, recorded as `Audit: human` |
| The right model for each job: model per subagent (`BOOTSTRAP.md` §3) | not established here | everything runs on the session model, in smaller batches, with usage checked between them |
