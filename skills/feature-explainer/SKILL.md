---
name: feature-explainer
description: Create or iterate on a self-contained static HTML page that explains how a feature, system, or branch works — with SVG diagrams, commit-derived narrative, side-by-side comparisons, class-relationship maps, and layered drill-downs. Accepts free-form `args` for focus hints ("focus on how firestore is emulated") and iteration requests ("iterate, go deeper on X and Y"); in iteration mode the skill appends to the existing page and never modifies prior content unless asked. Use when the user asks for an "explainer", "walkthrough", "how it works" page, architecture writeup, or similar educational artifact about code they own. Not for API reference docs, user-facing product docs, or one-pager summaries.
---

# feature-explainer

Produce one HTML file that makes a non-trivial piece of the codebase click for a colleague who has never seen it before. The hallmark of a good output is that the reader can stop reading at any section and still walk away with a coherent mental model.

## Arguments (`args`)

The skill accepts a free-form string that shapes how the current invocation runs. Parse it before starting any research and decide which **mode** to run in.

### Mode detection

Inspect `args` for these trigger phrases (case-insensitive):

- **Iteration mode** — triggered by words like `iterate`, `go deeper`, `expand`, `add more`, `append`, `extend`, `continue`, `more on …`, or any reference to an *existing* explainer (e.g. "the page we made", "the existing explainer"). In iteration mode, you are **adding** to a pre-existing HTML file, not replacing it.
- **Focus mode** — triggered by words like `focus on`, `emphasize`, `specifically`, `only the X part`, `zoom in on`. A focus hint narrows the scope of a fresh page: still create a full explainer, but give the specified topic disproportionate weight (more sections, more diagrams, more code excerpts).
- **Create mode** (default) — no `args`, or args that just name the feature. Follow the full structural template as-is.

A single `args` string can carry both hints (e.g. "iterate, focus on firestore emulation and copyShared.sh"). Apply both: iterate (append-only) *and* weight the new sections toward the focus topics.

### Iteration mode — rules

When iterating on an existing explainer:

1. **Find the target file first.** If the user references a page ("the explainer", "the page we made", "how-it-works.html"), locate it with `ls *.html` at the repo root and `find . -name "*.html"` across the tree. If there are multiple candidates, ask the user which one before editing. If there's exactly one plausible match, proceed.
2. **Read the entire file before writing.** You need to know which sections already exist, which anchor IDs are taken, and what the visual system / palette already looks like. Iterations must match the existing style exactly — don't introduce a new card style or color. Reuse the `<style>` block that's already there.
3. **Append, never modify.** Treat the existing HTML as immutable unless the user explicitly asks you to change something. New content goes at the bottom of `<main>`, before the `<footer>`. Use `Edit` to insert the new section — do not rewrite the whole file.
4. **Wrap appended content in a banner.** Start each iteration with a small header that makes it visually distinct but still belongs to the page. Use this pattern:

    ```html
    <!-- ═══ APPENDED <date> ═══ -->
    <h2 id="deeper-<topic-slug>">
      <span class="num">+</span>Going deeper: <topic>
    </h2>
    <p class="lead">Follow-up to the original sections. The user asked for more detail on …</p>
    ```

    Use `<span class="num">+</span>` (or a section number beyond the original count) so the appended h2 visually reads as an addition, not a replacement. Cross-link back to the original section the user is extending ("expands section 5 · Layers above").
5. **Add the new section to the TOC** via an `Edit` that inserts one `<li>` in the existing `<ol>`. This is the only modification allowed without explicit permission — without it, the appended section is orphaned.
6. **Diagrams in iterations follow the same rules as fresh pages** (inline SVG, bigger fonts, labeled edges, relationship diagrams when warranted). Reuse existing colors and arrow-marker IDs where possible, but if you need new markers, give them distinct IDs so they don't collide with the originals.
7. **Explicit-change exceptions.** If the user says things like "rename section X", "fix the diagram in Y", "the TL;DR is wrong" — those are explicit permissions to modify. Confirm in one sentence ("Updating section 3's diagram per your note") and use `Edit` narrowly on just that piece.

### Focus mode — rules

When the user passes a focus hint:

1. Acknowledge the focus in one sentence at the start of your research plan, e.g. *"Creating a fresh explainer focused on how Firestore is emulated — that will get the TL;DR diagram plus a dedicated drill-down section."*
2. Keep the full structural template, but **allocate ≥40% of the page's diagrams and prose to the focus topic.** The TL;DR diagram should showcase the focus topic directly.
3. Other sections still exist — skipping context makes the focus section harder to understand — but shrink them to the minimum needed to set up the deep dive.

### Examples

