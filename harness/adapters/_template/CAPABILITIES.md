# Capabilities: <engine name>

What this engine can and cannot do, as observed on the owner's machines. Declared under contract section 8, which permits an adapter to state vendor specific limits and forbids it from adding persona content, preferences or rules.

**This file is descriptive only.** It never says what the owner wants, never says which mechanism to prefer, and never carries a rule. It is the highest churn file in the harness: record the date and version you verified each line on, and re-verify before relying on it.

Verified: <YYYY-MM-DD>, <engine version>, <operating system>.

## Provides

· **Entry points.** <How a session is pointed at `harness/CONTRACT.md`: a rules file, a system prompt setting, a config file. Where per machine settings live, so absolute paths never reach git.>
· **Hooks.** <Lifecycle points where the engine runs a command and acts on its answer, if any. Can one refuse to end a turn? Can one deny a tool call before it runs? Can one inject text at session start?>
· **Subagents.** <Can a task be handed to a fresh agent that sees only its brief, not the parent's context?>
· **Headless runs.** <Can the engine run unattended from a scheduler, with a prompt on stdin?>
· **Model per subagent.** <Can a subagent be given its own model and reasoning effort? How (option name, config key)? Which models map to the fast and strong tiers in BOOTSTRAP.md section 3? Is there a usage readout the agent can check, and does it tell a subscription plan from pay per token billing?>

## Does not provide

· <Each missing mechanism, and what was observed when it was tried.>

## What the protocol asks for, and what satisfies it here

| Protocol requirement | Mechanism here | When absent, the protocol falls back to |
| --- | --- | --- |
| A turn may not end while the ledger says otherwise (`LEDGER.md` §9) | <stop hook, or none> | the ledger is advisory, and the agent pastes its full `ledger.py status` into every report so a human sees the same refusal |
| Nothing edits a declared ledger but the engine (`LEDGER.md` §9) | <pre tool hook, or none> | status, close and the stop gate re-run every ticked gate's CHECK, so a box ticked by any route the guard misses still counts for nothing; a changed outcome or CHECK breaks the lock |
| The ask coverage audit is performed by a party that did not do the work (`LEDGER.md` §6) | <isolated subagent, or none> | a human audit, recorded as `Audit: human` |
| SOUL and IDENTITY are always in context and re-read after compaction (`CONTRACT.md` §1) | <session start injection, or none> | the loader instruction in the engine's rules file, and an agent that has not read the core files says so before substantial work |
| The right model for each job: model per subagent (`BOOTSTRAP.md` §3) | <per subagent model option, or none> | everything runs on the session model, in smaller batches, with usage checked between them |
| The eval runner never sees ground truth (`eval-template/README.md`) | `blind.py` writes the only file the runner receives | the same: this one is a script on every engine |
