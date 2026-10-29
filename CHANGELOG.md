# Changelog

## 0.1.0, first public release

- Task ledger: request split into asks, each mapped to a frozen, hash-checked gate that must fail first; a stop hook and a lock guard enforce it (`harness/ledger.py`, `harness/LEDGER.md`).
- Contract template, engineering rules and autonomy ladder (`harness/CONTRACT.md`, `harness/ENGINEERING.md`, `harness/MATURITY.md`).
- Adapters for Claude Code, Codex CLI, Cursor, Antigravity CLI and Gemini CLI, plus an adapter template.
- Weekly review job for macOS and Windows, with self tests, and an ongoing history mining step.
- Vault template and linter (`vault-template/`, `harness/verify.py`).
- Eval template with blind runner and scorer (`eval-template/`).
- `BOOTSTRAP.md`, the prompt that builds a harness for its owner.
- Licensed under PolyForm Shield 1.0.0: free to use and change, not to compete with.
