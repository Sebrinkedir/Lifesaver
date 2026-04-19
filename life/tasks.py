# tasks.py
# LifeSaver - Tasks for each Agent

from crewai import Task
from agents import security_agent, performance_agent, logic_agent


def create_tasks(code: str):
    """
    Creates tasks for all three agents.
    Takes the Python code as input.
    Returns a list of three tasks.
    """

    # ── Task 1: Security Task ────────────────────
    security_task = Task(
        description=(
            f"Review the following Python code for security vulnerabilities.\n\n"
            f"```python\n{code}\n```\n\n"
            f"Use the BanditSecurityScanner tool to scan the code first. "
            f"Then add any additional security findings you are confident about. "
            f"For each finding report:\n"
            f"- What the issue is\n"
            f"- How severe it is (HIGH, MEDIUM, LOW)\n"
            f"- Your confidence score (0.0 to 1.0)\n"
            f"- Which line it is on\n"
            f"If no issues found, clearly state that."
        ),
        expected_output=(
            "A list of security findings. Each finding must include: "
            "issue description, severity (HIGH/MEDIUM/LOW), "
            "confidence score (0.0 to 1.0), and line number. "
            "If no issues found, state: NO SECURITY ISSUES FOUND."
        ),
        agent=security_agent
    )

    # ── Task 2: Performance Task ─────────────────
    performance_task = Task(
        description=(
            f"Review the following Python code for performance issues.\n\n"
            f"```python\n{code}\n```\n\n"
            f"Look for slow loops, repeated computations, unnecessary memory "
            f"usage, and inefficient patterns. "
            f"For each finding report:\n"
            f"- What the issue is\n"
            f"- How severe it is (HIGH, MEDIUM, LOW)\n"
            f"- Your confidence score (0.0 to 1.0)\n"
            f"- Which line it is on\n"
            f"If no issues found, clearly state that."
        ),
        expected_output=(
            "A list of performance findings. Each finding must include: "
            "issue description, severity (HIGH/MEDIUM/LOW), "
            "confidence score (0.0 to 1.0), and line number. "
            "If no issues found, state: NO PERFORMANCE ISSUES FOUND."
        ),
        agent=performance_agent
    )

    # ── Task 3: Logic Task ───────────────────────
    logic_task = Task(
        description=(
            f"Review the following Python code for logic errors.\n\n"
            f"```python\n{code}\n```\n\n"
            f"Look for incorrect conditions, missing return statements, "
            f"wrong variable usage, and broken program flow. "
            f"For each finding report:\n"
            f"- What the issue is\n"
            f"- How severe it is (HIGH, MEDIUM, LOW)\n"
            f"- Your confidence score (0.0 to 1.0)\n"
            f"- Which line it is on\n"
            f"If no issues found, clearly state that."
        ),
        expected_output=(
            "A list of logic findings. Each finding must include: "
            "issue description, severity (HIGH/MEDIUM/LOW), "
            "confidence score (0.0 to 1.0), and line number. "
            "If no issues found, state: NO LOGIC ISSUES FOUND."
        ),
        agent=logic_agent
    )

    return [security_task, performance_task, logic_task]