# Weekly vault review digest (Windows). Sweeps episodic notes and fresh
# auto-memories, drafts promotion proposals for the owner to yes/no. Never edits
# tier 1 or 2. Scheduled task mesosphere-review, for example Thursdays 19:00; stagger any second
# machine to another day so the two digests never collide.
#
# Runs from inside the clone, like ../macos/run.sh, so there is no copy under
# ~/schedules to drift. The differences from the Mac wrapper, and why each one
# exists, are listed in README.md beside this file.

# Argument refusal comes FIRST, before anything with a side effect. No param block
# on purpose: under `powershell -File`, a bare param() ignores unknown arguments
# and runs the body, and [CmdletBinding()] refuses them but still exits 0. Reading
# $args refuses anything with exit 64, the Mac's code, and was proven in isolation
# on 2026-09-28 before being trusted here (harness/ENGINEERING.md rule 2).
if ($args.Count -gt 0) {
    [Console]::Error.WriteLine("REFUSED: this job takes no arguments, got: $args")
    [Console]::Error.WriteLine('Nothing ran. To exercise the wrapper safely, use selftest.ps1, which touches only a temp directory.')
    exit 64
}

$ErrorActionPreference = 'Continue'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here 'heartbeat.ps1')

# Every path is derived or overridable, none hardcoded to a machine, which is what
# lets this file be committed. The overrides also let selftest.ps1 drive this exact
# file end to end against a throwaway vault and a fake claude.
function EnvOr($name, $default) { $v = [Environment]::GetEnvironmentVariable($name); if ($v) { $v } else { $default } }
$vault      = EnvOr 'MESOSPHERE_VAULT' (Get-VaultFromScript $here)
$promptFile = EnvOr 'MESOSPHERE_PROMPT' (Join-Path $vault 'harness\review-job\prompt.md')
# Below the scheduled task's ExecutionTimeLimit PT2H on purpose: if the two bounds
# were equal, Task Scheduler's kill would win and no outcome would be recorded.
$maxSeconds = [int](EnvOr 'MESOSPHERE_MAX_SECONDS' 6900)
$state      = EnvOr 'MESOSPHERE_STATE' (Join-Path $HOME 'schedules\mesosphere-review')
$memoryRoot = EnvOr 'MESOSPHERE_MEMORY_ROOT' (Join-Path $HOME '.claude\projects')
# Which engine runs the review is the adapter's business, not this wrapper's
# (contract section 8), as in ../macos/run.sh. Read from this clone, beside the
# wrapper, so it cannot drift from it; MESOSPHERE_ADAPTERS_DIR lets the mutation test's
# copies, which sit outside any clone, find the real adapter files.
$adapter    = EnvOr 'MESOSPHERE_ADAPTER' 'claude-code'
$adapters   = EnvOr 'MESOSPHERE_ADAPTERS_DIR' (Join-Path (Split-Path -Parent (Split-Path -Parent $here)) 'adapters')
$agentFile  = Join-Path $adapters "$adapter\review-job.ps1"
$today      = Get-Date -Format 'yyyy-MM-dd'

# State lives beside the schedule, never in the clone, which the job inspects for
# stray changes and could otherwise sweep into a commit.
$logDir = Join-Path $state 'logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
$log = Join-Path $logDir "run-$today.log"

# UTF-8 explicitly. Tee-Object and >> in Windows PowerShell 5.1 write UTF-16, which
# is why an earlier log could not be searched with grep. Write-LogLine retries a
# locked log, then falls back to a file beside it, then to memory, and Complete-Run
# says so: a bare Add-Content dropped every line while a tail -F held the file.
function Log($msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg"
    [void](Write-LogLine -Path $log -Line $line)
    Write-Output $line
}
function LogLines($lines) { foreach ($l in @($lines)) { if ("$l".Trim()) { Log "  $l" } } }
function Invoke-Git { $out = & git.exe @args 2>&1 | ForEach-Object { "$_" }; LogLines $out; return $out }

# A marker still on disk is either a dead predecessor or a live run. Only the
# first is ours to clear.
$slot = Test-RunSlot -LogDir $logDir -MaxAgeSeconds ($maxSeconds + 900)
if ($slot.Code -eq 2) {
    Log "REFUSED: a live run already holds this slot: $($slot.Names). Nothing was run and no marker was touched."
    exit 75
}
$staleNote = ''
if ($slot.Code -eq 1) {
    Log "WARNING: previous run(s) never finished: $($slot.Names)"
    # Handed to the digest as well, so it reaches the owner instead of only a log.
    $staleNote = "`n`nHOUSEKEEPING INPUT: a previous run of this job did not finish ($($slot.Names)). " +
                 "Report it under Housekeeping as a job that died mid run, so it is not " +
                 "mistaken for a quiet week."
}

