#!/usr/bin/env python3
"""
agents_chat: Orchestrate a discussion between Claude Code and OpenAI Codex.

Both agents run in the same target directory. They communicate through
`peer_message.md`, which is overwritten each turn with just the latest reply
from the other agent — each agent already has the full prior conversation
in its own resumed session, so re-reading the whole history would be wasted.

The orchestrator also writes `transcript.md` (append-only) so YOU can review
the conversation after the fact. The agents never read transcript.md.

After the discussion ends, the orchestrator automatically analyzes the transcript
to decide whether there's remaining work. If the agents converged on changes that
weren't fully implemented during the discussion, it generates `plan.md` — a
self-contained implementation plan ready to hand to a coding agent.

Usage:
    ./agents_chat.py "Your problem statement"
    ./agents_chat.py "Problem" --cwd /path/to/repo --max-turns 12 --first codex
    ./agents_chat.py "Problem" --cwd /path/to/repo --no-plan

Stop conditions:
    - Both agents end consecutive turns with `[DONE]` on its own line, OR
    - --max-turns is reached, OR
    - Ctrl-C
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from textwrap import dedent

# Per-agent-call wall-clock deadline. If an agent call (codex/claude) exceeds this,
# the orchestrator kills its whole process group and re-runs the SAME call from the
# same point, up to AGENTS_CHAT_RETRIES times. Guards against an agent CLI hanging
# (observed: `codex exec` stalling for 35+ min at 0% CPU). Tunable via env.
AGENTS_CHAT_DEADLINE = int(os.environ.get("AGENTS_CHAT_DEADLINE", "900"))
AGENTS_CHAT_RETRIES = int(os.environ.get("AGENTS_CHAT_RETRIES", "3"))


def _run_with_deadline(cmd, cwd, label):
    """subprocess.run with a wall-clock deadline + kill-group-and-retry on timeout.

    stdin is /dev/null: `codex exec` reads any piped stdin and appends it as a
    `<stdin>` block, so an inherited open pipe (e.g. when this orchestrator runs
    in the background under another agent) makes codex block forever on
    "Reading additional input from stdin..." even though the prompt is in argv.
    DEVNULL gives it an immediate EOF; claude doesn't read stdin in -p mode.
    """
    for attempt in range(1, AGENTS_CHAT_RETRIES + 1):
        proc = subprocess.Popen(
            cmd, cwd=str(cwd), stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, start_new_session=True,
        )
        try:
            out, err = proc.communicate(timeout=AGENTS_CHAT_DEADLINE)
            return subprocess.CompletedProcess(cmd, proc.returncode, out, err)
        except subprocess.TimeoutExpired:
            sys.stderr.write(
                f"\n[{_timestamp()}] [{label}] exceeded {AGENTS_CHAT_DEADLINE}s deadline "
                f"(attempt {attempt}/{AGENTS_CHAT_RETRIES}) — killing process group and "
                f"re-running this turn\n"
            )
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                pass
            continue
    sys.stderr.write(
        f"\n[{_timestamp()}] [{label}] still timing out after {AGENTS_CHAT_RETRIES} "
        f"attempts — aborting run\n"
    )
    sys.exit(1)

PEER_FILE = "peer_message.md"
TRANSCRIPT_FILE = "transcript.md"
STATE_FILE = ".agents_chat_state.json"
PLAN_FILE = "plan.md"


# ---------- logging ----------

def _timestamp() -> str:
    """Current wall-clock time as HH:MM, for log lines and transcript headers."""
    return datetime.now().strftime("%H:%M")


def log(msg: str = "") -> None:
    """Print an orchestrator log line prefixed with the current HH:MM timestamp.

    Leading newlines in `msg` are kept before the timestamp so callers can still
    add vertical spacing, e.g. log("\\n[orchestrator] turn 3 ...").
    """
    lead = ""
    while msg.startswith("\n"):
        lead += "\n"
        msg = msg[1:]
    print(f"{lead}[{_timestamp()}] {msg}")


# ---------- agent prompts ----------

INITIAL_CLAUDE_GOES_FIRST = dedent("""
    You are **Claude Code**, collaborating with another AI agent — **OpenAI Codex** — on a
    software problem in this working directory.

    HOW YOU TWO TALK:
    - You exchange messages via an orchestrator. After each of your replies, your final
      assistant message is written to `{peer_file}` for Codex to read on its next turn.
      When Codex replies, ITS message is written to `{peer_file}` for you to read.
    - `{peer_file}` is OVERWRITTEN each turn — it only ever contains the single most recent
      message from your peer. You do not need the full history in the file; your own session
      memory already has everything you've seen and said so far.
    - You do NOT need to write to `{peer_file}` yourself. Just reply — the orchestrator
      handles the plumbing. Don't bother reading `{peer_file}` on this turn either; nothing
      is there yet because you go first.
    - Both of you can read and edit code in this repo directly.

    THIS IS **TURN 1 — YOU GO FIRST**. The user's problem:

    ───────── PROBLEM ─────────
    {problem}
    ───────── END PROBLEM ─────

    WHAT TO DO NOW:
    1. Look at the relevant code so you actually understand the situation.
    2. Reply with your opening move: how you read the problem, your proposed approach, and
       anything specific you want Codex to push back on or build on. Be concrete — name
       files, functions, snippets.

    NORMS:
    - You and Codex are peers. Disagree when you have reason to and say why.
    - You may edit code to prototype or demonstrate; mention what you changed.
    - When you and Codex both believe the problem is solved, end your reply with `[DONE]`
      on its own line. The orchestrator stops when both of you sign off consecutively.

    Reply now.
