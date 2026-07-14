---
name: roger-build
description: Run a substantial build/analysis task the way Roger likes it — decompose into steps, delegate each well-defined step to an Opus 4.8 subagent (to conserve the main context window), commit at each step, and run an adversarial review at each step before moving on. Use when Roger says "roger-build this", "do this the usual way", "build this step by step with subagents", or kicks off a multi-step implementation/analysis and wants the disciplined subagent + commit + review cadence. For a one-off codex review use /codex-review; for a two-model debate use /agents-chat.
---

# roger-build

Roger's standard operating procedure for any task big enough to have multiple steps. The whole
point is **protect the main-thread context window while guaranteeing capability**: you (the main
thread) stay a thin orchestrator, and the heavy lifting happens in Opus 4.8 subagents whose output
you distill rather than absorb wholesale. Every step ends in a durable checkpoint (a commit or a
review-gated artifact) and an adversarial review before the next step starts.

## The four non-negotiables

1. **Opus 4.8 subagents for every well-defined step.** Spawn a subagent (`model: "opus"`) with a
   crisp, self-contained instruction for each chunk of work — recon, a build, a migration slice, an
   analysis pass. Run independent subagents in parallel (one message, multiple `Agent` calls). You
   write the instructions; they do the token-heavy work.
2. **Conserve your own context.** Do NOT read large logs, metric dumps, whole subsystems, or build
   output into the main thread — delegate that to a subagent and take back only the distilled
   result. You orchestrate and decide; you don't accumulate raw material.
3. **Commit at each step.** After each step lands, make a durable checkpoint. For code: a real
   `git commit` with a clear message (follow the repo's commit-message conventions incl. the
   Co-Authored-By / session trailers). For analysis/dashboards where there's nothing to commit: a
   written checkpoint artifact + explicit "Step N complete" state, so work survives a context reset.
4. **Adversarial review at each step.** Before advancing, subject the step's output to a skeptical
   pass — `/codex-review` (single-model adversarial), `/agents-chat` (Claude+Codex debate), or a
   dedicated "fresh-eyes / refute-this" Opus subagent. Triage the findings, fix what holds up, then
   proceed. Don't batch all reviews to the end.

## How to run it

### Step 0 — Plan the decomposition (main thread, cheap)

Break the task into ordered steps, each one small enough to hand to a single subagent with a
self-contained brief. Identify which steps are independent (parallelizable) vs. sequential. If the
task or the step boundaries are ambiguous, confirm the plan with Roger before spending subagent
tokens — a wrong decomposition is the expensive mistake here.

Prefer a review gate between steps: for analysis work Roger often wants to inspect a step's result
before you build on it ("Ready for review before Step N" — then stop and wait).

### For each step

1. **Delegate.** Spawn an Opus 4.8 subagent with a precise brief: the goal, the inputs/paths, the
   constraints, and exactly what to return (distilled — findings/diff summary/decision, not raw
   dumps). Parallelize independent subagents in a single message. Example:

   ```
   Agent(
     subagent_type: "general-purpose",   // or a specialized agent when one fits
     model: "opus",
     description: "<3-5 word label>",
     prompt: "<self-contained brief: goal, files/paths, constraints, and the exact
              distilled output to return>"
   )
   ```

   Use `Explore` for read-only recon, `general-purpose` for build/execute, or a repo-specific agent
   (e.g. `test-runner`, `pr-preparation`) when it matches. Reserve `run_in_background: false` for
   when you truly need the result before continuing.

2. **Distill + checkpoint.** Take the subagent's summary, verify the key claims against reality
   (don't blind-trust), and commit. Code → `git commit`. Analysis → write/update the checkpoint
   artifact and mark "Step N complete".

3. **Adversarial review.** Run a review over just this step's change:
   - Code: `/codex-review` on the step's commit/diff, or a "refute this implementation" Opus
     subagent, or `/agents-chat` for a genuine design fork.
   - Analysis: a fresh Opus subagent asked to attack the numbers/assumptions, or a review gate with
     Roger.
   Triage findings (verify each yourself — reviewers throw confident false positives), fix what
   survives, re-commit, and only then advance to the next step.

### Long-running / unattended

If Roger steps away ("keep the work going", "run overnight"), keep the loop alive with `/loop`
(e.g. every 30 min) and honor pause requests — "gracefully pause all subagents" means finish or
checkpoint in-flight subagents and stop spawning new ones, leaving durable state behind.

## Guardrails

- **Don't collapse the cadence.** The value is in per-step commit + per-step review. Don't do all
  the work then one big review at the end — that's the anti-pattern this skill exists to prevent.
- **Don't let the main thread bloat.** If you find yourself about to read a giant file/log/output
  into your own context, stop and delegate it instead.
- **Verify before trusting** — both subagent results and reviewer findings. You are the decider;
  they are instruments.
- **Match the medium.** "Commit" means a git commit for code and a durable written checkpoint for
  analysis/dashboards — the invariant is *work survives a context reset at every step*.

## Relationship to other skills

- `/codex-review` — the adversarial-review instrument this skill invokes per step (single-model).
- `/agents-chat` — use when a step needs a real two-model debate, not just a review.
- This skill is the orchestration wrapper; those are the tools it reaches for.
