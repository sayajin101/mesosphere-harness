# Harness maturity: the autonomy rungs

Contract section 7.3 says the harness may one day be promoted to resolve contradictions on its own, that promotion is earned per class rather than assumed, and that the holdout eval is the meter. It does not say what the rungs of that ladder are. This page is the ladder. It is harness material, not persona material: it describes what the atmosphere is trusted to do, never who the owner is.

Read this alongside `CONTRACT.md`. Where the two disagree, the contract wins.

## What this ladder measures, and what it does not

The axis here is **judgment**: how much the harness is trusted to decide without asking. That is the axis the vault exists to move, because the whole point of the vault is that an agent decides the way the owner decides.

Two things are deliberately NOT on this ladder:

· **Parallelism.** How many agents run at once is a throughput question, not a trust question. Running ten agents that all draft and stop for approval is rung 1 behaviour at ten times the speed. Scale it whenever it is useful; it earns no rungs and needs no permission.
· **Capability of the model.** A better model does not promote the harness. Contract section 4 already says benchmarks and hype do not qualify a model, the eval does. The same applies here: a smarter weather system does not mean the atmosphere gets more authority.

## The invariants, true at every rung including the top

These never move, at any level of trust, and no rung below is permitted to weaken them:

· Red lines outrank everything (the owner's red lines page). Grey areas stop and go to the owner.
· Only the owner edits `SOUL.md` and `IDENTITY.md`, and only the owner sets `status: signed` anywhere.
· `raw/` is immutable evidence. Agents never edit it.
· No secrets, credentials, tokens or phone numbers are ever written into the vault.
· Nothing is sent to a real human without the owner's approval (contract 2.4).
· Vault content never leaves the owner's machines except through the vault's own git remote (contract 4b).
· Contradictions are surfaced, never silently resolved or silently deleted.
· The git rules the owner recorded in contract 3.6.

## Rung 0 · Gated

**What the harness may do:** propose. The owner executes. Nothing is written to the vault without the owner watching it happen.

**Bottleneck:** the owner, on every keystroke. Everything queues behind their attention.

**Guardrail:** there is nothing to guard. The owner is the guardrail.

**To advance:** the vault has to exist and be loadable, and the write rules have to be written down rather than remembered.

**Status check:** the vault, the contract and `verify.py` exist.

## Rung 1 · Supervised

**What the harness may do:** write freely in `episodic/`. Draft tier 2 pages and enrichments with provenance, always at `draft` or `mined-unverified`. Sweep memory and produce the weekly digest unattended. Run the integrity gate. Everything that changes what the vault ASSERTS about the owner stops for their yes.

**Bottleneck:** the owner's review queue, which is the bottleneck showing itself exactly where the ladder predicts. A queue that grows faster than one sitting can clear is the signal to fix the loop (track what happened to each proposed lesson so nothing is re-proposed forever), not to review faster.

**Guardrail:** `verify.py` enforces the write rules mechanically rather than trusting an agent to remember them, including a `--diff` audit that catches tier 1 edits, `raw/` edits and status changes before they land.

**To advance to rung 2:** the eval has to score the harness on contradiction-resolution scenarios, and the harness's proposed resolutions have to match the owner's actual calls consistently, on a class of contradictions narrow enough to name in writing.

**Typical blocker at this rung.** The eval exists and has a scored baseline, but its scenarios are usually categorised by subject matter, and none of them is a contradiction-resolution scenario. Contract 7.3 requires exactly that category before any promotion. So rung 2 is blocked on one concrete piece of work: scenarios that present two pieces of guidance in genuine conflict, with the owner's real resolution as the ground truth. Contract 6.2 (preserve the fork before promoting the rule) is what produces them. Until enough exist, rung 1 is not a waiting room, it is the ceiling.

## Rung 2 · Bounded autonomy

**What the harness may do:** everything in rung 1, plus resolve contradictions inside ONE named class without asking. The class is written into the contract by the owner, is narrow on purpose, and is revocable at any time. The obvious first candidate is the one contract 7.3 already suggests: low stakes, single project scope, no money, no other humans involved.

Every auto-resolution is logged to `episodic/` with both sides and the reasoning, so the record of what it decided is complete even when nobody was watching.

**Bottleneck:** stops being the owner's attention and becomes context quality. An agent resolving on its own is only as good as the pages it loaded, so a stale or mislabelled page now produces a wrong decision instead of a wrong draft.

**Guardrail:** the log is mandatory and reviewed weekly. A single auto-resolution the owner disagrees with revokes the class immediately, no argument and no gradual wind-down.

**To advance to rung 3:** several classes running clean over enough time that the log stops producing surprises, plus the staleness problem solved rather than tolerated, since context quality is now load bearing.

## Rung 3 · Broad autonomy

**What the harness may do:** resolve most contradictions, and propose status changes on tier 2 pages rather than only content. The owner moves from reviewing each item to reviewing a digest of decisions already taken. Tier 1 still never moves without the owner, and they still set every `signed`.

**Bottleneck:** knowing when the harness is wrong in a way it cannot see. Volume is no longer the problem; blind spots are.

**Guardrail:** exception reporting has to actually work, which means the harness has to be reliable at saying "I am not sure" rather than reliable at sounding sure. That is a property the eval must test directly, because a confident wrong answer at this rung costs more than ten stops at rung 1.

**To advance to rung 4:** a long clean run at rung 3, and a deliberate decision by the owner about the rule below.

## Rung 4 · Steering by intent

**What the harness may do:** the owner states outcomes rather than tasks, and the harness plans, executes and reports by exception across the planet and whatever moons are in orbit.

**The wall in front of this rung, stated plainly:** contract 2.4 says nothing goes to a real human without the owner's approval, "No exceptions until the owner changes this contract themself." Rung 4 as usually described assumes the agent talks to people. So rung 4 is not reachable by earning trust; it is reachable only if the owner decides to change that rule. This page does not assume they ever will, and the ladder is fully useful without it. Rung 3 is the realistic ceiling for a harness that never speaks for the owner.

**Bottleneck:** trust in the harness stops being the limit. The owner's own willingness to not be in the loop becomes the limit, and that is a preference, not a capability.

## How a promotion actually happens

1. The owner names the class of decisions in writing, in `CONTRACT.md`.
2. The eval runs on scenarios from that class, per the eval runbook.
3. The harness's proposed resolutions are compared against the owner's real past calls. Matching is the bar; sounding reasonable is not.
4. The owner grants the class explicitly. Silence is not a grant, and neither is a good run.
5. Every decision taken under the grant is logged to `episodic/`.
6. Any disagreement the owner raises revokes the class on the spot.

Nothing here is automatic. A rung is granted by the owner, in writing, and can be taken back the same way.

## Sources

· `CONTRACT.md` section 7.3 defines earned, per-class, revocable promotion and makes the eval the meter. This page adds the rungs it left unspecified.
· External prior art: "Steps of AI Adoption" by Boris Cherny (Anthropic), 2026-07-16, a five stage enterprise adoption framework whose per-stage shape (name the bottleneck, name the guardrail, name what must be true to advance) is borrowed here. Its content is not: that framework measures organisational throughput for teams, while this one measures how much judgment one person delegates.