| `args` | Mode | Action |
|---|---|---|
| *(empty)* | Create | Full explainer, default template. |
| `"focus on how firestore is emulated"` | Create + Focus | Fresh page; weight toward emulation. |
| `"iterate on it, go deeper on --mode=mocked and copyShared.sh"` | Iterate + Focus | Find existing page, append two new sections titled for each focus topic. |
| `"iterate: add a section on the invariants system"` | Iterate | Append one new section. |
| `"update the tldr diagram to show X"` | Explicit change | Edit that diagram only; confirm first. |

## When to use this skill

**Do use when** the user asks for:
- "Explain how X works" as a static web page, report, or document
- An architectural explainer, walkthrough, or deep-dive
- A diagrammed summary of a feature or branch
- Onboarding material for a subsystem

**Don't use when** the user asks for:
- API reference docs (use their existing doc tooling)
- A README (write markdown directly)
- A one-paragraph summary (respond in chat)
- Slide decks or marketing material
- A plan or spec for work that hasn't happened yet — this skill explains code that exists

## Required inputs (gather before writing)

Before producing any HTML, spend enough tool calls to answer every question below. The page's quality is set by research depth, not by CSS polish. If the user hasn't told you, read the code.

1. **What is the feature, and what commits/files implement it?**
   Use `git log` with a range (e.g. `master..HEAD`, or commits touching a path). Read the commit bodies — they're the richest narrative source most repos have.
2. **What was it like before?** Find the seam that was carved out (refactor commits that made the new thing possible). This becomes the "how we got here" section.
3. **What are the key source files and functions?** Read them fully, not just signatures. Note the unfamiliar parts — if *you* had to pause, the reader will too.
4. **Where does this feature meet the rest of the system?** External APIs, emulators, env vars, shared packages, third-party SDKs. These are usually the most confusing parts and deserve their own diagram.
5. **What's the runtime flow?** Trace a single request/case/invocation end-to-end. This becomes the big flow diagram.
6. **What gotchas exist?** Module-load-time captures, env-var ordering, optional fallbacks, auth prerequisites. Surface these as sidebars/notes.

If any of the above feels thin after research, ask the user — don't invent.

## Structural template

Follow this outline unless the subject matter strongly suggests otherwise:

