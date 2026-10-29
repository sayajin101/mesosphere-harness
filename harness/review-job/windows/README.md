# The weekly review job on Windows

```
windows/
  run-review.ps1    the job itself, run by Task Scheduler from inside the clone
  heartbeat.ps1     proof of life helpers, functions only, dot sourced
  selftest.ps1      unit checks plus end to end runs of the real run-review.ps1
  mutationtest.ps1  breaks each fix in a copy and requires the selftest to fail
```

These four files are CRLF on disk, on every machine, while everything else in the
vault is LF: Windows script files are always CRLF (Windows PowerShell expects it), and
`.gitattributes` enforces it with `eol=crlf`. Git stores them LF internally, so a
diff never shows the endings.

## Deploying

The task runs the committed file in the clone, like the Mac's launchd job, so
there is no copy to drift. Point the `mesosphere-review` task's action at:

```
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<clone>\harness\review-job\windows\run-review.ps1"
```

Register it like this (example: **Thursdays 19:00**; pick any slot the machine is usually awake): weekly trigger, `ExecutionTimeLimit PT2H`, `MultipleInstances IgnoreNew`, `StartWhenAvailable`.

```
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument '-NoProfile -ExecutionPolicy Bypass -File "<clone>\harness\review-job\windows\run-review.ps1"'
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Thursday -At 19:00
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew -StartWhenAvailable
Register-ScheduledTask -TaskName "mesosphere-review" -Action $action -Trigger $trigger -Settings $settings
```

Replace `<clone>` with the absolute path of the clone. If a macOS machine also runs the job, give it a different day; the stagger is the
point. Verify by reading the schedule back **out of Task Scheduler**, never out of
a file:

```
powershell -NoProfile -Command "$t = Get-ScheduledTask -TaskName mesosphere-review; $t.Actions[0].Arguments; $t.Triggers[0].DaysOfWeek; $t.Triggers[0].StartBoundary"
```

`DaysOfWeek` is a bitmask: 1 is Sunday, 2 Monday, 4 Tuesday, 8 Wednesday, 16 Thursday, 32 Friday, 64 Saturday.

