#!/bin/zsh
# Selftest for the weekly review job.
#
# Safe to use as a ledger CHECK: read only with respect to the real system.
# Everything it writes lands in a temp directory it creates and removes.
#
# The end to end checks drive THIS DIRECTORY'S REAL run.sh, pointed by env at a
# throwaway vault with its own bare origin and a fake claude. Testing a
# reimplementation of the wrapper would prove nothing about the wrapper, which is
# harness/ENGINEERING.md rule 1. The one exception is the argument guard, which
# is exercised against a copy truncated at the guard so that a regression there
# cannot fire the live job. Whether this file would FAIL on a regression is not
# its own claim to make: mutationtest.sh answers that by breaking each fix in a
# copy and requiring this file to catch it.

HERE="${0:A:h}"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/mesosphere-selftest.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT INT TERM

COUNT=0
FAILED=0
ok()  { print "OK $1"; COUNT=$((COUNT + 1)) }
bad() { print -u2 "FAIL $1: $2"; FAILED=1; COUNT=$((COUNT + 1)) }

export HB_DIR="$TMP/hb"
# Cleared, so review-job-marker proves run.sh sets it: inherited from whoever ran this
# suite (the review job itself, say), it would pass with the wrapper's line gone.
unset MESOSPHERE_REVIEW_JOB
export HB_POLL=1
export HB_GRACE=1
mkdir -p "$HB_DIR"
source "$HERE/heartbeat.sh"

# ---------- unit checks over heartbeat.sh ----------

# inflight: begin writes a marker, only end clears it
hb_begin
if [[ -f "$HB_INFLIGHT" ]] && grep -q "pid=" "$HB_INFLIGHT"; then
  hb_end ok "selftest"
  [[ -f "$HB_INFLIGHT" ]] && bad inflight "hb_end left the marker behind" || ok inflight
else
  bad inflight "hb_begin did not write a marker naming the pid"
fi

# status-file: the outcome of the last run is on the record
hb_end ok "pushed a digest"
if [[ -f "$HB_STATUS" ]] && grep -q "outcome=ok" "$HB_STATUS" && grep -q "pushed a digest" "$HB_STATUS"; then
  ok status-file
else
  bad status-file "no status file naming the outcome and its detail"
fi

# stale-detect: a marker from a DEAD run is reported and cleared
print "pid=99999 started=long-ago host=test" > "$HB_INFLIGHT"
S_OUT="$(hb_stale_check 2>&1)"; S_RC=$?
if (( S_RC == 1 )) && [[ "$S_OUT" == *STALE* ]] && [[ ! -f "$HB_INFLIGHT" ]]; then
  hb_stale_check >/dev/null 2>&1 && ok stale-detect || bad stale-detect "reported a stale run with no marker present"
else
  bad stale-detect "rc=$S_RC out=$S_OUT"
fi

# live-refusal: a marker from a LIVE run must NOT be cleared, and must refuse
print "pid=$$ started=now host=test" > "$HB_INFLIGHT"
L_OUT="$(hb_stale_check 2>&1)"; L_RC=$?
if (( L_RC == 2 )) && [[ "$L_OUT" == *OCCUPIED* ]] && [[ -f "$HB_INFLIGHT" ]]; then
  ok live-refusal
else
  bad live-refusal "rc=$L_RC (want 2), marker kept=$([[ -f $HB_INFLIGHT ]] && print yes || print no), out=$L_OUT"
fi
rm -f "$HB_INFLIGHT"

# watchdog: the bound fires, and a normal exit code passes through untouched
W_START=$SECONDS
hb_watchdog 1 zsh -c 'exec sleep 30' >/dev/null 2>&1; W_RC=$?
W_ELAPSED=$((SECONDS - W_START))
hb_watchdog 10 zsh -c 'exit 3' >/dev/null 2>&1; W_PASS=$?
hb_watchdog 10 zsh -c 'exit 0' >/dev/null 2>&1; W_ZERO=$?
if (( W_RC == 124 && W_ELAPSED < 15 && W_PASS == 3 && W_ZERO == 0 )); then
  ok watchdog
else
  bad watchdog "timeout rc=$W_RC after ${W_ELAPSED}s (want 124), passthrough=$W_PASS (want 3), clean=$W_ZERO (want 0)"
fi