[void](Start-RunMarker -LogDir $logDir -Date $today)
$ref = Join-Path $logDir 'run-start.ref'
function Fail($detail) {
    Log "FAIL: $detail"
    [void](Complete-Run -LogDir $logDir -Date $today -Outcome 'failed' -Detail $detail)
    exit 1
}

Log "resolved vault: $vault"
if (-not (Test-Path (Join-Path $vault '.git'))) { Fail "vault clone not found at $vault" }
Set-Location $vault

# The run reads untrusted mined text with edit rights inside this clone, so it could
# plant code for next week: an adapter file, heartbeat.ps1, the prompt, or a hook in
# .claude\settings.local.json. Found by a readiness review on 2026-10-28. So the job
# starts only from a clean harness/ and .claude/, and Restore-Harness puts both back
# after the run, whatever it did. Content aware (git diff, not git status), so phantom
# line ending modifications do not refuse a clean clone.
function Get-HarnessChanges($base) {
    @(& git.exe diff --name-only $base -- harness .claude) +
    @(& git.exe ls-files --others --exclude-standard -- harness .claude) | Where-Object { $_ }
}
if (Get-HarnessChanges 'HEAD') {
    Fail 'REFUSED: uncommitted changes under harness/ or .claude/. The unattended run starts only from a committed, reviewed harness; commit or discard them first.'
}

Log 'git pull --no-rebase'
[void](Invoke-Git pull --no-rebase)
if ($LASTEXITCODE -ne 0) { Fail 'git pull failed. Not running, because both the vault and the prompt would be stale.' }

# The prompt is read from the clone after the pull, never from a local copy: a
# second copy beside the old script is what drifted for a week in August.
if (-not (Test-Path $promptFile)) { Fail "prompt file missing at $promptFile. There is deliberately no fallback prompt." }

# Read access for the memory sweep. A memory store may be a junction into a repo
# the owner owns (contract section 5), and its target sits outside the memory root,
# so each link target is granted as well; the sweep's find -L follows the link.
$dirs = @($memoryRoot)
Get-ChildItem -Path $memoryRoot -Directory -ErrorAction SilentlyContinue | ForEach-Object {
    $m = Get-Item (Join-Path $_.FullName 'memory') -Force -ErrorAction SilentlyContinue
    if ($m -and $m.LinkType -and $m.Target) { $dirs += @($m.Target) }
}

# Mining new chats, on the owner's cadence, as ../macos/run.sh does. A plain script,
# run HERE and not by the agent, because an unattended run cannot approve a command
# that writes files. It extracts only the owner's new messages since its last run,
# scrubbed, into a folder outside the vault, and prints one line that the agent is
# handed below. No mining.json at the vault root means no mining, and a failure never
# stops the review: an interpreter that will not start is caught and handed on too.
$mining = 'mining: not configured'
$miningConfig = Join-Path $vault 'mining.json'
if (Test-Path $miningConfig -PathType Leaf) {
    # The extract lands in the workdir, outside the vault, so the agent needs its own
    # --add-dir to read it. Created first, so the grant never points at nothing, and
    # ~ expanded to the profile as history.py's expanduser does.
    try {
        $workdir = (Get-Content $miningConfig -Raw -Encoding UTF8 | ConvertFrom-Json).workdir
        if ($workdir) {
            if ($workdir -match '^~[\\/]?') { $workdir = Join-Path $env:USERPROFILE ($workdir -replace '^~[\\/]?', '') }
            if (-not (Test-Path $workdir)) { New-Item -ItemType Directory -Path $workdir -Force | Out-Null }
            $dirs += @((Resolve-Path $workdir).Path)
        }
    } catch { Log "WARNING: mining workdir not granted: $($_.Exception.Message)" }
    $py = EnvOr 'MESOSPHERE_PYTHON' 'python'
    # UTF-8 both ways, so a non-ASCII profile path in the mining line survives the pipe.
    $env:PYTHONIOENCODING = 'utf-8'
    try { [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false) } catch { }
    try {
        $last = @(& $py (Join-Path $vault 'harness\history.py') --config $miningConfig 2>&1 |
                  ForEach-Object { "$_".Trim() } | Where-Object { $_ }) | Select-Object -Last 1
    } catch { $last = $_.Exception.Message }
    $mining = if ("$last" -like 'mining:*') { "$last" } elseif ($last) { "mining: FAILED: $last" } else { 'mining: FAILED: no output' }
}
Log $mining
# The adapter's review-job.ps1 sets $AgentCmd, the engine's headless command without
# the prompt, as an array, so the watchdog below starts and kills the agent process
# itself rather than a shell around it. It may set $AddDirFlag, the engine's flag for
# reading a folder outside the vault; an adapter without one gets no grants, said out
# loud. Dot sourced after Set-Location, because an adapter may name the vault by it.
if (-not (Test-Path $agentFile -PathType Leaf)) { Fail "no review-job agent file for adapter '$adapter' at $agentFile" }
$AgentCmd = @(); $AddDirFlag = ''
# An adapter that refuses (Cursor's does) throws. Caught, so the refusal is recorded as
# this run's outcome instead of leaving a marker that reads as a run that died.
try { . $agentFile } catch { Fail "$($_.Exception.Message)" }
if ($AgentCmd.Count -lt 1 -or -not $AgentCmd[0]) { Fail "the adapter file $agentFile did not set `$AgentCmd" }
$agentExe = Get-Command $AgentCmd[0] -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $agentExe) { Fail "the $adapter engine was not found at $($AgentCmd[0])" }
# A batch file shim (an npm install's codex.cmd, say) is run by cmd.exe, which cuts a
# multi line argument at its first newline: the engine would get the prompt's first
# line and nothing said. Refused, so the adapter is pointed at a real executable.
if ($agentExe.Source -match '\.(cmd|bat)$') { Fail "the $adapter engine resolves to a batch file, $($agentExe.Source), which would cut the prompt at its first newline. Point the adapter's override at a real executable." }

