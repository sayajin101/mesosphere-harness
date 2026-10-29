# The Task Completion Ledger

In force wherever `harness/CONTRACT.md` carries section 9: any substantial task runs against a ledger. First proposed and reviewed in 2026-08, and hardened by every incident recorded below.

Vendor neutral, like the contract. The protocol is a file format plus a set of refusals. Any agent that can read a markdown file and run a shell command can obey it, and the enforcement points are wired per vendor in `adapters/`.

## 1. The failure this exists to kill

An agent reports done while part of the request is silently missing. This has been observed directly and repeatedly: multi part instructions come back with the easy parts finished, the hard part quietly dropped, and a confident summary on top. Published measurements agree that this is a real behaviour rather than a bad run: partial compliance with multi instruction prompts, and code quality that erodes across long iterative work.

Instructions cannot fix it. An instruction is read by the same process that decides whether it was followed. The only durable fix is to move the completion decision out of that process.

## 2. The honest limit

Model judgment cannot be removed. It can be reduced to a small, named surface, and whatever remains must satisfy three properties:

1. It is recorded in a file, not held in a context that will be compacted.
2. It is made by a party that did not do the work.
3. It is diffable afterwards, so a change of mind mid task is visible rather than invisible.

Everything below is that principle applied.

What it does not stop, said plainly:

· **The audit line records who audited, it cannot prove it.** `ledger.py audit human "..."` or `audit subagent "..."` is a command the working agent can type itself, and nothing in a file can tell a typed verdict from a real one. The defence is that the verdict, its author and the time sit in the log where a human reads them, and that adapters say which party may record each kind.
· **An agent with a shell can still forge, if it is determined to.** The engine does not trust the file: `status`, `close` and the stop gate re-run every ticked gate's CHECK, so a forged tick counts for nothing, and an edited contract or a stripped lock reads as broken. But anything that runs shell commands as the owner can forge a pass by other means, and listing them all is a losing game: rewrite a CHECK and recompute the lock, edit `ledger.py`, the hooks or the tests a check runs, poison the environment or the tools a check calls (a fake binary on PATH, a Python startup file), run `close` in a doctored environment, delete the ledger folder, or unwire the hooks. The write guard is a set of patterns, not a sandbox. The harness is built against the failure that actually happens, an agent drifting into calling partial work done, and against that it holds; a cheating agent has to cheat on purpose. The deliberate, visible exits are `audit human` typed by the agent itself, `--force close` (logged FORCED, named by the stop gate for a day) and the stop gate's release after six unchanged blocks.

## 3. Separation of powers

| Party | Role | Who or what it is |
| --- | --- | --- |
| The asks | what was requested | enumerated from the raw prompt by the harness, never by the working agent |
| The contract | what counts as done | gates, written before work, frozen by a lock |
| The executive | the work | the agent, which may append evidence but never amend the contract |
| The judiciary | did it happen | `ledger.py`, which only compares strings and exit codes |
| The wall | may the turn end | a Stop hook that asks the judiciary, not the agent |

No party grades its own homework. The one remaining exception is a JUDGE gate, section 5, and it is named as an exception rather than hidden.

## 4. Gate classes and the red first rule

Every gate declares its class, because a rule that pretends every outcome is machine checkable is a rule agents route around.

**PROVE.** The work. Carries a runnable `CHECK` and must **fail at declaration time**. The failure is recorded as its `BASELINE`. A check that already passes before the work exists proves nothing, so the engine refuses to register it. This is the single rule that makes gate quality mechanical rather than aspirational: it kills `echo done` matched against `done`, it kills a file existence check on a file that already exists, and it kills any outcome vague enough that the machine cannot tell before from after.

**HOLD.** A regression guard. Must pass at declaration time and pass again at the end. The vault linter staying clean is a HOLD gate. A HOLD gate that is already failing is refused, with the advice to make it PROVE, because you cannot hold what is already broken.

