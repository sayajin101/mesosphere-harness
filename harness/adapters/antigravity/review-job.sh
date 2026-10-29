# Antigravity CLI (agy): how the review job runs this engine headless (contract
# section 8). Sourced by harness/review-job/macos/run.sh, which appends the prompt as
# the last argument. --mode accept-edits approves file edits, the equivalent of
# Claude Code's acceptEdits; -p prints headless and takes the prompt as its value, so
# it comes last. MESOSPHERE_AGY overrides the binary. Flags read from `agy --help`,
# version 1.4.8; confirm them against the installed version before relying on this.
AGENT_BIN="${MESOSPHERE_AGY:-$(command -v agy 2>/dev/null || true)}"
[[ -n "$AGENT_BIN" ]] || AGENT_BIN="$HOME/.local/bin/agy"
# --add-dir puts the vault in the workspace: headless reads need it as well as the
# owner's read_file allow rule (proven 2026-10-27). run.sh sources this from the vault.
AGENT_CMD=("$AGENT_BIN" --add-dir "$PWD" --mode accept-edits -p)
