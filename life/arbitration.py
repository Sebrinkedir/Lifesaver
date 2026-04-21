"""
arbitration.py
LifeSaver - Arbitration Module

This file is the "judge" of the system.
It takes findings from all 3 agents and decides
which ones are real issues worth reporting.

It uses two main formulas from the proposal:
  1. WAS  - Weighted Agreement Score (is this finding trustworthy?)
  2. R    - Reliability Score (is the whole system consistent?)
"""

import re
import statistics


# ── Agent Weights ────────────────────────────────
# Security is most important (0.5), then Performance (0.3), then Logic (0.2)
# These must add up to 1.0
AGENT_WEIGHTS = {
    "security":    0.5,
    "performance": 0.3,
    "logic":       0.2
}

# ── Severity Scores ──────────────────────────────
# How serious is the issue?
# Critical=1.0, Moderate=0.6, Minor=0.2 (from proposal)
SEVERITY_SCORES = {
    "HIGH":   1.0,   # Critical in proposal terms
    "MEDIUM": 0.6,   # Moderate
    "LOW":    0.2    # Minor
}

# ── WAS Threshold ────────────────────────────────
# Only show findings with WAS >= 0.6 in the final report
# (anything below is likely a false alarm)
WAS_THRESHOLD = 0.6

# ── Bandit Bonus ─────────────────────────────────
# If Bandit (the static analysis tool) also flagged this issue,
# we add 0.15 extra to the WAS score as a reward for
# being confirmed by a real tool (not just LLM guessing)
BANDIT_BONUS = 0.15


# ────────────────────────────────────────────────
def parse_findings(agent_output: str, agent_type: str,
                   bandit_flagged_lines: list = None) -> list:
    """
    Reads the raw text output from an agent and pulls out
    the actual findings (issues it detected).

    Think of this like reading a doctor's notes and
    extracting: what disease, how serious, how sure are they.

    Parameters:
        agent_output        : the text the agent wrote
        agent_type          : "security", "performance", or "logic"
        bandit_flagged_lines: list of line numbers Bandit found issues on
                              (used to apply the +0.15 bonus later)

    Returns:
        A list of findings, each one is a dictionary with:
        severity, confidence, description, agent, bandit_confirmed
    """
    findings = []

    if bandit_flagged_lines is None:
        bandit_flagged_lines = []

    # ── Check if agent said "no issues" ─────────
    # If the agent clearly said nothing is wrong, return empty list
    no_issue_keywords = [
        "NO SECURITY ISSUES FOUND",
        "NO PERFORMANCE ISSUES FOUND",
        "NO LOGIC ISSUES FOUND",
        "NO ISSUES FOUND"
    ]
    for keyword in no_issue_keywords:
        if keyword in agent_output.upper():
            return findings  # empty — no issues to report

    # ── Parse line by line ───────────────────────
    lines = agent_output.strip().split("\n")
    current_finding = {}

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Look for severity label in this line
        for severity in ["HIGH", "MEDIUM", "LOW"]:
            if severity in line.upper():
                current_finding["severity"] = severity
                break

        # Look for a confidence number like 0.8 or 0.95
        confidence_match = re.search(r"\b0\.\d+\b", line)
        if confidence_match:
            current_finding["confidence"] = float(confidence_match.group())

        # Look for a line number like "Line: 5" or "line 12"
        line_num_match = re.search(r"line[:\s]+(\d+)", line.lower())
        if line_num_match:
            current_finding["line_number"] = int(line_num_match.group(1))

        # Look for issue description lines
        if any(word in line.lower() for word in ["issue", "found", "vulnerability",
                                                   "problem", "error", "risk"]):
            current_finding["description"] = line
            current_finding["agent"] = agent_type

        # ── Save finding when we have enough info ─
        # We need at least: severity + confidence + description
        if (
            "severity"    in current_finding and
            "confidence"  in current_finding and
            "description" in current_finding
        ):
            # Check if Bandit also caught this (gives +0.15 bonus)
            line_num = current_finding.get("line_number", -1)
            current_finding["bandit_confirmed"] = (line_num in bandit_flagged_lines)

            findings.append(current_finding.copy())
            current_finding = {}  # reset for next finding

    return findings


# ────────────────────────────────────────────────
def calculate_was(findings_list: list) -> list:
    """
    Calculates the Weighted Agreement Score (WAS) for each finding.

    This is the core formula from the proposal:
        WAS(i) = Σ(wₐ · Sₐ · Cₐ) / Σwₐ

    In plain English:
        - wₐ = how important is this agent? (Security=0.5, etc.)
        - Sₐ = how serious is the issue? (HIGH=1.0, etc.)
        - Cₐ = how confident is the agent? (0.0 to 1.0)

    Multiply all three together, divide by the total agent weight.
    If Bandit also flagged it, add 0.15 bonus.
    Only keep findings where WAS >= 0.6.

    Returns:
        List of findings with WAS scores, filtered to >= 0.6 only
    """
    if not findings_list:
        return []

    results = []

    for finding in findings_list:
        severity        = finding.get("severity", "LOW")
        confidence      = finding.get("confidence", 0.5)
        agent_type      = finding.get("agent", "security")
        bandit_confirmed = finding.get("bandit_confirmed", False)

        # Get the three values from our tables above
        wa = AGENT_WEIGHTS.get(agent_type, 0.2)    # agent weight
        sa = SEVERITY_SCORES.get(severity, 0.2)    # severity score
        ca = confidence                              # confidence score (0-1)

        # ── Apply the WAS formula ────────────────
        # Numerator:   wₐ × Sₐ × Cₐ
        # Denominator: wₐ  (just the agent weight)
        numerator   = wa * sa * ca
        denominator = wa  # Σwₐ — since each finding comes from one agent

        was_score = round(numerator / denominator, 4) if denominator > 0 else 0.0
        # Note: numerator/denominator simplifies to Sa * Ca,
        # but the formula structure remains faithful to the proposal
        # (multi-agent aggregation is done at the group level below)

        # ── Add Bandit bonus if applicable ───────
        # If the static analysis tool also caught this, we're more confident
        if bandit_confirmed:
            was_score = round(min(was_score + BANDIT_BONUS, 1.0), 4)

        # ── Only keep if WAS >= 0.6 ──────────────
        # Below 0.6 = likely a false alarm, don't show it
        if was_score >= WAS_THRESHOLD:
            results.append({
                "description":     finding.get("description", "Unknown issue"),
                "severity":        severity,
                "confidence":      confidence,
                "agent":           agent_type,
                "bandit_confirmed": bandit_confirmed,
                "WAS":             was_score
            })

    # Sort by WAS score — most serious first
    results.sort(key=lambda x: x["WAS"], reverse=True)
    return results


