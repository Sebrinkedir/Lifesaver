from crewai import Crew, Process
from agents import security_agent, performance_agent, logic_agent
from tasks import create_tasks
from arbitration import (
    parse_findings,
    calculate_was,
    calculate_reliability,
    print_report
)

# ── Reliability Tracking ─────────────────────────
# These track consistency across multiple runs
consistent_runs = 0
total_runs      = 0


def review_code(code: str) -> None:
    """
    Main function that runs LifeSaver on a Python code snippet.
    1. Creates tasks for all three agents
    2. Runs the crew sequentially
    3. Parses findings from each agent
    4. Calculates WAS and Reliability Score
    5. Prints the final report
    """
    global consistent_runs, total_runs

    print("\n" + "="*60)
    print("         LIFESAVER - STARTING CODE REVIEW")
    print("="*60)
    print("\n📥 Code received. Starting agent analysis...\n")

    # Step 1 - Create tasks for this code
    tasks = create_tasks(code)

    # Step 2 - Build the crew
    crew = Crew(
        agents=[
            security_agent,
            performance_agent,
            logic_agent
        ],
        tasks=tasks,
        process=Process.sequential,
        verbose=True
    )

    # Step 3 - Run the crew
    result = crew.kickoff()

    # Step 4 - Get output from each agent task
    security_output    = tasks[0].output.raw if tasks[0].output else ""
    performance_output = tasks[1].output.raw if tasks[1].output else ""
    logic_output       = tasks[2].output.raw if tasks[2].output else ""

    # Step 5 - Parse findings from each agent
    all_findings = []

    security_findings = parse_findings(
        security_output, "security"
    )
    performance_findings = parse_findings(
        performance_output, "performance"
    )
    logic_findings = parse_findings(
        logic_output, "logic"
    )

    all_findings.extend(security_findings)
    all_findings.extend(performance_findings)
    all_findings.extend(logic_findings)

    # Step 6 - Calculate WAS for all findings
    was_results = calculate_was(all_findings)

    # Step 7 - Update reliability tracking
    total_runs += 1
    if was_results:
        consistent_runs += 1

    # Step 8 - Calculate Reliability Score
    reliability = calculate_reliability(
        consistent_runs,
        total_runs
    )

    # Step 9 - Print final report
    print_report(was_results, reliability)


# ── Entry Point ──────────────────────────────────
if __name__ == "__main__":

    # Example test code with known issues
    test_code = """
import os
import subprocess

password = "58dph"

def calculate(x, y):
    result = x / y
    return result

def run_command(cmd):
    os.system(cmd)

subprocess.call("rm -rf /", shell=True)
"""

    review_code(test_code)