**JUDGE.** No command can prove it. Reads as the owner rather than as an agent, for example. It carries no `CHECK`, and it is met only when a human readable `EVIDENCE` line replaces the word pending: a measurement, a quote, or a `file:line` citation. A JUDGE gate that carries a `CHECK` is refused, because a provable outcome must be proven.

Static refusals apply before anything runs: an `EXPECT` string that appears inside its own `CHECK` is a tautology, and a `CHECK` beginning with a command that cannot fail for the right reason (`echo`, `true`, `cat` and friends) is not a check. A `CHECK` using `grep -c` with no `EXPECT` is refused too: it would be judged on exit code, and grep exits 1 on a zero count, so a gate whose passing state is zero could never pass. So is a `CHECK` ending in `|| true`, `|| :` or `; exit 0` with no `EXPECT`: its exit code is 0 whatever happened, so it can never fail. **An `EXPECT` replaces the exit code**: with one, the gate passes when the output matches, whatever the check exited with. So never make it a word a failing run also prints (`pytest` says `1 failed, 4 passed` and exits 1): anchor it to the line only a full pass prints, or leave `EXPECT` out and let the exit code judge. A bare success word (`passed`, `ok`, `success`, `done`) is refused at declare. `EXPECT` patterns match line by line (`^` and `$` anchor to each line), because stdout and stderr are joined with a newline. A gate an escaping layer mangled on its way into the file is refused too: a control character in its outcome, `CHECK` or `EXPECT`, an `EXPECT` that opens a regex with `/` and never closes it, an `EXPECT` regex that does not compile, or a `CHECK` with an unclosed quote under a POSIX shell. On 2026-10-27 five gates written through a Python string that was not raw broke in exactly those four ways, and every one was red at declaration for the wrong reason, which the red first rule cannot tell from the right one. Write gates with a plain editor, never through a layer that interprets backslashes.

**A CHECK names its tools by absolute path when they come from a version manager or a login profile** (nvm, pyenv, a Homebrew prefix): the stop gate re-runs ticked checks in the hook's environment, whose PATH can be smaller than your shell's, and a tool it cannot find reads as a failed check that blocks the turn.

**A CHECK must be read-only.** Red first means every check runs once before the work exists, so a check with side effects fires those side effects at declaration time, against a system that is not ready for them. Learned the hard way on 2026-08-22: a baseline invoked the live review job with a flag that did not exist yet, expecting a clean failure, and instead the job ran, because the thing being invoked ignored the unknown flag and proceeded. A check may read, compile, parse, query and run a test suite. It may not deploy, commit, push, send, schedule, or invoke anything that does. When the only way to prove an outcome is to cause it, the gate is a JUDGE gate whose evidence cites the causing run, not a PROVE gate.

Corollary for what a check invokes: never rely on a target rejecting bad input. A script with no argument parsing, a CLI that ignores unknown flags, an endpoint that accepts anything: each of those turns an expected failure into a real execution. Prove the refusal exists before depending on it.

## 5. The ledger file

One file per task, in `.ledger/<session id>.md`. The session id names the file; it does not decide what is enforced (section 9). A finished ledger moves to `.ledger/closed/` on `close`, so yesterday's task never walls in today's session.

```
# Ledger: seven voice pages
Lock: sha256:0a1b2c3d4e5f6a7b
Session: example
Opened: 2026-08-21 14:02

## Contract
- [ ] G1 PROVE: all 7 pages carry a resolvable sources block
      CHECK: python harness/verify.py
      EXPECT: /, 0 failures/
      SHELL: bash
      BASELINE: fail at 14:02: 87 notes checked, 3 failures
      EVIDENCE: pending
- [ ] G2 HOLD: no banned dash enters the vault
      CHECK: python harness/verify.py --diff main
      EXPECT: /, 0 failures/
      SHELL: bash
      BASELINE: pass at 14:02: 0 failures
      EVIDENCE: pending
- [ ] G3 JUDGE: the taste page reads as the owner, not as an agent
      BASELINE: n/a, manual gate
      EVIDENCE: pending

## Asks
A1 "add the seven pages" -> G1
A2 "dont break the linter" -> G2
A3 "keep my voice" -> G3
A4 "also mention the index page" -> none: already done in an earlier commit

## Log
14:02 declared 3 gates, lock sha256:0a1b2c3d4e5f6a7b
```

