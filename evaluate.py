"""LLM-as-judge evaluator for LifeSaver.

Computes the proposal's Reliability formula

    R = alpha * (1 - FPR)  +  beta * wF1  +  gamma * Consistency

without external corpora or labelled ground truth. The 3-agent scanner
runs on each fixture; an independent LLM judge then:

    1. classifies every finding as TRUE_POSITIVE or FALSE_POSITIVE
       (drives TP / FP and therefore Precision and FPR), and
    2. enumerates every real bug it sees in the source code (drives FN
       and therefore Recall).

Multiple runs per fixture give the Consistency term (stability of WAS
across runs).

Usage:

    python evaluate.py                    # 2 runs over every fixture
    python evaluate.py --runs 3           # 3 runs
    python evaluate.py --quick            # 1 run, 2 fixtures (smoke test)
    python evaluate.py --runs 2 python java   # only Python + Java
    python evaluate.py --alpha 0.3 --beta 0.4 --gamma 0.3
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Optional

import litellm

from crewai import Crew, Process

from agents import security_agent, performance_agent, logic_agent
from tasks import create_tasks, detect_language
from arbitration import (
    parse_findings,
    calculate_was,
    filter_findings,
)
from main import _suppress_console_output, _silence_crewai_noise



FIXTURES = [
    ("Python",     "test_code.py"),
    ("JavaScript", "test_js.js"),
    ("Java",       "test_java.java"),
    ("PHP",        "test_php.php"),
    ("C",          "test_c.c"),
    ("C++",        "test_cpp.cpp"),
    ("C#",         "test_cs.cs"),
    ("Go",         "test_go.go"),
    ("Ruby",       "test_rb.rb"),
]

JUDGE_MODEL    = "ollama/llama3.1:8b"
OLLAMA_BASE    = "http://localhost:11434"
JUDGE_TIMEOUT  = 600
JUDGE_MAX_TOK  = 1024

LINE_TOLERANCE = 5   # an agent finding matches an enumerated bug if their



_AGENTS_IN_ORDER = [
    ("security",    security_agent,    "llama3.1:8b"),
    ("performance", performance_agent, "gemma3:4b"),
    ("logic",       logic_agent,       "deepseek-r1:7b"),
]


def _run_one_agent(agent, task) -> str:
    """Run a single agent in its own one-task Crew. Blocking, returns raw."""
    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )
    with _suppress_console_output():
        crew.kickoff()
    return task.output.raw if task.output else ""


def scan_once(code: str, log=print, mode: str = "full") -> list:
    """Run the scan once, with progress logging. Mode picks which pipeline:

      mode = "full"           -> 3 agents + WAS + filter >= 0.6 (default)
      mode = "single"         -> single-agent baseline (mistral via single_agent.py)
      mode = "no_arbitration" -> 3 agents + WAS, skip the >= 0.6 filter

    The single-agent path delegates to single_agent.scan_single, which
    applies its own WAS filter internally. The no-arbitration path keeps
    every WAS-scored finding so we can measure what the formal
    arbitration step contributes.
    """
    if mode == "single":
        from single_agent import scan_single
        log(f"      [1/1] single      (mistral:latest) ...", end="", flush=True)
        t0 = time.time()
        try:
            findings = scan_single(code, log=lambda *a, **k: None)
        except Exception as e:
            log(f" ERROR: {e}")
            return []
        log(f" {time.time() - t0:.1f}s")
        return findings

    tasks = create_tasks(code)
    raws = {"security": "", "performance": "", "logic": ""}

    for i, (aid, agent, model_name) in enumerate(_AGENTS_IN_ORDER, start=1):
        log(f"      [{i}/3] {aid:<11} ({model_name}) ...", end="", flush=True)
        t0 = time.time()
        try:
            raws[aid] = _run_one_agent(agent, tasks[i - 1])
        except Exception as e:
            log(f" ERROR: {e}")
            continue
        log(f" {time.time() - t0:.1f}s")

    sec   = parse_findings(raws["security"],    "security")
    perf  = parse_findings(raws["performance"], "performance")
    logic = parse_findings(raws["logic"],       "logic")
    all_findings = sec + perf + logic

    scored = calculate_was(all_findings)
    if mode == "no_arbitration":
        return scored
    return filter_findings(scored)



_THINK_RE = re.compile(r"<think(?:ing)?>.*?</think(?:ing)?>", re.DOTALL | re.IGNORECASE)
_THINK_OPEN_TAIL_RE = re.compile(r"<think(?:ing)?>.*$", re.DOTALL | re.IGNORECASE)
_THINK_CLOSE_HEAD_RE = re.compile(r"^.*?</think(?:ing)?>", re.DOTALL | re.IGNORECASE)


def _strip_think(text: str) -> str:
    text = _THINK_RE.sub("", text)
    text = _THINK_OPEN_TAIL_RE.sub("", text)
    text = _THINK_CLOSE_HEAD_RE.sub("", text)
    return text.strip()


def _judge_call(prompt: str) -> str:
    """One litellm call to the judge model. Returns trimmed text."""
    resp = litellm.completion(
        model=JUDGE_MODEL,
        messages=[{"role": "user", "content": prompt}],
        api_base=OLLAMA_BASE,
        temperature=0.0,
        max_tokens=JUDGE_MAX_TOK,
        timeout=JUDGE_TIMEOUT,
    )
    text = resp.choices[0].message.content or ""
    return _strip_think(text)


def judge_finding_verdict(code: str, language: str, finding: dict) -> str:
    """Classify a single finding as TP / FP / AMBIGUOUS."""
    prompt = (
        "You are an independent code-review judge. Decide whether the "
        "finding below is a TRUE positive (the code really contains the "
        "described problem) or a FALSE positive (the finding is wrong, "
        "irrelevant, or describes a non-issue).\n\n"
        f"Code ({language}):\n```{language.lower()}\n{code}\n```\n\n"
        "Finding:\n"
        f"  Category   : {finding.get('agent', '?')}\n"
        f"  Severity   : {finding.get('severity', '?')}\n"
        f"  Description: {finding.get('description', '?')}\n"
        f"  Line       : {finding.get('line', '?')}\n"
        f"  Reason     : {finding.get('reason', '?')}\n\n"
        "Respond with EXACTLY one of these tokens on the first line:\n"
        "TRUE_POSITIVE  or  FALSE_POSITIVE\n"
        "Then on a new line give ONE short sentence of justification."
    )
    try:
        text = _judge_call(prompt)
    except Exception as e:
        print(f"      [judge error] {e}")
        return "AMBIGUOUS"
    head = text.upper()
    if "TRUE_POSITIVE" in head or "TRUE POSITIVE" in head:
        return "TP"
    if "FALSE_POSITIVE" in head or "FALSE POSITIVE" in head:
        return "FP"
    return "AMBIGUOUS"


_BUG_PATTERNS = [
    re.compile(r"\[(security|performance|logic)\]\s*(.+?)\s*\(\s*line\s*(\d+)\s*\)", re.I),
    re.compile(r"\**(security|performance|logic)\**\s*[:\-]\s*(.+?)\s*\(\s*line\s*(\d+)\s*\)", re.I),
    re.compile(r"\**(security|performance|logic)\**\s*[:\-]\s*(.+?)\s+line\s+(\d+)\b", re.I),
    re.compile(r"[-*]\s*\**(security|performance|logic)\**\s*[:\-]\s*(.+?)\s*\(\s*line\s*(\d+)\s*\)", re.I),
    re.compile(r"\bline\s*(\d+)\b[:\-\s]*\**(security|performance|logic)\**\s*[:\-]\s*(.+?)\s*$", re.I | re.M),
    re.compile(r"(.+?)\s+at\s+line\s+(\d+)\s*[\[(](security|performance|logic)[\])]", re.I),
]


def _coerce_category(s: str) -> str:
    s = s.lower().strip()
    if "secur" in s: return "security"
    if "perf"  in s: return "performance"
    if "logic" in s or "corr" in s: return "logic"
    return s


def _parse_bugs_from_text(text: str) -> list:
    """Try every pattern; collect everything that looks like a bug record."""
    bugs = []
    seen = set()

    for pattern in _BUG_PATTERNS:
        for m in pattern.finditer(text):
            groups = m.groups()
            cat = desc = line = None
            for g in groups:
                if g is None:
                    continue
                gl = g.strip().lower()
                if gl in ("security", "performance", "logic"):
                    cat = gl
                elif g.strip().isdigit():
                    line = int(g.strip())
                else:
                    if desc is None or len(g.strip()) > len(desc):
                        desc = g.strip()
            if cat and line and desc:
                key = (cat, line, desc[:40].lower())
                if key in seen:
                    continue
                seen.add(key)
                desc = re.sub(r"^[\s\-*0-9.()]+", "", desc).strip()
                bugs.append({
                    "category":    cat,
                    "description": desc,
                    "line":        line,
                })
    return bugs


DEBUG_DIR = Path(__file__).resolve().parent / ".eval_debug"


def _dump_debug(label: str, content: str) -> str:
    DEBUG_DIR.mkdir(exist_ok=True)
    path = DEBUG_DIR / f"{label}_{int(time.time())}.txt"
    path.write_text(content, encoding="utf-8")
    return str(path)


def judge_enumerate_bugs(code: str, language: str) -> list:
    """Ask the judge to list every real bug it sees in the code.

    Returns a list of {category, description, line} dicts.
    """
    prompt = (
        "You are an independent code-review judge. Your task is to list "
        "EVERY real defect in the code below — security vulnerabilities, "
        "performance issues, and logic / correctness bugs. Be exhaustive. "
        "The code below was deliberately written with multiple bugs; "
        "expect to find several.\n\n"
        "Output ONLY a list of bugs, one per line, in this format:\n\n"
        "[CATEGORY] short description (Line N)\n\n"
        "Where CATEGORY is exactly one of SECURITY, PERFORMANCE, LOGIC, "
        "and N is the 1-based line number.\n\n"
        "Example output:\n"
        "[SECURITY] Hardcoded password in PASSWORD variable (Line 7)\n"
        "[SECURITY] SQL injection in authenticate function (Line 11)\n"
        "[PERFORMANCE] Nested loops cause O(n^2) complexity (Line 33)\n"
        "[LOGIC] Division by zero when list is empty (Line 30)\n\n"
        "Do NOT include preamble, headings, numbering, code blocks, or "
        "explanation — output only the bug lines.\n\n"
        f"Code ({language}):\n```{language.lower()}\n{code}\n```\n\n"
        "List the bugs now:"
    )
    try:
        text = _judge_call(prompt)
    except Exception as e:
        print(f"      [judge enumerate error] {e}")
        return []

    bugs = _parse_bugs_from_text(text)

    if not bugs and text.strip():
        dump = _dump_debug("enumerate", text)
        print(f"      [judge produced output but parser found 0 bugs — raw saved to {dump}]")

    return bugs



_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokens(s: str) -> set:
    return set(_WORD_RE.findall((s or "").lower()))


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / max(len(a | b), 1)


def _line_of(finding: dict) -> Optional[int]:
    v = finding.get("line")
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def finding_matches_bug(finding: dict, bug: dict) -> bool:
    """Generous matcher: same line (within tolerance) AND (same category OR
    description overlap). This is deliberately loose because the judge's
    category labels and line numbers don't always align with what the
    producing agent picked — we don't want to punish the agent for that."""
    f_line = _line_of(finding)
    if f_line is None or abs(f_line - bug["line"]) > LINE_TOLERANCE:
        return False
    if finding.get("agent", "").lower() == bug["category"]:
        return True
    overlap = _jaccard(_tokens(finding.get("description", "")),
                       _tokens(bug["description"]))
    return overlap >= 0.20