$grants = @()
if ($AddDirFlag) { foreach ($d in $dirs) { $grants += @($AddDirFlag, $d) } }
else { Log "WARNING: adapter $adapter declares no flag for reading outside the vault, so these were not granted: $($dirs -join ', ')" }

# The prompt is the last argument, as on the Mac: an engine whose -p takes the prompt
# as its value cannot read it from stdin. The grants go straight after the binary,
# ahead of the adapter's flags, because a flag taking several values (claude's
# --add-dir) would swallow a prompt that followed it. The mining line goes last,
# after the date line, where the prompt says to find it.
$promptText = (Get-Content $promptFile -Raw -Encoding UTF8) +
              "`n`nToday's date for the digest filename and frontmatter: $today" + $staleNote +
              "`n`nMonthly mining for this run: $mining"
$agentArgs = @($grants) + @($AgentCmd | Select-Object -Skip 1) + @($promptText)
$argLine = ($agentArgs | ForEach-Object { ConvertTo-NativeArg $_ }) -join ' '
# CreateProcess takes 32767 characters in all; past that the engine would never start.
if (($agentExe.Source.Length + $argLine.Length) -gt 32000) { Fail "the $adapter command line is $($argLine.Length) characters, past what Windows can start. Shorten the prompt." }
# A record of exactly what was handed over, and an empty stdin, so an engine that
# reads stdin when it is not a console finds nothing instead of waiting.
[System.IO.File]::WriteAllText((Join-Path $state 'prompt.txt'), $promptText, (New-Object System.Text.UTF8Encoding $false))
$stdin  = Join-Path $state 'agent.in'
$stdout = Join-Path $state 'agent.out'
$stderr = Join-Path $state 'agent.err'
[System.IO.File]::WriteAllText($stdin, '')

# The state this run must leave harness/ and .claude/ in. .claude/ holds ignored files
# git cannot see (settings.local.json, where hooks live), so it is copied aside whole.
$startHead = (& git.exe rev-parse HEAD).Trim()
$snap = Join-Path $state 'dotclaude-before'
if (Test-Path $snap) { Remove-Item $snap -Recurse -Force }
if (Test-Path '.claude') { Copy-Item '.claude' $snap -Recurse -Force }

function Get-TreeHash($dir) {
    if (-not (Test-Path $dir)) { return '' }
    $root = (Resolve-Path $dir).Path
    (Get-ChildItem $dir -Recurse -File -Force | Sort-Object FullName | ForEach-Object {
        $_.FullName.Substring($root.Length) + ':' + (Get-FileHash $_.FullName -Algorithm SHA256).Hash
    }) -join '|'
}