# unstaged-guard: written and staged, neither, and written but not staged
UREPO="$TMP/urepo"; mkdir -p "$UREPO/episodic"; cd "$UREPO"
git init -q -b main . ; git config user.email t@localhost; git config user.name t
print old > episodic/review-digest-2020-01-01.md
git add -A >/dev/null; git commit -q -m init
hb_begin
print new > episodic/review-digest-2026-08-24.md
hb_assert_digest "$UREPO/episodic" 'review-digest-*.md' 'episodic/review-digest-*.md' >/dev/null 2>&1; A_UNSTAGED=$?
git add -- 'episodic/review-digest-*.md' >/dev/null
hb_assert_digest "$UREPO/episodic" 'review-digest-*.md' 'episodic/review-digest-*.md' >/dev/null 2>&1; A_STAGED=$?
git commit -q -m tmp -- 'episodic/review-digest-*.md'
hb_begin
hb_assert_digest "$UREPO/episodic" 'review-digest-*.md' 'episodic/review-digest-*.md' >/dev/null 2>&1; A_QUIET=$?
if (( A_UNSTAGED == 1 && A_STAGED == 0 && A_QUIET == 2 )); then
  ok unstaged-guard
else
  bad unstaged-guard "unstaged=$A_UNSTAGED (want 1), staged=$A_STAGED (want 0), quiet=$A_QUIET (want 2)"
fi

# vault-derived: the same committed file must operate on whichever clone it sits
# in. Proven on the pure function with two different inputs, so a hardcoded
# return cannot pass, plus an assertion that run.sh actually calls it and carries
# no clone path of its own. Deliberately NOT proven by running the real job: a
# broken derivation would then write to the REAL vault, and a check may not risk
# causing the thing it is checking for. harness/ENGINEERING.md rule 3.
mkdir -p "$TMP/alpha/harness/review-job/macos"
mkdir -p "$TMP/beta/harness/review-job/macos"
D_A="$(hb_derive_vault "$TMP/alpha/harness/review-job/macos")"
D_B="$(hb_derive_vault "$TMP/beta/harness/review-job/macos")"
if [[ "$D_A" == "${TMP:A}/alpha" && "$D_B" == "${TMP:A}/beta" ]] \
   && grep -q 'hb_derive_vault' "$HERE/run.sh" \
   && ! grep -q '^[^#]*/Users/' "$HERE/run.sh"; then
  ok vault-derived
else
  bad vault-derived "A=$D_A (want ${TMP:A}/alpha), B=$D_B (want ${TMP:A}/beta), calls=$(grep -c hb_derive_vault "$HERE/run.sh"), hardcoded=$(grep -c '^[^#]*/Users/' "$HERE/run.sh")"
fi

# ---------- end to end over the real run.sh ----------

make_vault() {
  local V="$1" B="$1.git"
  git init -q --bare "$B"
  git init -q -b main "$V"
  git -C "$V" config user.email t@localhost
  git -C "$V" config user.name t
  mkdir -p "$V/episodic" "$V/harness/review-job"
  print "fake digest prompt" > "$V/harness/review-job/prompt.md"
  print old > "$V/episodic/review-digest-2020-01-01.md"
  git -C "$V" add -A >/dev/null
  git -C "$V" commit -q -m init
  git -C "$V" remote add origin "$B"
  git -C "$V" push -q -u origin main
}

make_claude() {
  local F="$1" MODE="$2"
  case "$MODE" in
    digest)  print '#!/bin/zsh\nprint -r -- "[${MESOSPHERE_REVIEW_JOB:-unset}]" > "$HB_DIR/marker.txt"\nprint "fake run wrote a digest"\nprint "body" > "episodic/review-digest-$(date +%Y-%m-%d).md"' > "$F" ;;
    nothing) print '#!/bin/zsh\nprint "nothing new to report"' > "$F" ;;
    hang)    print '#!/bin/zsh\nexec sleep 30' > "$F" ;;
  esac
  chmod +x "$F"
}

e2e() {
  local V="$1" FAKE="$2" MAX="$3" HBD="$4"
  mkdir -p "$HBD"
  ( HB_DIR="$HBD" HB_POLL=1 HB_GRACE=1 \
    MESOSPHERE_VAULT="$V" MESOSPHERE_CLAUDE="$FAKE" MESOSPHERE_MAX_SECONDS="$MAX" \
    zsh "$HERE/run.sh" ) 2>&1
}