1. **Hero** — title, one-sentence pitch, 4–6 at-a-glance facts (branch, SDK, model, etc.)
2. **TOC** — 2-column list of anchor links
3. **TL;DR diagram** — the single most important picture, on its own. Often a side-by-side "before/after" or "prod/eval" comparison with a shared middle.
4. **Timeline** — vertical timeline tracing the commits that got us here, short-hash + one-sentence takeaway per step. Lifts narrative from commit messages.
5. **Layers / core concepts** — a grid diagram naming the 3–5 main pieces with their files and one-line roles.
6. **Component relationship map** — a dedicated section with the relationship diagram (see diagram type #5). Each node carries its file path so readers can jump to source. Follow with a short table listing every node, its role, and one-line summary of who it talks to.
7. **The interface / integration point** — tables and code snippets showing exactly what is shared vs swapped between contexts (prod vs eval, v1 vs v2, old vs new).
8. **The tricky infra hop** — any place where the feature reaches outside its own directory (emulators, external APIs, module-load-order gotchas). Usually deserves its own diagram.
9. **Third-party / SDK integration** — if the feature uses an SDK, split its roles clearly. Most SDKs play 2+ roles; conflating them is the #1 source of reader confusion.
10. **End-to-end flow** — the full execution path as a numbered step diagram.
11. **Outputs / persistence** — where does the result go? Local files, dashboards, databases.
12. **How to run it / quickstart** — concrete commands. Separate one-time setup from every-run steps.
13. **Footer** — branch + commit SHA for traceability.

Skip sections that don't apply rather than padding them. Four great sections beat nine mediocre ones.

## Diagram guidelines (this is where the skill earns its keep)

**Use inline SVG, not Mermaid or ASCII.** SVG gives precise control, renders without network or JS, and scales to mobile. Mermaid is tempting but its auto-layout usually fights you for anything non-trivial. ASCII looks amateurish next to the rest of the page.

**Always include these five diagram types when the subject supports them:**

1. **Side-by-side comparison** (prod vs eval, before vs after, v1 vs v2). Three columns: left = one context, middle = shared core, right = the other context. Use two distinct accent colors for the contexts and a neutral/warm color for the shared middle. This diagram alone often conveys 50% of the insight.

2. **Sequential boxes with arrows** for the "tricky infra hop." Numbered STEP 1 / STEP 2 labels in small caps. Destination box filled (not outlined) so the endpoint visually "lands."

3. **Grid of concept boxes** for the "layers" section. 3–5 boxes in a row, each with header + divider + bulleted body. Colored borders matching the domain (blue for product, purple for eval, green for verification, etc.).

4. **Full-flow diagram** — numbered vertical stack for the "end-to-end flow." Nest sub-steps as smaller boxes within a larger container. Use one full-width container for the "heavy part" (the agent loop, the render cycle, whatever the core mechanism is).

5. **Component/class relationship diagram** — **required whenever the feature has more than ~5 interacting pieces.** Shows which classes, components, or modules talk to each other. Rules:
   - Each node is a rounded box containing **two lines of text**: the top line is the class or component name in bold (`font-weight="700"`, size 15–16px), the bottom line is the file path in monospace at 11–12px in muted color (`#64748b`). Example: `AgentAdapter` on top, `agent/AgentAdapter.ts` below.
   - Group related nodes inside a faint container rectangle with a dashed stroke and a small-caps label (e.g. "CORE", "ADAPTERS", "RUNTIME"). This signals architectural layers at a glance.
   - Edges are labeled verbs — "calls", "implements", "reads", "writes to", "emits trace to". Put the label on or next to the line in 11–12px muted text. An unlabeled arrow is a missed explanation.
   - Use different arrow styles to encode relationship kinds: solid for "calls/uses", dashed for "implements/extends", dotted for "observes/emits". Define each style once in `<defs>` with distinct marker colors, and add a mini-legend in the diagram corner.
   - Prefer a radial or grid layout over a long vertical chain — relationships branch, so the diagram should too. Leave generous whitespace between nodes (at least 30–40px gaps) so edges don't cross text.
   - If the diagram gets crowded, split into two: one showing control flow (who-calls-whom), one showing data flow (who-reads-what). Don't cram both into one picture.

**SVG craft rules:**
- Fixed `viewBox` (e.g. `0 0 1040 560`), `width: 100%; height: auto` in CSS so it scales.
- Define arrow markers once in `<defs>` and reuse them — don't redraw arrowheads.
- Use system fonts in the SVG: `font-family="-apple-system, system-ui, sans-serif"`.
- Round all box corners (`rx="8"` or `rx="10"`) — squared corners look dated.
- **Font sizes inside diagrams must be legible at zoom-out.** Body labels 13–15px, secondary/caption text 12–13px, section headers inside diagrams 16–20px, tiny footnotes no smaller than 11px. When in doubt, go bigger — diagrams render smaller than they look in the viewBox. If you're squeezing text by dropping to 10px, **grow the diagram's viewBox instead** (e.g. 1200×620 instead of 1040×560) and keep the fonts big. A diagram that scrolls horizontally is better than one where users squint.
- Give text enough breathing room: line spacing inside boxes should be ~18–20px between lines of 13px text, not 14px.
- For filled boxes with white text, pair with a slightly darker stroke of the same hue (e.g. `#0ea5e9` fill, `#0284c7` stroke).
- Wrap every diagram in `<div class="diagram">` with a subtle border and `overflow-x: auto` so wide diagrams scroll on narrow screens instead of clipping.

**Legends:** include a small legend bar above any diagram that uses more than two accent colors. A 10×10 color swatch + short label, flex-wrapped.

## Visual system (copy this palette)

A consistent palette across sections is what makes the page feel designed rather than hand-rolled. Start from these values and adjust only if the subject matter demands it (e.g. a different accent makes semantic sense):

```
--bg: #f6f8fb              (page background)
--surface: #ffffff         (cards)
--surface-alt: #f8fafc     (legend bars, subtle stripes)
--border: #e2e8f0          (card edges)
--text: #0f172a            (body)
--muted: #475569           (secondary text)
--accent: #2563eb          (default accent / CTAs)

Context colors (pick per-page which "kind of thing" each represents):
--prod: #0ea5e9 / --prod-bg: #e0f2fe     (one side of a comparison)
--eval: #8b5cf6 / --eval-bg: #ede9fe     (the other side)
--mock: #f59e0b / --mock-bg: #fef3c7     (swapped / inserted pieces)
--ok:   #16a34a / --ok-bg:   #dcfce7     (verification / success)
--ls:   #059669 / --ls-bg:   #d1fae5     (external SDK / infra)
```

**Typography:** system sans (`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto`), with a monospace stack for code (`"SF Mono", "Cascadia Code", "Fira Code"`). Body 0.9–1rem, code 0.82–0.85em. Generous line-height (1.55–1.6).

**Hero:** dark gradient background (`linear-gradient(135deg, #1e293b 0%, #312e81 100%)`), white text, uppercase eyebrow label above the H1, 6-cell fact grid in the lower half.

**Cards:** white surface, 1px `--border`, 14px radius, 22–24px padding. Two-column layouts collapse to one column below 760px.

**Code blocks:** dark (`#0f172a`), light text (`#e2e8f0`), 10px radius, no external syntax highlighter. Hand-tag keywords/strings/comments with `.kw/.str/.com/.fn/.ty` spans in inline color:

```
.kw { color: #f472b6; }   /* keyword pink */
.str { color: #fcd34d; }  /* string yellow */
.com { color: #94a3b8; font-style: italic; }  /* comment */
.fn { color: #60a5fa; }   /* function blue */
.ty { color: #34d399; }   /* type green */
```

Tags add warmth without pulling in a 200KB highlighter lib.

**Callouts/notes** — three variants (default blue left-border, warn yellow, ok green) for prerequisites, warnings, and reassurances. One short paragraph. Don't overuse — if every section has one, none stand out.

**Pills** for quick labels (case types, statuses, pieces-of-the-thing). Tiny (0.75rem), rounded-pill, colored border + tinted background in the context hue.

## Writing rules

- **Address the reader directly.** "You'll see…" beats "The user will see…".
- **Lead each section with the takeaway.** The one sentence after the heading should be the thing to remember if they skim.
- **Name the insight that made it click for you.** If "the eval adapter is just another caller of the production factory" unlocked the whole feature for you, say so explicitly — don't bury it.
- **Use tables for side-by-side differences.** Two columns with matching rows beat two bullet lists every time.
- **Quote the code.** Short, real snippets from the actual files. Don't paraphrase. Keep to 6–12 lines.
- **No emojis unless the user asked for them.**
- **No marketing copy** ("powerful", "seamless", "robust"). Describe what it does.
- **Cap code blocks at ~12 lines.** If a function is longer, excerpt the 8 lines that matter and say so.

## File placement

**Default to the repository root.** Use a descriptive, kebab-case filename that makes the topic obvious:
- `<feature>-how-it-works.html`
- `<feature>-explainer.html`
- `<feature>-architecture.html`

Examples: `agent-evals-how-it-works.html`, `billing-folders-architecture.html`.

Putting the page at the root keeps it easy to find (`ls *.html`) and easy to open locally
without having to remember a nested path. Don't drop it into a subdirectory unless the user
specifically asks for a particular location — and if you do, surface the path prominently in
your reply.

Never overwrite an existing file without asking.

## Workflow

1. **Parse `args` and pick a mode.** Create, iterate, or focus? (See the *Arguments* section above.) State the mode in one short sentence before researching.
2. **Clarify scope.** Confirm the feature/branch boundary with the user in one sentence. Surprising scope is cheaper to catch now than after an hour of reading. In iteration mode, confirm which file you're extending if ambiguous.
3. **Research.** Read commits, files, and cross-references as described in *Required inputs*. In iteration mode, also read the existing HTML file end-to-end so your additions match its voice, palette, and section numbering. Use a plan tracker (TaskCreate) if the feature spans more than a handful of files.
4. **Draft the outline** in your head or a scratchpad. Which sections apply? What's the TL;DR diagram going to show? Don't start on CSS until you know the story. In iteration mode, the "outline" is just the list of new sections to append.
5. **Write the HTML.**
   - *Create mode*: use `Write` to produce the full file in one pass. The page is ~1000 lines and rewrites beat incremental patches.
   - *Iteration mode*: use `Edit` to insert the new `<section>`s just before `</main>` (or `<footer>`), and a second `Edit` to add the TOC entry. Never use `Write` — it would overwrite the existing page.
6. **Verify.** Does the TL;DR diagram stand alone? Does the timeline narrate the "why"? Do the tables separate "shared" from "swapped"? In iteration mode, double-check that no original content was modified (only additions + one TOC insert).
7. **Report back.** One short message: the mode you ran in, what was added, and the file path. Don't re-explain the whole feature in chat — the page does that.

## Anti-patterns (things to avoid)

- **One giant wall of text with no diagrams.** If there's no SVG, the skill wasn't applied.
- **Mermaid instead of SVG.** It looks fine in demos and awful in real docs. Just write the SVG.
- **Copying the entire source file into `<pre>` blocks.** Excerpt. Link the file path with a line number.
- **Explaining things the code already makes obvious.** The reader can see that `buildAgentTools` takes parameters. Tell them *why those specific parameters are the seam that matters*.
- **Generic advice sections** ("Best Practices", "Summary of Concepts"). Every paragraph should be specific to this codebase.
- **Emojis, marketing adjectives, or exclamation points.** Respect the reader's time.
- **Hidden scope creep.** If the feature is bigger than expected, pause and check with the user rather than writing 3000 lines.

## Reference output

A canonical example of this skill's output lives at `app/evals/framework/how-it-works.html` in the roboflow repo. It covers the agent-evals framework + LangSmith integration, and demonstrates: a gradient hero, side-by-side TL;DR diagram, commit timeline, 4-layer grid, infra-hop diagram, split-role SDK explanation, full flow diagram with nested steps, and a quickstart. Study it before producing a new page — it shows the skill applied end-to-end.
