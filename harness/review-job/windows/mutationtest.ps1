# mutationtest.ps1 : does selftest.ps1 actually catch a regression, or merely pass?
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File mutationtest.ps1
#
# harness/ENGINEERING.md rule 1: a mechanism whose job is to refuse something must
# be tested by making it refuse. Each mutant breaks exactly one shipped fix in a
# COPY of this directory, then requires the copied selftest to fail. A mutant that
# survives names a fix that is shipped but unprotected. Read only with respect to
# the real files: nothing outside the temp directory is written, and no mutated
# wrapper is ever pointed at the real vault. The Mac counterpart is
# ../macos/mutationtest.sh.
#
# Before any mutant, the UNMUTATED copy must pass. Without that control, a copy
# that fails for an unrelated reason (a path that only resolves in the clone, say)
# would "kill" every mutant and the suite would look perfect while proving nothing.

$ErrorActionPreference = 'Continue'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here 'heartbeat.ps1')
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("mesosphere-mutation-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tmp | Out-Null
# The copies sit outside the clone, so they are pointed at the real shared prompt.
$env:MESOSPHERE_PROMPT = Join-Path (Get-VaultFromScript $here) 'harness\review-job\prompt.md'
# And at the real history.py, which the mining cases copy into their throwaway vaults.
$env:MESOSPHERE_HISTORY = Join-Path (Get-VaultFromScript $here) 'harness\history.py'
# And at the real adapter files, which pick the engine and its flags. Read only.
$env:MESOSPHERE_ADAPTERS_DIR = Join-Path (Get-VaultFromScript $here) 'harness\adapters'
# A mutated selftest can hang rather than fail, and a hang is not a catch. The bound
# is wide because powershell.exe can take several seconds to start and each
# selftest starts seven of them; at 240s, three honest runs were misreported as hangs.
$bound = 900
$files = 'run-review.ps1', 'heartbeat.ps1', 'selftest.ps1'
$script:killed = 0; $script:survived = 0; $script:declared = 0

# Each copy's selftest runs as its own process, several at once, because a serial
# pass over every mutant takes a quarter of an hour.
function Start-Copy($d) {
    $in = Join-Path $d 'empty.in'; Set-Content $in '' -Encoding ascii
    $p = Start-Process -FilePath 'powershell.exe' -NoNewWindow -PassThru -WorkingDirectory $d `
        -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$d\selftest.ps1`"" `
        -RedirectStandardInput $in -RedirectStandardOutput "$d\out.txt" -RedirectStandardError "$d\err.txt"
    $null = $p.Handle   # without this, ExitCode reads back empty after the process ends
    return $p
}
function Wait-Copy($p) {
    # Measured from this copy's own start, not from when the wait began.
    $left = [Math]::Max(1, $bound - [int]((Get-Date) - $p.StartTime).TotalSeconds)
    if (-not $p.WaitForExit($left * 1000)) { & taskkill.exe /T /F /PID $p.Id 2>&1 | Out-Null; return 124 }
    return $p.ExitCode
}
$script:pending = New-Object System.Collections.Generic.List[object]

function Mutant($name, $file, $find, $replace) {
    $script:declared++
    $d = Join-Path $tmp $name; New-Item -ItemType Directory -Path $d | Out-Null
    $files | ForEach-Object { Copy-Item (Join-Path $here $_) $d }
    $target = Join-Path $d $file
    $before = [System.IO.File]::ReadAllText($target)
    $after = $before.Replace($find, $replace)
    if ($after -eq $before) {
        Write-Output "ERROR    ${name}: the mutation changed nothing, so its target has moved"
        $script:survived++; return
    }
    [System.IO.File]::WriteAllText($target, $after, (New-Object System.Text.UTF8Encoding $true))
    $script:pending.Add([pscustomobject]@{ Name = $name; File = $file; Dir = $d })
}

function Invoke-Pending($width) {
    $queue = $script:pending.ToArray(); $i = 0
    while ($i -lt $queue.Count) {
        $batch = $queue[$i..([Math]::Min($i + $width, $queue.Count) - 1)]
        $procs = @($batch | ForEach-Object { [pscustomobject]@{ M = $_; P = (Start-Copy $_.Dir) } })
        foreach ($x in $procs) {
            $rc = Wait-Copy $x.P; $n = $x.M.Name
            if ($rc -eq 0)       { Write-Output "SURVIVED ${n}: $($x.M.File) was broken and the selftest still passed"; $script:survived++ }
            elseif ($rc -eq 124) { Write-Output "HUNG     ${n}: the selftest never finished, which is not a catch"; $script:survived++ }
            else                 { Write-Output "KILLED   $n"; $script:killed++ }
        }
        $i += $width
    }
}

try {
    $c = Join-Path $tmp 'control'; New-Item -ItemType Directory -Path $c | Out-Null
    $files | ForEach-Object { Copy-Item (Join-Path $here $_) $c }
    $crc = Wait-Copy (Start-Copy $c)
    if ($crc -ne 0) {
        Write-Output "CONTROL FAILED: the unmutated copy's selftest exited $crc, so no mutant result would mean anything"
        Get-Content "$c\out.txt" -ErrorAction SilentlyContinue | Where-Object { $_ -match '^FAIL' }
        Write-Output 'MUTATION TEST FAILED (control)'
        exit 1
    }
    Write-Output 'CONTROL  unmutated copy passes'

    # One mutant per shipped fix.
    Mutant 'arg-guard'      'run-review.ps1' '    exit 64'                                  '    $null = 64'
    Mutant 'commit-scope'   'run-review.ps1' ' -- @staged)'                                 ')'
    Mutant 'watchdog-mute'  'run-review.ps1' 'if ($rc -eq 124) { Fail '                     'if ($rc -eq 124) { Log '
    Mutant 'rebase-allowed' 'run-review.ps1' 'Invoke-Git pull --no-rebase)'                 'Invoke-Git pull)'
    Mutant 'utf16-log'      'heartbeat.ps1'  'Add-Content -Path $Path -Value $Line -Encoding UTF8 -ErrorAction Stop' '$Line | Out-File -FilePath $Path -Append -ErrorAction Stop'
    Mutant 'links-ungranted' 'run-review.ps1' '$dirs += @($m.Target)'                       '$null = $m.Target'
    Mutant 'marker-dropped' 'run-review.ps1' "`$env:MESOSPHERE_REVIEW_JOB = '1'"          '$null = 1'
    Mutant 'mining-handoff' 'run-review.ps1' '"`n`nMonthly mining for this run: $mining"' '""'
    Mutant 'mining-workdir' 'run-review.ps1' '$dirs += @((Resolve-Path $workdir).Path)'  '$null = $workdir'
    Mutant 'derive-fixed'   'heartbeat.ps1'  '$d = [System.IO.Path]::GetFullPath($ScriptDir)' '$d = "C:\nowhere\a\b\c\d\e"'
    Mutant 'live-clobber'   'heartbeat.ps1'  'return [pscustomobject]@{ Code = 2;'         'return [pscustomobject]@{ Code = 0;'
    Mutant 'marker-stuck'   'heartbeat.ps1'  'if (Test-Path $marker) { Remove-Item $marker -Force }' '$null = $marker'
    Mutant 'assert-blind'   'heartbeat.ps1'  'return "FAIL: digest written'                'return ''nothing-to-do''; "'
    Mutant 'fresh-via-git'  'heartbeat.ps1'  'if (-not (Test-Path $RefFile)) { return @() }' 'return @()'
    Mutant 'watchdog-unbound' 'heartbeat.ps1' 'if (-not $p.WaitForExit($Seconds * 1000)) {' 'if (-not $p.WaitForExit()) {'
    Mutant 'log-fallback'   'heartbeat.ps1'  'Add-Content -Path $fallback -Value $Line -Encoding UTF8 -ErrorAction Stop' '$null = $Line'
    Mutant 'adapter-ignored' 'run-review.ps1' "EnvOr 'MESOSPHERE_ADAPTER' 'claude-code'"   "'claude-code'"
    Mutant 'prompt-dropped' 'run-review.ps1' '+ @($AgentCmd | Select-Object -Skip 1) + @($promptText)' '+ @($AgentCmd | Select-Object -Skip 1)'
    Mutant 'dirty-guard'    'run-review.ps1' "    Fail 'REFUSED: uncommitted changes"           "    Log 'REFUSED: uncommitted changes"
    Mutant 'restore-off'    'run-review.ps1' "Restore-Harness`r`n# A change the run"          "`$null = 0`r`n# A change the run"
    Mutant 'cursor-swallowed' 'run-review.ps1' 'try { . $agentFile } catch { Fail '          'try { . $agentFile } catch { Log '
    Mutant 'grants-last'    'run-review.ps1' '@($grants) + @($AgentCmd | Select-Object -Skip 1)' '@($AgentCmd | Select-Object -Skip 1) + @($grants)'
    Mutant 'naive-quoting'  'heartbeat.ps1'  "`$q = `$Value -replace '(\\*)`"', '`$1`$1\`"' -replace '(\\+)`$', '`$1`$1'" '$q = $Value'
    Mutant 'batch-allowed'  'run-review.ps1' "if (`$agentExe.Source -match '\.(cmd|bat)`$') { Fail " "if (`$agentExe.Source -match '\.(cmd|bat)`$') { Log "
    Invoke-Pending 3
}
finally {
    Set-Location ([System.IO.Path]::GetTempPath())
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
}

# Zero mutants run must never read as zero survivors: on 2026-09-29 an exception
# in the runner left this at "0 of 0 killed" and it reported OK.
$total = $script:killed + $script:survived
if ($total -lt 1 -or $total -ne $script:declared) {
    Write-Output "MUTATION TEST FAILED ($total of $script:declared declared mutants produced a result)"
    exit 1
}
if ($script:survived -eq 0) { Write-Output "MUTATION TEST OK ($script:killed of $total mutants killed)"; exit 0 }
Write-Output "MUTATION TEST FAILED ($script:survived of $total mutants survived)"
exit 1