""").strip()


INITIAL_CLAUDE_GOES_SECOND = dedent("""
    You are **Claude Code**, collaborating with another AI agent — **OpenAI Codex** — on a
    software problem in this working directory.

    HOW YOU TWO TALK:
    - You exchange messages via an orchestrator. After each of your replies, your final
      assistant message is written to `{peer_file}` for Codex to read on its next turn.
      When Codex replies, ITS message is written to `{peer_file}` for you to read.
    - `{peer_file}` is OVERWRITTEN each turn — it only ever contains the single most recent
      message from your peer. You do not need the full history in the file; your own session
      memory already has everything you've seen and said so far.
    - You do NOT need to write to `{peer_file}` yourself. Just reply — the orchestrator
      handles the plumbing.
    - Both of you can read and edit code in this repo directly.

    Codex made the opening move. This is **turn {turn} — your turn.** The user's problem:

    ───────── PROBLEM ─────────
    {problem}
    ───────── END PROBLEM ─────

    WHAT TO DO NOW:
    1. Read `{peer_file}` to see Codex's opening message.
    2. Look at the relevant code so you can form your own opinion, not just react.
    3. Reply: what you agree with, where you disagree, your counter-proposal or refinement,
       what you'd like Codex to address. Be concrete — name files, functions, snippets.

    NORMS:
    - You and Codex are peers. Disagree when you have reason to and say why.
    - You may edit code to prototype or demonstrate; mention what you changed.
    - When you and Codex both believe the problem is solved, end your reply with `[DONE]`
      on its own line. The orchestrator stops when both of you sign off consecutively.

    Reply now.
""").strip()


RESUME_CLAUDE = dedent("""
    Your turn again (turn {turn}). Codex just replied — their message is in `{peer_file}`.
    Remember: that file is overwritten each turn, so it contains ONLY Codex's most recent
    message. Everything before that is already in your own session memory.

    Read `{peer_file}`, do whatever investigation or editing is warranted, and reply. The
    orchestrator will hand your reply to Codex.

    End with `[DONE]` on its own line only if you believe the work is finished.
""").strip()


RESUME_CLAUDE_WITH_USER = dedent("""
    The user has sent a new message into the conversation:

    ───────── USER MESSAGE ─────────
    {user_message}
    ───────── END USER MESSAGE ─────

    Your turn (turn {turn}). Codex's last reply is in `{peer_file}` (overwritten each turn —
    your own session memory has the rest of the history).

    Read `{peer_file}`, then respond to BOTH Codex's last message and the user's new message
    above. Do whatever investigation or editing is warranted. The orchestrator will hand your
    reply to Codex, and will also forward the user's message to Codex on its next turn.

    End with `[DONE]` on its own line only if you believe the work is finished.
