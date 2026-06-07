---
name: introspect
description: Reflect on the current session and surface concrete codebase friction — missing scripts, doc gaps, prompt-code drift, naming inconsistencies, undocumented constraints, surprising behaviors — that, if fixed, would make future agent sessions faster and safer. Produces structured findings with file:line refs and named fixes, logs them to `.claude/agent-friction.md` (per-repo), and offers to fix any quick wins inline. Use when the user types `/introspect`, asks for a "session retrospective", "what should we improve", "DX feedback", or "agent-friction log".
---

# introspect

A reflection skill. The user invokes it after a non-trivial coding session to harvest concrete improvements to the codebase from your *just-completed* experience working in it. The output is a structured friction report — every finding has a file:line reference and a named fix — that gets logged to a per-repo backlog so improvements compound over time.

You are reflecting, not investigating. Work *only* from what already happened in this conversation. Do not grep around looking for new problems.

## When to invoke

- User types `/introspect`.
- User asks for "what should we improve", "session retrospective", "DX feedback", "agent-friction log", or similar.
- User asks open-ended versions like "what slowed you down?" or "what would have made this easier?".

If the user invokes this on a session that was genuinely uneventful — copy-paste, simple rename, single file edit — say so honestly and stop. Don't manufacture findings to fill the report.

## The categories

Every finding belongs to one of seven categories. These are the recurring shapes of agent-codebase friction, ranked by how often they bite:

1. **prompt-drift** — A prompt or doc claims something the code doesn't support. Example: an LLM system prompt advertises a workflow block that's not in the manifest, so the agent confidently picks it and the validator rejects it. These are the highest-leverage fixes because they cause silent agent failures in production.

2. **tooling-gap** — Manual work you had to do that should be a one-liner. Example: pulling a single record out of a paginated API dump required hand-writing a loop because the existing parsing helper only accepts the full batch shape, not one item. Name the missing script and where it should live.

3. **doc-gap** — Information you had to grep for ≥3 times that should be findable in 30 seconds. Example: eval framework's case-naming convention isn't documented anywhere. Name the missing doc (or section) and where it belongs.

