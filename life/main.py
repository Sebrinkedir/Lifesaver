from crewai import Crew, Process
from agents import security_agent, performance_agent, logic_agent
from tasks import create_all_tasks


def get_user_code():
    print("\nPaste Python code (end with empty line):\n")

    lines = []
    while True:
        line = input()
        if line.strip() == "":
            break
        lines.append(line)

    return "\n".join(lines)


def run_review(code: str):
    tasks = create_all_tasks(code)

    crew = Crew(
        agents=[security_agent, logic_agent, performance_agent],
        tasks=tasks,
        process=Process.sequential
    )

    return crew.kickoff()


def main():
    print("\n==============================")
    print("     LIFESAVER CODE REVIEW")
    print("==============================\n")

    code = get_user_code()

    if not code.strip():
        print("No code provided.")
        return

    print("\nRunning analysis...\n")

    result = run_review(code)

    print("\n================ FINAL OUTPUT ================\n")
    print(result)


if __name__ == "__main__":
    main()