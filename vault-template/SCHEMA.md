# Schema

Every page in tiers 1 and 2 carries YAML frontmatter. Agents must follow this schema when creating or editing pages.

## Frontmatter fields

```yaml
---
type: heuristic | taste | voice | value | decision | person | skill | episode
status: mined-unverified | draft | interviewed | signed
scope: where this applies (e.g. "code review", "side projects", "everywhere")
confidence: low | medium | high
updated: YYYY-MM-DD
signed: YYYY-MM-DD by <owner name> (how they approved it)   # only on signed pages, only written by the owner
sources:
  - "[[raw/interviews/<file>.md]]"   # a vault file: quoted wikilink, full path from vault root
  - a described real event      # anything not a file: plain text
---
```

A `sources:` entry that points at a file in this vault is written as a quoted wikilink carrying its full path, so it resolves in Obsidian (backlinks from the evidence to the pages it produced) and still reads as a plain path to any agent. The quotes are required: bare `[[x]]` parses as a nested YAML list. Non-file evidence (a live conversation, a document the owner handed over) stays plain text. `raw/mined/*.json` files are not notes, so they stay plain paths too.

`status` meanings:

· `mined-unverified`: extracted from logs/history by an agent; the owner has not confirmed it.
· `draft`: written or restructured by an agent, awaiting review.
· `interviewed`: distilled from a self-interview answer; the owner saw the distillate.
· `signed`: the owner has read and approved this page as-is. Only the owner sets this, and the `signed:` field records when and how.

An agent may move a page to `interviewed` when the owner has seen and confirmed the distillate in a live session, recording where in `sources`; every move to `signed` is the owner's alone.

## Page types

· **heuristic** (`heuristics/`): a judgment rule with its reason and exceptions. Format: "Prefer X because Y, unless Z." Never a bare "always/never" without the why.
· **taste** (`taste/`): aesthetic and product preferences (design, UX, tools, media). Include concrete examples of things liked and disliked.
· **voice** (`voice/`): how the owner communicates: phrasing, tone, formatting habits, pet peeves in text.
· **value** (kept inside `SOUL.md` once signed): what matters, non-negotiables, motivations.
· **decision** (`decisions/`): a dated case file of a real decision. Must include: the situation, the options considered, what was chosen, what was rejected and why, and the outcome if known. Filename: `YYYY-MM-DD-short-slug.md`.
· **person** (`people/`): context on a person who matters to how the owner works or lives.
· **skill** (`skills/`): capability inventory and career history: what the owner can do, at what depth, and what they delegate.
· **episode** (`episodic/`): session notes, journal entries, observations awaiting promotion. Retired by moving the file to `episodic/archive/` once every item in it is applied, dropped, or recorded elsewhere. Never retire a note that still carries an open question, never delete one, and never invent a `status` value for the purpose: the four `status` values describe how well a claim is verified, not where a note is in its life.

## Writing style for pages

· Medium-grained: one topic per file, not one fact per file, not a monolith.
· Judgment over rules: capture the why so an agent can extrapolate to novel situations.
· Scope everything. "Prefers blunt feedback" is wrong if it only applies to code review.
· Link related pages with `[[wikilinks]]`; aim for at least two links per page.
· No em-dashes or double-hyphens anywhere in this vault (house rule, enforced by `harness/verify.py`).

## Provenance outside tiers 1 and 2

Documents that are not vault pages (`harness/CONTRACT.md`, `README.md`, and anything else without frontmatter) still carry distilled interview material. They record it in a `## Sources` section at the foot of the page, wikilinks with a one-line note on what each transcript shaped. No frontmatter, no `status:`, no `type:`: those fields imply a page an agent may draft against, and the contract is not one.

## Index discipline

`INDEX.md` holds one line per tier-2 page: `[[wikilink]] · one-line hook`. Update it whenever a page is added, renamed, or deleted. It is a map, never content.
