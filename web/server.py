"""FastAPI WebSocket server: LifeSaver as a ChatGPT-style web UI.

Run from the project root (life2/):

    uvicorn web.server:app --reload --host 127.0.0.1 --port 8765

Then open http://localhost:8765 and:

    user: python main.py test_php.php
    -> all 3 agents run back-to-back, post findings, then scan_complete + chat_open
    user: security: why do I need to fix the hardcoded password?
    -> Security agent answers
    user: performance: how do I optimise the nested loop?
    -> Performance agent answers
    user: logic: explain the division by zero risk
    -> Logic agent answers
    user: close
    -> conversation ends, ready for the next scan
"""

import asyncio
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from crewai import Crew, Process

from agents import security_agent, performance_agent, logic_agent
from tasks import create_tasks, detect_language
from arbitration import (
    parse_findings,
    calculate_was,
    filter_findings,
    calculate_reliability,
)
from main import _suppress_console_output, _silence_crewai_noise

_silence_crewai_noise()

WEB_DIR = Path(__file__).resolve().parent

app = FastAPI(title="LifeSaver Web")
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


AGENT_INFO = [
    ("security",    security_agent,    "llama3.1:8b + Bandit"),
    ("performance", performance_agent, "gemma3:4b"),
    ("logic",       logic_agent,       "deepseek-r1:7b"),
]

AGENT_MODELS = {
    "security":    "ollama/llama3.1:8b",
    "performance": "ollama/gemma3:4b",
    "logic":       "ollama/deepseek-r1:7b",
}

AGENT_LABELS = {a: lbl for a, _, lbl in AGENT_INFO}

OLLAMA_BASE = "http://localhost:11434"

_CODE_EXTS = (".py", ".js", ".java", ".php", ".cpp", ".cs", ".go", ".rb", ".c")

_CHAT_PREFIX_RE = re.compile(
    r'^\s*(security|performance|logic)\s*[:>\-]\s*(.+)$',
    re.IGNORECASE | re.DOTALL,
)


def _parse_command(cmd: str) -> Optional[str]:
    """Extract a target filename from chat input like `python main.py test.py`.
    Returns the LAST file-extension match so the script name (main.py) is
    not picked over the actual target.
    """
    cmd = cmd.strip()
    if not cmd:
        return None
    try:
        parts = shlex.split(cmd, posix=False)
    except ValueError:
        parts = cmd.split()
    candidate = None
    for tok in parts:
        bare = tok.strip('"').strip("'")
        if bare.lower().endswith(_CODE_EXTS) or bare.startswith("test_"):
            candidate = bare
    return candidate


def _has_flag(cmd: str, flag: str) -> bool:
    """True if the chat command contains the given flag as a whole token."""
    return any(t.lower() == flag.lower()
               for t in cmd.split())


def _parse_chat_prefix(cmd: str) -> Tuple[Optional[str], str]:
    """Return (agent_id, question) if input begins with 'agent:'.
    If no prefix is present, (None, cmd) is returned.
    """
    m = _CHAT_PREFIX_RE.match(cmd)
    if not m:
        return None, cmd
    return m.group(1).lower(), m.group(2).strip()


async def _run_agent(agent, task) -> str:
    """Run one agent's task in a single-task Crew, off the event loop."""
    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )

    def _kick():
        with _suppress_console_output():
            crew.kickoff()
        return task.output.raw if task.output else ""

    return await asyncio.to_thread(_kick)


def _strip_think_tags(text: str) -> str:
    """Strip deepseek-r1 <think>...</think> blocks (and dangling tags)."""
    text = re.sub(r'<think(?:ing)?>.*?</think(?:ing)?>', '', text,
                  flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<think(?:ing)?>.*$', '', text,
                  flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'^.*?</think(?:ing)?>', '', text,
                  flags=re.DOTALL | re.IGNORECASE)
    return text.strip()


def _format_findings_for_prompt(findings: list) -> str:
    if not findings:
        return "(no findings reported)"
    lines = []
    for i, f in enumerate(findings, 1):
        lines.append(
            f"#{i} [{f.get('severity','?')}] {f.get('description','')} "
            f"(Line {f.get('line','?')}, confidence "
            f"{float(f.get('confidence', 0)):.2f})\n"
            f"   reason: {f.get('reason','')}"
        )
    return "\n".join(lines)


