---
name: roger-review
description: Roger's maximum-scrutiny PR review — run codex exec (gpt-5.6-sol, adversarial), a tony-review-style Claude pass, an agents-chat debate (fable-5 vs gpt-5.6-sol), and harvest Cursor Bugbot comments, then synthesize every verified finding into ONE implementation-brief file a separate fixer agent can execute without conversation context. Use when Roger says "roger-review this PR", "/roger-review <PR>", "full review", or wants the multi-engine review treatment before merging. For a single-engine pass use /codex-review; for just a debate use /agents-chat.
---

# roger-review

Four review engines, one deliverable. You are the **orchestrator and final adjudicator**: launch
the slow engines in the background, do your own deep review while they run, harvest Bugbot, verify
every contested claim against the actual code, and write a single self-contained
**required-changes brief** that a fixer agent (with zero context from this session) can implement.
The brief is the product — everything else is raw material.

**Efficiency rules (non-negotiable):**

- Launch codex exec and agents-chat in the background FIRST — before your own review — so their
  minutes-long runtimes overlap your inline work. Never run them sequentially.
- Never read codex's full output log (it's ~1MB of tool noise); read only the tail containing the
  final findings message.
- Don't poll background tasks tightly; completion notifications re-invoke you.
- Don't produce intermediate artifacts beyond what the engines emit naturally — your own review's
  findings go straight into the synthesis.

## Step 0 — Resolve the PR and workspace

Parse `args`: a PR link/number, or empty → the current branch's PR (`gh pr view --json ...`).

```bash
gh pr view <n> --json number,title,body,author,baseRefName,headRefName,headRefOid,url,state,files,additions,deletions
```

- If the current directory is already checked out at the PR head, use it (verify
  `git rev-parse HEAD` == `headRefOid`; if the branch matches but is behind, `git pull`).
- Otherwise create a worktree at the head SHA. **Worktree naming gotcha:** the directory name must
  not contain the substrings `test`, `state`, or `scripts` — app/functions jest transform regexes
  match absolute paths and break (see memory `feedback_worktree_name_jest_transform`).
- If no PR exists, fall back to reviewing the branch diff vs `master` and skip Bugbot.

## Step 1 — Read the change and reconstruct intent

Read the full diff (`git diff <base>...HEAD`) and every changed file **in full** — you cannot write
good engine prompts or adjudicate findings from the diff alone. Then reconstruct the **original
intent**: PR title/body, linked issues, superseded PRs mentioned in the description, commit
messages, and any plan/spec the description references. You'll use this for the intent-misalignment
lens and to write the engines' "context" section.

Load repo review guidance: `docs/review-guidelines.md` and the relevant rows of
`docs/architecture_recipes.md` (in this repo, the recipes are the rubric — read the linked recipe
for any concern the PR touches).

## Step 2 — Launch the background engines (both at once, one message)

Write ONE adversarial prompt to the scratchpad (template below), tailored to this PR: fill in the
files-with-invariants list, the intent summary, PR-specific attack questions (the tailored
questions are where the value is — generic prompts get generic reviews), and every deliberate
tradeoff under "already adjudicated" so findings aren't wasted re-litigating design.

**Engine A — codex exec** (single-shot adversarial):

```bash
codex exec --model gpt-5.6-sol -c model_reasoning_effort="xhigh" \
  --sandbox read-only --skip-git-repo-check -C <WORKTREE> \
  "$(cat <SCRATCHPAD>/roger-review-prompt.md)" > <SCRATCHPAD>/codex-review-output.txt 2>&1
```

Run via Bash `run_in_background: true` (redirect inside the command as above).

**Engine B — agents-chat** (fable-5 vs gpt-5.6-sol debate — the skill's defaults; don't override):

```bash
python3 ~/.claude/skills/agents-chat/agents_chat.py "<same adversarial prompt, plus:>
Converge on a verdict (approve / approve-with-nits / request-changes) plus a findings list ordered
by severity, each with file:line and a real failure scenario. Litigate severity disagreements —
don't flatten them. This is review-only: do NOT change any code." \
  --first claude --no-plan --cwd <WORKTREE>
```