""").strip()


INITIAL_CODEX_GOES_FIRST = dedent("""
    You are **OpenAI Codex**, collaborating with another AI agent — **Claude Code** — on a
    software problem in this working directory.

    HOW YOU TWO TALK:
    - You exchange messages via an orchestrator. After each of your replies, your final
      assistant message is written to `{peer_file}` for Claude to read on its next turn.
      When Claude replies, ITS message is written to `{peer_file}` for you to read.
    - `{peer_file}` is OVERWRITTEN each turn — it only ever contains the single most recent
      message from your peer. You do not need the full history in the file; your own session
      memory already has everything you've seen and said so far.
    - You do NOT need to write to `{peer_file}` yourself. Just reply — the orchestrator
      handles the plumbing. Don't bother reading `{peer_file}` on this turn either; nothing
      is there yet because you go first.
    - Both of you can read and edit code in this repo directly.

    THIS IS **TURN 1 — YOU GO FIRST**. The user's problem:

    ───────── PROBLEM ─────────
    {problem}
    ───────── END PROBLEM ─────

    WHAT TO DO NOW:
    1. Look at the relevant code so you actually understand the situation.
    2. Reply with your opening move: how you read the problem, your proposed approach, and
       anything specific you want Claude to push back on or build on. Be concrete — name
       files, functions, snippets.

    NORMS:
    - You and Claude are peers. Disagree when you have reason to and say why.
    - You may edit code to prototype or demonstrate; mention what you changed.
    - When you and Claude both believe the problem is solved, end your reply with `[DONE]`
      on its own line. The orchestrator stops when both of you sign off consecutively.

    Reply now.
""").strip()


INITIAL_CODEX_GOES_SECOND = dedent("""
    You are **OpenAI Codex**, collaborating with another AI agent — **Claude Code** — on a
    software problem in this working directory.

    HOW YOU TWO TALK:
    - You exchange messages via an orchestrator. After each of your replies, your final
      assistant message is written to `{peer_file}` for Claude to read on its next turn.
      When Claude replies, ITS message is written to `{peer_file}` for you to read.
    - `{peer_file}` is OVERWRITTEN each turn — it only ever contains the single most recent
      message from your peer. You do not need the full history in the file; your own session
      memory already has everything you've seen and said so far.
    - You do NOT need to write to `{peer_file}` yourself. Just reply — the orchestrator
      handles the plumbing.
    - Both of you can read and edit code in this repo directly.

    Claude made the opening move. This is **turn {turn} — your turn.** The user's problem:

    ───────── PROBLEM ─────────
    {problem}
    ───────── END PROBLEM ─────

    WHAT TO DO NOW:
    1. Read `{peer_file}` to see Claude's opening message.
    2. Look at the relevant code so you can form your own opinion, not just react.
    3. Reply: what you agree with, where you disagree, your counter-proposal or refinement,
       what you'd like Claude to address. Be concrete — name files, functions, snippets.

    NORMS:
    - You and Claude are peers. Disagree when you have reason to and say why.
    - You may edit code to prototype or demonstrate; mention what you changed.
    - When you and Claude both believe the problem is solved, end your reply with `[DONE]`
      on its own line. The orchestrator stops when both of you sign off consecutively.

    Reply now.
""").strip()


RESUME_CODEX = dedent("""
    Your turn again (turn {turn}). Claude just replied — their message is in `{peer_file}`.
    Remember: that file is overwritten each turn, so it contains ONLY Claude's most recent
    message. Everything before that is already in your own session memory.

    Read `{peer_file}`, do whatever investigation or editing is warranted, and reply. The
    orchestrator will hand your reply to Claude.

    End with `[DONE]` on its own line only if you believe the work is finished.
""").strip()


RESUME_CODEX_WITH_USER = dedent("""
    The user has sent a new message into the conversation:

    ───────── USER MESSAGE ─────────
    {user_message}
    ───────── END USER MESSAGE ─────

    Your turn (turn {turn}). Claude's last reply is in `{peer_file}` (overwritten each turn —
    your own session memory has the rest of the history).

    Read `{peer_file}`, then respond to BOTH Claude's last message and the user's new message
    above. Do whatever investigation or editing is warranted. The orchestrator will hand your
    reply to Claude, and will also forward the user's message to Claude on its next turn.

    End with `[DONE]` on its own line only if you believe the work is finished.
