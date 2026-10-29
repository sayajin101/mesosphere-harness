---
type: episode
status: draft
scope: harness, every lesson the review loop has ever suggested and what happened to it
confidence: high
updated: YYYY-MM-DD
sources:
  - template, created at bootstrap
---

# Lesson outcomes

One row per lesson ever suggested for a tier 2 page, and what happened to it. The weekly review job reads this first and never re-suggests a lesson that is `added` or `rejected`; a `parked` lesson comes back only with a new case; a `waiting` one gets one line saying it is still waiting.

The review job never edits this file. The session that applies the owner's answers adds or updates rows in the same commit as the page edits. `harness/verify.py` checks it both ways: an `added` row fails the gate unless its page carries a matching "Approved by the owner <date>." marker, and a marker with no row is a warning. An empty tracker fails too, because "no rows read" and "nothing to check" look the same, so keep the example row until a real one exists.

Outcomes: `added` (on the page named), `rejected` (by the owner), `parked` (undecided, returns only if it recurs), `waiting` (in front of the owner; the page is the proposed target).

| Id | Lesson | Raised in | Outcome | Page | Decided | Record |
| --- | --- | --- | --- | --- | --- | --- |
| L-example | example row, delete once a real lesson exists | bootstrap | waiting | | | template |