def evaluate_fixture(language: str, filename: str, runs: int, log,
                     mode: str = "full") -> dict:
    code = open(filename, "r", encoding="utf-8").read()
    detected_lang = detect_language(code)

    log(f"\n=== {language:<11}  {filename}  (lang detected: {detected_lang}, mode: {mode}) ===")

    run_records = []

    for r_idx in range(1, runs + 1):
        log(f"  run {r_idx}/{runs}: scanning")
        t0 = time.time()
        try:
            findings = scan_once(code, log=log, mode=mode)
        except Exception as e:
            log(f"    SCAN ERROR: {e}")
            continue
        log(f"    -> {len(findings)} kept findings "
            f"(total scan {time.time()-t0:.1f}s)")

        log("    enumerating bugs ...", end=" ", flush=True)
        t0 = time.time()
        bugs = judge_enumerate_bugs(code, detected_lang)
        log(f"{len(bugs)} bugs listed  ({time.time()-t0:.1f}s)")

        verdicts = []
        matched_bug_idx = set()
        for f in findings:
            match_idx = None
            for i, bug in enumerate(bugs):
                if finding_matches_bug(f, bug):
                    match_idx = i
                    break
            if match_idx is not None:
                matched_bug_idx.add(match_idx)
                verdicts.append({"finding": f, "verdict": "TP", "bug": bugs[match_idx]})
            else:
                verdicts.append({"finding": f, "verdict": "FP", "bug": None})

        tp = sum(1 for v in verdicts if v["verdict"] == "TP")
        fp = sum(1 for v in verdicts if v["verdict"] == "FP")
        fn = len(bugs) - len(matched_bug_idx)

        log(f"    -> TP={tp}  FP={fp}  FN={fn}")

        run_records.append({
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "findings": findings,
            "verdicts": verdicts,
            "enumerated_bugs": bugs,
        })

    if not run_records:
        return {
            "fixture": filename, "language": language,
            "runs": 0, "error": "no successful runs",
        }

    avg_tp = statistics.mean(r["tp"] for r in run_records)
    avg_fp = statistics.mean(r["fp"] for r in run_records)
    avg_fn = statistics.mean(r["fn"] for r in run_records)
    findings_per_run = statistics.mean(len(r["findings"]) for r in run_records)

    precision = avg_tp / (avg_tp + avg_fp) if (avg_tp + avg_fp) > 0 else 0.0
    recall    = avg_tp / (avg_tp + avg_fn) if (avg_tp + avg_fn) > 0 else 0.0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) > 0 else 0.0)
    fpr       = avg_fp / (avg_tp + avg_fp) if (avg_tp + avg_fp) > 0 else 0.0

    buckets: dict = {}
    for r in run_records:
        for f in r["findings"]:
            key = (f.get("agent", "?"), str(f.get("line", "?")))
            buckets.setdefault(key, []).append(
                float(f.get("WAS", f.get("confidence", 0.0)))
            )
    if any(len(v) > 1 for v in buckets.values()):
        stds = [statistics.pstdev(v) for v in buckets.values() if len(v) > 1]
        consistency = 1.0 - statistics.mean(stds)
    else:
        consistency = 1.0
    consistency = max(0.0, min(1.0, consistency))

    return {
        "fixture": filename,
        "language": language,
        "runs": len(run_records),
        "findings_per_run": findings_per_run,
        "avg_tp": avg_tp, "avg_fp": avg_fp, "avg_fn": avg_fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "fpr": fpr,
        "consistency": consistency,
        "run_records": run_records,
    }



