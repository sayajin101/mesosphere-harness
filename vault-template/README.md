# Persona vault

A plain-markdown model of how one person thinks, works, decides, and what they value, built to be loaded by AI agents so they can act with that person's judgment.

This is a person-level vault. It is deliberately not a company or project knowledge base. Project facts live in their repos; this vault holds what stays true about the owner across any job, project or tool.

## The Earth model

Cut the planet in half:

· **Inner core** (immutable): what drives decisions when everything else is stripped away. Values, red lines, temperament, the why. This is `SOUL.md`.
· **Outer core** (molten, still core): the people and passions as they exist today. This is `IDENTITY.md` plus `people/`.
· **Lower mantle** (durable craft): judgment, quality bar, scar tissue, voice. Survives any job change. This is `heuristics/`, `taste/`, `voice/`.
· **Upper mantle** (current vehicles): the day job, current projects, current colleagues. High stakes today, replaceable in principle. This is `people/` (colleagues) and `decisions/`.
· **Crust** (erodes constantly): tickets, tools of the month, session notes. This is `episodic/`; the work repos themselves stay outside the vault entirely.
· **Atmosphere** (wraps the planet, durable): the AI harness in `harness/`. Three parts, and only two are replaceable: the protocol in `harness/CONTRACT.md` persists and carries the owner's judgment across vendors; the thin per-vendor adapters in `harness/adapters/` are rewritten per vendor and are cheap; the model of the day is weather, fully disposable. How much the harness is trusted to decide on its own is a separate axis, in `harness/MATURITY.md`.
· **Moons** (in orbit, come and go): company and project knowledge, each in its own repo or local sidecar folder outside this vault (contract section 5). When a company leaves the owner's life, its moon leaves orbit and the planet is untouched.

## How it is organised

| Tier | Where | Written by | Loaded |
|------|-------|-----------|--------|
| Identity | `SOUL.md`, `IDENTITY.md` | Drafted once at setup, then the owner only (human-signed) | Always, every session |
| Judgment | `heuristics/`, `taste/`, `voice/`, `people/`, `decisions/`, `skills/` | Drafted by agents, signed by the owner | Just-in-time via `INDEX.md` |
| Episodic | `episodic/` | Agents, freely | On demand |

`raw/` holds immutable evidence (mined distillates, interview transcripts). Never edit files in `raw/`.

A note in `episodic/` is retired by moving it to `episodic/archive/`, not by deleting it and not by changing its `status`, once every item in it is applied, dropped, or recorded elsewhere.

## Rules for agents working in this vault

1. You may create and edit files in `episodic/` freely.
2. You may draft new pages in tier 2 folders, but they must carry `status: mined-unverified` or `status: draft` until the owner reviews them. Never set `status: signed` yourself.
3. Never edit `SOUL.md` or `IDENTITY.md` once signed. Propose changes as a note in `episodic/` instead.
4. Every claim about the owner needs provenance: quote or point to the evidence in `raw/` or a real event.
5. Keep contradictions. Record them with their contexts rather than resolving them. Tie-break rule: the most context-specific guidance wins; if genuinely ambiguous, ask the owner instead of guessing.
6. See `SCHEMA.md` for page types and frontmatter before writing anything.
7. Substantial work (more than one deliverable, or long enough that its start leaves your context) runs against a task ledger per `harness/LEDGER.md` and contract section 9. Never report done while the ledger says otherwise.
8. Run `python3 harness/verify.py` before committing. It enforces the rules above mechanically.

## Sync

A PRIVATE git remote only. Git rules: see contract section 3.6.

## Evaluation

A private holdout set of real past decisions lives OUTSIDE this vault, in its own repo, so agents wearing the vault can never see the answers. It tests whether an agent loaded with this vault decides like the owner. Never add holdout material here, and never reference the eval repo from here.
