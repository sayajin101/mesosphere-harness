---
type: decision
status: interviewed
scope: production incidents
confidence: medium
updated: 2026-03-04
sources:
  - a live session on 2026-03-02, quoted below
---

# 2026-03-02 · Revert first, then re-fix

**Situation.** A query Alex shipped was timing out in production at peak. A fix was ready and reviewed, but tested only on staging data a fraction of production's size.

**Options.** Ship the fix now. Add database capacity and wait. Revert the original change, then re-test the fix at production scale.

**Chosen.** Revert first, re-fix second. Alex: "a fix tested on toy data is a guess."

**Rejected, and why.** Shipping the fix: a second untested change on top of a broken one. Adding capacity: pays to hide the problem.

**Outcome.** The re-tested fix shipped two days later and held. Not a standing "always revert" rule: Alex scoped it to changes that were never validated at production scale.

Related: [[red-lines]] · [[verification-and-source-of-truth]]
