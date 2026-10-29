# Antigravity CLI (agy): how the review job runs this engine headless (contract
# section 8). Dot sourced by harness\review-job\windows\run-review.ps1, from the
# vault, which then appends the prompt as the last argument. The same flags as
# review-job.sh beside it: --add-dir puts the vault in the workspace, which headless
# reads need as well as the owner's read_file allow rule (proven on macOS
# 2026-10-27); --mode accept-edits approves file edits; -p takes the prompt as its
# value, so it comes last. MESOSPHERE_AGY overrides the binary. Unproven on Windows,
# including the fallback path, which mirrors the Mac's ~/.local/bin/agy.
$onPath   = Get-Command agy -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
$agentBin = if ($env:MESOSPHERE_AGY) { $env:MESOSPHERE_AGY } elseif ($onPath) { $onPath.Source } else { Join-Path $HOME '.local\bin\agy.exe' }
$AgentCmd = @($agentBin, '--add-dir', (Get-Location).Path, '--mode', 'accept-edits', '-p')