# e2e 1: a digest is written while an interactive session has unrelated work
# staged. The commit must carry the digest and nothing else.
V1="$TMP/v1"; make_vault "$V1"; make_claude "$TMP/claude-digest" digest
print "someone else's work in progress" > "$V1/other-work.md"
git -C "$V1" add other-work.md >/dev/null
O1="$(e2e "$V1" "$TMP/claude-digest" 60 "$TMP/hb1")"; RC1=$?
LANDED="$(git -C "$V1" show --name-only --format='' HEAD | tr '\n' ' ')"
STILL_STAGED="$(git -C "$V1" diff --cached --name-only)"
PUSHED="$(git -C "$V1" rev-list --count origin/main..main)"
if (( RC1 == 0 )) && [[ "$LANDED" == "episodic/review-digest-$(date +%Y-%m-%d).md " ]] \
   && [[ "$STILL_STAGED" == "other-work.md" ]] && (( PUSHED == 0 )) \
   && grep -q "outcome=ok" "$TMP/hb1/last-run.status" \
   && [[ ! -f "$TMP/hb1/inflight" ]]; then
  ok commit-pathspec
else
  bad commit-pathspec "vault=$V1 rc=$RC1 landed='$LANDED' still-staged='$STILL_STAGED' unpushed=$PUSHED out=$O1"
fi

# review-job-marker: the claude run.sh launches must carry the marker, or the Stop
# hook walls it in behind any interactive session's open ledgers.
if [[ "$(cat "$TMP/hb1/marker.txt" 2>/dev/null)" == "[1]" ]]; then
  ok review-job-marker
else
  bad review-job-marker "claude saw MESOSPHERE_REVIEW_JOB as '$(cat "$TMP/hb1/marker.txt" 2>&1)' (want [1])"
fi

# e2e 2: nothing written is a quiet week, exit 0, no commit
V2="$TMP/v2"; make_vault "$V2"; make_claude "$TMP/claude-nothing" nothing
BEFORE="$(git -C "$V2" rev-list --count HEAD)"
O2="$(e2e "$V2" "$TMP/claude-nothing" 60 "$TMP/hb2")"; RC2=$?
AFTER="$(git -C "$V2" rev-list --count HEAD)"
if (( RC2 == 0 && BEFORE == AFTER )) && grep -q "outcome=no-op" "$TMP/hb2/last-run.status" \
   && [[ ! -f "$TMP/hb2/inflight" ]]; then
  ok quiet-week
else
  bad quiet-week "vault=$V2 rc=$RC2 commits $BEFORE->$AFTER out=$O2"
fi

# e2e 2b: a quiet week when every earlier digest has been archived, so the stage
# pattern matches no file at all. git exits 128 there, which once killed the run.
V2B="$TMP/v2b"; make_vault "$V2B"
git -C "$V2B" rm -q episodic/review-digest-2020-01-01.md && git -C "$V2B" commit -q -m archive
O2B="$(e2e "$V2B" "$TMP/claude-nothing" 60 "$TMP/hb2b")"; RC2B=$?
if (( RC2B == 0 )) && grep -q "outcome=no-op" "$TMP/hb2b/last-run.status" 2>/dev/null \
   && [[ ! -f "$TMP/hb2b/inflight" ]]; then
  ok quiet-week-archived
else
  bad quiet-week-archived "vault=$V2B rc=$RC2B out=$O2B"
fi

# e2e 3: the watchdog fires. A killed run must still record an outcome, which is
# the whole point: otherwise a hard terminate looks exactly like a quiet week.
V3="$TMP/v3"; make_vault "$V3"; make_claude "$TMP/claude-hang" hang
O3="$(e2e "$V3" "$TMP/claude-hang" 1 "$TMP/hb3")"; RC3=$?
if (( RC3 != 0 )) && [[ "$O3" == *WATCHDOG* ]] \
   && grep -q "outcome=fail" "$TMP/hb3/last-run.status" \
   && grep -q "watchdog" "$TMP/hb3/last-run.status" \
   && [[ ! -f "$TMP/hb3/inflight" ]]; then
  ok watchdog-outcome
else
  bad watchdog-outcome "rc=$RC3 status='$(cat $TMP/hb3/last-run.status 2>&1)' out=$O3"
fi

# arg-refusal, against a copy truncated at the guard so the body cannot run
STUB="$TMP/guard.sh"
sed -n '1,/^set -euo pipefail$/p' "$HERE/run.sh" | sed '$d' > "$STUB"
print 'print "BODY RAN"' >> "$STUB"
G_OUT="$(zsh "$STUB" --dry-run 2>&1)"; G_RC=$?
G_CLEAN="$(zsh "$STUB" 2>&1)"; G_CLEAN_RC=$?
if (( G_RC == 64 )) && [[ "$G_OUT" == *REFUSED* ]] && [[ "$G_OUT" != *"BODY RAN"* ]] \
   && (( G_CLEAN_RC == 0 )) && [[ "$G_CLEAN" == *"BODY RAN"* ]]; then
  ok arg-refusal
