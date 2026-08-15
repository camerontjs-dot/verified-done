#!/bin/sh
# Pull an Ollama model, retrying past transient network failures.
#
# Why this exists rather than a bare `ollama pull`:
#
#   1. Large pulls fail. A 16 GB model off a CDN can reset mid-layer, and the
#      default behaviour is to give up. Ollama keeps partial blobs, so a retry
#      resumes rather than restarting, which makes retrying almost free.
#
#   2. Exit status must be the pull's own. Piping `ollama pull` into `tail` to
#      trim its progress spam reports the *pipeline's* status, which is `tail`
#      succeeding at printing a failure. That happened here: a download that
#      died at 21% was recorded as a completed job. A harness that measures
#      false completion should not produce one.
#
# Success requires both a zero exit and the model appearing in `ollama list`,
# because the first alone has already proven insufficient.
#
# Usage: tools/pull_model.sh <model> [attempts]

set -u

MODEL="${1:-}"
ATTEMPTS="${2:-6}"

if [ -z "$MODEL" ]; then
    echo "usage: tools/pull_model.sh <model> [attempts]" >&2
    exit 2
fi

# Progress output is verbose and full of terminal control codes. It goes to a
# temp log so a failure can be diagnosed without drowning the caller.
LOG="$(mktemp -t vd-pull)" || exit 1
trap 'rm -f "$LOG"' EXIT

attempt=1
while [ "$attempt" -le "$ATTEMPTS" ]; do
    printf '=== attempt %s/%s ===\n' "$attempt" "$ATTEMPTS" >> "$LOG"
    ollama pull "$MODEL" >> "$LOG" 2>&1
    status=$?

    if [ "$status" -eq 0 ] && ollama list | grep -q "^${MODEL%%:*}"; then
        printf 'PULL_OK %s (attempt %s)\n' "$MODEL" "$attempt"
        exit 0
    fi

    printf 'attempt %s failed (exit %s)\n' "$attempt" "$status" >&2
    attempt=$((attempt + 1))
    [ "$attempt" -le "$ATTEMPTS" ] && sleep 20
done

printf 'PULL_FAILED %s after %s attempts\n' "$MODEL" "$ATTEMPTS" >&2
# Last few lines only, with carriage returns stripped: progress bars redraw on
# \r and would otherwise print as one unreadable line.
tr -d '\r' < "$LOG" | tail -5 >&2
exit 1
