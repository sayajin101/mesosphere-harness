# Capabilities: Codex CLI

What this engine can and cannot do. Descriptive only, per contract section 8: no preferences, no rules, nothing about the owner.

Verified: 2026-10-27, codex-cli 0.164.0, macOS, from the installed CLI's `--help`, the vendor's hook documentation, and running this adapter's files by hand. Proven end to end 2026-10-27: a fresh read-only `codex exec` in an unrelated folder followed the global AGENTS.md loader, read the vault and answered a question only it knows. Re-verify on your own version.

## Provides

· **Entry points.** A global instructions file, `~/.codex/AGENTS.md`, merged with each repo's own AGENTS.md. Installed on the source machine; whether a fresh session obeys it is the proof below.
· **Hooks.** `codex features list` reports `hooks` as stable. A session start event and its output format were not confirmed from official docs, so no hook ships here yet: the loader file is the mechanism, and it is an instruction the agent can skip.
· **Subagents.** Not established here.
· **Headless runs.** `codex exec <prompt>`, with `-s workspace-write` (writes allowed only inside the working directory) and `--skip-git-repo-check`, read from `codex exec --help`. `review-job.sh` uses exactly these.
· **Model per subagent.** `-c model=...` sets the model for a run; per subagent selection not established.
· **Usage readout.** None found for the agent; pay per token users read their provider console.

## What the protocol asks for, and what satisfies it here

| Protocol requirement | Mechanism here | When absent, the protocol falls back to |
| --- | --- | --- |
| SOUL and IDENTITY are in context every session (`CONTRACT.md` §1) | see Entry points and Hooks above | the loader file, and an agent that has not read the core files says so before substantial work |
| A turn may not end while the ledger says otherwise | none confirmed | advisory: paste `ledger.py status` into every report |
| The weekly review job runs unattended on this engine | `review-job.sh` sets `AGENT_CMD`; run with `MESOSPHERE_ADAPTER=codex` | review by hand |
| The eval runner never sees ground truth | `blind.py` | the same on every engine |
| The ask coverage audit is performed by a party that did not do the work (`LEDGER.md` §6) | isolated subagents not established here | a human audit, recorded as `Audit: human` |
| The right model for each job: model per subagent (`BOOTSTRAP.md` §3) | `-c model=...` sets the model for a whole run; per subagent selection not established | everything runs on the session model, in smaller batches, with usage checked between them |
