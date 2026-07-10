#!/usr/bin/env bash

# Companion to tmux-agent-status better-hook.sh: pops a short-lived macOS
# banner notification naming the tmux session that just stopped / needs input.
# Usage: session-notify.sh <title>

TITLE="${1:-Claude stopped}"

SESSION=$(tmux display-message -p '#{session_name}' 2>/dev/null)
[ -n "$SESSION" ] || SESSION=$(basename "$PWD")

# Pass the session name via argv so quotes/backslashes in it can't break the
# AppleScript source.
osascript \
    -e 'on run argv' \
    -e 'display notification (item 1 of argv) with title (item 2 of argv)' \
    -e 'end run' \
    "$SESSION" "$TITLE"