`SHELL` is written explicitly by the engine, never left implicit. A check authored under Git Bash that silently re runs under `cmd.exe` on another machine fails for the wrong reason, and a gate that fails for the wrong reason teaches an agent to distrust the ledger.

A checked box whose `EVIDENCE` still reads pending counts as unmet, and counts as worse than an unchecked box. A tick is a claim; evidence is the proof.

`ABANDON: <reason>` on a gate is the honest exit. A surrendered gate resolves the ledger, must appear in the report, and becomes a lesson stub at close, per contract section 6.1. Silent scope narrowing is the failure; visible surrender is not.

## 6. Asks and the coverage matrix

The `Asks` block is enumerated from the raw prompt by the harness, deterministically, before the agent starts. It over generates on purpose: dismissing a candidate costs one line, missing a real ask is the failure being designed against.

Every ask needs a mapping, either to a gate or to an explicit dismissal with a reason. An unmapped ask blocks declaration and blocks the end of the turn. This is the part aimed squarely at the observed failure: four things asked, three delivered, and nothing in the system that knew about the fourth.

### The coverage audit

Enumeration is text splitting, so it is fallible in both directions: it invents asks from sentence fragments, and it misses asks phrased without a verb it recognises. Both happened on 2026-08-22, and a four part instruction on a single line once collapsed into one truncated ask. A mapping table over the wrong list of asks is a contract that looks complete and is not.

So a declared ledger owes one more thing before it can close: **a coverage audit performed by a party that did not do the work.** The auditor is given the raw prompt and the gate titles, and nothing else. Not the transcript, not the diff, not the evidence. It answers one question: which asks in this prompt does no gate cover? It has no completion bias to overcome, because it did not build anything.

The verdict is recorded on the `Audit:` line, naming who reached it. It must start with `COVERED` or `GAPS FOUND` (optionally after `VERDICT:`), the words the brief asks the auditor for, and `audit subagent` or `audit human` refuses anything else: paste the auditor's verdict line, then any detail after a colon. A `COVERED` that goes on to name a gap ("COVERED except A3") is read as gaps. Only `awaiting-human` and `awaiting-subagent` take free text: they let the turn end so the verdict can be fetched, while `status` exits 1 and `close` refuses until a real one is recorded. Every verdict recorded, and any it replaced, stays in the log:

```
Audit: subagent: GAPS FOUND: the prompt also asks to keep the linter clean, which no gate names
Audit: human: COVERED: the owner confirmed the four gates cover what they asked for
```

Until that line is filled, the ledger reports `AUDIT PENDING`, `status` is non-zero however many boxes are ticked, and `close` refuses. A ledger with every gate met and no audit is exactly the shape of the failure being designed against, so it is not treated as clean.

The audit is deliberately outside the lock, since it is reached after the contract is frozen. And it is deliberately not performed by the engine: the engine makes no model calls, and a judgment about whether the work covers the request must not come from the party that chose what to build.

**Which mechanism performs it is an adapter question, never a protocol one.** The protocol requires an independent auditor; `adapters/<vendor>/CAPABILITIES.md` says what that is on a given engine, and states the fallback when the engine has none. Where isolated subagents exist, the auditor is one of them. Where they do not, the audit degrades to a human, recorded as `Audit: human`, which is weaker but honest. What is never permitted is skipping it silently, because a requirement that quietly evaporates when the harness is thin is not a requirement.

## 7. The lock

At declaration the engine hashes the frozen fields of every gate: id, class, outcome text, `CHECK`, `EXPECT`, `SHELL`, `BASELINE`, and `TIMEOUT` when declare recorded one.

Frozen after declare: everything in that list. Free to change: the checkbox, `EVIDENCE`, `ABANDON`, `VERDICT`, the asks mappings, and the log.

