# Operating manual

How the owner lives with the vault. One page; everything else is detail in the linked docs.

## Cadences

· **Daily: nothing.** Sessions wear the persona automatically (the SessionStart hook, or the loader block in each machine's agent config). Agents capture lessons into `episodic/` and flag contradictions as they happen.
· **Weekly: five minutes.** A scheduled job writes `episodic/review-digest-<date>.md` with promotion proposals. Read it, then tell a session e.g. "apply digest items 1 and 2, reject 3". Only the owner promotes.
· **Whenever: the signing backlog.** Pages at `status: mined-unverified` were mined by an agent and are not yet confirmed. Read one, and if it is true, flip its status to `signed` (only the owner may). Each signature hardens the persona.
· **Every 3 to 6 months, or before any model swap: the exam.** Run the eval from the separate eval repo's RUNBOOK. Misses become interview questions; answered lessons enter the vault and their scenarios get burned; refill per the RUNBOOK triggers.

## Lifecycle events

· **New machine:** clone the vault, wire the adapter (`harness/adapters/<vendor>/README.md`), optionally add the review job on a free weekday.
· **New AI vendor or model:** it earns adoption by beating the incumbent on the eval under identical protocol (contract section 4). Never adopted on hype.
· **New company:** repos the owner owns keep memory in-repo; an employer gets a LOCAL-ONLY sidecar folder on the hardware they provided (contract section 5).
· **Leaving a company:** final harvest of its folder (distill remaining person-level lessons into the vault), then it is archived and never referenced again (contract section 6).
· **Considering agent autonomy:** contract section 7 and `harness/MATURITY.md`; promotion is per contradiction class, in writing, eval-evidenced, revocable.

## The invariants (never change without deliberate intent)

· Only the owner signs tier 1 (SOUL, IDENTITY), and after the first signing only the owner edits it. Only the owner sets `status: signed` anywhere.
· No secrets in the vault, ever.
· The vault never references a moon's files, and never references or absorbs the eval repo.
· Contradictions are surfaced and kept, never silently resolved.
· Substantial work runs against a task ledger, and the ledger, not the agent, decides when it is done (contract section 9, protocol in `harness/LEDGER.md`, engineering rules in `harness/ENGINEERING.md`).
