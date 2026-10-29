# Claude Code: how the review job runs this engine headless (contract section 8).
# Dot sourced by harness\review-job\windows\run-review.ps1, which appends the prompt
# as the last argument. Sets $AgentCmd as an array so the wrapper's watchdog starts
# and kills the agent process itself. MESOSPHERE_CLAUDE overrides the binary; the
# selftest points it at a fake. --permission-mode acceptEdits lets the unattended
# run write its one digest. The Windows counterpart of review-job.sh beside it.
$onPath   = Get-Command claude -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
$agentBin = if ($env:MESOSPHERE_CLAUDE) { $env:MESOSPHERE_CLAUDE } elseif ($onPath) { $onPath.Source } else { Join-Path $HOME '.local\bin\claude.exe' }
$AgentCmd = @($agentBin, '-p', '--permission-mode', 'acceptEdits')
# The flag that grants read access to a folder outside the vault. Windows only: the
# Read tool was denied the memory root without it (2026-08-20). The wrapper puts
# these grants straight after the binary, because --add-dir takes several values
# and would swallow a prompt that followed it.
$AddDirFlag = '--add-dir'