**The lock covers what a gate means, never whether it was met.** A tick in the file is a claim. `status`, `close` and the stop gate re-run the CHECK of every ticked PROVE and HOLD gate that is not abandoned, and only the re-run counts, so a box ticked by hand, by a script, or by a line smuggled in through a free text argument is reported as `ticked, but its CHECK fails when re-run`. An unticked gate is unmet whatever its check says, so the unticked ones are not run. Every free text argument is refused if it holds a line break, and a repeated attribute line under a gate breaks the lock, since the parser would read only the last one. Until 2026-10-28 the file was trusted, and a readiness review forged a pass three different ways.

**Nothing is enforced before the lock exists.** A ledger whose `Lock` still reads `open` is a draft, and drafting is not a commitment: the Stop gate lets the turn end, and the PreToolUse guard permits edits. Enforcement begins at `declare` and not one moment earlier, because a wall in front of an undeclared ledger punishes an agent for having begun to write gates. The reverse error, treating a draft as binding, was made and fixed on 2026-08-22.

So ticking a box is legal and editing what the box means is not. A broken lock blocks the turn even when every box is ticked, which is exactly the case where a report would otherwise read as a clean success. Amending a contract mid task is allowed, deliberately, and it leaves the amendment in the log where a human can see it. Before the work starts that is `declare --force` over an edited draft. Once the lock exists the guard forbids editing the file, so new gates go in a file outside the ledger directory and `ledger.py --force declare --gates-file F` appends them: only the new gates run baselines, the old ones keep theirs, and a refused amendment leaves the ledger untouched. A gates file holds gate and attribute lines only, opens with a gate, arrives unticked, and every existing gate must come out of the amendment exactly as it went in, or the whole amendment is refused. Ask mappings stay free after the lock, so `ledger.py map <ask> "<gates>"` remaps one. Until 2026-09-29 neither existed, the guard's own advice named an amendment path it made unreachable, and a session had to split one contract across three ledgers to take in its audit's gaps.

## 8. Lifecycle

```
ledger.py open --title T --prompt-file F   # enumerate asks, create the ledger
ledger.py declare                          # lint, run baselines, refuse bad gates, lock
ledger.py run                              # execute every check, flip boxes, record evidence
ledger.py evidence <id> "<proof>"          # a JUDGE gate, by hand (--force on PROVE or HOLD: stamped FORCED, still re-checked)
ledger.py abandon <id> "<reason>"          # honest surrender, on the record
ledger.py --force declare --gates-file F   # add gates to a declared contract
ledger.py map <ask> "<gates>"              # remap an ask after the lock
ledger.py brief                            # print the brief for the coverage auditor
ledger.py audit subagent|human "<verdict>" # record the coverage audit (also awaiting-human, awaiting-subagent)
ledger.py --force relock "<reason>"        # re-hash only when the freeze algorithm itself changed
ledger.py status [--json]                  # re-runs ticked checks; 0 all met, 1 unmet, 2 usage, 3 lock broken
ledger.py --timeout 300 <command>          # seconds per check (default 120); a baseline that times out is refused, not red;
                                           # declare records a larger value on each gate as TIMEOUT, which later runs honour
ledger.py close --archive-to episodic      # re-runs ticked checks; summary scrubbed by history.py, lesson stubs
ledger.py --force close                    # override: closes over unmet work, logged FORCED, named by the stop gate for a day
```

Every CHECK runs in the folder that holds `.ledger`, wherever the command was typed, so `run` in a subfolder and the stop gate at the root judge the same thing. Checks run in a plain shell, never a login shell, so nothing in the owner's profile runs first; on Windows Git Bash keeps `-l`, which is what puts its tools on PATH. A draft can be replaced with `--force open`, which retires it to `closed/`; a declared ledger never can: close it first.

## 9. Enforcement points

Wired per vendor in `adapters/`, never in this file. For Claude Code, phase 1 uses two:

