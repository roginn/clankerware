# Claude Code status line — `claude-powerline` (tokyo-night)

This folder reproduces a specific Claude Code status line: a **powerline**-style
bar themed **tokyo-night** showing, left to right:

- **directory** — current folder, `fish`-style (abbreviated parent path)
- **git** — branch only (no SHA, no working-tree/upstream/stash counts)
- **model** — the active Claude model
- **context** — context-window usage, drawn as **blocks**

## What this actually is (read this first)

It is **not a Claude Code plugin.** Nothing needs to be installed into
`~/.claude/plugins`. The status line is produced by the npm package
[`@owloops/claude-powerline`](https://www.npmjs.com/package/@owloops/claude-powerline),
which Claude Code runs on every render via the `statusLine` command in
`settings.json`. There are exactly **two pieces** to put in place:

1. The `statusLine` block in `~/.claude/settings.json` (the command that runs the tool).
2. The tool's own config file at `~/.claude/claude-powerline.json` (chooses theme + segments).

Both are provided in this folder verbatim:

| File | Where it goes |
|------|---------------|
| `settings.statusLine.json` | merge its `statusLine` key into `~/.claude/settings.json` |
| `claude-powerline.json`    | copy to `~/.claude/claude-powerline.json` |

## Prerequisites

- **Node.js** and **npx** on `PATH` (npx ships with npm). The tool is fetched and
  run by `npx -y @owloops/claude-powerline@latest` at render time — no manual
  `npm install` is required. Verify with `node --version` and `command -v npx`.
  (Known-good: Node 24, npm 11. Node ≥ 18 should be fine.)

## Install (agent-friendly, idempotent)

Run from anywhere. These commands assume this folder is the current directory; if
not, replace `./` with the path to this folder.

**1. Drop in the powerline config** (overwrites any existing one — that's intended):

```bash
mkdir -p ~/.claude
cp ./claude-powerline.json ~/.claude/claude-powerline.json
```

**2. Merge the `statusLine` block into `~/.claude/settings.json`** without
clobbering other settings. Uses `jq`; creates `settings.json` if absent:

```bash
mkdir -p ~/.claude
[ -f ~/.claude/settings.json ] || echo '{}' > ~/.claude/settings.json
tmp="$(mktemp)"
jq --slurpfile s ./settings.statusLine.json '.statusLine = $s[0].statusLine' \
   ~/.claude/settings.json > "$tmp" && mv "$tmp" ~/.claude/settings.json
```

If `jq` is unavailable, instead open `~/.claude/settings.json` and add the
`"statusLine": { ... }` key from `settings.statusLine.json` by hand (keep every
other existing key intact).

## Verify

- Start (or restart) Claude Code — the status line should render at the bottom.
- Or render it once standalone (it reads JSON about the session on stdin, so an
  empty object is enough to smoke-test that the tool runs):

  ```bash
  echo '{}' | npx -y @owloops/claude-powerline@latest --style=powerline --theme=tokyo-night
  ```

  The first run downloads the package and may take a few seconds.

## Customizing / pinning

- **Theme & style** are passed both on the command line (`--theme`, `--style`)
  and set in `claude-powerline.json`; keep them in sync if you change one.
- **Segments** (which parts show, and their options) live entirely in
  `claude-powerline.json` — edit that file to add/remove segments.
- **Pin the version** for reproducibility by replacing `@latest` with a fixed
  version in the `statusLine` command, e.g. `@owloops/claude-powerline@1.27.0`.
- Full option reference: https://github.com/owloops/claude-powerline