async def _ask_agent_followup(agent_id: str, code: str, language: str,
                              findings: list, history: list,
                              question: str) -> str:
    """Call the agent's underlying LLM directly with a chat-style history."""
    import litellm

    system_prompt = (
        f"You are the {agent_id.title()} Agent in LifeSaver, a multi-agent "
        f"code review system. You just reviewed this {language} code:\n\n"
        f"```{language.lower()}\n{code}\n```\n\n"
        f"You produced these findings:\n"
        f"{_format_findings_for_prompt(findings)}\n\n"
        f"The user is asking follow-up questions about your findings. "
        f"Answer concisely and helpfully. Refer to findings by number "
        f"when relevant (e.g. \"finding #2\"). Do not invent new findings "
        f"-- only discuss what you already found above. Stay focused on "
        f"your domain ({agent_id})."
    )

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": question})

    max_tokens = 6144 if agent_id == "logic" else 4096
    timeout    = 1200 if agent_id == "logic" else 900

    def _call():
        resp = litellm.completion(
            model=AGENT_MODELS[agent_id],
            messages=messages,
            api_base=OLLAMA_BASE,
            temperature=0.2,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        return resp.choices[0].message.content or ""

    raw = await asyncio.to_thread(_call)
    return _strip_think_tags(raw)


class SessionState:
    """Per-WebSocket state.

    chat_open:
        False -> idle, awaiting a scan command
        True  -> all 3 agents have posted; user can chat with any of them
                 via 'agent: question' prefix, or type 'close' to end.
    """

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.file: Optional[str] = None
        self.code: Optional[str] = None
        self.language: Optional[str] = None
        self.tasks: Optional[list] = None
        self.findings_by_agent: dict = {}
        self.chat_history_by_agent: dict = {
            a: [] for a, _, _ in AGENT_INFO
        }
        self.chat_open: bool = False


async def _run_single_agent_baseline(ws: WebSocket,
                                     session: SessionState) -> None:
    """Run the single-agent baseline and emit findings + scan_complete."""
    from single_agent import scan_single, SINGLE_MODEL

    await ws.send_json({
        "type": "agent_start",
        "step": 1, "total": 1,
        "agent": "single",
        "model": SINGLE_MODEL.replace("ollama/", "") + " (baseline)",
    })

    try:
        findings = await asyncio.to_thread(
            scan_single, session.code, session.language,
        )
    except Exception as e:
        await ws.send_json({
            "type": "agent_error",
            "agent": "single",
            "message": str(e),
        })
        findings = []

    by_cat: dict = {"security": [], "performance": [], "logic": []}
    for f in findings:
        cat = f.get("agent", "logic")
        by_cat.setdefault(cat, []).append(f)
    session.findings_by_agent = by_cat

    for cat in ("security", "performance", "logic"):
        await ws.send_json({
            "type": "agent_findings",
            "agent": cat,
            "model": f"{SINGLE_MODEL.replace('ollama/', '')} (baseline)",
            "count": len(by_cat[cat]),
            "findings": by_cat[cat],
        })

    was_results = calculate_was(findings)
    kept = filter_findings(was_results)
    reliability = calculate_reliability(1 if kept else 0, 1)
    counts = {cat: len(by_cat[cat]) for cat in ("security", "performance", "logic")}

    await ws.send_json({
        "type": "scan_complete",
        "file": session.file,
        "language": session.language,
        "mode": "single",
        "totals": {
            **counts,
            "total": len(findings),
            "kept": len(kept),
        },
        "reliability": reliability,
        "kept_findings": kept,
    })

    session.chat_open = True
    await ws.send_json({
        "type": "chat_open",
        "hint_title": "Conversation open (single-agent baseline)",
        "hint_lines": [
            "Ask the single baseline agent by typing one of:",
            "  • security: <your question>",
            "  • performance: <your question>",
            "  • logic: <your question>",
            "(all three route to the same single agent in baseline mode)",
            "",
            "Type `pdf` at any time to download the conversation as a PDF.",
            "Type `close` to end the conversation.",
        ],
    })


async def _start_scan(ws: WebSocket, session: SessionState,
                      filename: str, single: bool = False,
                      no_arbitration: bool = False) -> None:
    """Resolve file, run the configured pipeline, open the chat.

    Three modes:
      - default        : full 3-agent LifeSaver (WAS filter applied)
      - single=True    : single-agent baseline (qwen2.5-coder)
      - no_arbitration : 3 agents, WAS filter skipped (raw multi-agent baseline)

    `single` takes precedence over `no_arbitration` if both are set.
    """
    target = (
        Path(filename) if os.path.isabs(filename) else (ROOT / filename)
    ).resolve()
    if not target.is_file():
        await ws.send_json({
            "type": "system",
            "message": f"File not found: {filename}",
        })
        return

    with open(target, "r", encoding="utf-8") as fh:
        code = fh.read()
    language = detect_language(code)

    session.reset()
    session.file = target.name
    session.code = code
    session.language = language
    session.tasks = create_tasks(code)

    mode_label = ("single" if single
                  else "no-arbitration" if no_arbitration
                  else "three")
    await ws.send_json({
        "type": "scan_start",
        "file": target.name,
        "language": language,
        "lines": len(code.strip().splitlines()),
        "mode": mode_label,
    })

    if single:
        await _run_single_agent_baseline(ws, session)
        return

    for idx, (aid, agent, model_label) in enumerate(AGENT_INFO):
        await ws.send_json({
            "type": "agent_start",
            "step": idx + 1,
            "total": len(AGENT_INFO),
            "agent": aid,
            "model": model_label,
        })
        try:
            raw = await _run_agent(agent, session.tasks[idx])
        except Exception as e:
            await ws.send_json({
                "type": "agent_error",
                "agent": aid,
                "message": str(e),
            })
            session.findings_by_agent[aid] = []
            continue

        findings = parse_findings(raw, aid)
        session.findings_by_agent[aid] = findings

        await ws.send_json({
            "type": "agent_findings",
            "agent": aid,
            "model": model_label,
            "count": len(findings),
            "findings": findings,
        })

    all_findings: list = []
    for aid, _, _ in AGENT_INFO:
        all_findings.extend(session.findings_by_agent.get(aid, []))
    was_results = calculate_was(all_findings)
    kept = was_results if no_arbitration else filter_findings(was_results)
    reliability = calculate_reliability(1 if kept else 0, 1)

    counts = {aid: len(session.findings_by_agent.get(aid, []))
              for aid, _, _ in AGENT_INFO}

    await ws.send_json({
        "type": "scan_complete",
        "file": session.file,
        "language": session.language,
        "mode": mode_label,
        "totals": {
            **counts,
            "total": len(all_findings),
            "kept": len(kept),
        },
        "reliability": reliability,
        "kept_findings": kept,
    })

    session.chat_open = True

    await ws.send_json({
        "type": "chat_open",
        "hint_title": "Conversation open",
        "hint_lines": [
            "Ask any agent by typing one of:",
            "  • security: <your question>",
            "  • performance: <your question>",
            "  • logic: <your question>",
            "",
            "Type `pdf` at any time to download the conversation as a PDF.",
            "Type `close` to end the conversation.",
        ],
    })


async def _handle_question(ws: WebSocket, session: SessionState,
                           agent_id: str, question: str) -> None:
    if not question:
        await ws.send_json({
            "type": "system",
            "message": f"Type a question after `{agent_id}:`.",
        })
        return

    history = session.chat_history_by_agent.setdefault(agent_id, [])
    model_label = AGENT_LABELS.get(agent_id, agent_id)

    await ws.send_json({
        "type": "agent_typing",
        "agent": agent_id,
        "model": model_label,
    })

    try:
        answer = await _ask_agent_followup(
            agent_id=agent_id,
            code=session.code or "",
            language=session.language or "Unknown",
            findings=session.findings_by_agent.get(agent_id, []),
            history=history,
            question=question,
        )
    except Exception as e:
        await ws.send_json({
            "type": "agent_error",
            "agent": agent_id,
            "message": f"Follow-up failed: {e}",
        })
        return

    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": answer})

    await ws.send_json({
        "type": "agent_reply",
        "agent": agent_id,
        "model": model_label,
        "text": answer,
    })


@app.websocket("/ws/scan")
async def ws_scan(ws: WebSocket) -> None:
    await ws.accept()
    session = SessionState()
    try:
        while True:
            msg = await ws.receive_json()
            command = (msg.get("command") or "").strip()

            await ws.send_json({"type": "user_echo", "command": command})

            if not command:
                await ws.send_json({
                    "type": "system",
                    "message": "Empty command. Try: python main.py test_php.php",
                })
                continue

            target = _parse_command(command)
            if target is not None:
                single = _has_flag(command, "--single")
                no_arb = _has_flag(command, "--no-arbitration")
                await _start_scan(ws, session, target,
                                  single=single, no_arbitration=no_arb)
                continue

            cmd_norm = " ".join(command.lower().split())
            if cmd_norm in (
                "close", "/close", "end", "exit",
                "exit conversation", "close conversation",
                "end conversation",
            ):
                if session.chat_open:
                    session.reset()
                    await ws.send_json({
                        "type": "chat_closed",
                        "message": ("Conversation closed. "
                                    "Type a new scan command to start over."),
                    })
                else:
                    await ws.send_json({
                        "type": "system",
                        "message": "No active conversation to close.",
                    })
                continue

            if session.chat_open:
                agent_id, question = _parse_chat_prefix(command)
                if agent_id is None:
                    await ws.send_json({
                        "type": "system",
                        "message": (
                            "Pick an agent with a prefix: "
                            "`security: <question>` | `performance: <question>` "
                            "| `logic: <question>` (or `close`)."
                        ),
                    })
                    continue
                await _handle_question(ws, session, agent_id, question)
                continue

            await ws.send_json({
                "type": "system",
                "message": "No active scan. Try: python main.py test_php.php",
            })

    except WebSocketDisconnect:
        return
