---
name: codex-review
description: Run an adversarial code review of the current change with OpenAI Codex (`codex exec`, gpt-5.5 / xhigh effort, read-only), then triage its findings and implement the ones that hold up. Use when the user asks to "codex review this", "run a codex adversarial review", "have codex review my code/commit/branch", or wants a skeptical second-model pass over a diff before shipping. Not the same as /agents-chat (a multi-turn Claude+Codex debate) or /code-review (Claude-only review).
---

# codex-review

Drive a single-shot **adversarial** review of the current change through `codex exec`, then triage
the results and implement what survives scrutiny. Codex runs read-only; you own the analysis and
any edits.

This is a one-way review (Claude prepares → Codex reviews → Claude triages), not a debate. For a
back-and-forth between the two models, use `/agents-chat`. For a Claude-only review, use
`/code-review`.

## Model & sandbox (non-negotiable defaults)

Always invoke with **`--model gpt-5.5`** and **`-c model_reasoning_effort="xhigh"`**, sandboxed
**`-s read-only`**. These are deliberate — a shallower model or effort defeats the purpose. Only
deviate if the user explicitly asks.

## Step 1 — Establish scope

Figure out exactly what Codex should review. From `args` or the conversation:

- **A single commit** → `git show <SHA>` (default to `HEAD` if the user just says "this commit").
- **A branch vs its base** → find the base (usually `master`; `git merge-base HEAD master`), then
  `git log --oneline BASE..HEAD` + `git diff BASE..HEAD`.
- **Uncommitted work** → `git diff` (and `git diff --staged`); tell Codex the change is uncommitted.

Confirm the worktree path (`pwd`) — you'll pass it as `-C`. If the user is in a git worktree for a
feature branch, use that path.

## Step 2 — Build the prompt

Read the change yourself first — you cannot fill in the template well without knowing what the
change does, which files it touches, what invariants matter, and which tradeoffs were deliberate.
Then write a filled-in copy of the template below to a temp file (use the scratchpad dir, e.g.
`.../scratchpad/codex_review_prompt.md`).

Fill every `{{PLACEHOLDER}}`. The three sections that most determine review quality:

- **File/module list** — one line each on purpose + the invariant that file must uphold.
- **"Already adjudicated"** — every conscious tradeoff, so Codex spends findings on real bugs, not
  re-litigating your design. This is the highest-leverage section; err toward listing more.
- **Pass 4 invariants** — pick the ones that actually apply (drop money/residency for a pure
  frontend change; add auth/RBAC for anything touching permissions).

### Prompt template