Also background. Start the live viewer (`serve.py --no-open`, same `--cwd`) and give Roger the URL
(http://127.0.0.1:8765). Kill the viewer when the session wraps up.

### Adversarial prompt core (fill every placeholder)

```markdown
You are performing an ADVERSARIAL review of PR #{{N}} ({{URL}}). Try hard to break this change.
Assume the author is competent and the happy path works — hunt for what they missed, and push back
on the overall approach if it's wrong, not just line-level details. Verify every claim against the
ACTUAL code and INSTALLED dependencies before asserting it; drop anything you can refute yourself.

Scope: branch {{HEAD_REF}} at {{HEAD_SHA}}, base {{BASE}} — inspect via `git diff {{BASE}}...HEAD`.
Files: {{one line per file: purpose + the invariant it must uphold}}
Original intent: {{2-4 sentences: the task/bug this PR claims to solve, per its description}}

Review lenses — cover ALL of these, report per-lens even if "nothing found":
1. Correctness & edge cases — boundaries, empty/null, concurrency & retry re-entry, error paths,
   partial failure, ordering assumptions, resource/cleanup leaks (incl. exception & timeout paths).
2. False assumptions — claims in code comments, the PR description, or commit messages that the
   code, the installed SDK source, or the environment contradicts. Verify against
   node_modules/installed versions, not memory. Environment-specific assumptions (emulator vs
   prod, local vs CI) are prime suspects.
3. Stale documentation — comments/docstrings that outlived the code, wrong version claims,
   placeholder/unfiled links, PR-description claims the diff doesn't implement, docs/README/
   CLAUDE.md drift, TODOs already done.
4. Unused/dead code — unused functions, variables, exports, fields, params, imports; dead
   branches; scaffolding for phases that don't exist (this repo forbids Phase-2-only stubs).
5. Intent misalignment — does the diff actually solve the stated task? Missing pieces, silent
   scope creep, a fix at the wrong layer, tests that pass without exercising the claimed behavior
   (vacuous/tautological tests are a top target).
6. Performance — N+1 queries/reads, unbounded loops or fan-out, hot-path allocations, missing
   pagination/limits, sync work in async paths, retry amplification, CI runtime impact.
7. Test adequacy via mutation thinking — for plausible single-line mutations to the new code,
   would any test fail? Survivors are findings with a suggested test.
8. Repo contract — {{repo-specific: recipes/RBAC/DNA/invariants that apply, or "n/a"}}.

PR-specific attack questions (find your own too):
{{3-8 tailored questions naming the riskiest mechanisms — locks, retries, migrations, caching,
authz — and asking for concrete failure constructions}}

Already adjudicated — do NOT re-report (deliberate decisions):
{{every conscious tradeoff; err toward listing more}}

Output: severity-ranked findings (BLOCKER/MAJOR/MINOR/NIT), each with file:line, a concrete
failure scenario walked through the code, VERIFIED-vs-SUSPECTED, and a minimal fix. End with a
verdict: approve / approve-with-nits / request-changes, and one paragraph on whether the approach
itself is sound.
```

## Step 3 — While the engines run (inline work)

**3a. Harvest Cursor Bugbot.** Bugbot material lives in three places — check all, filtering
authors matching `/cursor|bugbot/i`:

```bash
gh api repos/{owner}/{repo}/pulls/{n}/reviews --jq '.[] | select(.user.login|test("cursor|bugbot";"i"))'
gh api repos/{owner}/{repo}/pulls/{n}/comments --jq '.[] | select(.user.login|test("cursor|bugbot";"i")) | {path,line,body}'
gh api repos/{owner}/{repo}/issues/{n}/comments --jq '.[] | select(.user.login|test("cursor|bugbot";"i")) | .body'
```

Plus the `CURSOR_SUMMARY` block embedded in the PR body. If nothing is there yet and the head
commit is fresh (<~15 min), do ONE re-check after the background engines finish — never block on
Bugbot, and beware stale/decoy runs against an older commit (memory `feedback_bugbot_wait_race`):
only trust comments whose commit matches the head SHA you're reviewing.

**3b. Your own review (tony-review pass).** Load the tony-review mindset if the plugin is
installed — `~/.claude/plugins/marketplaces/rf-internal/plugins/rf-developer/skills/tony-review/references/review-mindset.md`
(the skill is user-invoke-only, but reading its references is how this skill embeds it). If the
path is missing, proceed with the lenses from the prompt template — they're a superset. Apply
every lens to the full diff yourself, severity-tagged (❌ Critical / ⚠️ Warning / 🤨 Minor). Where
an engine will need adjudication later, pre-verify the load-bearing facts now (installed SDK
versions, the seam a monkeypatch relies on, what the callers actually pass) — cite what you
checked. Do NOT write a separate artifact; your findings feed Step 4 directly.

## Step 4 — Synthesize and adjudicate

When both engines complete (read codex's output **tail only**; read `transcript.md` for the
debate), merge all four sources — codex, debate, your pass, Bugbot — into one findings list:

- **Dedupe** across sources; record which engines found each item (corroboration is signal).
- **Verify before including.** Every finding you didn't personally verify in Step 3b gets checked
  against the code now. Engines produce confident false positives; a finding nobody verified
  doesn't ship.
- **Severity disputes:** the debate's litigated outcome wins by default (it's already been
  attacked from both sides) — override only when your own verification contradicts it, and say so.
