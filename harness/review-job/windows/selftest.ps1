# selftest.ps1 : the Windows review job's own test suite.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File selftest.ps1
#   prints one OK/FAIL/SKIP line per check, then SELFTEST OK (n checks), exit 0,
#   or SELFTEST FAILED, exit 1
#
# Safe as a ledger CHECK: read only with respect to the real system. Everything it
# writes lands in a temp directory it creates and removes. The end to end checks
# drive THIS DIRECTORY'S REAL run-review.ps1, pointed by env at a throwaway vault
# with its own bare origin and a fake claude, because testing a reimplementation
# would prove nothing about the wrapper (harness/ENGINEERING.md rule 1). The one
# exception is the argument guard, exercised on a copy truncated at the guard so a
# regression there cannot fire the live job. Whether this file would FAIL on a
# regression is not its own claim to make: mutationtest.ps1 answers that.
#
# The sweep checks read the SHARED prompt, the one both machines run. Its path is
# derived from this file's location, or MESOSPHERE_PROMPT when set, which is how the
# mutation test points a copied suite at the real prompt.

# Continue, not Stop: under Windows PowerShell 5.1 any native stderr line (git push
# reports progress there) becomes a terminating error under Stop.
$ErrorActionPreference = 'Continue'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here 'heartbeat.ps1')

$script:count = 0; $script:failed = 0
function Ok($name)          { Write-Output "OK $name"; $script:count++ }
function Bad($name, $why)   { Write-Output "FAIL ${name}: $why"; $script:count++; $script:failed++ }
function Skip($name, $why)  { Write-Output "SKIP ${name}: $why" }
function Check($name, $cond, $why) { if ($cond) { Ok $name } else { Bad $name $why } }

