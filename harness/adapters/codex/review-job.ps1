# Codex CLI: how the review job runs this engine headless (contract section 8).
# Dot sourced by harness\review-job\windows\run-review.ps1, which appends the prompt
# as the last argument. The same flags as review-job.sh beside it: workspace-write
# lets the run write inside the vault (its working directory) and nowhere else;
# --skip-git-repo-check is harmless in a clone and needed in a test vault.
# MESOSPHERE_CODEX overrides the binary. Unproven on Windows: an npm install gives a
# codex.cmd shim, which the wrapper refuses because a batch file cuts a multi line
# argument at its first newline, so point MESOSPHERE_CODEX at a real executable.
$onPath   = Get-Command codex -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
$agentBin = if ($env:MESOSPHERE_CODEX) { $env:MESOSPHERE_CODEX } elseif ($onPath) { $onPath.Source } else { 'codex' }
$AgentCmd = @($agentBin, 'exec', '-s', 'workspace-write', '--skip-git-repo-check')
