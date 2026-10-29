#!/bin/zsh
# Weekly vault review digest. Sweeps episodic notes and fresh auto-memories,
# drafts promotion proposals for the owner to yes/no. Never edits tier 1 or 2.
#
# The digest prompt is deliberately NOT kept in this directory. It is read from
# the vault clone at run time, after the pull, so a fix committed to the prompt
# reaches this job the moment it lands. A local copy drifted silently once and
# cost a week of digests that ran without their collision guard. See the
# weekly review job section of harness/adapters/claude-code/README.md.
#
# Ported from the Windows wrapper on 2026-08-24: argument refusal, proof of life
# via heartbeat.sh, a wall clock watchdog (launchd has no ExecutionTimeLimit),
# a written-but-unstaged hard failure, and a pathspec scoped commit.

# Argument refusal comes FIRST, before anything with a side effect, because a
# zsh script with no argument parsing ignores unknown flags and runs its body.
# harness/ENGINEERING.md rule 2: never rely on a target rejecting bad input.
# On the Windows side that exact assumption turned a read-only check into two
# full runs of the live job in one day.
if (( $# > 0 )); then
  print -u2 "REFUSED: this job takes no arguments, got: $*"
  print -u2 "Nothing ran. To exercise the wrapper safely, use selftest.sh, which touches only a temp directory."
  exit 64
fi

set -euo pipefail

export PATH="$HOME/.local/bin:/usr/local/bin:/opt/homebrew/bin:$PATH"

HERE="${0:A:h}"
source "$HERE/heartbeat.sh"

# Every path below is derived or overridable, and none is hardcoded to a machine,
# which is what lets this file be committed and run from any clone. The overrides
# also let selftest.sh drive this exact file end to end against a throwaway vault
# and a fake claude, rather than a reimplementation of its logic, which is
# harness/ENGINEERING.md rule 1. launchd hands the job a minimal environment, so
# the defaults are what run in production.
VAULT="${MESOSPHERE_VAULT:-$(hb_derive_vault "$HERE")}"
PROMPT="${MESOSPHERE_PROMPT:-$VAULT/harness/review-job/prompt.md}"
MAX_SECONDS="${MESOSPHERE_MAX_SECONDS:-7200}"   # PT2H, the bound the Windows scheduled task imposes
PATTERN='episodic/review-digest-*.md'
GLOB='review-digest-*.md'

# State lives beside the schedule, never in the clone. See heartbeat.sh.
STATE="${MESOSPHERE_STATE:-$HOME/schedules/mesosphere-review}"
HB_DIR="${HB_DIR:-$STATE}"
mkdir -p "$HB_DIR"

# Which engine runs the review is the adapter's business, not this wrapper's
# (contract section 8). The adapter's review-job.sh sets AGENT_CMD, the engine's
# headless command without the prompt, as a list, so the watchdog below still
# kills the agent process itself rather than a shell around it. It is read from
# this clone, beside the wrapper, so it cannot drift from it.
ADAPTER="${MESOSPHERE_ADAPTER:-claude-code}"
AGENT_FILE="${MESOSPHERE_AGENT_FILE:-${HERE:h:h}/adapters/$ADAPTER/review-job.sh}"

# A marker still sitting here is either a dead predecessor or a live run. Only
# the first is ours to clear. Overwriting a live one would let two jobs write the
# same digest and would destroy the first run's proof of life on the way in.
SC=0
hb_stale_check || SC=$?
if (( SC == 2 )); then
  print -u2 "REFUSED: a live run already holds this slot. Nothing was run and no marker was touched."
  exit 75
fi
STALE=""
(( SC == 1 )) && STALE="the previous run died without recording an outcome"

hb_begin

HB_INFLIGHT="$HB_DIR/inflight"
HB_STATUS="$HB_DIR/last-run.status"
HB_REF="$HB_DIR/run-start.ref"

print "resolved vault: $VAULT"

fail() {
  hb_end fail "$*"
  print -u2 "FATAL: $*"
  exit 1
}

cd "$VAULT" || fail "vault clone not found at $VAULT"

# The run reads untrusted mined text with edit rights inside this clone, so it could
# plant code for next week: an adapter file, heartbeat.sh, the prompt, or a hook in
# .claude/settings.local.json. Found by a readiness review on 2026-10-28. So the job
# starts only from a clean harness/ and .claude/, and restore_harness below puts both
# back after the run, whatever it did.
if [[ -n "$(git status --porcelain --untracked-files=all -- harness .claude)" ]]; then
  fail "REFUSED: uncommitted changes under harness/ or .claude/. The unattended run starts only from a committed, reviewed harness; commit or discard them first."
fi

if ! git pull --no-rebase -q; then
  fail "git pull failed. Not running, because both the vault and the prompt would be stale."
fi

if [[ ! -r "$PROMPT" ]]; then
  fail "digest prompt not found or unreadable at $PROMPT. There is deliberately no fallback prompt: a local copy is exactly how this job drifted."
fi

[[ -r "$AGENT_FILE" ]] || fail "no review-job agent file for adapter '$ADAPTER' at $AGENT_FILE"
AGENT_CMD=()
source "$AGENT_FILE"
(( ${#AGENT_CMD} )) || fail "the adapter file $AGENT_FILE did not set AGENT_CMD"

DATE=$(date +%Y-%m-%d)
print "$(date '+%Y-%m-%d %H:%M:%S') starting, prompt: $PROMPT${STALE:+ (note: $STALE)}"

# Mining new chats, on the owner's cadence. A plain script, run HERE and not by the
# agent, because an unattended run cannot approve a command that writes files. It
# extracts only the owner's new messages since its last run, scrubbed, into a folder
# outside the vault, and prints one line that the agent is handed below. No
# mining.json at the vault root means no mining, and a failure never stops the review.
MINING="mining: not configured"
if [[ -r "$VAULT/mining.json" ]]; then
  PY="${MESOSPHERE_PYTHON:-$(command -v python3 2>/dev/null || true)}"
  if [[ -z "$PY" ]]; then
    MINING="mining: FAILED: no python3 on the job's PATH; set MESOSPHERE_PYTHON"
  else
    MINING="$("$PY" "$VAULT/harness/history.py" --config "$VAULT/mining.json" 2>&1 | tail -1)" || true
    [[ "$MINING" == mining:* ]] || MINING="mining: FAILED: ${MINING:-no output}"
  fi
fi
print "$MINING"

# The state this run must leave harness/ and .claude/ in. .claude/ holds ignored files
# git cannot see (settings.local.json, where hooks live), so it is copied aside whole.
START_HEAD="$(git rev-parse HEAD)"
SNAP="$HB_DIR/dotclaude-before"
rm -rf "$SNAP"
[[ -d .claude ]] && cp -Rp .claude "$SNAP"

restore_harness() {
  local touched f
  touched="$(git status --porcelain --untracked-files=all -- harness .claude)"
  git reset -q -- harness .claude 2>/dev/null || true
  git diff --name-only "$START_HEAD" -- harness .claude | while IFS= read -r f; do
    git checkout -q "$START_HEAD" -- "$f" 2>/dev/null || rm -f -- "$f"
  done
  git clean -fdq -- harness .claude
  if [[ -d "$SNAP" ]]; then
    if ! diff -rq "$SNAP" .claude >/dev/null 2>&1; then
      touched+=$'\n'"ignored files under .claude/"
      rm -rf .claude && cp -Rp "$SNAP" .claude
    fi
  elif [[ -e .claude ]]; then
    touched+=$'\n'".claude/ created by the run"
    rm -rf .claude
  fi
  rm -rf "$SNAP"
  if [[ -n "${touched//[[:space:]]/}" ]]; then
    print -u2 "WARNING: the run changed files under harness/ or .claude/. They were restored:"
    print -u2 "$touched"
  fi
}

# Marks this claude as the review job, which contract 9.6 exempts from the ledger.
# The Stop hook enforces every open ledger in the clone, so without this another
# session's ledgers block this unattended run until the hook's release valve fires.
export MESOSPHERE_REVIEW_JOB=1

# Bounded, because nothing outside this script bounds it. Hitting the bound is
# reported as its own outcome rather than looking like a quiet week.
RC=0
hb_watchdog "$MAX_SECONDS" "${AGENT_CMD[@]}" "$(cat "$PROMPT")

Today's date for the digest filename and frontmatter: ${DATE}

Monthly mining for this run: ${MINING}" || RC=$?

restore_harness
# A change the run COMMITTED is beyond a restore, and the push below would publish it.
if [[ -n "$(git diff --name-only "$START_HEAD" HEAD -- harness .claude)" ]]; then
  fail "a commit made during this run changed harness/ or .claude/. Nothing was pushed; review the commits since $START_HEAD before pushing by hand."
fi

if (( RC == 124 )); then
  fail "the run hit its ${MAX_SECONDS}s watchdog bound and was terminated. No digest is trustworthy from a killed run."
elif (( RC != 0 )); then
  fail "the headless run exited $RC. Not committing anything from a failed run."
fi

# The job may write ONLY a digest. Anything else it touched is reported and
# left uncommitted; the commit below is pathspec scoped so it cannot ride along.
STRAY="$(git status --porcelain | grep -v 'review-digest-' || true)"
if [[ -n "$STRAY" ]]; then
  print -u2 "WARNING: this run changed files outside the digest. Left uncommitted for review:"
  print -u2 "$STRAY"
fi

# Stage by pattern, never one exact filename: the collision guard may write
# review-digest-<date>.md, or a -second-run suffix when the day already has a
# digest, or nothing at all when there is genuinely nothing new. A pattern that
# matches no file at all (every digest archived, as BOOTSTRAP advises) makes git
# exit 128, which under set -e killed the run mid flight; the assert below judges.
git add -- "$PATTERN" 2>/dev/null || true

# Then ask the two questions separately. Was a digest written during this run,
# and did git see it? Collapsing them is the bug this replaces: the old wrapper
# read an empty index and called it a quiet week while a digest sat on disk.
ASSERT=0
hb_assert_digest "$VAULT/episodic" "$GLOB" "$PATTERN" || ASSERT=$?

if (( ASSERT == 1 )); then
  fail "a digest was written during this run but git did not stage it. Written-but-unstaged is a failure, not a quiet week."
fi

if (( ASSERT == 2 )); then
  hb_end no-op "no digest written, genuinely nothing new to report${STALE:+; $STALE}"
  print "no digest written this run: nothing new to report. Correct outcome, exiting clean."
  exit 0
fi

# Pathspec scoped, so a concurrent interactive session's staged work cannot land
# under a digest message. harness/ENGINEERING.md rule 5: two agents share one
# repository and neither owns the index.
git commit -q -m "Weekly review digest ${DATE} (scheduled job)" -- "$PATTERN"

if ! git push -q; then
  hb_end partial "committed locally, push failed${STALE:+; $STALE}"
  print -u2 "WARNING: committed locally but push failed. The digest is safe in this clone and will go up on the next run or a manual push."
  exit 1
fi

COMMITTED="$(git show --name-only --format='' HEAD | tr '\n' ' ')"
hb_end ok "pushed: ${COMMITTED}${STALE:+; $STALE}"
print "pushed: $COMMITTED"
