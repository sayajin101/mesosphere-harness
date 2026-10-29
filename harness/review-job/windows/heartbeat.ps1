# heartbeat.ps1 : proof of life helpers for the weekly vault review job (Windows).
#
# Functions only. Dot sourcing this file must have no side effects, so selftest.ps1
# can drive it in a scratch directory without touching the vault or running the job.
# The Mac counterpart is ../macos/heartbeat.sh; the two answer the same questions.
#
# Why this exists: on 2026-08-22 a run was killed part way, and a killed run and a
# genuinely quiet week produced the same observable output, which is nothing. Same
# day, the job wrote a digest and then reported "no digest changes to commit"
# because its index read came back empty. See harness/ENGINEERING.md rules 1 and 4.

# The wrapper lives at harness\review-job\windows inside the
# clone, three levels below the repo root. Pure, so it can be proven on two inputs
# without running the job against the real vault (harness/ENGINEERING.md rule 3).
function Get-VaultFromScript {
    param([Parameter(Mandatory)][string]$ScriptDir)
    $d = [System.IO.Path]::GetFullPath($ScriptDir)
    for ($i = 0; $i -lt 3; $i++) { $d = Split-Path -Parent $d }
    return $d
}

# Decide whether this run may take the slot. A marker on disk means one of two very
# different things, and the first Windows version collapsed them: it deleted any
# marker from another date and overwrote today's, so a manual run started beside a
# live one would destroy the first run's proof of life on the way in.
#   Code 0  no marker, clear to run
#   Code 1  a dead predecessor's marker was found and cleared; Names says which
#   Code 2  a LIVE run holds the slot, the caller must not start
function Test-RunSlot {
    param([Parameter(Mandatory)][string]$LogDir, [int]$MaxAgeSeconds = 7200)
    $markers = @(Get-ChildItem -Path $LogDir -Filter 'inflight-*.marker' -ErrorAction SilentlyContinue)
    if ($markers.Count -eq 0) { return [pscustomobject]@{ Code = 0; Names = '' } }
    foreach ($m in $markers) {
        $line = (Get-Content $m.FullName -Raw -ErrorAction SilentlyContinue) -as [string]
        $procId = if ($line -match 'pid[= ](\d+)') { [int]$Matches[1] } else { 0 }
        $age = ((Get-Date) - $m.LastWriteTime).TotalSeconds
        # A pid can be recycled, so liveness alone is not enough: a marker older than
        # the watchdog bound plus its grace cannot belong to a run still going.
        if ($procId -gt 0 -and $age -lt $MaxAgeSeconds -and (Get-Process -Id $procId -ErrorAction SilentlyContinue)) {
            return [pscustomobject]@{ Code = 2; Names = "$($m.Name) ($($line.Trim()), $([int]$age)s old)" }
        }
    }
    $names = ($markers | ForEach-Object { $_.Name }) -join ', '
    $markers | ForEach-Object { Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue }
    return [pscustomobject]@{ Code = 1; Names = $names }
}

# Claim the run. The reference file's timestamp is what later tells us whether a
# digest was written during THIS run, independently of anything git reports.
function Start-RunMarker {
    param([Parameter(Mandatory)][string]$LogDir, [Parameter(Mandatory)][string]$Date)
    if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }
    $marker = Join-Path $LogDir "inflight-$Date.marker"
    "pid=$PID started=$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') host=$env:COMPUTERNAME" |
        Out-File -FilePath $marker -Encoding utf8
    $ref = Join-Path $LogDir 'run-start.ref'
    Set-Content -Path $ref -Value '' -Encoding utf8
    (Get-Item $ref).LastWriteTime = (Get-Item $marker).LastWriteTime
    return $marker
}

# Append one line to the run log without ever losing it. On 2026-10-27 a Git bash
# tail -F held the log open, Add-Content failed on every line with "being used by
# another process", and the job carried on with nothing said (harness/ENGINEERING.md
# rule 4). Antivirus, the search indexer, OneDrive or an open editor can hold it the
# same way. So a failed write is retried, then appended to run-<date>.fallback.log
# beside the log, then held in memory; Complete-Run reports whatever did not reach
# the main log. Returns where the line went: log, fallback or memory.
function Write-LogLine {
    param([Parameter(Mandatory)][string]$Path, [Parameter(Mandatory)][string]$Line,
          [int]$Retries = 5, [int]$DelayMs = 200)
    if (-not $script:LogSpill) {
        $script:LogSpill = [pscustomobject]@{ Fallback = ''; Count = 0; Held = New-Object System.Collections.Generic.List[string] }
    }
    for ($i = 0; $i -le $Retries; $i++) {
        try { Add-Content -Path $Path -Value $Line -Encoding UTF8 -ErrorAction Stop; return 'log' }
        catch { if ($i -lt $Retries) { Start-Sleep -Milliseconds $DelayMs } }
    }
    $fallback = $Path -replace '\.log$', '.fallback.log'
    if ($fallback -eq $Path) { $fallback = "$Path.fallback.log" }
    try {
        Add-Content -Path $fallback -Value $Line -Encoding UTF8 -ErrorAction Stop
        $script:LogSpill.Fallback = $fallback; $script:LogSpill.Count++
        return 'fallback'
    } catch {
        $script:LogSpill.Held.Add($Line)
        return 'memory'
    }
}

