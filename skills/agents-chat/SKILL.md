---
name: agents-chat
description: Orchestrate a multi-turn debate between Claude Code and OpenAI Codex on a problem, PR, architecture decision, or idea. The two agents propose, push back, and refine across turns in a target directory, converging toward a better answer than either reaches alone; an implementation plan is optionally written to plan.md afterward. Use when the user wants "two agents to discuss / debate / pair on / scrutinize / argue about" something, asks for a second-model opinion, wants to review a PR or bugbot comments with both agents, or wants to stress-test a design or idea. Supports resuming an existing discussion to feed in new information (e.g. "changes implemented, re-review", "wait for bugbot then discuss"). Requires the `claude` and `codex` CLIs on PATH.
---

# agents-chat

Drives `agents_chat.py`, which runs **Claude Code** and **OpenAI Codex** in a turn-by-turn
debate inside a target directory. Each agent keeps its own resumed session; the orchestrator
relays the latest message between them via `peer_message.md`, logs the full exchange to
`transcript.md`, and (unless disabled) writes an `implementation plan` to `plan.md` at the end.

**Your job is to launch and shepherd the script — not to do the debating yourself.** The two
real agents are separate `claude -p` and `codex exec` subprocesses the script spawns. Do not
try to simulate the back-and-forth in this session. Run the script, watch it, then read the
artifacts and report back.

## The script

Bundled here (real files, shipped with the skill):

- `agents_chat.py` — the orchestrator (the thing you run)
- `serve.py` + `index.html` — optional live transcript viewer at `http://127.0.0.1:8765`

Invoke as `python3 ~/.claude/skills/agents-chat/agents_chat.py ...`.

## Step 1 — figure out the inputs

From the user's request, determine:

- **Problem statement** (positional arg, quoted): the thing to debate. Pass it through richly —
  these prompts are usually long and specific (links to PRs/bugbot comments/LangSmith traces,
  "analyze the architecture", "don't change any code yet"). Don't summarize the user's intent away.
- **`--cwd <dir>`** (optional; defaults to the current directory): the repo/dir the agents operate
  in. Usually you're already inside the repo you want to discuss, so you can omit this. Pass `--cwd`
  only when the target repo is somewhere else — e.g. the user names a branch/feature/PR that lives in
  a different worktree or path. If they do and the path is ambiguous, map it to the right local path;
  if you can't, ask.
- **`--continue`**: use when the user is *resuming an existing discussion* in that dir — phrasings
  like "we implemented your changes, re-review", "what's the final verdict?", "wait for bugbot then
  discuss the new comments". With `--continue`, a problem statement is optional and, if given, is
  injected as a new user message to both agents. Requires prior `.agents_chat_state.json` in `--cwd`.
- **`--first claude|codex`** (default `claude`): the user almost always lets Claude open. Only set
  `codex` if asked.
- **`--max-turns N`** (default 20), **`--min-turns N`**, **`--no-plan`** (skip plan generation —
  appropriate for pure discussion/"don't change code" sessions where no implementation is expected).

When unsure whether to resume — or when the target repo isn't the current directory and which one is
ambiguous — ask before launching; a wrong directory wastes a long run.

## Step 2 — launch it (background) + the live viewer

These runs take many minutes (typically 7–14 turns to converge; the cap is `--max-turns`, default
20, which real runs rarely hit — only raise it for an unusually deep debate). **Run in the
background** so you're notified on completion, rather than blocking:

```bash
python3 ~/.claude/skills/agents-chat/agents_chat.py "<problem>" --first claude
```

(Add `--cwd <dir>` only if the repo to discuss isn't the current directory.) Run that with the Bash
tool's `run_in_background` option. **By default, also start the live viewer** in the background so the
user can watch the debate stream in — use `--no-open` (give them the URL to click rather than
hijacking a browser tab):

```bash
python3 ~/.claude/skills/agents-chat/serve.py --no-open
```

(Likewise pass `--cwd <dir>` to the viewer only if you passed it above — it must point at the same
directory.)

Then tell the user it's running and surface the viewer URL (`http://127.0.0.1:8765`). Skip the viewer
only if the user asks to. While it runs you can tail `<dir>/transcript.md` to report progress, but
don't burn turns polling tightly — the completion notification is enough. Stop the viewer process
once the user is done reading.

## Step 3 — when it finishes, synthesize (don't dump)

Once the script exits:

1. Read `<dir>/transcript.md` — the full debate.
2. Read `<dir>/plan.md` if it exists (no file ⇒ the agents either finished all work inline or it
   was a discussion-only run).
3. Report back with: **where the two agents converged**, **where they still disagree and why**, the
   **key decisions/conclusions**, and any concrete changes they made or propose. Surface the tension —
   the value of this tool is the push-back, so don't flatten a real disagreement into false consensus.
4. Offer next steps that match how this gets used:
   - If `plan.md` exists and the user wants it built: `claude -p "$(cat <dir>/plan.md)"`.
   - To continue the debate (new info, re-review after changes, "final verdict?"): re-run this skill
     with `--continue` and a new message.

## Notes & gotchas

- `agents_chat.py` runs the inner Claude with `--permission-mode bypassPermissions` and Codex with
  `--dangerously-bypass-approvals-and-sandbox` so the agents can read/edit freely. Only point it at
  repos where that's acceptable (it's how the tool is normally used).
- Both `claude` and `codex` must be on PATH. A nonzero exit from either subprocess aborts the run and
  prints stderr — relay that to the user.
- Artifacts written into `--cwd`: `transcript.md` (append-only; prior one is backed up on a fresh run),
  `peer_message.md` (last message only), `plan.md` (optional), `.agents_chat_state.json` (resume state).
- `--continue` reads `.agents_chat_state.json` from `--cwd`; if it's missing, start a fresh run instead.
