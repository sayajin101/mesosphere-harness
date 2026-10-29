# Capabilities: Antigravity CLI (agy)

Descriptive only, per contract section 8.

Verified: 2026-10-27, agy 1.4.8, macOS, from `agy --help`, files the installer created, and live sessions.

## Provides

· **Entry points.** Reads `~/.gemini/GEMINI.md` (the same global loader as Gemini CLI): a fresh session reported the persona files exist. It is an instructions file, so the agent loads the vault by reading it. Interactive, inside a trusted workspace, it read the core files on its first turn (proven 2026-10-27).
· **Headless.** `agy -p <prompt>`; `--mode accept-edits` approves file edits; `--add-dir` adds folders. Headless mode cannot ask for permission, so it auto-denies file reads unless `~/.gemini/antigravity-cli/settings.json` allows them: `"permissions": {"allow": ["read_file(/absolute/path/to/vault/**)"]}` (its docs: an exact path, never `*` or `/`; `/**` covers the files inside). The owner adds this, by editing the file or with `/permissions` inside `agy`, in the Global scope (a Project rule only covers sessions opened in the vault folder): the runtime refuses to let any agent read or edit its own settings, by a hardcoded rule.
· **Headless proof, 2026-10-27:** with the Global read rule AND `--add-dir <vault>`, a fresh `agy -p` in an unrelated folder answered from the vault. The rule alone was not enough.
· **Hooks.** None found in `--help`; plugins can be imported from Gemini or Claude (`agy plugin import`), not explored.
· **Login.** Google sign-in, interactively (`agy`).
· **Subagents.** Not established here.
· **Model per subagent.** Not established here.
· **Usage readout.** None found for the agent: ask the owner whether they are on a plan with limits, and pay per token users read their provider console.

## What the protocol asks for, and what satisfies it here

| Protocol requirement | Mechanism here | When absent, the protocol falls back to |
| --- | --- | --- |
| SOUL and IDENTITY in context every session | `~/.gemini/GEMINI.md` loader, plus the read permission for headless | an agent that has not read the core files says so before substantial work |
| A turn may not end while the ledger says otherwise | none found | advisory: paste `ledger.py status` into every report |
| The weekly review job runs unattended on this engine | `review-job.sh` (`--mode accept-edits -p`), with the read permission | review by hand |
| The ask coverage audit is performed by a party that did not do the work (`LEDGER.md` §6) | isolated subagents not established here | a human audit, recorded as `Audit: human` |
| The right model for each job: model per subagent (`BOOTSTRAP.md` §3) | not established here | everything runs on the session model, in smaller batches, with usage checked between them |