else
  bad arg-refusal "with a flag: rc=$G_RC out=$G_OUT | with no args: rc=$G_CLEAN_RC out=$G_CLEAN"
fi

# e2e 5: mining.json present. run.sh must run history.py BEFORE claude and hand its
# one line to the agent; the extract lands in the workdir outside the vault and
# nothing from it reaches a commit.
V5="$TMP/v5"; make_vault "$V5"
mkdir -p "$V5/harness" "$TMP/hist5/-repo" "$TMP/hb5"
cp "${MESOSPHERE_HISTORY:-${HERE:h:h}/history.py}" "$V5/harness/history.py"
NOW5="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
print -r -- "{\"type\":\"user\",\"timestamp\":\"$NOW5\",\"message\":{\"role\":\"user\",\"content\":\"a fresh owner message long enough to mine\"}}" > "$TMP/hist5/-repo/s.jsonl"
print -r -- "{\"every_days\":30,\"max_chars\":100000,\"workdir\":\"$TMP/mine5\",\"start_from\":\"2000-01-01\",\"sources\":[{\"type\":\"claude-code\",\"path\":\"$TMP/hist5\"}]}" > "$V5/mining.json"
git -C "$V5" add -A >/dev/null; git -C "$V5" commit -q -m "mining config"; git -C "$V5" push -q
print '#!/bin/zsh\nprint -r -- "$*" > "$HB_DIR/prompt.txt"\nprint "nothing new to report"' > "$TMP/claude-prompt"; chmod +x "$TMP/claude-prompt"
O5="$(e2e "$V5" "$TMP/claude-prompt" 60 "$TMP/hb5")"; RC5=$?
if (( RC5 == 0 )) && grep -q "Monthly mining for this run: mining: 1 new messages" "$TMP/hb5/prompt.txt" \
   && [[ -n "$(print -l $TMP/mine5/new-*.jsonl(N))" ]] \
   && [[ -z "$(git -C "$V5" status --porcelain)" ]] \
   && [[ -z "$(find "$V5" -name 'new-*.jsonl' -not -path '*/.git/*')" ]]; then
  ok mining-handoff
else
  bad mining-handoff "rc=$RC5 prompt='$(cat "$TMP/hb5/prompt.txt" 2>&1 | tail -2)' extract=$(print -l $TMP/mine5/new-*.jsonl(N) | wc -l) status='$(git -C "$V5" status --porcelain)' out=$O5"
fi

