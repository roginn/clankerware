# tmux agent status — `samleeney/tmux-agent-status`

This folder reproduces a tmux setup that monitors AI agent sessions (Claude Code,
Codex, etc.) from inside tmux: a **sidebar**, a **status-line** summary, and an
**fzf switcher** showing each session as *working / waiting-for-input / done*.

Upstream: https://github.com/samleeney/tmux-agent-status

## What this actually is (read this first)

It is a **tmux plugin** (managed by TPM), **not** a Claude Code plugin. It works
in any terminal emulator as long as you run tmux — including tmux **inside
WezTerm**. It does **not** integrate with WezTerm's native (non-tmux) multiplexer.

There are five pieces to put in place:

1. Prereqs — modern **bash** (≥4) and **fzf** (the switcher uses it).
2. **TPM** at `~/.tmux/plugins/tpm` and the plugin at `~/.tmux/plugins/tmux-agent-status`.
3. The plugin block in your **`~/.tmux.conf`** (loads TPM + the plugin + a couple of options).
4. `session-notify.sh` at **`~/.claude/hooks/`** — pops a macOS banner naming the tmux
   session when Claude stops or needs input (auto-dismisses; no-op off macOS).
5. Four Claude Code **hooks** in `~/.claude/settings.json` so Claude sessions report
   status; the `Stop`/`Notification` events also fire the banner script.

Provided here verbatim:

| File | Where it goes |
|------|---------------|
| `tmux.conf.snippet`   | append to `~/.tmux.conf` (the TPM `run` line must end up at the bottom) |
| `session-notify.sh`   | copy (executable) to `~/.claude/hooks/session-notify.sh` |
| `settings.hooks.json` | merge its `hooks` key into `~/.claude/settings.json` |
| `install.sh`          | does all of the above, idempotently |

## Prerequisites

- **tmux** (3.x) and **git** on `PATH`.
- **bash ≥ 4** — macOS ships 3.2; the plugin's sidebar needs a modern bash. The
  plugin auto-detects `/opt/homebrew/bin/bash` or `/usr/local/bin/bash` (or set
  `TMUX_AGENT_STATUS_BASH`).
- **fzf** — powers the `prefix + S` switcher.
- **jq** — only for the scripted hooks merge in `install.sh` (otherwise merge by hand).

## Install (agent-friendly, idempotent)

One command, from this folder:

```bash
./install.sh
```

It will: brew-install `bash`/`fzf` if missing (macOS), clone TPM + the plugin,
append `tmux.conf.snippet` to `~/.tmux.conf` (only once), install
`session-notify.sh` to `~/.claude/hooks/`, and merge the hooks into
`~/.claude/settings.json` (preserving your other settings and any other hook
events). If a tmux server is already running it sources the config so bindings go
live immediately.

### Manual steps (if you'd rather not run the script)

1. Prereqs (macOS): `brew install bash fzf`
2. Clone TPM + plugin:
   ```bash
   git clone --depth 1 https://github.com/tmux-plugins/tpm ~/.tmux/plugins/tpm
   git clone --depth 1 https://github.com/samleeney/tmux-agent-status ~/.tmux/plugins/tmux-agent-status
   ```
3. Append `tmux.conf.snippet` to `~/.tmux.conf` (keep `run '~/.tmux/plugins/tpm/tpm'` last).
4. Copy `session-notify.sh` to `~/.claude/hooks/session-notify.sh` and `chmod +x` it.
5. Merge the `hooks` key from `settings.hooks.json` into `~/.claude/settings.json`,
   leaving every other key intact.
6. Start tmux and press **`prefix + I`** to let TPM install the plugins (only
   needed if you skipped the direct clones in step 2).

## Use it

Prefix is the tmux default **`Ctrl-b`** (unless you've remapped it):

| Keys | Action |
|------|--------|
| `prefix + S` | fzf switcher — jump between agent sessions (main UI) |
| `prefix + o` | toggle the agent sidebar |
| `prefix + N` | jump to next finished / inbox agent |
| `prefix + W` | wait mode for a session/pane |
| `prefix + p` | park a session for later |

Inside the switcher: `Enter` switch · `Tab` expand/collapse · `Ctrl-X` close ·
`Ctrl-P` park · `Ctrl-W` wait · `Ctrl-R` reset.

## The catch (why it sometimes shows nothing)

Status only maps to a pane when **`claude` runs *inside* a tmux pane**, and the
hooks load **at session start**. A Claude session started outside tmux, or before
the hooks existed, won't appear. Workflow: open your terminal → run `tmux` → start
`claude` in a tmux pane.

## Verify

- `tmux list-keys -T prefix | grep tmux-agent-status` should list the `S/o/N/W/p` bindings.
- `ls ~/.tmux/plugins/tmux-agent-status/hooks/better-hook.sh` should exist and be executable.
- `python3 -c "import json;json.load(open('$HOME/.claude/settings.json'))"` confirms settings.json is still valid JSON.
- `~/.claude/hooks/session-notify.sh 'Test'` should pop a macOS banner with the
  current tmux session name (banners auto-dismiss; if it lingers, set Script
  Editor's notification style to "Banners" in System Settings → Notifications).

## Customizing

Edit the options in `~/.tmux.conf`, then reload (`prefix + r` or
`tmux source-file ~/.tmux.conf`):

```tmux
set -g @agent-switcher-style "both"        # popup | sidebar | both
set -g @agent-sidebar-width  "42"
set -g @agent-notification-sound "chime"   # chime|bell|fanfare|frog|speech|none
set -g @agent-status-key  "S"
set -g @agent-sidebar-key "o"
```

Full option reference: https://github.com/samleeney/tmux-agent-status
