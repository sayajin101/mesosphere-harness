# Gemini CLI: how the review job runs this engine headless (contract section 8).
# Dot sourced by harness\review-job\windows\run-review.ps1, which appends the prompt
# as the last argument. The same flags as review-job.sh beside it: auto_edit
# approves file edits but still asks for other tools, the equivalent of Claude
# Code's acceptEdits; -p is last because it takes the prompt as its value.
# MESOSPHERE_GEMINI overrides the binary. Unproven on Windows: an npm install gives a
# gemini.cmd shim, which the wrapper refuses because a batch file cuts a multi line
# argument at its first newline, so point MESOSPHERE_GEMINI at a real executable.
$onPath   = Get-Command gemini -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
$agentBin = if ($env:MESOSPHERE_GEMINI) { $env:MESOSPHERE_GEMINI } elseif ($onPath) { $onPath.Source } else { 'gemini' }
$AgentCmd = @($agentBin, '--approval-mode', 'auto_edit', '-p')
