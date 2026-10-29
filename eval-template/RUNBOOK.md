# Runbook

Plain-English operating guide. Two activities happen here: RUNNING an eval (exam day) and REFILLING scenarios (restocking the exam). Replace `<EVAL_REPO>` and `<VAULT_CLONE>` below with your own private repo and local path.

## When to run an eval

· Considering a new AI model or vendor (the swap gate: it must meet or beat the incumbent score under this exact protocol).
· After a big batch of vault changes or sign-offs (did fidelity move?).
· Every few months as a health check.
· Before promoting any autonomy (contract section 7).

## Running an eval

Needs: this repo cloned, the vault cloned, and an agent that can dispatch isolated subagents. Paste:

> i want to run my persona eval. pull <EVAL_REPO> and read its README.md protocol section carefully, then run it exactly. step 1: run blind.py on scenarios/scenarios.json, writing blind.json and key.json to a temp folder outside both repos; if it refuses, stop and tell me which count leaked. step 2: split blind.json across one or two runner subagents. each runner must wear my vault (read SOUL.md, IDENTITY.md, INDEX.md, harness/CONTRACT.md in <VAULT_CLONE>, and it may pull heuristics/taste/voice/people/decisions/skills pages just in time) but is strictly FORBIDDEN from reading the vault's raw/ and episodic/ folders, this eval repo, my chat transcripts, or my agent config directory. runners answer blind: what did i decide and why, in my terms. step 3: a separate strict judge subagent gets the answers, key.json and the ground truth, writes runs/<today>-<label>-scores.json per the README rubric, checks for near-verbatim ground truth quoting as a contamination signal, and analyses every miss. step 4: run score.py on that file with --scenarios and --incumbent set to the latest previous scores file, and report its output verbatim. write a dated report into runs/, commit and push, and give me the plain english summary: the score, whether the incumbent held, and what each miss says my vault still gets wrong about me.

The orchestrating session may see ground truth (it prepares and judges); only the runner subagents must stay blind, and blind.py is what guarantees what they receive.

## After a run

· Misses are gold: each one is a question for the owner about an exception boundary the vault lacks. Answer them; the answers get written into the vault as interviewed content.
· BURN any scenario whose lesson gets written into the vault (move it to `scenarios/retired/`): the vault now contains its answer.
· If a new model beat the incumbent under identical protocol, it may be promoted per the harness contract; record the decision in the run report.

## Refilling scenarios

Refill when ANY of these is true:
· Active scenario count drops below 25 (burns after runs eat the set).
· A model swap decision is coming and the set is older than about 3 months.
· Roughly every 3 to 6 months regardless, because the best scenarios are recent: they test who the owner is NOW.
· After any major life or work change, which creates whole new decision categories.

Refilling needs access to chat history on whichever machine the fresh decisions happened. Paste:

> i want to refill my persona eval with fresh scenarios. read <EVAL_REPO> README.md and RUNBOOK.md first. mine my recent agent chat history on this machine (my own typed messages only) for real decisions i made: genuine forks with two or more plausible options, my actual choice and reasoning verbatim-quotable. also read the fork notes in my vault's episodic/ that have not been promoted yet. scrub any credentials from extracted text BEFORE any mining agent reads it. contamination rule: a scenario is only valid if the specific event appears NOWHERE in the judgment tiers of my vault, and you must grep the pages' evidence quote sections too, not just their claims. write new scenarios into scenarios/scenarios.json in the existing format with contamination_check filled in, run blind.py --selfcheck on the result, commit and push, and summarise what you added. never invent a scenario to reach a count.

## Machine guidance

· Vault repo: pull on every machine (it is what agents wear).
· Eval repo: pull only where and when you are running or refilling; day-to-day machines are better off without it on disk.
· Both repos are private. Keep them that way.
