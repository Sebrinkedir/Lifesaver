from crewai import Task
from agents import security_agent, logic_agent, performance_agent


def create_all_tasks(code: str):

    security_task = Task(
        description=f"""
Check this Python code for SECURITY issues:

{code}

Focus on:
- hardcoded secrets
- unsafe system calls
- injection risks
- unsafe imports
""",
        expected_output="""
A list of security issues with:
- description
- severity (LOW / MEDIUM / HIGH)
- confidence (0.0 - 1.0)
""",
        agent=security_agent
    )

    logic_task = Task(
        description=f"""
Check this Python code for LOGIC errors:

{code}

Focus on:
- incorrect conditions
- missing returns
- wrong variables
- broken flow
""",
        expected_output="""
A list of logic errors with explanation and confidence score.
""",
        agent=logic_agent
    )

    performance_task = Task(
        description=f"""
Check this Python code for PERFORMANCE issues:

{code}

Focus on:
- slow operations
- inefficient loops
- memory waste
""",
        expected_output="""
A list of performance issues with explanation and confidence score.
""",
        agent=performance_agent
    )

    return [security_task, logic_task, performance_task]