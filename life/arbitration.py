SEVERITY_WEIGHTS = {
    "HIGH":   1.0,
    "MEDIUM": 0.6,
    "LOW":    0.3
}

# ── Agent Type Weights ───────────────────────────
# Security agent findings are prioritized
AGENT_WEIGHTS = {
    "security":    1.0,
    "performance": 0.7,
    "logic":       0.7
}


def parse_findings(agent_output: str, agent_type: str) -> list:
    """
    Parses the raw text output from an agent.
    Extracts findings with severity and confidence.
    Returns a list of finding dictionaries.
    """
    findings = []
    lines = agent_output.strip().split("\n")

    # Check if agent found no issues
    no_issue_keywords = [
        "NO SECURITY ISSUES FOUND",
        "NO PERFORMANCE ISSUES FOUND",
        "NO LOGIC ISSUES FOUND"
    ]
    for keyword in no_issue_keywords:
        if keyword in agent_output.upper():
            return findings

    # Try to extract severity and confidence from output
    current_finding = {}
    for line in lines:
        line = line.strip()

        # Look for severity
        for severity in ["HIGH", "MEDIUM", "LOW"]:
            if severity in line.upper():
                current_finding["severity"] = severity
                break

        # Look for confidence score (e.g. 0.8 or 0.9)
        import re
        confidence_match = re.search(r"0\.\d+", line)
        if confidence_match:
            current_finding["confidence"] = float(
                confidence_match.group()
            )

        # Look for issue description
        if "issue" in line.lower() or "found" in line.lower():
            current_finding["description"] = line
            current_finding["agent"] = agent_type

        # Save finding if we have enough info
        if (
            "severity" in current_finding and
            "confidence" in current_finding and
            "description" in current_finding
        ):
            findings.append(current_finding.copy())
            current_finding = {}

    return findings


def calculate_was(findings_list: list) -> list:
    """
    Calculates the Weighted Agreement Score (WAS)
    for each finding reported by the agents.

    Formula from paper:
    WAS = sum(Ai * Si * Ci) / sum(Si)

    Where:
    - Ai = 1 if agent reported finding, 0 if not
    - Si = severity weight of agent i
    - Ci = confidence score of agent i
    """
    if not findings_list:
        return []

    results = []

    for finding in findings_list:
        severity  = finding.get("severity", "LOW")
        confidence = finding.get("confidence", 0.5)
        agent_type = finding.get("agent", "security")

        # Get weights
        Si = SEVERITY_WEIGHTS.get(severity, 0.3)
        Ci = confidence
        Ai = 1  # Agent reported this finding

        # Calculate WAS for this finding
        numerator   = Ai * Si * Ci
        denominator = Si

        was_score = round(numerator / denominator, 2) if denominator > 0 else 0.0

        results.append({
            "description": finding.get("description", "Unknown issue"),
            "severity":    severity,
            "confidence":  confidence,
            "agent":       agent_type,
            "WAS":         was_score
        })

    # Sort by WAS score — highest first
    results.sort(key=lambda x: x["WAS"], reverse=True)
    return results


def calculate_reliability(
    consistent_runs: int,
    total_runs: int
) -> float:
    """
    Calculates the Reliability Score (R).

    Formula from paper:
    R = (Cr / Tr) x 100

    Where:
    - Cr = number of consistent correct runs
    - Tr = total number of runs
    """
    if total_runs == 0:
        return 0.0

    R = (consistent_runs / total_runs) * 100
    return round(R, 2)


def print_report(was_results: list, reliability: float):
    """
    Prints the final LifeSaver report clearly.
    """
    print("\n" + "="*60)
    print("         LIFESAVER - FINAL CODE REVIEW REPORT")
    print("="*60)

    if not was_results:
        print("\n✅ No issues found by any agent.")
    else:
        print(f"\n📋 Total Findings: {len(was_results)}\n")
        print("-"*60)

        for i, result in enumerate(was_results, 1):
            print(f"\nFinding #{i}")
            print(f"  Agent      : {result['agent'].upper()}")
            print(f"  Description: {result['description']}")
            print(f"  Severity   : {result['severity']}")
            print(f"  Confidence : {result['confidence']}")
            print(f"  WAS Score  : {result['WAS']}")

            # Trust level based on WAS
            if result["WAS"] >= 0.7:
                print(f"  Trust Level: 🔴 HIGH - Act on this immediately")
            elif result["WAS"] >= 0.4:
                print(f"  Trust Level: 🟡 MEDIUM - Review carefully")
            else:
                print(f"  Trust Level: 🟢 LOW - Possible false positive")

        print("\n" + "-"*60)

    print(f"\n📊 Reliability Score (R): {reliability}%")

    if reliability >= 85:
        print("   Status: ✅ RELIABLE - System is consistent")
    else:
        print("   Status: ⚠️  NEEDS MORE RUNS to confirm reliability")

    print("\n" + "="*60 + "\n")