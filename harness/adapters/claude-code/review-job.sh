# Claude Code: how the review job runs this engine headless (contract section 8).
# Sourced by harness/review-job/macos/run.sh, which appends the prompt as the last
# argument. Sets AGENT_CMD as a list so the wrapper's watchdog kills the agent
# process itself. MESOSPHERE_CLAUDE overrides the binary; the selftest points it at a
# fake. --permission-mode acceptEdits lets the unattended run write its one digest.
AGENT_BIN="${MESOSPHERE_CLAUDE:-$(command -v claude 2>/dev/null || true)}"
[[ -n "$AGENT_BIN" ]] || AGENT_BIN="$HOME/.local/bin/claude"
AGENT_CMD=("$AGENT_BIN" -p --permission-mode acceptEdits)
