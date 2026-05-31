import contextlib
import io
import os
import sys


@contextlib.contextmanager
def _suppress_console_output():
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


def review_code(code: str, debug: bool = False,
                no_arbitration: bool = False) -> None:
    """Full 3-agent LifeSaver review.

    When `no_arbitration` is True the WAS-threshold filter is skipped —
    all findings are kept regardless of score. This is the proposal's
    "multi-agent without formal arbitration" baseline.
    """
    global consistent_runs, total_runs

    print("=" * 60)
    mode_label = ("STARTING CODE REVIEW (no arbitration baseline)"
                  if no_arbitration else "STARTING CODE REVIEW")
    print(f"     LIFESAVER - {mode_label}")
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

        was_results = calculate_was(all_findings)
        if no_arbitration:
            filtered_results = was_results
            print(f"  WAS filter SKIPPED (no-arbitration baseline): "
                  f"all {len(filtered_results)} findings kept")
        else:
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


def review_code_single(code: str, debug: bool = False) -> None:
    """Single-agent baseline review. Uses one model (qwen2.5-coder by
    default; see single_agent.SINGLE_MODEL) to find all issue categories
    at once. Used to compare against the 3-agent pipeline in the paper."""
    global consistent_runs, total_runs

    from single_agent import scan_single, SINGLE_MODEL

    print("=" * 60)
    print(f"     LIFESAVER - SINGLE-AGENT BASELINE ({SINGLE_MODEL})")
    print("=" * 60)

    if not code or not code.strip():
        print("ERROR: No code provided.")
        return

    language = detect_language(code)
    print(f"Lines    : {len(code.strip().splitlines())}")
    print(f"Language : {language}")
    print(f"Mode     : SINGLE-AGENT (baseline)")
    print()

    if not debug:
        _silence_crewai_noise()

    try:
        kept = scan_single(code, language=language, debug=debug)

        print(f"Results:")
        print(f"  Findings (post WAS >= 0.6): {len(kept)}")

        total_runs += 1
        if kept:
            consistent_runs += 1
        reliability = calculate_reliability(consistent_runs, total_runs)
        print_report(kept, reliability)

    except Exception as e:
        err = str(e)
        print(f"\nERROR: {err}")
        if debug:
            import traceback
            traceback.print_exc()
        print()
        if "CUDA" in err or "shared object" in err or "llama runner" in err:
            print("This looks like a GPU / CUDA error. Recovery steps:")
            print("  1. Stop Ollama:           ollama stop")
            print("  2. Restart it:            ollama serve")
            print("  3. Confirm GPU is free:   nvidia-smi  (no leftover process)")
            print("  4. Retry the command")
            print()
            print("If it still fails, switch single_agent.SINGLE_MODEL to a")
            print("smaller fallback:")
            print("  ollama/llama3.2:latest   (~2.0 GB)")
            print("  ollama/phi4-mini:latest  (~2.5 GB)")
            print("  ollama/qwen2.5:3b        (~1.9 GB)")
        elif "connection" in err.lower() or "10061" in err:
            print("Ollama is not reachable. Recovery steps:")
            print("  1. ollama serve     (in a separate terminal)")
            print("  2. Wait until 'Listening on 127.0.0.1:11434'")
            print("  3. Retry the command")
        elif "not found" in err.lower():
            print("Baseline model not installed. Pull it with:")
            print("  ollama pull mistral")
            print("(or whichever model single_agent.SINGLE_MODEL points to)")
        else:
            print("Make sure:")
            print("  1. ollama serve is running")
            print("  2. The baseline model is installed")
            print("     (see SINGLE_MODEL in single_agent.py)")


if __name__ == "__main__":

    flags    = {"--debug", "--single", "--no-arbitration"}
    args     = [a for a in sys.argv[1:] if a not in flags]
    debug    = "--debug"          in sys.argv[1:]
    single   = "--single"         in sys.argv[1:]
    no_arb   = "--no-arbitration" in sys.argv[1:]
    filename = args[0] if args else DEFAULT_TEST_FILE

    if not os.path.isfile(filename):
        print(f"ERROR: file not found: {filename}")
        print()
        print("Usage: python main.py [path-to-code-file] [flags]")
        print(f"       (defaults to {DEFAULT_TEST_FILE} when no file is given)")
        print()
        print("Flags (mutually exclusive baselines):")
        print("  --single           = single-agent baseline (one model)")
        print("  --no-arbitration   = 3 agents but skip the WAS >=0.6 filter")
        print("  --debug            = dump raw agent output + full traceback")
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
    if single:
        review_code_single(test_code, debug=debug)
    else:
        review_code(test_code, debug=debug, no_arbitration=no_arb)
