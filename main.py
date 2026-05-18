from crewai import Crew, Process
from agents import security_agent, performance_agent, logic_agent
from tasks import create_tasks, detect_language
from arbitration import (
    parse_findings,
    calculate_was,
    filter_findings,
    calculate_reliability,
    print_report
)

consistent_runs = 0
total_runs      = 0


def review_code(code: str) -> None:
    global consistent_runs, total_runs

    print("=" * 60)
    print("     LIFESAVER - STARTING CODE REVIEW")
    print("=" * 60)

    if not code or not code.strip():
        print("ERROR: No code provided.")
        return

    language = detect_language(code)

    print(f"Lines    : {len(code.strip().splitlines())}")
    print(f"Language : {language}")
    print(f"Agents   :")
    print(f"  [1/3] Security Agent    (llama3.1:8b + Bandit)")
    print(f"  [2/3] Performance Agent (gemma3:4b)")
    print(f"  [3/3] Logic Agent       (deepseek-r1:7b)")
    print()

    try:
        tasks = create_tasks(code)

        crew = Crew(
            agents=[
                security_agent,
                performance_agent,
                logic_agent
            ],
            tasks=tasks,
            process=Process.sequential,
            verbose=False
        )

        result = crew.kickoff()

        security_output    = tasks[0].output.raw if tasks[0].output else ""
        performance_output = tasks[1].output.raw if tasks[1].output else ""
        logic_output       = tasks[2].output.raw if tasks[2].output else ""

        security_findings    = parse_findings(security_output,    "security")
        performance_findings = parse_findings(performance_output, "performance")
        logic_findings       = parse_findings(logic_output,       "logic")

        all_findings = []
        all_findings.extend(security_findings)
        all_findings.extend(performance_findings)
        all_findings.extend(logic_findings)

        print(f"Results:")
        print(f"  Security    : {len(security_findings)} finding(s)")
        print(f"  Performance : {len(performance_findings)} finding(s)")
        print(f"  Logic       : {len(logic_findings)} finding(s)")
        print(f"  Total       : {len(all_findings)} finding(s)")

        was_results      = calculate_was(all_findings)
        filtered_results = filter_findings(was_results)

        print(f"  After WAS filter (>=0.6): {len(filtered_results)} kept")

        total_runs += 1
        if filtered_results:
            consistent_runs += 1

        reliability = calculate_reliability(consistent_runs, total_runs)
        print_report(filtered_results, reliability)

    except Exception as e:
        print(f"\nERROR: {str(e)}")
        print("Make sure:")
        print("  1. ollama serve is running")
        print("  2. Models installed:")
        print("     ollama pull llama3.1:8b")
        print("     ollama pull gemma3:4b")
        print("     ollama pull deepseek-r1:7b")


if __name__ == "__main__":

    # Change filename here to test different languages:
    # test_code.py   → Python
    # test_js.js     → JavaScript
    # test_java.java → Java
    # test_php.php   → PHP

    filename = "test_php.php"

    with open(filename, "r") as f:
        test_code = f.read()

    review_code(test_code)