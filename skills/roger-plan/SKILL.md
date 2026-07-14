---
name: roger-plan
description: Plan a substantial feature/change the way Roger likes it — a Fable 5 vs GPT 5.6 Sol adversarial debate (via agents-chat) that opens with a fast parallel interview of Roger on product/goal/premise questions, uses cheap subagents for grunt work, converges on a plan.md shaped for /roger-build, and ends with a visual explainer website. Use when Roger says "roger-plan this", "plan this properly", "have the agents plan this", or kicks off planning for a multi-step task that deserves two frontier models pushing back on each other. For the build phase use /roger-build; for a plain debate use /agents-chat.
---

# roger-plan

Planning for tasks that deserve real intelligence: two frontier models — **Claude Fable 5** and
**OpenAI GPT 5.6 Sol**, both at **high** reasoning effort — debate the design and push back on each
other until they converge. Cross-model disagreement is the value: one model catches what the other
hand-waves. You (the main thread) are the orchestrator and Roger's interface; the debaters do the
thinking; cheap subagents do the fetching.

The output is twofold: a `plan.md` shaped so `/roger-build` can execute it step-by-step, and a
static explainer website (via `/feature-explainer`) so Roger can see the final shape of the
solution visually.

## Models (non-negotiable defaults)

- Claude side: `claude-fable-5`, effort `high` (verified to resolve headless — do NOT use the
  `[1m]` suffix, which 404s in `claude -p`).
- Codex side: `gpt-5.6-sol`, `model_reasoning_effort=high` (slug verified).

Set via the agents-chat env knobs:

```bash
export AGENTS_CHAT_CLAUDE_MODEL="claude-fable-5"
export AGENTS_CHAT_CLAUDE_EFFORT="high"
export AGENTS_CHAT_CODEX_MODEL="gpt-5.6-sol"
export AGENTS_CHAT_CODEX_EFFORT="high"
```

Only deviate if Roger explicitly asks.

## Phase 0 — Recon dossier (cheap, parallel)

Before any expensive model turn, spawn cheap `Explore` subagents (in one message, parallel) to map
the terrain: relevant files/modules, existing patterns and recipes that apply (check
`docs/architecture_recipes.md` in this repo), current behavior, adjacent prior art. Distill into
`recon_dossier.md` in the working directory — file paths, key functions, constraints, with
`file:line` references. Both debaters get this identical dossier so neither burns frontier tokens
on discovery.

Keep Phase 0 under a few minutes. It's a map, not an audit.

## Phase 1 — The interview (fast; Roger wants to context-switch)

Run BOTH models **in parallel** (direct CLI calls in the background, not via agents_chat.py) with
the task + dossier, asking each for its clarifying questions for Roger. Speed matters more than
cross-pollination here — Roger answers and moves on to another task.

```bash
claude -p --model claude-fable-5 --effort high "$(cat interview_prompt.md)" > claude_questions.md 2>&1 &
codex exec --skip-git-repo-check -m gpt-5.6-sol -c model_reasoning_effort="high" -s read-only \
  "$(cat interview_prompt.md)" -o codex_questions.md > /dev/null 2>&1 &
wait
```

The interview prompt must enforce this rubric — every question ships with:

1. **The decision it unblocks** (one line).
2. **A proposed default** — what will be assumed if Roger says "don't care" / "don't know".
3. **A category**: `user-impact` / `goal-priority` / `premise-check` / `org-context`. Questions
   answerable from the code (`code-internal`) are forbidden — the agents resolve those themselves
   during the debate, via recon or their own subagents.

Then, quickly: merge and dedupe the two lists (flag overlap — "both models asked this" signals what
genuinely matters), cap at ~6–8, and present to Roger via AskUserQuestion (options should include
the proposed default; "don't know / don't care" simply promotes the default). Every
default-accepted answer goes into an **assumptions ledger** with a revisit trigger.

Do not editorialize or slow-walk this phase. Merge, ask, record, move on.

## Phase 2 — The debate