4. **naming-inconsistency** — Same kind of file with multiple names (`*.case.ts` vs `*.regression.ts` vs `*.behavior.ts` for what's structurally one thing). Or APIs that almost-but-don't match. Pick a winner; suggest the rename.

5. **surprising-behavior** — A tool or hook did something unexpected. Example: a hook auto-amended your edits into the prior commit, leaving HEAD inconsistent. Document the surprise so the next agent expects it.

6. **undocumented-constraint** — Quirks of an API/SDK only discovered by tripping over them. Example: a paginated endpoint's `limit`/page-size parameter is silently capped (requests above the cap error out or get truncated), and the ceiling appears nowhere in the docs — only in an error response. Name the constraint and where to document it.

7. **introspection-gap** — Framework code that *could* expose more to graders, callers, or downstream code but doesn't. Example: `judgeRubrics` only sees `ctx.result.answer`; if you want to grade tool calls you have to read other source files to discover `ctx.result.trace.toolCalls` exists. Suggest the doc-comment or type-level addition that would have made it discoverable.

## Output: the report

Produce a markdown report with one section per finding. Schema:

```markdown
### <short imperative title — what should change, not what's broken>
- **Category**: <one of the 7 above>
- **Cost**: <rough estimate — "≈3 turns", "≈15 min of grepping", "1 wrong commit">
- **Observed**: <what happened, in 1–3 sentences, with file:line refs from this session>
- **Fix**: <concrete, named change. Bad: "improve docs". Good: "add `app/evals/README.md` with sections: Naming convention, How to register a case, Where fixtures go, How to run">
- **Quick win?**: <yes (≤15 min) | no | partial>
```

Sort findings by category first (prompt-drift at the top — highest leverage), then by Cost descending within a category.

If you have nothing for a category, omit it. Don't pad.

## Calibration rules

- **Be concrete or be silent.** Every finding cites a real file path and, where useful, a line number. "The framework could be cleaner" is not a finding. "`app/evals/framework/cases/index.ts` has no test that imports compile against existing fixtures, so a missing fixture shows up only at runtime — add a `*.test.ts` next to it that imports `ALL_CASES`" is.

- **Distinguish your mistakes from codebase friction.** If you lost time because you misread a clearly-documented thing, that's a *self-correction*, not a backlog entry. List those at the end of the chat report under a "Self-corrections" section so the user sees them, but don't log them to the backlog file.

- **Honest empty results.** If a session truly had no friction worth recording, say "Nothing worth logging from this session." and stop. The backlog's value depends on signal-to-noise.

- **Name a specific fix, not a direction.** "Better tooling" is a wish. "Add `dev/queryRecords.mjs` that takes `--endpoint --filter --group-by <field>` and outputs `(group_id, item_ids[], first_item, last_item)`" is a fix.

- **Don't conflate "I had to learn this" with "this is a friction point".** Onboarding cost is normal. The bar is: would a *future* agent (or the same agent in a fresh session) hit the same wall? If yes, log it. If it was a one-time learning curve about a well-documented pattern, don't.

## Dispositions

After producing the report, ask the user how to dispose of the findings. Three modes:

1. **Backlog** (default for non-trivial findings) — append each finding to `.claude/agent-friction.md` in the current repo. See backlog format below.
2. **Quick wins inline** — for any finding tagged `Quick win? yes`, offer to make the change immediately in the same turn (e.g., add the missing README, fix the naming, add the doc comment). Larger fixes go to the backlog regardless.
3. **Just the chat report** — ephemeral, no files written. Reasonable when the user is in the middle of unrelated work and wants the signal but not the action.

Present the three options as a numbered choice. Default to (1) if the user picks something ambiguous or just says "yes".

## Backlog file format

Path: `.claude/agent-friction.md` in the repo root. Created on first append. Header:

```markdown
# Agent Friction Log

Concrete codebase improvements identified during agent sessions. Each entry
captures something that, if fixed, would make a future agent session in this
area faster, safer, or less error-prone. Newest first.

Maintained by `/introspect`. To add an entry by hand, follow the same schema.
```

Each appended entry:

```markdown
## <YYYY-MM-DD> — <short imperative title>
- **Category**: <one of the 7>
- **Branch / PR**: <current git branch; PR # if known>
- **Session topic**: <one phrase: "adding manga OCR eval", "debugging billing folder attribution", etc.>
- **Cost**: <as above>
- **Observed**: <as above, with file:line refs>
- **Fix**: <as above>
- **Quick win?**: <yes | no | partial>
- **Status**: open
```

Sort newest-first within the file (insert below the header, above existing entries). When a finding is fixed, an engineer (or another `/introspect` run that notices the fix landed) sets `Status: done <YYYY-MM-DD> in <commit-or-PR>`.

## Dedup before appending

Before appending a finding to the backlog, scan the existing file (if it exists) for entries with `Status: open` whose **Fix** field overlaps substantially with the new one (same file path, same prescribed change, or same missing script). If you find a near-duplicate:

- Don't silently skip it.
- Show the existing entry's date and title in the chat report alongside the new finding, with a note: "**already logged** on YYYY-MM-DD as `<title>` — not re-appending".
- Let the user override if they think it's actually distinct.

## Things to avoid

- **Don't re-investigate.** This skill works only with what's in the current conversation. Don't run greps, fetch files, or browse the codebase looking for friction beyond what you already encountered. The signal you have *is* the signal.
- **Don't pad to hit a count.** Three sharp findings beat ten vague ones.
- **Don't write the fix in the report.** The Fix field names what should change, in one sentence. Actual implementation only happens for items chosen as quick wins, and only after the user picks disposition (2).
- **Don't log private/sensitive details to the backlog.** No API keys, customer data, or internal-only links. The backlog is checked into the repo.
- **Don't generalize beyond one repo.** Each backlog is scoped to its repo. If a finding is genuinely cross-repo (e.g., a Claude Code limitation), surface it in chat but don't write it anywhere — let the user decide.
- **Don't moralize.** "The codebase should be more X" is not a finding. Either there's a concrete fix or there isn't.

## Optional: Slack-ready summary

If the user adds `--slack` (or asks for a "summary I can share"), append a one-paragraph summary at the end of the chat report:

> Working on `<session topic>` in `<repo>`, hit `<N>` friction points worth tracking. Top issue: `<finding 1 title>` — `<one-sentence why it matters>`. Logged to backlog.

Keep it under 50 words. No emojis. No "I" — this is the user posting it.
