#!/bin/zsh
# Does selftest.sh actually catch a regression, or does it merely pass?
#
# harness/ENGINEERING.md rule 1: any mechanism whose job is to refuse something
# must be tested by making it actually refuse. selftest.sh is such a mechanism,
# and until this file existed nothing had ever made it fail, so a selftest full
# of vacuous checks would have satisfied its gate exactly as well as a real one.
# Found by the ledger's coverage audit on 2026-08-24, not by writing the tests.
#
# Each mutant breaks exactly one shipped fix in a COPY of this directory, then
# requires the copied selftest to fail. A mutant that survives names a fix that
# is shipped but unprotected. Read only with respect to the real files: nothing
# outside the temp directory is written, and no mutated run.sh is ever pointed
# at the real vault.

HERE="${0:A:h}"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/mesosphere-mutation.XXXXXX")"
# A mutated selftest can hang rather than fail, so every mutant run is bounded.
# A hang is not a kill: it is reported separately, because "the test never
# finished" and "the test caught it" are different facts.
HB_DIR="$TMP" HB_POLL=2 HB_GRACE=2 source "$HERE/heartbeat.sh"
MUTANT_BOUND=70
trap 'rm -rf "$TMP"' EXIT INT TERM

KILLED=0
SURVIVED=0

# The copies sit in a temp folder, outside the clone, so they are told where the
# clone's history.py and adapter file are. Without this every copied selftest
# failed for that reason alone and "killed" every mutant, which proved nothing.
export MESOSPHERE_HISTORY="${HERE:h:h}/history.py"
export MESOSPHERE_AGENT_FILE="${HERE:h:h}/adapters/claude-code/review-job.sh"

# Control first: the UNMUTATED copy must pass. A copy that fails for an unrelated
# reason would make every mutant look killed and the suite look perfect.
CTRL="$TMP/control"; mkdir -p "$CTRL"
cp "$HERE/run.sh" "$HERE/heartbeat.sh" "$HERE/selftest.sh" "$CTRL/"
CRC=0; hb_watchdog "$MUTANT_BOUND" zsh "$CTRL/selftest.sh" >/dev/null 2>&1 || CRC=$?
if (( CRC != 0 )); then
  print -u2 "CONTROL FAILED: the unmutated copy's selftest exited $CRC, so no mutant result would mean anything"
  exit 1
fi
print "control  unmutated copy passes"

mutant() {
  local name="$1" file="$2" expr="$3" D="$TMP/$name"
  mkdir -p "$D"
  cp "$HERE/run.sh" "$HERE/heartbeat.sh" "$HERE/selftest.sh" "$D/"
  if ! sed -i '' "$expr" "$D/$file"; then
    print -u2 "ERROR $name: the mutation could not be applied"
    SURVIVED=$((SURVIVED + 1)); return
  fi
  if ! diff -q "$HERE/$file" "$D/$file" >/dev/null; then
    local rc=0
    hb_watchdog "$MUTANT_BOUND" zsh "$D/selftest.sh" >/dev/null 2>&1 || rc=$?
    if (( rc == 0 )); then
      print -u2 "SURVIVED $name: $file was broken and the selftest still passed"
      SURVIVED=$((SURVIVED + 1))
    elif (( rc == 124 )); then
      print -u2 "HUNG     $name: the selftest never finished, which is not a catch"
      SURVIVED=$((SURVIVED + 1))
    else
      print "KILLED   $name"
      KILLED=$((KILLED + 1))
    fi
  else
    print -u2 "ERROR $name: the mutation changed nothing, so the target has moved"
    SURVIVED=$((SURVIVED + 1))
  fi
}

# One mutant per shipped fix.
mutant arg-guard     run.sh       's|^  exit 64$|  :|'
mutant commit-scope  run.sh       '/^git commit /s| -- "$PATTERN"||'
mutant watchdog-mute run.sh       '/watchdog bound and was terminated/s|^  fail |  : fail |'
mutant marker-stuck  heartbeat.sh '/^hb_end()/,/^}/s|^  rm -f "$HB_INFLIGHT"$|  :|'
mutant assert-blind  heartbeat.sh '/^hb_assert_digest()/,/^}/s|^    return 1$|    return 0|'
mutant live-clobber  heartbeat.sh '/^hb_stale_check()/,/^}/s|^    return 2$|    return 0|'
mutant marker-dropped run.sh      's|^export MESOSPHERE_REVIEW_JOB=1$|:|'
mutant mining-handoff run.sh      's#^Monthly mining for this run: ${MINING}" || RC=$?$#" || RC=$?#'
mutant dirty-guard   run.sh       '/uncommitted changes under harness\/ or .claude\//s|^  fail |  : fail |'
mutant restore-off   run.sh       's|^restore_harness$|:|'
mutant derive-fixed  heartbeat.sh '/^hb_derive_vault()/s|.*|hb_derive_vault() { print -r -- /nowhere }|'

TOTAL=$((KILLED + SURVIVED))
if (( SURVIVED == 0 )); then
  print "MUTATION TEST OK ($KILLED of $TOTAL mutants killed)"
  exit 0
fi
print -u2 "MUTATION TEST FAILED ($SURVIVED of $TOTAL mutants survived)"
exit 1
