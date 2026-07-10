#!/usr/bin/env bash
# Idempotent installer for the tmux-agent-status setup.
# Safe to re-run: each step is skipped if already in place.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="${HOME}/.tmux/plugins"
TPM_DIR="${PLUGIN_DIR}/tpm"
AGENT_DIR="${PLUGIN_DIR}/tmux-agent-status"
TMUX_CONF="${HOME}/.tmux.conf"
SETTINGS="${HOME}/.claude/settings.json"

echo "==> tmux-agent-status setup"

# 1. Prerequisites: modern bash (>=4) + fzf.
if [[ "$(uname)" == "Darwin" ]]; then
  if command -v brew >/dev/null 2>&1; then
    for pkg in bash fzf; do
      if brew list --formula "$pkg" >/dev/null 2>&1; then
        echo "    $pkg already installed"
      else
        echo "==> brew install $pkg"
        brew install "$pkg"
      fi
    done
  else
    echo "!! Homebrew not found — install bash (>=4) and fzf manually."
  fi
else
  command -v bash >/dev/null 2>&1 || echo "!! bash not found."
  command -v fzf  >/dev/null 2>&1 || echo "!! fzf not found — install it (needed for the prefix+S switcher)."
fi

# 2. TPM + the plugin (cloned directly so it works even before 'prefix + I').
mkdir -p "$PLUGIN_DIR"
if [[ -d "$TPM_DIR" ]]; then
  echo "    TPM already present"
else
  echo "==> cloning TPM"
  git clone --depth 1 https://github.com/tmux-plugins/tpm "$TPM_DIR"
fi
if [[ -d "$AGENT_DIR" ]]; then
  echo "    tmux-agent-status already present"
else
  echo "==> cloning tmux-agent-status"
  git clone --depth 1 https://github.com/samleeney/tmux-agent-status "$AGENT_DIR"
fi

# 3. tmux.conf snippet (appended once; the TPM 'run' line must stay at the bottom).
if [[ ! -f "$TMUX_CONF" ]]; then
  echo "==> creating $TMUX_CONF"
  : > "$TMUX_CONF"
fi
if grep -q 'samleeney/tmux-agent-status' "$TMUX_CONF"; then
  echo "    tmux.conf already has the plugin block"
else
  echo "==> appending tmux.conf.snippet to $TMUX_CONF"
  printf '\n' >> "$TMUX_CONF"
  cat "${SCRIPT_DIR}/tmux.conf.snippet" >> "$TMUX_CONF"
fi

# 4. macOS notification helper referenced by the Stop/Notification hooks.
CLAUDE_HOOKS_DIR="${HOME}/.claude/hooks"
mkdir -p "$CLAUDE_HOOKS_DIR"
if cmp -s "${SCRIPT_DIR}/session-notify.sh" "${CLAUDE_HOOKS_DIR}/session-notify.sh"; then
  echo "    session-notify.sh already installed"
else
  echo "==> installing session-notify.sh into $CLAUDE_HOOKS_DIR"
  cp "${SCRIPT_DIR}/session-notify.sh" "${CLAUDE_HOOKS_DIR}/session-notify.sh"
fi
chmod +x "${CLAUDE_HOOKS_DIR}/session-notify.sh"

# 5. Claude Code hooks merged into settings.json (preserves other settings & hook events).
mkdir -p "$(dirname "$SETTINGS")"
[[ -f "$SETTINGS" ]] || echo '{}' > "$SETTINGS"
if command -v jq >/dev/null 2>&1; then
  echo "==> merging hooks into $SETTINGS"
  tmp="$(mktemp)"
  jq --slurpfile s "${SCRIPT_DIR}/settings.hooks.json" \
     '.hooks = ((.hooks // {}) + $s[0].hooks)' "$SETTINGS" > "$tmp" && mv "$tmp" "$SETTINGS"
else
  echo "!! jq not found — manually merge the \"hooks\" key from settings.hooks.json into $SETTINGS"
fi

# 6. Activate immediately if a tmux server is already running.
if tmux info >/dev/null 2>&1; then
  echo "==> sourcing tmux config in the running server"
  tmux source-file "$TMUX_CONF" || true
fi

echo
echo "==> Done."
echo "    In tmux: prefix + S = switcher, prefix + o = sidebar."
echo "    Fresh install with no running server: start 'tmux', then press 'prefix + I' so TPM installs the plugins."
echo "    Note: agent status only shows when 'claude' runs INSIDE a tmux pane, and hooks load at session start."