# The only way a run is allowed to end: clear the marker, record the outcome. Any
# log line that missed the main log is named here, so a short log is never mistaken
# for a short run; lines that reached no file at all are written out in full.
function Complete-Run {
    param([Parameter(Mandatory)][string]$LogDir, [Parameter(Mandatory)][string]$Date,
          [Parameter(Mandatory)][ValidateSet('committed','nothing-new','failed')][string]$Outcome,
          [string]$Detail = '')
    $marker = Join-Path $LogDir "inflight-$Date.marker"
    if (Test-Path $marker) { Remove-Item $marker -Force }
    $status = Join-Path $LogDir "status-$Date.txt"
    $lines = @("$Outcome $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Detail".TrimEnd())
    $spill = $script:LogSpill
    if ($spill -and $spill.Count -gt 0) {
        $lines += "log: $($spill.Count) line(s) could not be written to the run log and went to the fallback $($spill.Fallback)"
    }
    if ($spill -and $spill.Held.Count -gt 0) {
        $lines += "log: $($spill.Held.Count) line(s) could not be written to the run log or the fallback, so they follow here:"
        $lines += @($spill.Held)
    }
    $lines | Out-File -FilePath $status -Encoding utf8
    return $status
}

# Digests written since the run started, found on the filesystem rather than
# through git. The first Windows version asked git (diff plus untracked), so a
# digest git could not see, an ignored one for example, read as a quiet week.
function Get-FreshDigests {
    param([Parameter(Mandatory)][string]$EpisodicDir, [Parameter(Mandatory)][string]$RefFile)
    if (-not (Test-Path $RefFile)) { return @() }
    $since = (Get-Item $RefFile).LastWriteTime
    @(Get-ChildItem -Path $EpisodicDir -Filter 'review-digest-*.md' -File -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -ge $since } | ForEach-Object { $_.Name })
}

# Pure: given what this run wrote and what git has staged, decide the outcome.
#   ok             written and staged
#   nothing-to-do  nothing written, nothing staged, a genuinely quiet week
#   FAIL           written but not staged, the failure that used to be logged as success
function Assert-DigestStaged {
    param([string[]]$Fresh = @(), [string[]]$Staged = @())
    $disk = @($Fresh | Where-Object { $_ })
    $idx  = @($Staged | Where-Object { $_ })
    if ($disk.Count -eq 0 -and $idx.Count -eq 0) { return 'nothing-to-do' }
    if ($disk.Count -gt 0 -and $idx.Count -eq 0) {
        return "FAIL: digest written but nothing staged ($($disk -join ', '))"
    }
    return 'ok'
}

# Quote one argument for a Windows command line, by the rules a C runtime or .NET
# program uses to split it back into argv: wrapped in quotes when it holds a space,
# tab, newline or quote, each quote escaped, and the backslashes before a quote or
# the closing quote doubled. Start-Process in Windows PowerShell 5.1 passes its
# argument string through untouched, so this is the only quoting the prompt gets,
# and prompt-as-argument proves a prompt with quotes and backslashes arrives exact.
function ConvertTo-NativeArg {
    param([AllowEmptyString()][string]$Value)
    if ($Value -ne '' -and $Value -notmatch '[\s"]') { return $Value }
    $q = $Value -replace '(\\*)"', '$1$1\"' -replace '(\\+)$', '$1$1'
    return '"' + $q + '"'
}

# Run a native command under a wall clock bound, with stdin from a file and output
# to files. Task Scheduler's PT2H limit kills the whole job with no outcome
# recorded, so this bound sits below it and fires first. Returns the exit code,
# or 124 when the bound was hit, after killing the whole process tree.
function Invoke-Watchdog {
    param([Parameter(Mandatory)][string]$FilePath, [string]$Arguments = '',
          [Parameter(Mandatory)][string]$StdinFile, [Parameter(Mandatory)][string]$StdoutFile,
          [Parameter(Mandatory)][string]$StderrFile, [Parameter(Mandatory)][int]$Seconds,
          [string]$WorkingDirectory = (Get-Location).Path)
    $sp = @{ FilePath = $FilePath; NoNewWindow = $true; PassThru = $true
             RedirectStandardInput = $StdinFile; RedirectStandardOutput = $StdoutFile
             RedirectStandardError = $StderrFile; WorkingDirectory = $WorkingDirectory }
    if ($Arguments) { $sp.ArgumentList = $Arguments }   # Start-Process refuses an empty one
    $p = Start-Process @sp
    $null = $p.Handle   # without this, ExitCode reads back empty after the process ends
    if (-not $p.WaitForExit($Seconds * 1000)) {
        & taskkill.exe /T /F /PID $p.Id 2>&1 | Out-Null
        $null = $p.WaitForExit(10000)
        return 124
    }
    return $p.ExitCode
}
