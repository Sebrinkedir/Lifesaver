import contextlib
import io
import os
import sys


@contextlib.contextmanager
def _suppress_console_output():
    # With verbose=False the only thing crew.kickoff() writes to the console
    # is CrewAI's non-fatal event-bus warnings ("[CrewAIEventsBus] Warning:
    # Event pairing mismatch..."), which rich wraps across several lines.
    # Discard stdout/stderr for the duration; genuine failures raise
    # exceptions and are reported by the caller with the streams restored.
    sink = io.StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = sink, sink
    try:
        yield
    finally:
        sys.stdout, sys.stderr = old_out, old_err


def _silence_crewai_noise() -> None:
    import logging
    import warnings

    warnings.filterwarnings("ignore")
    os.environ.setdefault("OTEL_SDK_DISABLED", "true")
    for name in (
        "crewai",
        "crewai.utilities.events",
        "litellm",
        "LiteLLM",
        "httpx",
    ):
        logging.getLogger(name).setLevel(logging.ERROR)


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


def review_code(code: str, debug: bool = False) -> None:
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

    if not debug:
        _silence_crewai_noise()

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

        if debug:
            result = crew.kickoff()
        else:
            with _suppress_console_output():
                result = crew.kickoff()

        security_output    = tasks[0].output.raw if tasks[0].output else ""
        performance_output = tasks[1].output.raw if tasks[1].output else ""
        logic_output       = tasks[2].output.raw if tasks[2].output else ""

        if debug:
            for label, out in (
                ("SECURITY",    security_output),
                ("PERFORMANCE", performance_output),
                ("LOGIC",       logic_output),
            ):
                print("\n" + "=" * 60)
                print(f"RAW {label} AGENT OUTPUT "
                      f"(type={type(out).__name__}, len={len(out or '')})")
                print("=" * 60)
                print(repr(out) if not (out or "").strip() else out)

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
        if debug:
            import traceback
            traceback.print_exc()
        print("Make sure:")
        print("  1. ollama serve is running")
        print("  2. Models installed:")
        print("     ollama pull llama3.1:8b")
        print("     ollama pull gemma3:4b")
        print("     ollama pull deepseek-r1:7b")


DEFAULT_TEST_FILE = "test_js.js"

CODE_EXTENSIONS = ("py", "js", "java", "php", "cpp", "cs", "go", "rb")


def list_available_test_files() -> list:
    return sorted(
        f for f in os.listdir(".")
        if f.startswith("test_")
        and "." in f
        and f.rsplit(".", 1)[-1].lower() in CODE_EXTENSIONS
    )


if __name__ == "__main__":

    args     = [a for a in sys.argv[1:] if a != "--debug"]
    debug    = "--debug" in sys.argv[1:]
    filename = args[0] if args else DEFAULT_TEST_FILE

    if not os.path.isfile(filename):
        print(f"ERROR: file not found: {filename}")
        print()
        print("Usage: python main.py [path-to-code-file] [--debug]")
        print(f"       (defaults to {DEFAULT_TEST_FILE} when no file is given)")
        print()
        available = list_available_test_files()
        if available:
            print("Available test files in this directory:")
            for f in available:
                print(f"  python main.py {f}")
        sys.exit(1)

    with open(filename, "r", encoding="utf-8") as f:
        test_code = f.read()

    print(f"File     : {filename}")
    review_code(test_code, debug=debug)