# e2e 6: every shipped adapter. run.sh must start the chosen engine with that
# adapter's flags, in order, and hand it the prompt. A fake binary records its
# arguments one per line. The adapter files are found beside the real clone, or
# beside MESOSPHERE_AGENT_FILE when the mutation test runs a copy from a temp folder.
ADIR="${${MESOSPHERE_AGENT_FILE:-${HERE:h:h}/adapters/claude-code/review-job.sh}:h:h}"
for ad in claude-code codex gemini antigravity; do
  VA="$TMP/ad-$ad"; make_vault "$VA"
  FA="$TMP/fake-$ad"; HBA="$TMP/hb-ad-$ad"; mkdir -p "$HBA"
  print '#!/bin/zsh\nprint -rl -- "$@" > "$HB_DIR/args.txt"\nprint "nothing new to report"' > "$FA"; chmod +x "$FA"
  OA="$( ( HB_DIR="$HBA" HB_POLL=1 HB_GRACE=1 MESOSPHERE_VAULT="$VA" MESOSPHERE_MAX_SECONDS=60 \
      MESOSPHERE_ADAPTER="$ad" MESOSPHERE_AGENT_FILE="$ADIR/$ad/review-job.sh" \
      MESOSPHERE_CLAUDE="$FA" MESOSPHERE_CODEX="$FA" MESOSPHERE_GEMINI="$FA" MESOSPHERE_CURSOR="$FA" MESOSPHERE_AGY="$FA" \
      zsh "$HERE/run.sh" ) 2>&1 )"; RA=$?
  case "$ad" in
    claude-code) WA="-p --permission-mode acceptEdits" ;;
    codex)       WA="exec -s workspace-write --skip-git-repo-check" ;;
    gemini)      WA="--approval-mode auto_edit -p" ;;
    cursor)      WA="-p --force" ;;
    antigravity) WA="--add-dir --mode accept-edits -p" ;;
  esac
  NA=${#${(z)WA}}
  if [[ "$ad" == antigravity ]]; then
    # the second argument is the vault path, which differs per temp folder; check the rest
    GA="$(sed -n '1p;3,5p' "$HBA/args.txt" 2>/dev/null | tr '\n' ' ')"
  else
    GA="$(head -n $NA "$HBA/args.txt" 2>/dev/null | tr '\n' ' ')"
  fi
  if (( RA == 0 )) && [[ "$GA" == "$WA " ]] && grep -q "fake digest prompt" "$HBA/args.txt" 2>/dev/null; then
    ok "adapter-$ad"
  else
    bad "adapter-$ad" "rc=$RA got='$GA' want='$WA ' out=$OA"
  fi
done


# e2e 7: a dirty harness/ or .claude/ refuses the run before the agent starts, because
# the job must never run on harness code nobody committed (2026-10-28).
VD="$TMP/vdirty"; make_vault "$VD"; make_claude "$TMP/claude-digest-d" digest
print "edited by hand" >> "$VD/harness/review-job/prompt.md"
OD="$(e2e "$VD" "$TMP/claude-digest-d" 60 "$TMP/hbd")"; RD=$?
if (( RD != 0 )) && [[ "$OD" == *"uncommitted changes under harness/ or .claude/"* ]] && [[ ! -f "$TMP/hbd/marker.txt" ]]; then
  ok review-dirty-refused
else
  bad review-dirty-refused "rc=$RD agent ran=$([[ -f $TMP/hbd/marker.txt ]] && print yes || print no) out=$OD"
fi

# e2e 8: whatever the run does to harness/ or .claude/, tracked, untracked or ignored,
# is put back before anything is committed, and the digest still lands.
VR="$TMP/vrestore"; make_vault "$VR"
print ".claude/settings.local.json" > "$VR/.gitignore"
git -C "$VR" add .gitignore >/dev/null; git -C "$VR" commit -q -m ignore; git -C "$VR" push -q
mkdir -p "$VR/.claude"; print '{"hooks": {}}' > "$VR/.claude/settings.local.json"
FP="$TMP/claude-plant"
print '#!/bin/zsh
print "planted" >> harness/review-job/prompt.md
print "evil" > harness/next-week.sh
print "{\"hooks\": \"planted\"}" > .claude/settings.local.json
print "body" > "episodic/review-digest-$(date +%Y-%m-%d).md"' > "$FP"; chmod +x "$FP"
OR="$(e2e "$VR" "$FP" 60 "$TMP/hbr")"; RR=$?
if (( RR == 0 )) && [[ "$(cat "$VR/harness/review-job/prompt.md")" == "fake digest prompt" ]] \
    && [[ ! -e "$VR/harness/next-week.sh" ]] \
    && [[ "$(cat "$VR/.claude/settings.local.json")" == '{"hooks": {}}' ]] \
    && git -C "$VR" show --name-only --format='' HEAD | grep -q review-digest- \
    && [[ "$OR" == *"were restored"* ]]; then
  ok review-restores-tracked
else
  bad review-restores-tracked "rc=$RR prompt='$(cat "$VR/harness/review-job/prompt.md")' planted=$([[ -e $VR/harness/next-week.sh ]] && print yes || print no) settings='$(cat "$VR/.claude/settings.local.json")' out=$OR"
fi

# Cursor's unattended review job is unsupported: the run must refuse, run nothing, and
# say why (2026-10-28).
VC="$TMP/ad-cursor-x"; make_vault "$VC"; FC="$TMP/fake-cursor"; HBC="$TMP/hb-cursor-x"; mkdir -p "$HBC"
print '#!/bin/zsh\nprint ran > "$HB_DIR/ran.txt"' > "$FC"; chmod +x "$FC"
OC="$( ( HB_DIR="$HBC" HB_POLL=1 HB_GRACE=1 MESOSPHERE_VAULT="$VC" MESOSPHERE_MAX_SECONDS=60 \
    MESOSPHERE_ADAPTER=cursor MESOSPHERE_AGENT_FILE="$ADIR/cursor/review-job.sh" MESOSPHERE_CURSOR="$FC" \
    zsh "$HERE/run.sh" ) 2>&1 )"; RC_C=$?
if (( RC_C != 0 )) && [[ "$OC" == *"not supported"* ]] && [[ ! -f "$HBC/ran.txt" ]]; then
  ok adapter-cursor-unsupported
else
  bad adapter-cursor-unsupported "rc=$RC_C ran=$([[ -f $HBC/ran.txt ]] && print yes || print no) out=$OC"
fi

if (( FAILED == 0 )); then
  print "SELFTEST OK ($COUNT checks)"
  exit 0
fi
print -u2 "SELFTEST FAILED ($COUNT checks)"
exit 1