$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("mesosphere-selftest-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tmp | Out-Null
$savedEnv = @{}
'MESOSPHERE_VAULT','MESOSPHERE_CLAUDE','MESOSPHERE_MAX_SECONDS','MESOSPHERE_STATE','MESOSPHERE_MEMORY_ROOT','MESOSPHERE_SELFTEST_OUT','MESOSPHERE_REVIEW_JOB',
'MESOSPHERE_ADAPTER','MESOSPHERE_CODEX','MESOSPHERE_GEMINI','MESOSPHERE_CURSOR','MESOSPHERE_AGY' |
    ForEach-Object { $savedEnv[$_] = [Environment]::GetEnvironmentVariable($_) }
# Cleared, so review-job-marker proves the WRAPPER sets it: inherited from whoever ran
# this suite (the review job itself, say), it would pass with the wrapper's line gone.
# MESOSPHERE_ADAPTER likewise, so adapter-default proves the wrapper's own default.
Remove-Item Env:MESOSPHERE_REVIEW_JOB, Env:MESOSPHERE_ADAPTER -ErrorAction SilentlyContinue

$realPrompt = if ($env:MESOSPHERE_PROMPT) { $env:MESOSPHERE_PROMPT } else {
    Join-Path (Get-VaultFromScript $here) 'harness\review-job\prompt.md' }
# The mining cases copy the real history.py into each throwaway vault. Derived the same
# way, or MESOSPHERE_HISTORY, because a copied suite outside the clone has no harness\ above it.
$realHistory = if ($env:MESOSPHERE_HISTORY) { $env:MESOSPHERE_HISTORY } else {
    Join-Path (Get-VaultFromScript $here) 'harness\history.py' }
# The adapter cases run the real adapter files. In the clone the wrapper finds them
# itself; a copied suite is handed MESOSPHERE_ADAPTERS_DIR by the mutation test, which
# the wrapper reads too.
$adapterDir = if ($env:MESOSPHERE_ADAPTERS_DIR) { $env:MESOSPHERE_ADAPTERS_DIR } else {
    Join-Path (Get-VaultFromScript $here) 'harness\adapters' }
# The bash the review agent's Bash tool runs is Git for Windows', which Claude Code finds
# by its install location, not PATH. So without bash on PATH, fall back to Git's own.
# Never WSL's launcher (System32 or WindowsApps): it would test Linux find, not the
# agent's. No Git bash at all stays a FAIL, naming where it looked.
$bashTried = @()
$bash = Get-Command bash -CommandType Application -All -ErrorAction SilentlyContinue |
    Where-Object { $_.Source -notmatch '\\(System32|WindowsApps)\\' } | Select-Object -First 1 -ExpandProperty Source
if (-not $bash) {
    $gitExe = (Get-Command git.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1).Source
    $bashTried = @($env:CLAUDE_CODE_GIT_BASH_PATH) +
        @(if ($gitExe) { Join-Path (Split-Path -Parent (Split-Path -Parent $gitExe)) 'bin\bash.exe' }) +
        @($env:ProgramFiles, ${env:ProgramFiles(x86)}, (Join-Path "$env:LOCALAPPDATA" 'Programs') |
            Where-Object { $_ } | ForEach-Object { Join-Path $_ 'Git\bin\bash.exe' }) | Where-Object { $_ } | Select-Object -Unique
    $bash = $bashTried | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
}
function Posix($p) { '/' + $p.Substring(0,1).ToLower() + ($p.Substring(2) -replace '\\','/') }
# Through a script file, because Windows PowerShell 5.1 drops the embedded quotes in
# a native argument, which would mangle -path "*/memory/*" before bash saw it.
function Invoke-Bash($cmd) { $f = Join-Path $tmp ('sweep-' + [guid]::NewGuid().ToString('N') + '.sh'); [System.IO.File]::WriteAllText($f, $cmd + "`n"); (& $bash $f 2>&1) -join ' ' }
function G { & git.exe @args 2>&1 | Out-Null }

try {
    # ---------- unit checks over heartbeat.ps1 ----------
    $hb = Join-Path $tmp 'hb'; $d = '2026-01-02'

    $marker = Start-RunMarker -LogDir $hb -Date $d
    $hasPid = (Test-Path $marker) -and ((Get-Content $marker -Raw) -match "pid=$PID")
    [void](Complete-Run -LogDir $hb -Date $d -Outcome 'committed' -Detail 'selftest digest')
    Check 'inflight' ($hasPid -and -not (Test-Path $marker)) "marker named the pid: $hasPid, left behind: $(Test-Path $marker)"

    $st = Join-Path $hb "status-$d.txt"
    Check 'status-file' ((Test-Path $st) -and ((Get-Content $st -Raw) -match '^committed .* selftest digest')) 'no status file naming the outcome and its detail'

    "pid=999999 started=long-ago host=test" | Out-File (Join-Path $hb 'inflight-2025-12-25.marker') -Encoding utf8
    $s1 = Test-RunSlot -LogDir $hb; $s2 = Test-RunSlot -LogDir $hb
    Check 'stale-detect' ($s1.Code -eq 1 -and $s1.Names -match '2025-12-25' -and $s2.Code -eq 0) "first=$($s1.Code) (want 1) second=$($s2.Code) (want 0)"

    $live = Join-Path $hb 'inflight-2026-01-02.marker'
    "pid=$PID started=now host=test" | Out-File $live -Encoding utf8
    $s3 = Test-RunSlot -LogDir $hb
    Check 'live-refusal' ($s3.Code -eq 2 -and (Test-Path $live)) "code=$($s3.Code) (want 2), marker kept=$(Test-Path $live)"
    Remove-Item $live -Force

    # ---------- the run log never drops a line ----------
    # Guarded, so a heartbeat.ps1 without Write-LogLine fails these two checks and
    # the suite carries on to the end to end cases instead of crashing.
    $ll = Join-Path $tmp 'll'; New-Item -ItemType Directory -Path $ll | Out-Null
    $llLog = Join-Path $ll 'run-2026-01-03.log'; $llFb = Join-Path $ll 'run-2026-01-03.fallback.log'
    $haveWriter = [bool](Get-Command Write-LogLine -ErrorAction SilentlyContinue)
    if (-not $haveWriter) {
        Bad 'log-retry' 'heartbeat.ps1 has no Write-LogLine'
        Bad 'log-held' 'heartbeat.ps1 has no Write-LogLine'
    } else {
        # A lock released inside the retry window. The holder runs on its own runspace
        # thread, because this thread is the one sleeping between retries.
        $script:LogSpill = $null
        $sync = [hashtable]::Synchronized(@{ Held = $false })
        $holder = [powershell]::Create().AddScript({
            param($p, $s) $h = [System.IO.File]::Open($p, 'OpenOrCreate', 'ReadWrite', 'None'); $s.Held = $true
            Start-Sleep -Milliseconds 500; $h.Dispose() }).AddArgument($llLog).AddArgument($sync)
        $async = $holder.BeginInvoke()
        $deadline = (Get-Date).AddSeconds(10)
        while (-not $sync.Held -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 10 }
        $t0 = Get-Date
        $where = Write-LogLine -Path $llLog -Line 'retried line'
        $waited = ((Get-Date) - $t0).TotalMilliseconds
        $holder.EndInvoke($async); $holder.Dispose()
        $inLog = (Test-Path $llLog) -and ((Get-Content $llLog -Encoding UTF8) -contains 'retried line')
        Check 'log-retry' ($sync.Held -and $where -eq 'log' -and $inLog -and $waited -ge 200 -and -not (Test-Path $llFb)) "held=$($sync.Held) went to=$where (want log) in log=$inLog waited=$([int]$waited)ms (want 200 or more) fallback exists=$(Test-Path $llFb)"

        # The log and the fallback both locked: the line is kept in memory and
        # Complete-Run writes it into the status file itself.
        $script:LogSpill = $null
        $h1 = [System.IO.File]::Open($llLog, 'OpenOrCreate', 'ReadWrite', 'None')
        $h2 = [System.IO.File]::Open($llFb, 'OpenOrCreate', 'ReadWrite', 'None')
        try { $where = Write-LogLine -Path $llLog -Line 'held line one' } finally { $h1.Dispose(); $h2.Dispose() }
        $st = Complete-Run -LogDir $ll -Date '2026-01-03' -Outcome 'failed' -Detail 'held test'
        $stText = (Get-Content $st -Raw -Encoding UTF8) -as [string]
        $inFiles = ((Get-Content $llLog -Raw) -as [string]) + ((Get-Content $llFb -Raw) -as [string])
        Check 'log-held' ($where -eq 'memory' -and $stText -match '(?m)^failed .* held test' -and
                          $stText -match '(?m)^log: 1 line\(s\) could not be written to the run log or the fallback' -and
                          $stText -match '(?m)^held line one\s*$' -and $inFiles -notmatch 'held line one') "went to=$where (want memory) status='$stText'"
        $script:LogSpill = $null
    }

    $in = Join-Path $tmp 'empty.in'; Set-Content $in '' -Encoding ascii
    $o = Join-Path $tmp 'w.out'; $e = Join-Path $tmp 'w.err'
    $t0 = Get-Date
    $wHang = Invoke-Watchdog -FilePath 'cmd.exe' -Arguments '/c ping -n 30 127.0.0.1 >nul' -StdinFile $in -StdoutFile $o -StderrFile $e -Seconds 2
    $wSecs = ((Get-Date) - $t0).TotalSeconds
    $wPass = Invoke-Watchdog -FilePath 'cmd.exe' -Arguments '/c exit 3' -StdinFile $in -StdoutFile $o -StderrFile $e -Seconds 20
    $wZero = Invoke-Watchdog -FilePath 'cmd.exe' -Arguments '/c exit 0' -StdinFile $in -StdoutFile $o -StderrFile $e -Seconds 20
    Check 'watchdog' ($wHang -eq 124 -and $wSecs -lt 15 -and $wPass -eq 3 -and $wZero -eq 0) "timeout=$wHang after $([int]$wSecs)s (want 124), passthrough=$wPass (want 3), clean=$wZero (want 0)"

    Check 'unstaged-guard' (((Assert-DigestStaged -Fresh @('d.md') -Staged @()) -like 'FAIL*') -and
                            ((Assert-DigestStaged -Fresh @('d.md') -Staged @('d.md')) -eq 'ok') -and
                            ((Assert-DigestStaged -Fresh @() -Staged @()) -eq 'nothing-to-do')) 'written-unstaged, staged or quiet was misjudged'

    $a = Get-VaultFromScript (Join-Path $tmp 'alpha\harness\review-job\windows')
    $b = Get-VaultFromScript (Join-Path $tmp 'beta\harness\review-job\windows')
    $runText = Get-Content (Join-Path $here 'run-review.ps1') -Raw
    Check 'vault-derived' ($a -eq (Join-Path $tmp 'alpha') -and $b -eq (Join-Path $tmp 'beta') -and
                           $runText -match 'Get-VaultFromScript' -and $runText -notmatch '(?i)C:\\Users\\[a-z]') "alpha=$a beta=$b"

    Check 'no-rebase' ($runText -match "Invoke-Git pull --no-rebase") 'the pull does not pass --no-rebase explicitly'

    # ---------- the shared prompt's memory sweep ----------
    $promptText = if (Test-Path $realPrompt) { Get-Content $realPrompt -Raw -Encoding UTF8 } else { '' }
    # Commands the prompt prescribes: backtick spans that start with find and name
    # the path they sweep. Spans with no path, like `find -exec` in the sources list
    # or the bare `find -type d` example, are mentions in prose; a span containing
    # "..." is a quoted bad example. Neither is a command the sweep runs.
    $cmds = @([regex]::Matches($promptText, '`(find [^`]+)`') | ForEach-Object { $_.Groups[1].Value } |
              Where-Object { $_ -match '~/' -and $_ -notmatch '\.\.\.' })
    $banned = @($cmds | Where-Object { $_ -match '(^|\s)(-exec|-execdir|-ok|-okdir|-delete)(\s|$)|\bxargs\b' })
    Check 'sweep-read-only' ($cmds.Count -ge 2 -and $banned.Count -eq 0) "prompt=$realPrompt, $($cmds.Count) commands found (want 2 or more), banned: $($banned -join ' | ')"

    $listCmd = $cmds | Where-Object { $_ -match '-path "\*/memory/\*"' } | Select-Object -First 1
    $proj = Join-Path $tmp 'projects'; $tgt = Join-Path $tmp 'repo-memory'
    New-Item -ItemType Directory -Path (Join-Path $proj 'p1'), $tgt | Out-Null
    Set-Content (Join-Path $tgt 'note.md') 'fresh' -Encoding utf8
    New-Item -ItemType Junction -Path (Join-Path $proj 'p1\memory') -Target $tgt | Out-Null
    if (-not $listCmd -or -not $bash) {
        Bad 'junction-sweep' "no sweep list command in the prompt ($([bool]$listCmd)) or no Git bash (not on PATH, none at: $($bashTried -join '; '))"
    } else {
        $run = $listCmd -replace '~/\.claude/projects', (Posix $proj)
        $withL = Invoke-Bash $run
        $bare  = Invoke-Bash ($run -replace '^find -L ', 'find ')
        # The bare control proves the check discriminates: without -L a junction is invisible.
        Check 'junction-sweep' ($withL -match 'p1/memory/note\.md' -and $bare -notmatch 'note\.md') "with -L: '$withL', bare: '$bare'"

        New-Item -ItemType Directory -Path (Join-Path $proj 'p2') | Out-Null
        try {
            New-Item -ItemType SymbolicLink -Path (Join-Path $proj 'p2\memory') -Target $tgt -ErrorAction Stop | Out-Null
            $withL = Invoke-Bash $run
            Check 'symlink-sweep' ($withL -match 'p2/memory/note\.md') "with -L: '$withL'"
        } catch {
            # Not a pass and not a failure of the wrapper: this account cannot make a
            # symlink (needs admin or Developer Mode). Said out loud rather than hidden.
            Skip 'symlink-sweep' "this machine refused to create a symlink: $($_.Exception.Message)"
        }
    }

    # ---------- end to end over the real run-review.ps1 ----------
    function New-Vault($v) {
        G init -q --bare "$v.git"; G init -q -b main $v
        G -C $v config user.email t@localhost; G -C $v config user.name t; G -C $v config core.autocrlf false
        New-Item -ItemType Directory -Path "$v\episodic", "$v\harness\review-job" -Force | Out-Null
        Set-Content "$v\harness\review-job\prompt.md" $fakePrompt -Encoding utf8
        Set-Content "$v\episodic\review-digest-2020-01-01.md" 'old' -Encoding utf8
        G -C $v add -A; G -C $v commit -q -m init; G -C $v remote add origin "$v.git"; G -C $v push -q -u origin main
    }
    # The throwaway prompt carries quotes, a backslash before a quote and a percent
    # pair, so prompt-as-argument proves the wrapper's quoting hands it over exact.
    $fakePrompt = 'fake digest prompt with "quotes", a\" escape, %PATH% and C:\a\b\ backslashes'
    # The fake engine is a real executable, not a batch file: the wrapper refuses a
    # batch file, which would cut the prompt at its first newline. It records argv
    # NUL separated, so every argument is seen exactly as the engine would split it,
    # and takes its behaviour from its own file name.
    $fakeSrc = @'
using System; using System.IO; using System.Text; using System.Threading;
public static class FakeEngine {
    public static int Main(string[] a) {
        string o = Environment.GetEnvironmentVariable("MESOSPHERE_SELFTEST_OUT");
        UTF8Encoding u = new UTF8Encoding(false);
        File.WriteAllText(Path.Combine(o, "argv.txt"), string.Join("\0", a), u);
        File.WriteAllText(Path.Combine(o, "marker.txt"), "[" + Environment.GetEnvironmentVariable("MESOSPHERE_REVIEW_JOB") + "]", u);
        string mode = Path.GetFileNameWithoutExtension(System.Reflection.Assembly.GetEntryAssembly().Location);
        if (mode.Contains("hang")) { Thread.Sleep(60000); }
        else if (mode.Contains("ignored")) {
            File.AppendAllText(@".git\info\exclude", "episodic/review-digest-*.md\r\n");
            File.WriteAllText(@"episodic\review-digest-selftest.md", "body\r\n");
        }
        else if (mode.Contains("plant")) {
            File.AppendAllText(@"harness\review-job\prompt.md", "planted\r\n");
            File.WriteAllText(@"harness\next-week.ps1", "evil\r\n");
            File.WriteAllText(@".claude\settings.local.json", "{\"hooks\": \"planted\"}");
            File.WriteAllText(@"episodic\review-digest-selftest.md", "body\r\n");
        }
        else if (mode.Contains("digest")) { File.WriteAllText(@"episodic\review-digest-selftest.md", "body\r\n"); }
        else { Console.WriteLine("nothing new to report"); }
        return 0;
    }
}
'@
    $fakeExe = Join-Path $tmp 'fake-engine.exe'
    Add-Type -TypeDefinition $fakeSrc -OutputAssembly $fakeExe -OutputType ConsoleApplication
    function New-Claude($f, $mode) { Copy-Item $fakeExe $f }
    function ArgvOf($state) { $p = "$state\argv.txt"; if (Test-Path $p) { ,([System.IO.File]::ReadAllText($p).Split([char]0)) } else { ,@() } }
    # True when the flag is immediately followed by the value somewhere in argv.
    function HasPair($argv, $flag, $value) { for ($i = 0; $i -lt $argv.Count - 1; $i++) { if ($argv[$i] -eq $flag -and $argv[$i + 1] -eq $value) { return $true } }; return $false }
    function Show($argv) { ($argv | ForEach-Object { "[$_]" }) -join ' ' }
    function Invoke-E2E($v, $fake, $max, $state, $mem) {
        New-Item -ItemType Directory -Path $state -Force | Out-Null
        $env:MESOSPHERE_VAULT = $v; $env:MESOSPHERE_CLAUDE = $fake; $env:MESOSPHERE_MAX_SECONDS = "$max"
        $env:MESOSPHERE_STATE = $state; $env:MESOSPHERE_MEMORY_ROOT = $mem; $env:MESOSPHERE_SELFTEST_OUT = $state
        # MESOSPHERE_PROMPT is withheld from the child: it points this suite's sweep checks
        # at the real prompt, and inherited it would make the wrapper read that instead
        # of the throwaway vault's, leaving its own default derivation untested.
        $keepPrompt = $env:MESOSPHERE_PROMPT; Remove-Item Env:MESOSPHERE_PROMPT -ErrorAction SilentlyContinue
        $out = (& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here 'run-review.ps1') 2>&1) -join "`n"
        $rc = $LASTEXITCODE
        if ($keepPrompt) { $env:MESOSPHERE_PROMPT = $keepPrompt }
        return [pscustomobject]@{ Rc = $rc; Out = $out }
    }
    function StatusOf($state) { $f = Get-ChildItem "$state\logs" -Filter 'status-*.txt' | Select-Object -First 1; if ($f) { (Get-Content $f.FullName -Raw).Trim() } else { '(none)' } }
    function InflightLeft($state) { @(Get-ChildItem "$state\logs" -Filter 'inflight-*.marker' -ErrorAction SilentlyContinue).Count -gt 0 }
    # Every line Log writes is also printed, timestamp first, so the run's own output
    # names the lines that should have reached a file.
    function LogLinesOf($out) { @(($out -split "`n") | ForEach-Object { $_.TrimEnd() } | Where-Object { $_ -match '^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} ' }) }
    function FileLines($p) { if (Test-Path $p) { @(Get-Content $p -Encoding UTF8 | ForEach-Object { $_.TrimEnd() }) } else { @() } }
    function Missing($want, $have) { @($want | Where-Object { $have -notcontains $_ }) }
    function RunLog($state, $suffix) { Get-ChildItem "$state\logs" -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -match "^run-\d{4}-\d{2}-\d{2}$suffix$" } | Select-Object -First 1 }
    $emptyMem = Join-Path $tmp 'nomem'; New-Item -ItemType Directory -Path $emptyMem | Out-Null

    # e2e 1: a digest is written while an interactive session has unrelated work
    # staged. The commit must carry the digest and nothing else, and be pushed.
    # The memory root holds a junctioned store, whose target must be granted.
    $v1 = Join-Path $tmp 'v1'; New-Vault $v1; New-Claude "$tmp\claude-digest.exe" 'digest'
    Set-Content "$v1\other-work.md" "someone else's work" -Encoding utf8; G -C $v1 add other-work.md
    $r = Invoke-E2E $v1 "$tmp\claude-digest.exe" 60 "$tmp\s1" $proj
    $landed = (& git.exe -C $v1 show --name-only --format= HEAD) -join ' '
    $still  = (& git.exe -C $v1 diff --cached --name-only) -join ' '
    $unpushed = (& git.exe -C $v1 rev-list --count origin/main..main)
    Check 'commit-pathspec' ($r.Rc -eq 0 -and $landed -eq 'episodic/review-digest-selftest.md' -and $still -eq 'other-work.md' -and
                             $unpushed -eq '0' -and (StatusOf "$tmp\s1") -match '^committed ' -and -not (InflightLeft "$tmp\s1")) "rc=$($r.Rc) landed='$landed' still-staged='$still' unpushed=$unpushed status='$(StatusOf "$tmp\s1")' out=$($r.Out)"

    $argv1 = ArgvOf "$tmp\s1"
    Check 'link-targets-granted' ((HasPair $argv1 '--add-dir' $proj) -and (HasPair $argv1 '--add-dir' $tgt)) "claude was given: $(Show $argv1)"

    # The claude the wrapper launches must carry the review job marker, or the Stop
    # hook walls it in behind any interactive session's open ledgers.
    $markerSeen = ((Get-Content "$tmp\s1\marker.txt" -Raw -ErrorAction SilentlyContinue) -as [string])
    if ($markerSeen) { $markerSeen = $markerSeen.Trim() }
    Check 'review-job-marker' ($markerSeen -eq '[1]') "claude saw MESOSPHERE_REVIEW_JOB as '$markerSeen' (want [1])"

    # The prompt is the last argument and arrives byte for byte, quotes and backslashes
    # included, with the date and mining lines the wrapper appends.
    $wantPrompt = "$fakePrompt`r`n`n`nToday's date for the digest filename and frontmatter: $(Get-Date -Format 'yyyy-MM-dd')`n`nMonthly mining for this run: mining: not configured"
    $lastArg = if ($argv1.Count) { $argv1[-1] } else { '(none)' }
    Check 'prompt-as-argument' ($argv1.Count -ge 2 -and $lastArg -ceq $wantPrompt) "last argument: [$lastArg] want: [$wantPrompt]"

    # MESOSPHERE_ADAPTER unset means claude-code: its flags, in order, right before the prompt.
    $tail1 = if ($argv1.Count -ge 4) { $argv1[-4..-2] -join ' ' } else { '' }
    Check 'adapter-default' ($tail1 -ceq '-p --permission-mode acceptEdits') "flags before the prompt: '$tail1', all: $(Show $argv1)"

    $logFile = Get-ChildItem "$tmp\s1\logs" -Filter 'run-*.log' | Select-Object -First 1
    $bytes = if ($logFile) { [System.IO.File]::ReadAllBytes($logFile.FullName) } else { @() }
    Check 'log-utf8' ($bytes.Count -gt 0 -and -not ($bytes -contains 0)) "log has $($bytes.Count) bytes, NUL present (UTF-16): $($bytes -contains 0)"

    # e2e 2: nothing written is a quiet week, exit 0, no commit.
    $v2 = Join-Path $tmp 'v2'; New-Vault $v2; New-Claude "$tmp\claude-nothing.exe" 'nothing'
    $before = & git.exe -C $v2 rev-list --count HEAD
    $r = Invoke-E2E $v2 "$tmp\claude-nothing.exe" 60 "$tmp\s2" $emptyMem
    $after = & git.exe -C $v2 rev-list --count HEAD
    Check 'quiet-week' ($r.Rc -eq 0 -and $before -eq $after -and (StatusOf "$tmp\s2") -match '^nothing-new' -and -not (InflightLeft "$tmp\s2")) "rc=$($r.Rc) commits $before->$after status='$(StatusOf "$tmp\s2")' out=$($r.Out)"

    # The same unlocked run wrote every line to the main log and nothing anywhere else.
    $want2 = LogLinesOf $r.Out; $main2 = RunLog "$tmp\s2" '\.log'; $fb2 = RunLog "$tmp\s2" '\.fallback\.log'
    $miss2 = Missing $want2 $(if ($main2) { FileLines $main2.FullName } else { @() })
    Check 'log-unlocked' ($want2.Count -ge 3 -and $main2 -and $miss2.Count -eq 0 -and -not $fb2 -and (StatusOf "$tmp\s2") -notmatch 'fallback') "printed $($want2.Count) lines, missing from main log: $($miss2 -join ' | '), fallback file: $([bool]$fb2), status='$(StatusOf "$tmp\s2")'"

    # e2e 6, log-locked: the run's log is held with no sharing for the whole run, as a
    # tail -F, antivirus or an editor can. The run must still finish, every line must
    # reach the fallback beside the log, and the status file must say so and where.
    $v6 = Join-Path $tmp 'v6'; New-Vault $v6
    $day6 = Get-Date -Format 'yyyy-MM-dd'
    New-Item -ItemType Directory -Path "$tmp\s6\logs" -Force | Out-Null
    $log6 = "$tmp\s6\logs\run-$day6.log"; $fb6 = "$tmp\s6\logs\run-$day6.fallback.log"
    $hold6 = [System.IO.File]::Open($log6, 'OpenOrCreate', 'ReadWrite', 'None')
    try { $r = Invoke-E2E $v6 "$tmp\claude-nothing.exe" 60 "$tmp\s6" $emptyMem } finally { $hold6.Dispose() }
    # Printed lines are not the whole log (Invoke-Git logs git's output but its caller
    # discards the printed copy), so the reference is the unlocked run in e2e 2, same
    # fake claude: its main log must equal this fallback line for line, once the
    # timestamp is cut and each vault path is made neutral.
    function Norm($lines, $v) { @($lines | Where-Object { $null -ne $_ } | ForEach-Object { $_.Substring([Math]::Min(20, $_.Length)) -replace [regex]::Escape($v), 'VAULT' }) }
    $fbl6 = FileLines $fb6; $want6 = LogLinesOf $r.Out; $miss6 = Missing $want6 $fbl6
    $ref6 = Norm $(if ($main2) { FileLines $main2.FullName } else { @() }) $v2; $got6 = Norm $fbl6 $v6
    $same6 = $ref6.Count -ge 3 -and ($ref6 -join "`n") -eq ($got6 -join "`n")
    $st6 = StatusOf "$tmp\s6"; $main6 = (Get-Item $log6).Length
    $named6 = $st6 -match ("(?m)^log: $($fbl6.Count) line\(s\) could not be written to the run log and went to the fallback " + [regex]::Escape($fb6) + '\s*$')
    Check 'log-locked' ($r.Rc -eq 0 -and $st6 -match '^nothing-new' -and -not (InflightLeft "$tmp\s6") -and $want6.Count -ge 3 -and
                        $miss6.Count -eq 0 -and $same6 -and $main6 -eq 0 -and $named6) "rc=$($r.Rc) printed $($want6.Count) lines, missing from fallback: $($miss6.Count) ($($miss6 -join ' | ')), unlocked log ($($ref6.Count)) matches fallback ($($got6.Count)): $same6, main log bytes=$main6, status='$st6'"

    # e2e 3: a digest git cannot see. The old wrapper asked git what was on disk, so
    # an ignored digest read as a quiet week. It must be a hard failure.
    $v3 = Join-Path $tmp 'v3'; New-Vault $v3; New-Claude "$tmp\claude-ignored.exe" 'ignored'
    $before = & git.exe -C $v3 rev-list --count HEAD
    $r = Invoke-E2E $v3 "$tmp\claude-ignored.exe" 60 "$tmp\s3" $emptyMem
    $after = & git.exe -C $v3 rev-list --count HEAD
    Check 'unstaged-ignored-digest' ($r.Rc -eq 1 -and $before -eq $after -and (Test-Path "$v3\episodic\review-digest-selftest.md") -and
                                     (StatusOf "$tmp\s3") -match '^failed .*written but nothing staged') "rc=$($r.Rc) (want 1) commits $before->$after status='$(StatusOf "$tmp\s3")' out=$($r.Out)"

    # e2e 4: the watchdog fires. A killed run must still record an outcome.
    $v4 = Join-Path $tmp 'v4'; New-Vault $v4; New-Claude "$tmp\claude-hang.exe" 'hang'
    $r = Invoke-E2E $v4 "$tmp\claude-hang.exe" 2 "$tmp\s4" $emptyMem
    Check 'watchdog-outcome' ($r.Rc -ne 0 -and (StatusOf "$tmp\s4") -match '^failed .*watchdog' -and -not (InflightLeft "$tmp\s4")) "rc=$($r.Rc) status='$(StatusOf "$tmp\s4")' out=$($r.Out)"

    # e2e 5: mining.json present. run-review.ps1 must run history.py BEFORE claude and
    # hand its one line to the agent; the extract lands in the workdir outside the
    # vault and nothing from it reaches a commit. The interpreter is MESOSPHERE_PYTHON as
    # inherited, else python. Written without a BOM, which json.loads would refuse.
    $v5 = Join-Path $tmp 'v5'; New-Vault $v5
    New-Item -ItemType Directory -Path "$v5\harness", "$tmp\hist5\-repo" -Force | Out-Null
    Copy-Item $realHistory "$v5\harness\history.py"
    $utf8 = New-Object System.Text.UTF8Encoding $false; $fwd = $tmp -replace '\\', '/'
    $now5 = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    [System.IO.File]::WriteAllText("$tmp\hist5\-repo\s.jsonl", "{`"type`":`"user`",`"timestamp`":`"$now5`",`"message`":{`"role`":`"user`",`"content`":`"a fresh owner message long enough to mine`"}}`n", $utf8)
    [System.IO.File]::WriteAllText("$v5\mining.json", "{`"every_days`":30,`"max_chars`":100000,`"workdir`":`"$fwd/mine5`",`"start_from`":`"2000-01-01`",`"sources`":[{`"type`":`"claude-code`",`"path`":`"$fwd/hist5`"}]}", $utf8)
    G -C $v5 add -A; G -C $v5 commit -q -m 'mining config'; G -C $v5 push -q
    $r = Invoke-E2E $v5 "$tmp\claude-nothing.exe" 60 "$tmp\s5" $emptyMem
    $argv5 = ArgvOf "$tmp\s5"
    $prompt5 = if ($argv5.Count) { $argv5[-1] } else { '' }
    $extract5 = @(Get-ChildItem "$tmp\mine5" -Filter 'new-*.jsonl' -ErrorAction SilentlyContinue)
    $dirty5   = (& git.exe -C $v5 status --porcelain) -join ' '
    $inVault5 = @(Get-ChildItem $v5 -Recurse -Force -Filter 'new-*.jsonl' -ErrorAction SilentlyContinue | Where-Object { $_.FullName -notmatch '\\\.git\\' })
    $tail5 = if ($prompt5) { ($prompt5.Trim() -split "`n")[-1] } else { '(none)' }
    Check 'mining-handoff' ($r.Rc -eq 0 -and $prompt5 -match 'Monthly mining for this run: mining: 1 new messages' -and
                            $extract5.Count -eq 1 -and -not $dirty5 -and $inVault5.Count -eq 0) "rc=$($r.Rc) prompt tail='$tail5' extract=$($extract5.Count) status='$dirty5' in vault=$($inVault5.Count) out=$($r.Out)"
    # The extract sits outside the vault, so the headless run is refused reading it
    # unless the workdir gets its own --add-dir, as the fake claude's arguments show.
    Check 'mining-workdir-granted' (HasPair $argv5 '--add-dir' "$tmp\mine5") "claude was given: $(Show $argv5)"

    # e2e 7, mining-workdir-tilde: a workdir written as ~/... is expanded against
    # USERPROFILE, as history.py's expanduser does, and never made as a literal ~
    # folder. USERPROFILE points at a temp folder for this run only, so nothing in
    # the real profile is touched. This proves the outcome, not the wrapper's own ~
    # line: Windows PowerShell 5.1 takes $HOME from USERPROFILE, so its paths expand
    # ~ to the same folder without that line, and deleting it alone passes here.
    $v7 = Join-Path $tmp 'v7'; New-Vault $v7; $prof7 = Join-Path $tmp 'profile7'
    New-Item -ItemType Directory -Path "$v7\harness", $prof7 -Force | Out-Null
    Copy-Item $realHistory "$v7\harness\history.py"
    [System.IO.File]::WriteAllText("$v7\mining.json", "{`"every_days`":30,`"max_chars`":100000,`"workdir`":`"~/mine7`",`"start_from`":`"2000-01-01`",`"sources`":[{`"type`":`"claude-code`",`"path`":`"$fwd/hist5`"}]}", $utf8)
    G -C $v7 add -A; G -C $v7 commit -q -m 'mining config'; G -C $v7 push -q
    $keepProfile = $env:USERPROFILE; $env:USERPROFILE = $prof7
    try { $r = Invoke-E2E $v7 "$tmp\claude-nothing.exe" 60 "$tmp\s7" $emptyMem } finally { $env:USERPROFILE = $keepProfile }
    $argv7 = ArgvOf "$tmp\s7"
    $want7 = Join-Path $prof7 'mine7'
    # A literal ~ folder would land beside whatever the wrapper or history.py had as
    # its working directory: the vault, the state folder, this folder, or the profile.
    $tilde7 = @(Get-ChildItem $tmp -Recurse -Force -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -eq '~' } | ForEach-Object { $_.FullName })
    if ([System.IO.Directory]::Exists((Join-Path $here '~'))) { $tilde7 += Join-Path $here '~' }
    Check 'mining-workdir-tilde' ($r.Rc -eq 0 -and (HasPair $argv7 '--add-dir' $want7) -and
                                  [System.IO.Directory]::Exists($want7) -and $tilde7.Count -eq 0) "rc=$($r.Rc) want --add-dir `"$want7`", claude was given: $(Show $argv7) folder made there: $([System.IO.Directory]::Exists($want7)) literal ~ folders: $($tilde7 -join ' | ')"

    # e2e 8, adapter-<name>: every shipped adapter, as ../macos/selftest.sh checks them.
    # MESOSPHERE_ADAPTER alone picks the adapter file, and the wrapper must start that
    # engine with the adapter's flags, in order, right before the prompt as the last
    # argument. Only claude-code declares a grant flag, so only it gets grants ahead.
    $flagsOf = [ordered]@{
        'claude-code' = @('-p', '--permission-mode', 'acceptEdits')
        'codex'       = @('exec', '-s', 'workspace-write', '--skip-git-repo-check')
        'gemini'      = @('--approval-mode', 'auto_edit', '-p')
        'antigravity' = @('--add-dir', 'VAULT', '--mode', 'accept-edits', '-p')
    }
    $bins = 'MESOSPHERE_CODEX', 'MESOSPHERE_GEMINI', 'MESOSPHERE_CURSOR', 'MESOSPHERE_AGY'
    foreach ($ad in $flagsOf.Keys) {
        $va = Join-Path $tmp "ad-$ad"; New-Vault $va; $fa = "$tmp\fake-$ad.exe"; New-Claude $fa 'nothing'
        $env:MESOSPHERE_ADAPTER = $ad; foreach ($b in $bins) { [Environment]::SetEnvironmentVariable($b, $fa) }
        try { $r = Invoke-E2E $va $fa 60 "$tmp\s-ad-$ad" $emptyMem }
        finally { Remove-Item Env:MESOSPHERE_ADAPTER -ErrorAction SilentlyContinue; foreach ($b in $bins) { [Environment]::SetEnvironmentVariable($b, $null) } }
        $want = @($flagsOf[$ad] | ForEach-Object { if ($_ -eq 'VAULT') { $va } else { $_ } })
        $got = ArgvOf "$tmp\s-ad-$ad"; $n = $want.Count
        $flagsGot = if ($got.Count -gt $n) { $got[(-1 - $n)..-2] } else { @() }
        $pre = $got.Count - $n - 1
        $preOk = if ($ad -eq 'claude-code') { $pre -eq 2 -and $got[0] -eq '--add-dir' -and $got[1] -eq $emptyMem } else { $pre -eq 0 }
        Check "adapter-$ad" ($r.Rc -eq 0 -and (($flagsGot -join "`n") -ceq ($want -join "`n")) -and $preOk -and $got[-1] -ceq $wantPrompt) "rc=$($r.Rc) got: $(Show $got) want flags: $(Show $want) then the prompt out=$($r.Out)"
    }

    # e2e 8b, adapter-cursor-unsupported: Cursor's review-job.ps1 throws, because its only
    # headless write mode allows any command. The run must refuse, record the refusal as
    # its outcome, and never start the engine (2026-10-28).
    $vc = Join-Path $tmp 'ad-cursor-x'; New-Vault $vc; $fc = "$tmp\fake-cursor-x.exe"; New-Claude $fc 'digest'
    $env:MESOSPHERE_ADAPTER = 'cursor'; $env:MESOSPHERE_CURSOR = $fc
    try { $r = Invoke-E2E $vc $fc 60 "$tmp\s-cursor-x" $emptyMem }
    finally { Remove-Item Env:MESOSPHERE_ADAPTER, Env:MESOSPHERE_CURSOR -ErrorAction SilentlyContinue }
    Check 'adapter-cursor-unsupported' ($r.Rc -eq 1 -and (StatusOf "$tmp\s-cursor-x") -match '^failed .*not supported' -and -not (Test-Path "$tmp\s-cursor-x\argv.txt") -and -not (InflightLeft "$tmp\s-cursor-x")) "rc=$($r.Rc) (want 1) status='$(StatusOf "$tmp\s-cursor-x")' engine ran: $(Test-Path "$tmp\s-cursor-x\argv.txt") out=$($r.Out)"

    # e2e 8c, review-dirty-refused: an uncommitted change under harness/ refuses the run
    # before the engine starts, because the job must never run harness code nobody
    # committed (2026-10-28).
    $vd = Join-Path $tmp 'vdirty'; New-Vault $vd; New-Claude "$tmp\claude-digest-d.exe" 'digest'
    Add-Content "$vd\harness\review-job\prompt.md" 'edited by hand' -Encoding utf8
    $r = Invoke-E2E $vd "$tmp\claude-digest-d.exe" 60 "$tmp\s-dirty" $emptyMem
    Check 'review-dirty-refused' ($r.Rc -eq 1 -and (StatusOf "$tmp\s-dirty") -match 'uncommitted changes under harness/ or \.claude/' -and -not (Test-Path "$tmp\s-dirty\argv.txt")) "rc=$($r.Rc) status='$(StatusOf "$tmp\s-dirty")' engine ran: $(Test-Path "$tmp\s-dirty\argv.txt")"

    # e2e 8d, review-restores-tracked: whatever the run does to harness/ or .claude/,
    # tracked, untracked or ignored, is put back, and the digest still lands.
    $vr = Join-Path $tmp 'vrestore'; New-Vault $vr
    Set-Content "$vr\.gitignore" '.claude/settings.local.json' -Encoding ascii
    G -C $vr add .gitignore; G -C $vr commit -q -m ignore; G -C $vr push -q
    New-Item -ItemType Directory -Path "$vr\.claude" -Force | Out-Null
    [System.IO.File]::WriteAllText("$vr\.claude\settings.local.json", '{"hooks": {}}')
    $promptBefore = [System.IO.File]::ReadAllText("$vr\harness\review-job\prompt.md")
    New-Claude "$tmp\claude-plant.exe" 'plant'
    $r = Invoke-E2E $vr "$tmp\claude-plant.exe" 60 "$tmp\s-restore" $emptyMem
    $landed = (& git.exe -C $vr show --name-only --format='' HEAD) -join ' '
    Check 'review-restores-tracked' ($r.Rc -eq 0 -and [System.IO.File]::ReadAllText("$vr\harness\review-job\prompt.md") -eq $promptBefore -and -not (Test-Path "$vr\harness\next-week.ps1") -and [System.IO.File]::ReadAllText("$vr\.claude\settings.local.json") -eq '{"hooks": {}}' -and $landed -match 'review-digest-' -and $r.Out -match 'were restored') "rc=$($r.Rc) planted=$(Test-Path "$vr\harness\next-week.ps1") settings='$([System.IO.File]::ReadAllText("$vr\.claude\settings.local.json"))' landed='$landed' out=$($r.Out)"

    # e2e 9, batch-shim: an engine that resolves to a .cmd is refused before it runs,
    # because cmd.exe would cut the prompt at its first newline and nothing would say so.
    $v9 = Join-Path $tmp 'v9'; New-Vault $v9; $shim = "$tmp\claude-shim.cmd"
    Set-Content $shim "@echo off`r`necho ran> `"%MESOSPHERE_SELFTEST_OUT%\argv.txt`"" -Encoding ascii
    $r = Invoke-E2E $v9 $shim 60 "$tmp\s9" $emptyMem
    Check 'batch-shim' ($r.Rc -eq 1 -and (StatusOf "$tmp\s9") -match '^failed .*batch file' -and -not (Test-Path "$tmp\s9\argv.txt") -and -not (InflightLeft "$tmp\s9")) "rc=$($r.Rc) (want 1) status='$(StatusOf "$tmp\s9")' shim ran: $(Test-Path "$tmp\s9\argv.txt")"

    # arg-refusal, against a copy truncated at the guard so the body cannot run.
    $lines = Get-Content (Join-Path $here 'run-review.ps1')
    $end = [array]::IndexOf($lines, ($lines | Where-Object { $_ -match '^\$ErrorActionPreference' } | Select-Object -First 1))
    $stub = Join-Path $tmp 'guard.ps1'
    Set-Content $stub (($lines[0..($end - 1)] + "'BODY RAN'") -join "`r`n") -Encoding utf8
    $gOut = (& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $stub -WhatIfOnly 2>&1) -join ' '; $gRc = $LASTEXITCODE
    $cOut = (& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $stub 2>&1) -join ' '; $cRc = $LASTEXITCODE
    Check 'arg-refusal' ($end -gt 0 -and $gRc -eq 64 -and $gOut -match 'REFUSED' -and $gOut -notmatch 'BODY RAN' -and $cRc -eq 0 -and $cOut -match 'BODY RAN') "with a flag: rc=$gRc out=$gOut | with none: rc=$cRc out=$cOut"
}
catch {
    Bad 'selftest-crashed' "$($_.Exception.Message) at line $($_.InvocationInfo.ScriptLineNumber)"
}
finally {
    foreach ($k in $savedEnv.Keys) { [Environment]::SetEnvironmentVariable($k, $savedEnv[$k]) }
    Set-Location ([System.IO.Path]::GetTempPath())
    # Junctions first, so a recursive delete can never walk through one.
    Get-ChildItem $tmp -Recurse -Force -Attributes ReparsePoint -ErrorAction SilentlyContinue | ForEach-Object { cmd.exe /c rmdir "$($_.FullName)" 2>&1 | Out-Null }
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
}

if ($script:failed -eq 0) { Write-Output "SELFTEST OK ($script:count checks)"; exit 0 }
Write-Output "SELFTEST FAILED ($script:failed of $script:count checks)"
exit 1