Same env overrides as the Mac, with Windows defaults: `MESOSPHERE_VAULT` (derived,
three levels up), `MESOSPHERE_PROMPT`, `MESOSPHERE_ADAPTER` (`claude-code`), which picks
`harness\adapters\<adapter>\review-job.ps1`, `MESOSPHERE_ADAPTERS_DIR` (the clone's
`harness\adapters`, overridden only by the mutation test's copies), `MESOSPHERE_MAX_SECONDS` (6900), `MESOSPHERE_STATE`
(`~\schedules\mesosphere-review`), plus `MESOSPHERE_MEMORY_ROOT` (`~\.claude\projects`)
and `MESOSPHERE_PYTHON` (`python`), the interpreter for the monthly mining step that
runs `harness/history.py` before the engine whenever `mining.json` sits at the vault root.
Set `MESOSPHERE_PYTHON` once to the machine profile's absolute `python.exe`, as a user
environment variable the scheduled task inherits:
`[Environment]::SetEnvironmentVariable('MESOSPHERE_PYTHON', '<absolute python.exe>', 'User')`.
Bare `python` can be the Microsoft Store stub, and the mining step then fails (the
log and the digest say so). The macOS plist carries the same variable.

The engine is the adapter's business, as on the Mac. Its `review-job.ps1` sets
`$AgentCmd`, the headless command without the prompt, as an array, with the same
flags as the `review-job.sh` beside it and its own binary override
(`MESOSPHERE_CLAUDE`, `MESOSPHERE_CODEX`, `MESOSPHERE_GEMINI`, `MESOSPHERE_CURSOR`,
`MESOSPHERE_AGY`). It may set `$AddDirFlag`; today only claude-code does, so only it
is granted the memory root, link targets and mining workdir. The wrapper starts
the binary itself under the watchdog, with the grants first, then the adapter's
flags, then the prompt as the last argument. An engine that resolves to a `.cmd`
or `.bat` shim is refused (`batch-shim`), because cmd.exe cuts a multi line
argument at its first newline.

## Testing

```
powershell -NoProfile -ExecutionPolicy Bypass -File selftest.ps1       # about 70s
powershell -NoProfile -ExecutionPolicy Bypass -File mutationtest.ps1   # minutes
```

`python harness/verify.py` runs the selftest on every invocation on win32, and
`--wrappers-full` adds the mutation test, exactly as it runs the zsh suites on the
Mac. Both suites are slow because `powershell.exe` can take several seconds to start on a
machine and each selftest starts seven of them.

`symlink-sweep` reports SKIP, not OK, on an account that cannot create symlinks
(it needs admin or Developer Mode). That is a gap said out loud: junctions are
proven here, and creating a junction needs no special rights.

## Every difference from macos/run.sh

Compared line by line on 2026-09-29. **Ported** means Windows now matches the
Mac; **kept** means the difference stays on purpose.

| # | What differed | Now | Why |
| --- | --- | --- | --- |
| 1 | Vault and claude paths hardcoded to one machine | Ported | Vault derived from the script's location, claude found on `PATH`, both overridable, so the file can be committed |
| 2 | The wrapper lived in `~/schedules`, outside the clone | Ported | A copy outside the clone is how the prompt drifted for a week in August |
| 3 | "A digest is on disk" was asked of git (diff plus untracked), so a digest git could not see, such as an ignored one, read as a quiet week | Ported | Fresh digests are now found on the filesystem against `run-start.ref`, stamped at start, as on the Mac. Written but not staged is a hard failure, proven by `unstaged-ignored-digest` |
| 4 | Any marker from another date was deleted and today's was overwritten, so a live run could be clobbered | Ported | `Test-RunSlot` refuses a marker whose pid is alive and younger than the bound, exit 75 |
| 5 | No watchdog in the script: Task Scheduler's PT2H kill left the marker behind, and the kill was only noticed a week later | Ported, with a different number | The in-script bound is 6900s, not the Mac's 7200, so it fires before Task Scheduler's PT2H and records the outcome itself. The whole process tree is killed |
| 6 | `git pull` relied on config for merge only | Ported | `--no-rebase` is explicit, per contract 3.6 |
| 7 | A `-WhatIfOnly` switch; unknown arguments were refused by `[CmdletBinding()]` but with exit 0 | Ported | Every argument is refused with exit 64 by reading `$args`, proven in isolation first. The selftest is the safe way to exercise the job now |
| 8 | Logs were UTF-16 (the Windows PowerShell 5.1 default for `Tee-Object` and `>>`), so a log could not be searched with grep | Ported | Logs are UTF-8, proven by `log-utf8` |
| 9 | Selftest had 9 unit checks and no end to end run; no mutation test | Ported | Unit checks plus end to end runs of the real wrapper against a throwaway vault and a fake engine, plus a mutation test with an unmutated control |
| 10 | The prompt goes in as the last argument | Reversed 2026-10-27 | It went in on stdin until the move to engine neutral adapters: Gemini's and Antigravity's `-p` takes the prompt as its value, so stdin cannot reach them. Each argument is quoted to the C runtime rules by `ConvertTo-NativeArg`, the command line is refused past 32000 characters, and `prompt-as-argument` proves a prompt with quotes and backslashes arrives byte for byte |
| 11 | `--add-dir` grants the memory root | Kept, and extended | The Windows Read tool was denied there without it (2026-08-20). A linked store's target sits outside the root, so each junction or symlink target is granted too, proven by `link-targets-granted`. The Mac needs neither |
| 12 | A dead run's marker is handed to the digest prompt as a Housekeeping input | Kept, Mac lacks it | Otherwise it reaches only a log nobody reads. A candidate for the Mac wrapper, not ported there from here |
| 13 | State layout: dated `run-DATE.log`, `status-DATE.txt`, `inflight-DATE.marker` under `logs\`; the Mac keeps single `last-run.status`, `inflight` and `run-start.ref` files | Kept | The dated history stays continuous. `run-start.ref` was added |
| 14 | Outcome words: `committed`, `nothing-new`, `failed` (a failed push is `failed`); the Mac uses `ok`, `no-op`, `fail`, `partial` | Kept | Only the logs and a person read them; renaming would split the history |
| 15 | Stray changes are found with `git diff --name-only` plus untracked files; the Mac uses `git status --porcelain` | Kept | Content aware on purpose, so a checkout's phantom line ending modifications do not cry wolf on every run |
| 16 | Commit scoped to the explicit staged digest paths; the Mac scopes by the digest pattern | Kept | Same effect: nothing staged by another session can ride along, proven by `commit-pathspec` |
| 17 | The date line appended to the prompt | Ported | Now worded exactly as the Mac's |

The two memory sweep fixes live in the shared prompt, not in either wrapper, so
they reach both machines at once. On Windows: Git Bash treats a junction the way
it treats a symlink, so a bare `find` skips a junctioned store silently while
`find -L` follows it (`junction-sweep`, with the bare command as the control that
proves the check can fail). And every sweep command the prompt prescribes is read
only in form, with no `-exec`, `-execdir`, `-ok`, `-delete` or `xargs`
(`sweep-read-only`).

## The state directory stays out of the clone

Same rule as the Mac: markers, status files, logs, a copy of the prompt handed to the
engine, and the engine's own output all live in `~/schedules/mesosphere-review/`, never
in the working tree the job inspects.
