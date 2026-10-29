#!/bin/zsh
# Proof of life for the weekly vault review job. Sourced by run.sh, driven in
# isolation by selftest.sh.
#
# Why this exists. launchd has no ExecutionTimeLimit, so unlike the Windows
# scheduled task this job has no bound outside its own code, and a run that dies
# mid flight leaves exactly the same observable output as a genuinely quiet week:
# nothing. See harness/ENGINEERING.md rule 1 (a mechanism that fails open is
# invisible when it fails) and rule 4 (an empty result is not a clean result).
#
# Everything here writes only inside $HB_DIR, which the selftest points at a
# temp directory, so the selftest is safe to use as a ledger CHECK.

# Never defaults into the clone: runtime state in a git working tree would
# dirty the very tree this job inspects, and could be swept into a commit.
HB_DIR="${HB_DIR:-$HOME/schedules/mesosphere-review}"
HB_INFLIGHT="$HB_DIR/inflight"
HB_STATUS="$HB_DIR/last-run.status"
HB_REF="$HB_DIR/run-start.ref"
HB_POLL="${HB_POLL:-5}"
HB_GRACE="${HB_GRACE:-10}"
HB_MAX_AGE="${HB_MAX_AGE:-7800}"   # watchdog bound plus grace: older than this cannot be a live run

# The vault is derived from the wrapper's own location rather than hardcoded, so
# the identical committed file works from any clone on any machine. The wrapper
# lives at harness/review-job/macos/ inside the clone, which is three levels below
# the repo root. Kept as a pure function with no side effects
# so it can be proven read-only, per harness/ENGINEERING.md rule 3: proving it by
# running the real job would mean a broken derivation writes to the real vault,
# which is exactly what a check may not risk.
hb_derive_vault() { print -r -- "${1:A:h:h:h}" }

# Decide whether this run may take the slot. A marker on disk means one of two
# very different things, and the first version of this function collapsed them:
# it cleared any marker it found, which would have let a second run start
# alongside a live one and destroy the first run's proof of life on the way in.
#
# 0 = no marker, clear to run
# 1 = a dead predecessor's marker was found and cleared, carry it into the status
# 2 = a LIVE run holds the slot, the caller must not start
hb_stale_check() {
  [[ -f "$HB_INFLIGHT" ]] || return 0
  local line pid age
  line="$(cat "$HB_INFLIGHT")"
  pid="${${line#pid=}%% *}"
  age=$(( $(date +%s) - $(stat -f %m "$HB_INFLIGHT") ))
  # A pid can be recycled, so liveness alone is not enough: a marker older than
  # the watchdog bound plus its grace cannot belong to a run still legitimately
  # going, whatever now owns that pid number.
  if [[ -n "$pid" ]] && (( age < HB_MAX_AGE )) && kill -0 "$pid" 2>/dev/null; then
    print -u2 "OCCUPIED: a live run already holds this slot, started ${age}s ago:"
    print -u2 "  $line"
    print -u2 "  Refusing to start a second one. Clearing a live marker would destroy the first run's proof of life."
    return 2
  fi
  print -u2 "STALE: the previous run left an inflight marker and never recorded an outcome:"
  print -u2 "  $line"
  print -u2 "  A killed run and a quiet week look identical without this line. Treating it as a failed run."
  rm -f "$HB_INFLIGHT"
  return 1
}

# Claim the run. The reference file is what later tells us whether a digest was
# actually written during THIS run, independently of anything git reports.
hb_begin() {
  print "pid=$$ started=$(date '+%Y-%m-%d %H:%M:%S') host=$(hostname -s)" > "$HB_INFLIGHT"
  : > "$HB_REF"
  touch -r "$HB_INFLIGHT" "$HB_REF"
}

# The only way the marker is allowed to disappear: an outcome on the record.
hb_end() {
  local outcome="$1"; shift
  print "$(date '+%Y-%m-%d %H:%M:%S') outcome=$outcome detail=${*:-none}" > "$HB_STATUS"
  rm -f "$HB_INFLIGHT"
}

# Run a command under a wall clock bound, because there is no timeout binary on
# this machine and launchd will not impose one. Mirrors the Windows task's
# ExecutionTimeLimit PT2H. Returns 124 when the bound was hit.
hb_watchdog() {
  local secs="$1"; shift
  "$@" &
  local pid=$! waited=0 rc=0
  while (( waited < secs )); do
    kill -0 "$pid" 2>/dev/null || { if wait "$pid"; then rc=0; else rc=$?; fi; return $rc }
    sleep "$HB_POLL"
    (( waited += HB_POLL ))
  done
  print -u2 "WATCHDOG: bound of ${secs}s reached, terminating pid $pid."
  kill -TERM "$pid" 2>/dev/null
  sleep "$HB_GRACE"
  kill -KILL "$pid" 2>/dev/null
  wait "$pid" 2>/dev/null
  return 124
}

# Did this run write a digest, and did git see it? Answers the two questions
# separately, because collapsing them is the bug this replaces: the wrapper read
# an empty index and called it a quiet week while a digest sat on disk.
#
# 0 = a digest was written and is staged, go ahead and commit
# 1 = a digest was written and is NOT staged, hard failure
# 2 = no digest was written this run, a genuinely quiet week
hb_assert_digest() {
  local root="$1" glob="$2" pathspec="$3"
  local fresh staged
  fresh="$(find "$root" -type f -name "$glob" -newer "$HB_REF" 2>/dev/null)"
  staged="$(git diff --cached --name-only -- "$pathspec" 2>/dev/null)"
  if [[ -n "$fresh" && -z "$staged" ]]; then
    print -u2 "MISMATCH: a digest was written during this run but nothing is staged. This is a failure, not a quiet week."
    print -u2 "$fresh"
    return 1
  fi
  [[ -z "$fresh" && -z "$staged" ]] && return 2
  return 0
}