function Restore-Harness {
    $touched = @(Get-HarnessChanges $startHead)
    [void](Invoke-Git reset -q -- harness .claude)
    foreach ($f in @(& git.exe diff --name-only $startHead -- harness .claude)) {
        & git.exe checkout -q $startHead -- $f 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { Remove-Item -LiteralPath $f -Force -ErrorAction SilentlyContinue }
    }
    [void](Invoke-Git clean -fdq -- harness .claude)
    if (Test-Path $snap) {
        if ((Get-TreeHash $snap) -ne (Get-TreeHash '.claude')) {
            $touched += 'ignored files under .claude/'
            if (Test-Path '.claude') { Remove-Item '.claude' -Recurse -Force }
            Copy-Item $snap '.claude' -Recurse -Force
        }
        Remove-Item $snap -Recurse -Force
    } elseif (Test-Path '.claude') {
        $touched += '.claude/ created by the run'
        Remove-Item '.claude' -Recurse -Force
    }
    if ($touched) {
        Log 'WARNING: the run changed files under harness/ or .claude/. They were restored:'
        LogLines $touched
    }
}

# Marks this agent as the review job, which contract 9.6 exempts from the ledger.
# The Stop hook enforces every open ledger in the clone, so without this another
# session's ledgers block this unattended run until the hook's release valve fires.
$env:MESOSPHERE_REVIEW_JOB = '1'
Log "running $adapter review (headless), bound ${maxSeconds}s, granted $($grants.Count / 2) dir(s): memory and mining"
$rc = Invoke-Watchdog -FilePath $agentExe.Source -Arguments $argLine `
        -StdinFile $stdin -StdoutFile $stdout -StderrFile $stderr -Seconds $maxSeconds
LogLines (Get-Content $stdout -Encoding UTF8 -ErrorAction SilentlyContinue)
LogLines (Get-Content $stderr -Encoding UTF8 -ErrorAction SilentlyContinue)
Restore-Harness
# A change the run COMMITTED is beyond a restore, and the push below would publish it.
if (@(& git.exe diff --name-only $startHead HEAD -- harness .claude | Where-Object { $_ })) {
    Fail "a commit made during this run changed harness/ or .claude/. Nothing was pushed; review the commits since $startHead before pushing by hand."
}
if ($rc -eq 124) { Fail "the run hit its ${maxSeconds}s watchdog bound and was terminated. No digest is trustworthy from a killed run." }
if ($rc -ne 0)   { Fail "the headless run exited $rc. Not committing anything from a failed run." }

# The job may write ONLY a digest. Anything else is reported and left uncommitted.
# Content aware on purpose, so phantom line ending modifications do not cry wolf.
$changed = @(& git.exe diff --name-only) + @(& git.exe ls-files --others --exclude-standard)
$stray = $changed | Where-Object { $_ -and ($_ -notmatch '^episodic/review-digest-.*\.md$') }
if ($stray) {
    Log 'WARNING: changes outside the digest, deliberately left uncommitted:'
    LogLines $stray
}

# Stage by pattern: the collision guard may write a suffixed file, or nothing.
# git add exits non zero on a pattern matching nothing, so the outcome below is
# what is tested, not this exit code.
[void](Invoke-Git add -- 'episodic/review-digest-*.md')

# Two questions, asked separately. Was a digest written during this run (the
# filesystem answers), and did git stage it (the index answers)? Collapsing them
# is the bug this replaces. The index is filtered to digests, because an
# interactive session may have its own work staged (harness/ENGINEERING.md rule 5).
$fresh  = Get-FreshDigests -EpisodicDir (Join-Path $vault 'episodic') -RefFile $ref
$staged = @(& git.exe diff --cached --name-only | Where-Object { $_ -match '^episodic/review-digest-.*\.md$' })
$verdict = Assert-DigestStaged -Fresh $fresh -Staged $staged
if ($verdict -like 'FAIL*') {
    Log 'The digest is on disk and uncommitted. Read it, then commit it by hand.'
    Fail $verdict
}
if ($verdict -eq 'nothing-to-do') {
    Log 'no digest this week: nothing written and nothing staged. Verified, not assumed.'
    # done is logged before Complete-Run, so a line that missed the log is counted.
    Log 'done'
    [void](Complete-Run -LogDir $logDir -Date $today -Outcome 'nothing-new' -Detail $(if ($slot.Code -eq 1) { "previous run died: $($slot.Names)" } else { '' }))
    exit 0
}

Log ("committing: " + ($staged -join ', '))
[void](Invoke-Git commit -m "Weekly review digest $today (scheduled job)" -- @staged)
if ($LASTEXITCODE -ne 0) { Fail 'git commit failed' }

[void](Invoke-Git push)
if ($LASTEXITCODE -ne 0) { Fail 'git push failed, digest committed locally only' }

Log 'done'
[void](Complete-Run -LogDir $logDir -Date $today -Outcome 'committed' -Detail ($staged -join ', '))
exit 0
