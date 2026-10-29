# Gemini CLI: how the review job runs this engine headless (contract section 8).
# Sourced by harness/review-job/macos/run.sh, which appends the prompt as the last
# argument. auto_edit approves file edits but still asks for other tools, the equivalent of Claude Code's acceptEdits; -p is last because it takes the prompt as its value.
# MESOSPHERE_GEMINI overrides the binary. Flags read from `gemini --help`; confirm them against
# the installed version before relying on this file.
AGENT_BIN="${MESOSPHERE_GEMINI:-$(command -v gemini 2>/dev/null || true)}"
[[ -n "$AGENT_BIN" ]] || AGENT_BIN="gemini"
AGENT_CMD=("$AGENT_BIN" --approval-mode auto_edit -p)
