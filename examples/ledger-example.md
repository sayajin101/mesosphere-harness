# Ledger: invoice pdf download
Lock: sha256:4f1c9a0b7e2d3c5a
Audit: subagent: COVERED: A1 to A3 covered, nothing in the prompt is uncovered
Session: example
Opened: 2026-03-12 21:40

## Contract
- [x] G1 PROVE: GET /invoices/<id>/pdf returns a valid PDF
      CHECK: python -m pytest tests/test_invoice_pdf.py -q
      EXPECT: /^[0-9]+ passed/
      SHELL: bash
      BASELINE: fail at 21:40: 1 failed
      EVIDENCE: pass at 22:15: 3 passed in 0.41s
- [x] G2 HOLD: the existing test suite stays green
      CHECK: python -m pytest -q
      EXPECT: /^[0-9]+ passed/
      SHELL: bash
      BASELINE: pass at 21:40: 118 passed
      EVIDENCE: pass at 22:16: 121 passed
- [x] G3 JUDGE: the error for a missing invoice names the outcome in plain words
      BASELINE: n/a, manual gate
      EVIDENCE: Alex read it at 22:20: "We could not find that invoice, so there is nothing to download." approved

## Asks
A1 "let users download their invoices as a pdf" -> G1
A2 "dont break anything" -> G2
A3 "make the not found case friendly" -> G3

## Log
21:40 declared 3 gates, lock sha256:4f1c9a0b7e2d3c5a
22:16 run: 3/3 met