Launch `/agents-chat` (the `agents_chat.py` harness) with the env overrides above and an opening
prompt containing: the task, the recon dossier path, Roger's interview answers verbatim, the
assumptions ledger, and the debate rules below.

### Debate rules (bake into the opening prompt)

- **Premise attack first.** Before solutioning, each agent spends its first turn trying to refute
  the task framing itself: is this the right problem? Is there a 10x simpler path? Informed by
  Roger's answers.
- **Anti-convergence-theater.** Every turn must contain that agent's strongest remaining objection
  to the other's current position. "I agree" is only legal alongside a concession log: *what I
  conceded and the specific argument that moved me*. Polite pseudo-convergence is failure.
- **Convergence has criteria, not vibes.** The debate ends when both agents sign a checklist: all
  decisions enumerated; each decision records the losing alternative and why it lost (a **minority
  report**); no remaining unstated disagreements.
- **Turn cap ~8–10** with disagree-and-commit: unresolved disagreements get written into the plan
  as flagged risks for Roger to adjudicate — neither model caves for the sake of harmony.
- **Cheap subagents for grunt work.** Both agents should delegate mechanical tasks (reading many
  files, running searches, summarizing logs) rather than doing them inline — the Claude side via
  its Task tool, the Codex side by shelling out to `codex exec` / `claude -p`. Prefer lighter
  models whenever possible; they know best which. The frontier model's job is **context curation**:
  give each subagent a surgical brief — exact files, exact question, exact output shape — never "go
  look around." Never delegate judgment; subagents fetch and summarize, the debater decides. If a
  lookup is one file read, just read it — no ceremonial delegation.
- **Ask Roger when it's super important.** If a genuinely new product/goal/premise question emerges
  mid-debate that materially changes the design, emit a clearly marked block:
  `QUESTION FOR ROGER: <question + why it matters + proposed default>` and continue with the
  default until answered. No heavy protocol around it — reserve it for things that matter.

### Orchestrating

Run the harness in the background and monitor the transcript between turns. When a
`QUESTION FOR ROGER` block appears, surface it to Roger immediately (AskUserQuestion), then resume
the discussion with the answer injected (agents-chat supports resume). Keep Roger's wait time near
zero — he may be on another task; a proactive notification beats blocking.

## Phase 3 — The plan

The closing turns produce `plan.md`, structured for `/roger-build` to consume:

- **Goal** + Roger's interview answers (verbatim) + the assumptions ledger (with revisit triggers).
- **Decision log** — every decision with its minority report.
- **Step decomposition sized for one Opus subagent per step**, each step with: its commit
  checkpoint, and what the per-step adversarial review should specifically attack.
- **Concrete values inline** — actual flag names, endpoints, function signatures, arg values.
  No "configure appropriately". (Standing Roger feedback: show real values in plans; prefer
  state-based verification over tool-call-args checks.)
- **Risks** + any disagree-and-commit leftovers, clearly flagged for Roger's adjudication.

Sanity-check the plan yourself before presenting: does each step stand alone? Do the file paths
exist? Are the decisions consistent with Roger's answers?

## Phase 4 — The explainer website

Once `plan.md` is final, invoke the **`/feature-explainer`** skill against the converged design —
ask it for the visual shape of the solution: architecture/component diagrams, **sequence diagrams**
of the key flows, before/after comparisons, and the step plan as a visual roadmap. Charts follow
the dataviz skill's guidance.

Deliver via `SendUserFile` with `display: "render"` (the claude.ai artifact viewer can blank on
pages >~3KB, so prefer SendUserFile or a local server for viewing).

## Handoff

End by telling Roger: the plan is at `plan.md`, the explainer is delivered, and the natural next
step is `/roger-build` on the plan. Do not start building unless asked.

## Relationship to other skills

- `/agents-chat` — the debate harness this skill drives (Phase 2).
- `/feature-explainer` — builds the Phase 4 website.
- `/roger-build` — consumes the plan; the step decomposition is written for it.
- `/codex-review` — not used here; that's the per-step review instrument during the build.