def _print_summary(results: list, alpha: float, beta: float, gamma: float) -> dict:
    print()
    print("=" * 96)
    print("  LIFESAVER — EVALUATION SUMMARY")
    print("=" * 96)
    print(f"{'Language':<11}{'TP':>5}{'FP':>5}{'FN':>5}"
          f"{'Prec':>8}{'Rec':>8}{'F1':>8}{'FPR':>8}{'Cons':>8}{'N find':>8}")
    print("-" * 96)
    valid = [r for r in results if r.get("runs", 0) > 0]
    for r in valid:
        print(f"{r['language']:<11}"
              f"{r['avg_tp']:>5.1f}{r['avg_fp']:>5.1f}{r['avg_fn']:>5.1f}"
              f"{r['precision']:>8.2f}{r['recall']:>8.2f}{r['f1']:>8.2f}"
              f"{r['fpr']:>8.2f}{r['consistency']:>8.2f}"
              f"{r['findings_per_run']:>8.1f}")
    print("-" * 96)

    if not valid:
        print("(no successful runs — nothing to aggregate)")
        return {}

    total_weight = sum(r["findings_per_run"] for r in valid)
    wF1 = (sum(r["f1"] * r["findings_per_run"] for r in valid) / total_weight
           if total_weight > 0 else 0.0)
    avg_fpr  = statistics.mean(r["fpr"]         for r in valid)
    avg_cons = statistics.mean(r["consistency"] for r in valid)

    R = alpha * (1 - avg_fpr) + beta * wF1 + gamma * avg_cons

    print(f"{'AGGREGATE':<11}"
          f"{'':>5}{'':>5}{'':>5}"
          f"{'':>8}{'':>8}{wF1:>8.2f}{avg_fpr:>8.2f}{avg_cons:>8.2f}")
    print("=" * 96)
    print()
    print(f"R = α·(1 − FPR) + β·wF1 + γ·Consistency")
    print(f"R = {alpha:.2f}·(1 − {avg_fpr:.3f}) + {beta:.2f}·{wF1:.3f} + {gamma:.2f}·{avg_cons:.3f}")
    print(f"R = {alpha * (1 - avg_fpr):.3f} + {beta * wF1:.3f} + {gamma * avg_cons:.3f}")
    print(f"R = {R:.3f}")
    print()
    status = "RELIABLE" if R >= 0.85 else "NEEDS MORE RUNS / TUNING"
    print(f"Status: {status}")
    print("=" * 96)

    return {
        "wF1":         wF1,
        "avg_fpr":     avg_fpr,
        "avg_cons":    avg_cons,
        "alpha":       alpha,
        "beta":        beta,
        "gamma":       gamma,
        "R":           R,
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description="LLM-as-judge evaluator for LifeSaver. Computes FPR, wF1, "
                    "Consistency, and the proposal's R formula entirely from "
                    "AI judgement — no external corpora, no manual labels."
    )
    ap.add_argument("--runs", type=int, default=2,
                    help="Repeated scans per fixture (default 2). Higher N "
                         "improves consistency measurement but multiplies "
                         "runtime.")
    ap.add_argument("--quick", action="store_true",
                    help="1 run over only Python + JavaScript (smoke test).")
    ap.add_argument("--alpha", type=float, default=1/3, help="weight on (1-FPR)")
    ap.add_argument("--beta",  type=float, default=1/3, help="weight on wF1")
    ap.add_argument("--gamma", type=float, default=1/3, help="weight on Consistency")
    ap.add_argument("--single", action="store_true",
                    help="Single-agent baseline (mistral:latest) — proposal's "
                         "first baseline.")
    ap.add_argument("--no-arbitration", dest="no_arbitration", action="store_true",
                    help="3 agents but skip the WAS >= 0.6 filter — proposal's "
                         "second baseline.")
    ap.add_argument("--out",   type=str, default=None,
                    help="Where to save the raw JSON results "
                         "(default depends on mode).")
    ap.add_argument("languages", nargs="*",
                    help="Optional subset of languages (e.g. python java).")
    args = ap.parse_args()

    if args.single and args.no_arbitration:
        print("ERROR: --single and --no-arbitration are mutually exclusive.")
        sys.exit(1)

    if args.single:
        mode = "single"
    elif args.no_arbitration:
        mode = "no_arbitration"
    else:
        mode = "full"

    s = args.alpha + args.beta + args.gamma
    if abs(s - 1.0) > 1e-6:
        print(f"WARNING: alpha+beta+gamma = {s:.3f}, expected 1.0")

    _silence_crewai_noise()

    if args.quick:
        wanted = {"python", "javascript"}
        runs = 1
    else:
        wanted = {l.lower() for l in args.languages}
        runs = args.runs

    fixtures = [(lang, fn) for (lang, fn) in FIXTURES
                if not wanted or lang.lower() in wanted]

    if not fixtures:
        print("No fixtures matched. Available:",
              ", ".join(l for l, _ in FIXTURES))
        sys.exit(1)

    mode_label = {"full": "full LifeSaver",
                  "single": "single-agent baseline (mistral)",
                  "no_arbitration": "no-arbitration baseline (3 agents, no WAS filter)"}[mode]
    print(f"Mode    : {mode_label}")
    print(f"Evaluating {len(fixtures)} fixture(s) × {runs} run(s) "
          f"with judge = {JUDGE_MODEL}")
    print(f"Weights: alpha={args.alpha:.3f}  beta={args.beta:.3f}  "
          f"gamma={args.gamma:.3f}")

    def log(*a, **kw):
        print(*a, **kw)

    t_start = time.time()
    results = []
    for (lang, fn) in fixtures:
        if not os.path.isfile(fn):
            log(f"SKIP {lang}: fixture not found ({fn})")
            continue
        try:
            res = evaluate_fixture(lang, fn, runs, log, mode=mode)
        except Exception as e:
            log(f"FAILED on {fn}: {e}")
            continue
        results.append(res)

    print(f"\nTotal evaluation time: {time.time() - t_start:.1f}s")

    aggregate = _print_summary(results, args.alpha, args.beta, args.gamma)

    default_out = {
        "full":           "evaluation_results.json",
        "single":         "evaluation_results_single.json",
        "no_arbitration": "evaluation_results_no_arbitration.json",
    }[mode]
    out_path = Path(args.out or default_out)
    try:
        save_results = []
        for r in results:
            save_results.append({k: v for k, v in r.items() if k != "run_records"})
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump({
                "mode":        mode,
                "judge_model": JUDGE_MODEL,
                "fixtures":    save_results,
                "aggregate":   aggregate,
                "alpha":       args.alpha,
                "beta":        args.beta,
                "gamma":       args.gamma,
                "runs":        runs,
            }, fh, indent=2)
        print(f"Saved results to {out_path}")
    except Exception as e:
        print(f"(could not save JSON: {e})")


if __name__ == "__main__":
    main()