""").strip()


# ---------- plan generation prompt ----------

PLAN_PROMPT = dedent("""
    You are a technical architect. You have just been given the full transcript of a
    discussion between two AI coding agents (Claude Code and OpenAI Codex) who were
    collaborating on a software problem in this working directory.

    Your job has two parts:

    **PART 1 — DECIDE:** Read the transcript carefully. By the end of the discussion,
    did the agents converge on changes that still need to be made to the codebase?
    Possible outcomes:
    - The agents agreed on an approach but did NOT fully implement it → plan needed.
    - The agents implemented some things but left other agreed-upon work undone → plan needed.
    - The agents already made all the changes during their discussion → no plan needed.
    - The agents couldn't agree or the discussion was inconclusive → no plan needed.

    **PART 2 — IF A PLAN IS NEEDED**, produce a self-contained implementation plan that
    a separate coding agent can follow WITHOUT ever seeing the transcript. Everything the
    coding agent needs — file paths, function names, the rationale for each change, edge
    cases to handle — must be in the plan.

    Rules for the plan:
    - Extract the **converged approach** — what the agents agreed on. If they disagreed
      on something and never resolved it, pick the stronger option with a brief justification.
    - Be concrete: name files, functions, line ranges, data structures.
    - Organize as an ordered sequence of steps, each independently actionable.
    - Start with a 2-3 sentence summary of the problem and the agreed-upon solution.
    - Include tests to write or update as explicit steps.
    - Do NOT include the transcript or quote it at length.

    RESPONSE FORMAT — you MUST follow this exactly:

    If no plan is needed, respond with ONLY this single line (no other text):
    [NO_PLAN_NEEDED]

    If a plan IS needed, respond with the plan content in markdown. Do NOT include
    the [NO_PLAN_NEEDED] marker anywhere.

    {extra_instructions}

    ───────── TRANSCRIPT ─────────
    {transcript}
    ───────── END TRANSCRIPT ─────

    Now read through the codebase as needed to verify file paths, function names, and
    current state — the agents may have already changed things during their discussion.
    Ground your plan in what the code looks like RIGHT NOW.

    Respond.