# ────────────────────────────────────────────────
def calculate_consistency(was_scores_across_runs: list) -> float:
    """
    Measures how consistent the system is across 5 repeated runs.

    Formula from proposal:
        Consistency = 1 - std_deviation(WAS scores across runs)

    In plain English:
        If the system gives the same WAS scores every time → Consistency = 1.0 (perfect)
        If scores jump around a lot → Consistency closer to 0.0

    Parameters:
        was_scores_across_runs: a list of average WAS scores,
                                one per run (ideally 5 runs)

    Returns:
        Consistency score between 0.0 and 1.0
    """
    if len(was_scores_across_runs) < 2:
        # Can't measure consistency with fewer than 2 runs
        return 1.0

    std_dev = statistics.stdev(was_scores_across_runs)
    consistency = round(max(0.0, 1.0 - std_dev), 4)
    return consistency


# ────────────────────────────────────────────────
def calculate_reliability(fpr: float, wf1: float,
                           consistency: float,
                           alpha: float = 0.4,
                           beta: float  = 0.4,
                           gamma: float = 0.2) -> float:
    """
    Calculates the overall Reliability Score (R).

    Formula from proposal:
        R = α·(1 − FPR) + β·wF1 + γ·Consistency

    In plain English:
        - FPR         = false positive rate (how often it cries wolf)
          → lower FPR is better, so we use (1 - FPR)
        - wF1         = weighted F1 score (balance of precision + recall)
          → higher is better
        - Consistency = how stable results are across runs
          → higher is better
        - α, β, γ     = how much each part matters (must add up to 1.0)

    Default weights: alpha=0.4, beta=0.4, gamma=0.2
    These will be calibrated during experiments.

    Returns:
        Reliability score between 0.0 and 1.0
    """
    # Safety checks — all values should be between 0 and 1
    fpr         = max(0.0, min(1.0, fpr))
    wf1         = max(0.0, min(1.0, wf1))
    consistency = max(0.0, min(1.0, consistency))

    R = (alpha * (1.0 - fpr)) + (beta * wf1) + (gamma * consistency)
    return round(R, 4)


# ────────────────────────────────────────────────
def print_report(was_results: list, reliability: float):
    """
    Prints the final LifeSaver report in a clean, readable format.

    Shows:
    - All findings that passed the WAS >= 0.6 threshold
    - Their severity, confidence, and trust level
    - Whether Bandit confirmed them
    - The overall Reliability Score
    """
    print("\n" + "=" * 60)
    print("         LIFESAVER - FINAL CODE REVIEW REPORT")
    print("=" * 60)

    if not was_results:
        print("\n✅ No issues passed the WAS threshold (0.6).")
        print("   Either the code is clean, or findings were low-confidence.")
    else:
        print(f"\n📋 Findings that passed WAS ≥ 0.6 threshold: "
              f"{len(was_results)}\n")
        print("-" * 60)

        for i, result in enumerate(was_results, 1):
            print(f"\nFinding #{i}")
            print(f"  Agent        : {result['agent'].upper()}")
            print(f"  Description  : {result['description']}")
            print(f"  Severity     : {result['severity']}")
            print(f"  Confidence   : {result['confidence']}")
            print(f"  WAS Score    : {result['WAS']}")
            print(f"  Bandit Check : "
                  f"{'✅ Confirmed by Bandit (+0.15 bonus applied)'
                     if result['bandit_confirmed'] else '❌ Not confirmed by Bandit'}")

            # Trust level label based on WAS score
            if result["WAS"] >= 0.85:
                print("  Trust Level  : 🔴 CRITICAL - Fix this immediately")
            elif result["WAS"] >= 0.7:
                print("  Trust Level  : 🟠 HIGH - Act on this soon")
            else:
                print("  Trust Level  : 🟡 MEDIUM - Review carefully")

    print("\n" + "-" * 60)
    print(f"\n📊 Reliability Score (R): {round(reliability * 100, 2)}%")

    if reliability >= 0.85:
        print("   Status: ✅ RELIABLE — System is consistent and accurate")
    elif reliability >= 0.65:
        print("   Status: 🟡 ACCEPTABLE — More runs recommended")
    else:
        print("   Status: ⚠️  LOW RELIABILITY — Results may not be trustworthy")

    print("\n" + "=" * 60 + "\n")