```markdown
You are performing an ADVERSARIAL code review. Your job is to find real defects — not to
summarize, not to compliment. Verify everything against the ACTUAL code (and, where relevant, the
INSTALLED dependencies) rather than reasoning from the diff alone; the defects that matter are
often subtle. You have read-only access; do NOT modify any file.

## Scope

Review {{WHAT: e.g. "commit HEAD (SHA) on branch X" OR "the N commits on this branch vs base SHA"}}:

    {{HOW TO SEE IT: e.g. git show HEAD  |  git log --oneline BASE..HEAD && git diff BASE..HEAD}}

What the change does, and the files it touches:

- {{FILE / MODULE 1}} — {{one-line purpose + the key invariant or mechanism it must uphold}}
- {{FILE / MODULE 2}} — {{...}}
- {{TESTS}} — {{where the new/changed tests live}}

{{OPTIONAL 2-4 sentences of CONTEXT: the bug being fixed, the prod incident, the correctness model
or plan this implements — enough that a cold reader knows what "correct" means here.}}

## How to review (do ALL passes; do not stop at the first finding)

Pass 1 — End-to-end trace. Read every touched file IN FULL, then read its real consumers
({{name them: callers, endpoints, the framework entry point}}). Trace one representative
{{operation/request/turn}} end-to-end and check where each assumption in the new code actually
gets exercised.

Pass 2 — State & concurrency. Enumerate the lifecycle of any mutable/shared state
({{name it: instance fields, locks, timers, cached values}}). Can two operations overlap? Look
for: torn writes, double-owners, resource leaks (readers/handles/timers not released on every
path), abort/cancel races, and retry re-entry.

Pass 3 — Contract verification. Do NOT trust the code's comments about {{the SDK / API / schema}};
verify against the INSTALLED source ({{paths, e.g. node_modules/.../dist/index.d.ts}}). Confirm the
real shapes, unions, and error/retry semantics match what the code assumes. Count worst-case
amplification for retries/fallbacks and decide if it's a real problem.

Pass 4 — Domain invariants. Try to construct a REACHABLE production scenario that violates a
core invariant: {{list the ones that matter here — correctness / data-integrity / money /
residency / security / auth / idempotency}}. Walk the exact sequence that breaks it.

Pass 5 — Test adequacy via mutation thinking. For each plausible single-line mutation to the new
code, decide whether ANY existing test would fail; report the survivors as coverage gaps with a
concrete suggested test. Flag tautological tests (asserting the mock, not the behavior) and tests
that pass vacuously.

Pass 6 — Stale documentation & comments. Compare the prose against what the code actually does and
report every drift as a finding: the PR description / commit message ({{git show / gh pr view}});
in-code comments and docstrings on or near the changed lines; and any docs, READMEs, or CLAUDE.md
touched by or describing this change. Flag claims that no longer match the code — wrong function
or file names, stale signatures/flags/defaults, described behavior the code doesn't implement,
comments that outlived the code they explain, and TODOs already done or now impossible. A comment
or doc that lies is a defect, not a nit.

## Already adjudicated — do NOT re-report these (deliberate decisions)

- {{decision 1 and why}}
- {{decision 2 and why}}
- {{...list every conscious tradeoff so codex doesn't waste findings on them}}
- {{repo conventions that look wrong but aren't — e.g. structural typing, no extra try/catch}}

## Output format

A severity-ranked list — CRITICAL (correctness/data/money/residency/security bug reachable in
production) / MAJOR (wrong behavior in a realistic scenario, or a survived mutation on a critical
path) / MINOR (hygiene, incl. stale docs/comments). For each finding:

1. `file:line` + a one-sentence problem statement.
2. The concrete scenario: walk the exact data/sequence through the code, naming functions and values.
3. Whether you VERIFIED it by tracing the code/deps, or it is SUSPECTED (and what would confirm it).
4. A minimal suggested fix that does NOT expand scope.

Before reporting each finding, actively try to REFUTE it yourself; drop anything you refute. If a
pass finds nothing, say "Pass N: nothing found" — do not pad. End with a one-paragraph verdict:
ship / ship-after-fixes / do-not-ship.
```

## Step 3 — Run Codex

Codex reviews take minutes and produce large output, so run it backgrounded and capture to a file.
Use absolute paths for both the prompt and the output file.

```bash
cd {{WORKTREE_PATH}} && nohup codex exec \
  --model gpt-5.5 \
  -c model_reasoning_effort="xhigh" \
  -s read-only -C {{WORKTREE_PATH}} \
  "$(cat {{PROMPT_FILE}})" > {{OUTPUT_FILE}} 2>&1 &
echo "codex pid: $!"
```

Then wait for it to finish — poll the output file / process rather than blocking. A `Monitor`
until-loop on the pid (or on a completion marker in the output) is a good fit; do **not** foreground
`sleep`. Tell the user it's running and roughly how long it may take.

## Step 4 — Triage and act

When Codex finishes, read the full output, then:

1. **Independently verify each finding** against the actual code before trusting it. Codex at xhigh
   is strong but still produces confident false positives — check the cited `file:line` and walk the
   scenario yourself.
2. **Separate real defects from noise** — drop anything that's wrong, already handled, or an
   intentional tradeoff you listed under "already adjudicated".
3. **Present a triaged summary** to the user: which findings are real (ranked by severity), which
   you're dismissing and why, and your recommendation on the ship/no-ship verdict.
4. **Offer to implement** the fixes that hold up. Don't auto-apply — let the user pick, unless they
   already said "fix what you find."

## Notes

- `codex` must be on PATH (`codex-cli`). If it errors on auth or isn't found, tell the user; don't
  silently fall back to a Claude-only review.
- `gpt-5.5` / `xhigh` are also the user's `~/.codex/config.toml` defaults, but pass them explicitly
  so the skill is robust to config changes.
- Keep the prompt and output files in the scratchpad dir, not the repo.
