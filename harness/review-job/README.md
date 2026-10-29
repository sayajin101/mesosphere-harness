# The weekly review job

The wrapper that runs the learning loop's heartbeat, one directory per OS.
The digest prompt itself is NOT here: it lives one level up at
`prompt.md` beside these folders, deliberately shared by every OS, because a per machine
copy of the prompt is exactly how this job drifted for a week.

```
review-job/
  macos/     run.sh, heartbeat.sh, selftest.sh, mutationtest.sh, plist template
  windows/   run-review.ps1, heartbeat.ps1, selftest.ps1, mutationtest.ps1, see its README
```

## Why the job runs from inside the clone

The scheduler points straight at `macos/run.sh`, or `windows/run-review.ps1`, in the working tree. There is no
copy under `~/schedules`, so there is nothing to drift, which is the same reason
the prompt is read from the clone at run time.

The obvious objection is that the job's own `git pull` rewrites the script while
it is executing. Measured on 2026-08-24 rather than assumed: git replaces a
tracked file by writing a temp file and renaming it into place, so the inode
changes and the running shell keeps its descriptor on the old inode. A script
whose file was replaced two seconds into a four second run still completed on the
old content, with no corruption. The consequence worth knowing is a timing one, not
a safety one: **a wrapper change takes effect on the next run, a prompt change
takes effect on the current one**, because the prompt is read with `cat` after the
pull while the wrapper was already open before it.

## Why runtime state is not in here

The inflight marker, the status file, the start reference and both logs live in
`~/schedules/mesosphere-review/`, outside the clone. State inside the working tree
would dirty the very tree the job inspects for stray changes, and could be swept
into a commit. `MESOSPHERE_STATE` overrides the location.

## Nothing machine specific is committed

`run.sh` derives the vault from its own location through `hb_derive_vault`, three
levels up from `macos/`, so the identical committed file works from any clone path
on any machine. The claude binary is found on `PATH` first. Everything else is an
env override with a portable default:

| Variable | Default |
| --- | --- |
| `MESOSPHERE_VAULT` | derived from the script's own path |
| `MESOSPHERE_PROMPT` | `<vault>/harness/review-job/prompt.md` |
| `MESOSPHERE_CLAUDE` | `claude` on `PATH`, else `$HOME/.local/bin/claude` |
| `MESOSPHERE_MAX_SECONDS` | 7200, matching the Windows task's `ExecutionTimeLimit PT2H` |
| `MESOSPHERE_STATE` | `$HOME/schedules/mesosphere-review` |

The launchd plist is the one file that cannot avoid an absolute path, because
launchd does not expand `$HOME`. So the repo carries
`macos/local.mesosphere-review.plist.template` with `__HOME__`, `__VAULT__`, `__WEEKDAY__`, `__HOUR__`, `__MINUTE__` and `__PYTHON__` as placeholders,
and the live copy in `~/Library/LaunchAgents/` is generated from it per machine.

## Deploying on macOS

```
mkdir -p ~/schedules/mesosphere-review   # launchd does not create the log folder
VAULT="$(cd ../.. && pwd)"   # run from harness/review-job
PYTHON=/absolute/path/to/python3    # the absolute python3 from the machine profile
WEEKDAY=1 HOUR=9 MINUTE=0          # pick a slot the machine is usually awake: launchd weekday 0 or 7 is Sunday, 1 Monday ... 6 Saturday
sed -e "s|__HOME__|$HOME|g" -e "s|__VAULT__|$VAULT|g" -e "s|__WEEKDAY__|$WEEKDAY|g" \
    -e "s|__HOUR__|$HOUR|g" -e "s|__MINUTE__|$MINUTE|g" -e "s|__PYTHON__|$PYTHON|g" macos/local.mesosphere-review.plist.template \
  > ~/Library/LaunchAgents/local.mesosphere-review.plist
plutil -lint ~/Library/LaunchAgents/local.mesosphere-review.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/local.mesosphere-review.plist
```

The generated plist must carry an `EnvironmentVariables` block with `MESOSPHERE_PYTHON` set to the machine profile's absolute python3 (the template has it, filled from `__PYTHON__`): launchd's minimal PATH may not find any python3, and the mining step needs one. The agent checks the block is in the generated plist before loading it.

If the Mac is asleep at the chosen time, launchd runs the job once when it wakes. If the job cannot find `claude` under launchd's minimal PATH, set `MESOSPHERE_CLAUDE` to its absolute path (from the machine profile) in the plist's `EnvironmentVariables`.

Then verify by reading the schedule back **out of launchd**, never out of the file,
because the loaded copy and the file on disk are different things:

```
launchctl print gui/$(id -u)/local.mesosphere-review | grep -E "Minute|Hour|Weekday"
```

## Testing

`zsh macos/selftest.sh` drives the real `run.sh` end to end against a throwaway
vault with its own bare origin and a fake claude. It is read only with respect to
the real system, so it is safe as a ledger CHECK.

`zsh macos/mutationtest.sh` breaks each shipped fix in a copy and requires the
selftest to catch it. Run it after touching either script: a selftest that has
never been made to fail is not evidence of anything.

The selftest also runs on **every** `verify.py` invocation, with no flag:

```
python3 harness/verify.py              # notes plus the selftest, about 18s
python3 harness/verify.py --wrappers-full   # adds the 92s mutation test
python3 harness/verify.py --no-wrappers     # skips them, when you know why
```

A ledger HOLD gate asserting "the wrapper tests are green" dies when that ledger
closes, so the claim had no permanent home. `verify.py` is the harness integrity
gate and now carries it. It runs by default rather than behind a flag on purpose:
a flag plus a line here saying a ledger *should* pass it would be an instruction,
read by the same process that decides whether it was followed, which is the form
rejected on 2026-08-21 and the whole reason contract section 9 is a mechanism.
Each machine runs its own OS's suites: on win32 that is the Windows PowerShell
pair in `windows/` (a deliberate choice), and on any other platform
neither applies, so the check warns rather than implying a pass. The
check is proven to refuse, not merely written: `harness/tests/test_wrapper_standing_check.py`
feeds it a red selftest, a red mutation test, a missing suite and an absent
directory, and requires a failure from each.

It is deliberately not wired into `run.sh` itself. The selftest's end to end cases
invoke `run.sh`, so a self check there would recurse without end.
