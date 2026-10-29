# Codex CLI: how the review job runs this engine headless (contract section 8).
# Sourced by harness/review-job/macos/run.sh, which appends the prompt as the last
# argument. workspace-write lets the run write inside the vault (its working directory) and nowhere else; --skip-git-repo-check is harmless in a clone and needed in a test vault.
# MESOSPHERE_CODEX overrides the binary. Flags read from `codex --help`; confirm them against
# the installed version before relying on this file.
AGENT_BIN="${MESOSPHERE_CODEX:-$(command -v codex 2>/dev/null || true)}"
[[ -n "$AGENT_BIN" ]] || AGENT_BIN="codex"
AGENT_CMD=("$AGENT_BIN" exec -s workspace-write --skip-git-repo-check)