**Which ledgers are enforced, the one rule.** The ledger folder is the nearest `.ledger` holding a ledger, found walking up from the working folder and stopping at the checkout's root (any `.git`, folder or file, so a worktree or submodule is its own checkout), plus the project folder's own `.ledger` when the engine names it (Claude Code: `CLAUDE_PROJECT_DIR`). An empty `.ledger` never wins. Every open ledger in it is enforced, whoever opened it and whatever the session id. A finished ledger leaves the folder on `close`. Every hook and every doc follows this rule; until 2026-10-28 the stop gate enforced only the session's own ledger when one existed, so a second session's small ledger silenced a long running one.

- **Stop**: refuse to end a turn while any open ledger has an unmet gate, an unmapped ask, a missing audit, or a broken lock. No model calls: it runs `status`, which re-runs the ticked checks, so it needs a long hook timeout, and a status that cannot finish in time blocks rather than passes. It shows every FORCED gate, every ABANDONED gate, a RELOCKED ledger, and any ledger force closed in the last day. A ledger whose status cannot be read blocks: a wall that cannot read the record proves nothing was met. It releases rather than traps: after six consecutive blocks with no change to what is outstanding (gates met, asks mapped, the audit, the lock; a `run` that changes none of those is not progress) it allows the stop and says so, because a genuinely stuck agent must be able to hand over. The release then holds for that session until something outstanding changes: every later stop is allowed with the same message, and a new session starts counting from zero.
- **PreToolUse**: deny direct writes into the ledger directory, including the indirect routes (in place editors, copies and links, inline interpreter code, writes after `cd .ledger`, names built in variables, spliced quotes and globs). This is defence in depth that keeps the honest path the easy one; the re-run is the wall. Every legal mutation has a subcommand, and the subcommands enforce the rules.
- **Engines without these hooks** run the same protocol on advice: the agent runs `status` before reporting done and treats exit 1 as not done. Prove that advisory path the same way, by watching `status` exit 1 on a gate that cannot pass.

## 10. Rules for an agent under this protocol

1. Open the ledger and write the gates before the work, not after. Intentions do not survive a compaction; files do.
2. Every number that will appear in your report gets its own gate with a check that measures it. Report no number you did not measure at report time.
3. When you feel finished, run `status` instead of concluding.
4. If a gate is impossible, abandon it out loud. Never quietly rewrite it smaller.
5. Full sweeps stay full. If the ask says all 80 files, the gate measures 80.

## 11. Where ledgers live, and why not in the vault

A live ledger holds raw command output. That collides with two write rules: output routinely carries dashes banned by section 3.5, and it can carry anything at all, including a credential, which section 3.4 forbids from ever entering the vault.

So live ledgers live in `.ledger/`, which is gitignored, and `close` writes a summary scrubbed by `history.py`'s scrubber (credential shapes, card and ID numbers, phone numbers), with evidence inside a fenced block and banned dashes normalised in the prose. The scrubber knows shapes, not secrets, so read the Evidence block before committing. Where that summary goes follows contract section 5: a ledger for work on the vault or the harness closes with `--archive-to episodic`; a ledger for work in a project repo closes with `--archive-to <that repo's own docs or memory folder>`, so project content stays in its moon. Only a lesson from it that would survive a change of employer comes here, as its own distilled note in `episodic/`. The closing summary is an episode note like any other, and its abandoned gates arrive as lesson stubs for the promotion cadence in contract section 6.2.

## 12. What this is not

Not for conversational replies, factual questions, or one line fixes. A ledger for a typo is ceremony, and ceremony that does not pay for itself teaches everyone to skip the ceremony that does. The threshold is a task with more than one deliverable, or work long enough that its own start will have left the context by the time it ends.

## Sources

- `harness/CONTRACT.md` · sections 3.4 and 3.5 set the write rules this protocol works around, section 6 the learning loop that closing summaries feed, and section 8 the adapter rule that keeps the enforcement points out of this file
- The motivating review, 2026-08-21: a popular open source anti laziness skill built entirely from markdown instructions. The weakness named then: an agent enforcing a rule set written in markdown is still the same agent grading itself. The gate classes, the red first rule and the lock are the answer to that objection.