""").strip()


# ---------- agent runners ----------

def run_claude(prompt: str, cwd: Path, session_id: str | None) -> tuple[str, str]:
    """Invoke Claude Code once. Returns (assistant_text, new_session_id)."""
    cmd = [
        "claude", "-p",
        "--permission-mode", "bypassPermissions",
        "--output-format", "json",
    ]
    # Pin an explicit model (owner directive 2026-06-13): the inner `claude -p`
    # otherwise inherits the session default, and a default like
    # `claude-fable-5[1m]` is not resolvable in a headless invocation
    # (404 model_not_found), which kills every debate at turn 1. Default to
    # Opus 4.8; override with AGENTS_CHAT_CLAUDE_MODEL.
    cmd += ["--model", os.environ.get("AGENTS_CHAT_CLAUDE_MODEL", "claude-opus-4-8")]
    if session_id:
        cmd += ["--resume", session_id]
    cmd.append(prompt)

    proc = _run_with_deadline(cmd, cwd, "claude")
    if proc.returncode != 0:
        sys.stderr.write(
            f"\n[{_timestamp()}] [claude] exited {proc.returncode}\n--- stderr ---\n{proc.stderr}\n"
            f"--- stdout ---\n{proc.stdout}\n"
        )
        sys.exit(1)

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        sys.stderr.write(f"\n[{_timestamp()}] [claude] non-JSON stdout:\n{proc.stdout}\n")
        sys.exit(1)

    # `claude -p --output-format json` emits a single result OBJECT by default,
    # but with `verbose: true` in settings.json (or --verbose) it emits a JSON
    # ARRAY of every event (init, assistant, ...) with the result event last.
    # Handle both shapes; previously the array shape crashed with AttributeError.
    if isinstance(data, list):
        result_evt = None
        for evt in reversed(data):
            if isinstance(evt, dict) and evt.get("type") == "result":
                result_evt = evt
                break
        if result_evt is None:
            sys.stderr.write(
                f"\n[{_timestamp()}] [claude] no result event in JSON output "
                f"(last 2000 chars):\n{proc.stdout[-2000:]}\n--- stderr ---\n{proc.stderr}\n"
            )
            sys.exit(1)
        data = result_evt

    text = (data.get("result") or "").strip()
    new_sid = data.get("session_id") or session_id or ""
    return text, new_sid


def run_codex(prompt: str, cwd: Path, session_id: str | None) -> tuple[str, str]:
    """Invoke Codex once. Returns (assistant_text, session_id).

    First turn (session_id is None): `codex exec -C <cwd>`, capturing the
    session id from the `thread.started` event in the `--json` stream so later
    turns resume THIS exact session by id. (The old `resume --last` grabbed
    whatever codex session was newest machine-wide — fragile if any unrelated
    codex run happened between turns.) Subsequent turns: `codex exec resume
    <session_id>`, which inherits the original session's cwd and sandbox — so it
    rejects -C/--cd and --sandbox; pass neither here.
    """
    last_msg_file = cwd / ".codex-last-message.txt"
    if last_msg_file.exists():
        last_msg_file.unlink()

    base_flags = [
        "--skip-git-repo-check",
        "--dangerously-bypass-approvals-and-sandbox",
        "--json",                       # emit JSONL events so we can read the session id
        "-o", str(last_msg_file),       # final assistant message written here
    ]
    if session_id:
        cmd = ["codex", "exec", "resume", session_id, *base_flags, prompt]
    else:
        cmd = ["codex", "exec", "-C", str(cwd), *base_flags, prompt]

    proc = _run_with_deadline(cmd, cwd, "codex")
    if proc.returncode != 0:
        sys.stderr.write(
            f"\n[{_timestamp()}] [codex] exited {proc.returncode}\n--- stderr ---\n{proc.stderr}\n"
            f"--- stdout ---\n{proc.stdout}\n"
        )
        sys.exit(1)

    # Walk the JSONL event stream for the session id (thread.started) and, as a
    # fallback reply source, the last agent_message (item.completed).
    new_sid = session_id
    stream_reply = ""
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue
        if evt.get("type") == "thread.started" and evt.get("thread_id"):
            new_sid = evt["thread_id"]
        elif evt.get("type") == "item.completed":
            item = evt.get("item") or {}
            if item.get("type") == "agent_message" and item.get("text"):
                stream_reply = item["text"]

    if last_msg_file.exists():
        text = last_msg_file.read_text().strip()
        last_msg_file.unlink()
    else:
        text = stream_reply.strip()

    return text, (new_sid or "")


def generate_plan(transcript_path: Path, plan_path: Path, cwd: Path) -> bool:
    """Read the transcript, ask Claude to decide if a plan is needed, and write it.
    Returns True if a plan was generated, False otherwise."""
    transcript = transcript_path.read_text()
    if not transcript.strip():
        log("[orchestrator] transcript is empty — skipping plan generation.")
        return False

    log("\n[orchestrator] analyzing transcript for remaining work...")

    prompt = PLAN_PROMPT.format(transcript=transcript, extra_instructions="")
    plan, _ = run_claude(prompt, cwd, session_id=None)

    if not plan or "[NO_PLAN_NEEDED]" in plan:
        log("[orchestrator] agents completed all work during discussion — no plan needed.")
        return False

    plan_path.write_text(plan + "\n")
    log(f"[orchestrator] implementation plan written to {plan_path} ({len(plan)} chars)")
    return True


# ---------- file management ----------

def write_peer_message(peer_path: Path, from_agent: str, text: str) -> None:
    """Overwrite peer_message.md with just the latest message."""
    header = f"<!-- from: {from_agent} -->\n"
    peer_path.write_text(header + text.strip() + "\n")


def init_transcript(transcript_path: Path, problem: str) -> None:
    if transcript_path.exists():
        backup = transcript_path.with_suffix(
            transcript_path.suffix + f".bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        )
        shutil.move(str(transcript_path), str(backup))
        log(f"[orchestrator] existing transcript backed up to {backup.name}")
    transcript_path.write_text(dedent(f"""\
        # Agent Discussion Transcript

        _Started {datetime.now().isoformat(timespec='seconds')}_

        ## User — Problem Statement

        {problem.strip()}

        ---
        """))


def append_transcript(transcript_path: Path, agent: str, turn: int, text: str) -> None:
    with transcript_path.open("a") as f:
        f.write(f"\n## {agent} — Turn {turn} — {_timestamp()}\n\n{text.strip()}\n\n---\n")


def append_user_message(transcript_path: Path, before_turn: int, text: str) -> None:
    """Append a mid-conversation user message to the transcript."""
    with transcript_path.open("a") as f:
        f.write(
            f"\n## User — Message (before turn {before_turn}) — {_timestamp()}\n\n"
            f"{text.strip()}\n\n---\n"
        )


def is_done(text: str) -> bool:
    tail = text.strip().splitlines()[-5:]
    return any(line.strip() == "[DONE]" for line in tail)


def load_state(state_path: Path) -> dict | None:
    if not state_path.exists():
        return None
    try:
        return json.loads(state_path.read_text())
    except json.JSONDecodeError:
        return None


def save_state(state_path: Path, state: dict) -> None:
    state_path.write_text(json.dumps(state, indent=2))


# ---------- main loop ----------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Orchestrate a back-and-forth between Claude Code and OpenAI Codex."
    )
    ap.add_argument(
        "problem",
        nargs="?",
        help=(
            "Problem statement to discuss. Required for a fresh run. With --continue, "
            "if provided, it's injected into the conversation as a new user message "
            "delivered to both agents on their next turns."
        ),
    )
    ap.add_argument("--cwd", default=".", help="Working directory both agents operate in (default: cwd).")
    ap.add_argument("--max-turns", type=int, default=20, help="Maximum turns in THIS invocation.")
    ap.add_argument(
        "--min-turns",
        type=int,
        default=0,
        help="Don't stop on [DONE] until at least this many total turns have happened (default: 0).",
    )
    ap.add_argument(
        "--first",
        choices=["claude", "codex"],
        default="claude",
        help="Which agent speaks first (default: claude). Ignored with --continue.",
    )
    ap.add_argument(
        "-c", "--continue",
        dest="cont",
        action="store_true",
        help="Resume the previous conversation in --cwd (keeps transcript, resumes both sessions).",
    )
    ap.add_argument(
        "--no-plan",
        action="store_true",
        help="Skip automatic plan generation after the discussion ends.",
    )
    args = ap.parse_args()

    cwd = Path(args.cwd).expanduser().resolve()
    if not cwd.is_dir():
        sys.stderr.write(f"--cwd does not exist or is not a directory: {cwd}\n")
        return 2

    peer_path = cwd / PEER_FILE
    transcript_path = cwd / TRANSCRIPT_FILE
    state_path = cwd / STATE_FILE

    if args.cont:
        state = load_state(state_path)
        if state is None:
            sys.stderr.write(
                f"--continue specified but no prior state at {state_path}.\n"
                "Run without --continue to start a fresh conversation.\n"
            )
            return 2
        claude_session = state.get("claude_session_id")
        codex_session = state.get("codex_session_id")
        start_turn = state.get("last_turn", 0) + 1
        next_agent = state.get("next_agent", "claude")
        claude_started = state.get("claude_started", False)
        codex_started = state.get("codex_started", False)
        original_problem = state.get("original_problem", "")
        # Carry any still-undelivered user message from a prior --continue.
        pending_user_message = state.get("pending_user_message") or None
        user_message_pending_for = list(state.get("user_message_pending_for") or [])
        done_streak = 0  # reset so they need to re-converge on [DONE]
        log(f"[orchestrator] continuing previous conversation in {cwd}")
        log(f"[orchestrator] next up: {next_agent} (turn {start_turn})")
        if args.problem:
            # User is contributing a new message into the ongoing chat. Add it to the
            # transcript and queue it for delivery to both agents on their next turns.
            pending_user_message = args.problem.strip()
            user_message_pending_for = ["claude", "codex"]
            append_user_message(transcript_path, start_turn, pending_user_message)
            log(f"[orchestrator] user message queued for both agents ({len(pending_user_message)} chars)")
    else:
        if not args.problem:
            ap.error("problem is required (or pass --continue to resume an existing conversation)")
        if peer_path.exists():
            peer_path.unlink()
        if state_path.exists():
            state_path.unlink()
        init_transcript(transcript_path, args.problem)
        claude_session = None
        codex_session = None
        start_turn = 1
        next_agent = args.first
        claude_started = False
        codex_started = False
        original_problem = args.problem
        pending_user_message = None
        user_message_pending_for = []
        done_streak = 0
        log(f"[orchestrator] working in {cwd}")
        log(f"[orchestrator] peer mailbox: {peer_path.name}")
        log(f"[orchestrator] transcript:   {transcript_path.name}")
        log(f"[orchestrator] starting with: {args.first}")

    order = [next_agent, "codex" if next_agent == "claude" else "claude"]
    end_turn = start_turn + args.max_turns  # exclusive
    stop_reason = "max-turns"

    for turn in range(start_turn, end_turn):
        agent = order[(turn - start_turn) % 2]
        log(f"\n[orchestrator] turn {turn} — {agent} thinking...")

        deliver_user_message = (
            pending_user_message is not None and agent in user_message_pending_for
        )

        if agent == "claude":
            if not claude_started:
                template = INITIAL_CLAUDE_GOES_FIRST if turn == 1 else INITIAL_CLAUDE_GOES_SECOND
                prompt = template.format(problem=original_problem, peer_file=PEER_FILE, turn=turn)
                claude_started = True
            elif deliver_user_message:
                prompt = RESUME_CLAUDE_WITH_USER.format(
                    user_message=pending_user_message, peer_file=PEER_FILE, turn=turn,
                )
            else:
                prompt = RESUME_CLAUDE.format(peer_file=PEER_FILE, turn=turn)
            reply, claude_session = run_claude(prompt, cwd, claude_session)
            label = "Claude"
        else:
            is_first_codex_turn = not codex_started
            if is_first_codex_turn:
                template = INITIAL_CODEX_GOES_FIRST if turn == 1 else INITIAL_CODEX_GOES_SECOND
                prompt = template.format(problem=original_problem, peer_file=PEER_FILE, turn=turn)
                codex_started = True
            elif deliver_user_message:
                prompt = RESUME_CODEX_WITH_USER.format(
                    user_message=pending_user_message, peer_file=PEER_FILE, turn=turn,
                )
            else:
                prompt = RESUME_CODEX.format(peer_file=PEER_FILE, turn=turn)
            reply, codex_session = run_codex(prompt, cwd, codex_session)
            label = "Codex"

        if deliver_user_message:
            user_message_pending_for = [a for a in user_message_pending_for if a != agent]
            if not user_message_pending_for:
                pending_user_message = None
            log(f"[orchestrator] delivered user message to {agent}")

        if not reply:
            log(f"[orchestrator] {label} returned an empty reply — stopping.")
            stop_reason = "empty-reply"
            break

        write_peer_message(peer_path, label, reply)
        append_transcript(transcript_path, label, turn, reply)
        log(f"[orchestrator] {label} → {peer_path.name} ({len(reply)} chars)")

        if is_done(reply):
            done_streak += 1
            log(f"[orchestrator] {label} signaled [DONE] (streak={done_streak}).")
        else:
            done_streak = 0

        save_state(state_path, {
            "claude_session_id": claude_session,
            "codex_session_id": codex_session,
            "last_turn": turn,
            "next_agent": "codex" if agent == "claude" else "claude",
            "claude_started": claude_started,
            "codex_started": codex_started,
            "original_problem": original_problem,
            "pending_user_message": pending_user_message,
            "user_message_pending_for": user_message_pending_for,
        })

        if done_streak >= 2:
            if turn >= args.min_turns:
                log("[orchestrator] both agents signed off consecutively — stopping.")
                stop_reason = "done"
                break
            else:
                log(f"[orchestrator] both signed off but min-turns ({args.min_turns}) not reached — continuing.")

    if stop_reason == "max-turns":
        log(f"[orchestrator] reached max-turns ({args.max_turns}) for this run — stopping.")

    log(f"\n[orchestrator] discussion finished. Full transcript: {transcript_path}")

    plan_path = cwd / PLAN_FILE
    if args.no_plan:
        log("[orchestrator] --no-plan specified, skipping plan generation.")
    else:
        generated = generate_plan(transcript_path, plan_path, cwd)
        if generated:
            log(f"\n[orchestrator] to execute the plan:")
            print(f'  claude -p "$(cat {plan_path})"')

    log(f"[orchestrator] resume discussion with: {sys.argv[0]} --cwd {cwd} --continue")
    return 0


if __name__ == "__main__":
    sys.exit(main())
