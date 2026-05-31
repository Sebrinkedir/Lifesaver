"""Single-agent baseline for LifeSaver.

The proposal's evaluation section names a single-agent LLM review as the
first baseline to compare against the full 3-agent LifeSaver pipeline.
This module implements that baseline using one model not currently used
by the three production agents (llama3.1 / gemma3 / deepseek-r1).

Default model: qwen2.5-coder — coding-specialised, fast, and independent
from the production agents so the comparison is meaningful. To switch
to a different unused model from your Ollama install (deepseek-coder-v2,
gemma2, llama3.2, mistral, phi4-mini, qwen2.5), edit SINGLE_MODEL below.

Public surface:
    scan_single(code, language=None) -> list of kept findings
"""
from __future__ import annotations

from crewai import Agent, Crew, LLM, Process, Task

from arbitration import (
    DOMAIN_KEYWORDS,
    parse_findings,
    calculate_was,
    filter_findings,
)
from tasks import detect_language, extract_functions
from main import _suppress_console_output



SINGLE_MODEL = "ollama/mistral:latest"

llm_single = LLM(
    model=SINGLE_MODEL,
    base_url="http://localhost:11434",
    temperature=0.0,
    max_tokens=4096,
    timeout=900,
)

single_agent = Agent(
    role="Code Reviewer",
    goal=(
        "Find bugs and security issues in the code. "
        "Output each finding as five labelled lines: "
        "ISSUE, SEVERITY, CONFIDENCE, LINE, REASON."
    ),
    backstory=(
        "You are a code reviewer. You read code, you find problems, and "
        "you list them in a fixed format. You do not invent issues."
    ),
    tools=[],
    llm=llm_single,
    verbose=False,
    allow_delegation=False,
    max_iter=2,
    max_rpm=10,
)



def _create_single_task(code: str, language: str, functions: str) -> Task:
    """Build a short, example-driven task for the single-agent baseline.

    The previous task asked for category tags inside descriptions; that has
    been dropped. _infer_category() in this module routes findings into
    security / performance / logic by keyword after parsing, so the agent
    only has to find issues and describe them clearly.
    """
    return Task(
        description=(
            f"Review this {language} code and list every problem you "
            f"find. Look for:\n"
            f" - hardcoded passwords / API keys / secrets\n"
            f" - SQL injection, command injection, unsafe deserialisation\n"
            f" - nested O(n^2) loops, string concat in loops\n"
            f" - division by zero, empty list access, missing return\n\n"
            f"{functions}\n\n"
            f"Code:\n{code}\n\n"
            f"For each problem you find, output FIVE labelled lines in "
            f"this exact format (blank line between findings):\n\n"
            f"ISSUE: short description\n"
            f"SEVERITY: Critical or Moderate or Minor\n"
            f"CONFIDENCE: a number between 0.0 and 1.0\n"
            f"LINE: the line number in the code\n"
            f"REASON: one sentence explaining why\n\n"
            f"EXAMPLE of one finding:\n"
            f"ISSUE: Hardcoded password in PASSWORD variable\n"
            f"SEVERITY: Critical\n"
            f"CONFIDENCE: 0.95\n"
            f"LINE: 7\n"
            f"REASON: Credentials stored in source can be read by anyone "
            f"with code access.\n\n"
            f"If you find nothing, output exactly: NO ISSUES FOUND"
        ),
        expected_output=(
            "A list of findings, each with ISSUE / SEVERITY / "
            "CONFIDENCE / LINE / REASON on five lines. Blank line "
            "between findings. Or 'NO ISSUES FOUND' if clean."
        ),
        agent=single_agent,
    )



def _infer_category(finding: dict) -> str:
    desc = (finding.get("description", "") + " " +
            finding.get("reason", "")).lower()

    head = finding.get("description", "").strip().lower()
    for cat in ("security", "performance", "logic"):
        if head.startswith(f"[{cat}]") or head.startswith(f"{cat}:"):
            return cat

    scores = {
        cat: sum(1 for kw in kws if kw in desc)
        for cat, kws in DOMAIN_KEYWORDS.items()
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "logic"


def _strip_category_prefix(description: str) -> str:
    """Strip '[SECURITY] ' / '[PERFORMANCE] ' / '[LOGIC] ' from the front
    of a description so the rendered finding doesn't double up the tag."""
    import re
    return re.sub(r'^\s*\[(security|performance|logic)\]\s*', '',
                  description, flags=re.IGNORECASE).strip()



def scan_single(code: str, language: str = None, log=print,
                debug: bool = False) -> list:
    """Run the single-agent baseline on code and return kept findings.

    When `debug` is True the raw model output is dumped after kickoff,
    so we can see what mistral actually produced — useful when the parser
    drops everything and the scan returns 0 findings.
    """
    if not language:
        language = detect_language(code)
    functions = extract_functions(code, language)

    log(f"  [single] {SINGLE_MODEL} on {language} ...", end="", flush=True)
    task = _create_single_task(code, language, functions)
    crew = Crew(
        agents=[single_agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )
    import time
    t0 = time.time()
    if debug:
        crew.kickoff()
    else:
        with _suppress_console_output():
            crew.kickoff()
    log(f" {time.time() - t0:.1f}s")

    raw = task.output.raw if task.output else ""

    if debug:
        log("\n" + "=" * 60)
        log(f"RAW SINGLE-AGENT OUTPUT (type={type(raw).__name__}, "
            f"len={len(raw or '')})")
        log("=" * 60)
        log(repr(raw) if not (raw or "").strip() else raw)
        log("=" * 60 + "\n")

    findings = parse_findings(raw, "single")

    if debug:
        log(f"[debug] parser produced {len(findings)} finding(s) "
            f"from raw output\n")

    for f in findings:
        cat = _infer_category(f)
        f["agent"] = cat
        f["description"] = _strip_category_prefix(f.get("description", ""))

    kept = filter_findings(calculate_was(findings))
    return kept


__all__ = ["scan_single", "single_agent", "SINGLE_MODEL"]
