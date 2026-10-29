# Harness engineering rules

Rules for building the harness itself, as distinct from rules about the owner. They live here rather than in `heuristics/` because a heuristic is a judgment rule of a person, and these are properties of mechanisms.

Each rule below was paid for. The incident is named, because a rule without its story gets softened by the next person who finds it inconvenient.

## 1. A mechanism that fails open is invisible when it fails

Enforcement code often has to fail open, because a wall that traps a stuck agent is worse than no wall. The `Stop` hook allows the turn when it has nothing to enforce, and releases after six blocks with no change to any open ledger. Where ledgers exist and it cannot get an answer (a missing engine, a timeout, unreadable output), it fails closed instead, because those failures look exactly like a pass. Every path that still fails open has a consequence that must be designed around rather than hoped away:

**A broken wall and an approving wall look identical from the outside.** Silence means allow, and silence is also what a wall that never ran looks like.

So any mechanism whose job is to refuse something must be tested by making it actually refuse, in the real harness. Feeding a hook synthetic input proves the hook parses input. It does not prove the harness calls the hook. Those are different claims and only the second one matters.

Paid for on 2026-08-22: of six defects in the task ledger, the one that survived writing the code, reading the code and six passing tests was a session-id mismatch that made the `Stop` hook allow silently. Every one of those six tests fed the hook a matching id, so all six shared one assumption. The proof that finally counted was deliberately ending a turn with an unmet gate and being refused.

The corollary for anything unattended: a job that cannot tell you it finished has not been observed to succeed, it has merely not been observed to fail. The weekly review job now writes an inflight marker and clears it only on a recorded outcome, because a hard-terminated run and a genuinely quiet week produced the same observable output, which was nothing.

## 2. Never rely on a target rejecting bad input

Prove the refusal exists before depending on it. A script with no argument parsing, a CLI that ignores unknown flags, an endpoint that accepts anything: each turns an expected failure into a real execution.

Paid for twice on the same day, which is why it is a rule and not a note. A ledger check invoked the live review job with a flag that did not exist, expecting a clean failure. PowerShell scripts ignore unknown arguments and run the body, so the job ran. Then, having written this very rule down, the fix was assumed to work: a `param()` block does not refuse an unknown argument under `powershell -File` either, so the job ran a second time. The third attempt proved the refusal in isolation on a throwaway script first, and `[CmdletBinding()]` turned out to be the thing that actually refuses.

## 3. A verification step must be read-only

Anything that runs to check whether work is done will also run before the work exists, so a check with side effects fires those side effects against a system that is not ready for them. A check may read, parse, compile, query and run a test suite. It may not deploy, commit, push, send, schedule, or invoke anything that does.

When the only way to prove an outcome is to cause it, that is not a mechanical gate. It is a judgment whose evidence cites the causing run.

## 4. An empty result is not a clean result

Distinguish "looked and found nothing" from "could not look". They are different facts and only one of them is good news. The pairs seen so far in this harness:

· A digest that swept an unreadable path versus one that swept an empty path. The prompt is explicit about this because the failure already happened once.
· A job that read an empty git index and reported nothing to commit, while the digest it had just written sat unstaged on disk.
· A gate whose silent check recorded "(no output)" as its evidence, which tells a later reader nothing about what was verified.

Whenever a mechanism reports nothing, ask which of the two it means, and make it say which.

## 5. Two agents share one repository, and neither owns the index

A scheduled job and an interactive session can run at the same time. Anything that stages, commits, or writes a shared file must scope itself explicitly: commit by pathspec, never by whatever happens to be staged. The review job previously committed every staged path under a "Weekly review digest" message, which would have swept an interactive session's work into it.

## 6. Enforcement begins when the contract is frozen, not before

A draft is not a commitment. Both ledger hooks now allow everything until `declare` writes the lock, because a wall in front of an undeclared ledger punishes an agent for having started to write gates. The general form: a mechanism that enforces a rule must know when the rule started to apply, and default to permitting outside that window.

## Sources

- The incidents named in each rule, from the harness this template was extracted from (2026-08 to 2026-10). Keep your own versions as `episodic/` notes, recorded before promotion per contract section 6.2.
- `harness/LEDGER.md` · rules 3 and 6 are enforced there mechanically, not merely stated