- **Keep the kill list.** Findings that were raised and refuted go in the brief as
  "explicitly optional / rejected, with reasoning" — this stops the fixer agent from re-adding
  gold-plating an engine suggested and the review rejected.

## Step 5 — Write the required-changes brief

Path: `<WORKTREE>/pr-reviews/<repo>-<PR>-required-changes.md`. **Never commit anything under
pr-reviews/** (local-dev artifact). The reader is an agent with ZERO context: no shorthand, no
references to "the debate" without the transcript path, every claim self-contained.

```markdown
# PR #{{N}} — Required changes before approving

Implementation brief from a multi-engine review (codex gpt-5.6-sol adversarial, Claude review
pass, fable-5↔gpt-5.6-sol debate, Cursor Bugbot) of {{URL}} ({{HEAD_REF}} → {{BASE}}, reviewed at
head {{HEAD_SHA}}). Verdicts: {{one line per engine}}. {{One sentence: is the APPROACH endorsed —
so the fixer hardens, not re-architects.}}

Files in scope ({{constraints, e.g. "test-only; ZERO production-code changes"}}): {{list}}
Line numbers are as of {{HEAD_SHA}}.

## Required change {{i}} — {{title}} ({{severity}})
**Where:** {{file:line(s)}}
**Problem:** {{mechanism + concrete failure scenario, walked through the code}}
**Fix:** {{specific enough to implement without judgment calls; sub-steps if needed}}
**Found by:** {{engines}}; verified {{how}}.

## Should-fix nits (same pass, all small)
{{numbered, each with file:line and the one-line fix}}

## Explicitly optional / rejected (do NOT implement)
{{each with the reasoning that killed it}}

## Constraints & verification
- {{scope guards, repo conventions (Prettier, .test.ts, no pr-reviews commits), assertion-keeping}}
- Acceptance bar: {{exact commands + expected results, incl. stress/repeat runs when flakiness is
  in scope; note environment prerequisites (emulators, Java, secrets) the fixer must have}}

## Source artifacts
{{paths: codex output, transcript.md, bugbot links}}
```

## Step 6 — Report to Roger

Lead with the consolidated verdict and the per-engine verdict table, then the required list in one
screen, disagreements you adjudicated (and how), and the brief's path. Offer: implement the fixes
here, or hand the brief to the fixer agent. Remind about the viewer URL if the debate transcript
is worth reading, then kill the viewer process when done.

## Notes & gotchas

- `codex`, `gh`, and `python3` must be on PATH; agents-chat needs `claude` too. A missing engine
  degrades gracefully: note it in the brief's engine table, don't silently skip synthesis.
- tony-review is `disable-model-invocation` — never call it via the Skill tool; read its reference
  files directly (Step 3b).
- agents-chat writes `transcript.md` / `.agents_chat_state.json` into the worktree — leave them
  uncommitted; `--continue` can resume the debate later with new information (e.g. after fixes:
  "changes implemented, re-review").
- Typical wall-clock: codex ~5-10 min, debate ~10-20 min. Your inline pass should finish first —
  if you're idle, pre-verify more engine-independent facts; don't just wait.
- If the PR is huge (>~2k changed lines), scope each engine to the riskiest surface and say so in
  the brief ("not reviewed: X") — silent partial coverage reads as full coverage.
