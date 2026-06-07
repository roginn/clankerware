---
name: pr-comment
description: Verify, explain, plan, and respond to a single review comment on one of the user's GitHub PRs. Pass the comment URL (e.g. `https://github.com/<org>/<repo>/pull/<num>#discussion_r<id>`) or just the discussion ID as `args`. Use when the user asks to "address this PR comment", "look at this review comment", "what does this comment mean", or pastes a `#discussion_r...` link from a PR review. Not for opening PRs, not for general PR review, not for top-level (non-review) PR comments.
---

# pr-comment

A four-phase workflow for working through a single inline review comment on one of the user's PRs. Each phase has a hard stop — do not skip ahead and do not collapse the phases into one response.

## Arguments (`args`)

`args` is normally a GitHub comment URL or a bare comment ID:

- `https://github.com/<org>/<repo>/pull/<num>#discussion_r<commentId>` — preferred, gives you the repo and PR for free.
- `<commentId>` alone (e.g. `3134781838`) — usable if the conversation already names the PR; otherwise ask which PR.

If the user just says "look at the comment from <reviewer>" without an ID, ask them for the URL — guessing the wrong comment wastes a round trip and risks acting on the wrong feedback.

## Phase 1 — Verify the comment still tracks

The PR has likely moved since the comment was written. Before explaining anything, confirm the criticism still applies to the **current** branch state.

1. **Fetch the comment** with `gh api repos/<org>/<repo>/pulls/<num>/comments --paginate` and filter to the one matching the ID. Capture: `path`, `line`, `original_line`, `commit_id`, `original_commit_id`, `body`, `diff_hunk`, `user.login`.
2. **Read the file at the cited path** as it stands on the current working branch (not the commit the comment was attached to). Use the `line` field if present, else `original_line`, plus a generous window (±25 lines) so you can see context.
3. **Decide whether the issue still tracks.** Three outcomes:
   - **Still tracks** — the code at the cited location still exhibits the problem the reviewer flagged. Continue to Phase 2.
   - **Already addressed** — the code has been changed and the criticism no longer applies. Stop and tell the user: name the file/lines that resolved it (use `git log -p -- <file>` if helpful to find the commit) and draft a one-line reply they can post to close the thread. Do not proceed to Phase 3 or 4.
   - **Partially addressed / shifted** — the original concern morphed (e.g. moved to a sibling file, or only one of two flagged spots was fixed). Tell the user what changed, what's left, and ask whether they want a plan for the remaining piece.

   When in doubt, lean toward "still tracks" — over-explaining a stale comment is cheaper than dismissing a live one.

4. State the verdict in one sentence at the top of your reply, then show the *current* code at that location (file + line range) so the user can see what you're working from.

## Phase 2 — Explain the comment didactically

Reviewers write terse comments. Your job is to expand the comment into something the user can act on without re-reading the surrounding code.

A good explanation has four parts:

- **Where** — exact file paths and line ranges of the code in question. If the comment spans two places (e.g. duplicated logic), show **both** with the duplication side by side.
- **What the reviewer is saying** — restate their point in plain language, expanding any shorthand. Avoid quoting the comment verbatim unless it's already clear.
- **Why it matters** — the underlying principle or failure mode the reviewer is pointing at. This is the part most users want: "what bad thing happens if I don't fix this?" Be concrete: "if someone adds a 4th tool, the eval silently misses it" beats "drift between prod and eval."
- **The fix in one sentence** — a single sentence preview of the direction. Don't expand it yet; that's Phase 3.

Match length to severity. A `[nit]` comment doesn't need four paragraphs. A `[high]` or architectural comment usually does.

**Stop after explaining.** Do not start writing the plan in the same response. The user may push back on your reading of the comment — let them.

## Phase 3 — Plan the fix (no code yet)

Once the user has confirmed the explanation lands, write a numbered plan. Keep it tight: most fixes are 3-6 steps.

A good plan names:

1. **New / modified files** — exact paths. If creating a helper, propose the path and explain *why there* (e.g. "co-located with `buildAgentTools.ts` so the agent-assembly surface stays in one place").
2. **What changes in each file** — line ranges, the rough shape of the edit, and any imports being added or dropped.
3. **Verification step** — how the user will know it worked. A test command (`npm run evals:fx -- --mode=mocked`), a type check, or a manual repro. If the area has no tests, say so honestly.
4. **Trade-offs worth flagging** — anything the reviewer might push back on (e.g. "this adds a one-caller helper module — the indirection is the point, but worth naming").

**Do not write code in this phase.** Sketch with file paths and short pseudo-code blocks if it helps, but don't open `Edit` or `Write`. End with a clear handoff: "Want me to go ahead with this?" or similar.

## Phase 4 — Implement, then draft the reply

Once the user approves the plan:

1. **Implement** the changes following the plan. If you discover the plan was wrong mid-implementation, stop and re-align with the user before continuing.
2. **Verify** — run whatever check you proposed in Phase 3 if it's available locally. Report the result honestly; don't claim success on something you couldn't actually run.
3. **Draft the reply.** Write **one short line** the user can copy-paste as a response to the review comment. The line should:
   - Be one sentence, ideally under 20 words.
   - Name *what* changed and *where* (file path or helper name) — concrete enough that the reviewer can verify without asking follow-ups.
   - Use past tense ("Extracted...", "Moved...", "Both call sites now...").
   - Not include emojis, "thanks for the feedback", or other filler.
   - Not mention you (Claude) — write as the PR author.

   Present the draft on its own line, in a code block or quote, so the user can copy it cleanly.

   Examples:
   - `Extracted to buildSolutionsSurfaceTools(apiKey); both solutionsAgent.ts and AgentAdapter.ts now import it.`
   - `Fixed — guard moved into checkAccess() so all three call sites share it.`
   - `Renamed to evalCaseId and updated the four references.`

## Things to avoid

- **Don't act on a stale comment.** Phase 1 exists for a reason. If the code already changed, stop.
- **Don't combine phases.** Each phase is a checkpoint where the user might redirect you. Compressing them defeats the workflow.
- **Don't write code in Phase 2 or 3.** Even small edits. The user explicitly wants to approve the plan first.
- **Don't pad the reply line.** Reviewers read these in a queue; a one-liner that names the fix is more respectful than a paragraph.
- **Don't rewrite the reviewer's comment in your reply.** They wrote it; they remember it. Just describe what you did.
- **Don't use the `Agent` tool** for any phase of this skill. Each phase is short and benefits from the user seeing your reasoning directly.
