import re

SEVERITY_WEIGHTS = {
    "HIGH":   1.0,
    "MEDIUM": 0.6,
    "LOW":    0.3
}


def parse_findings(agent_output: str, agent_type: str) -> list:
    findings = []

    no_issue_keywords = [
        "NO SECURITY ISSUES FOUND",
        "NO PERFORMANCE ISSUES FOUND",
        "NO LOGIC ISSUES FOUND"
    ]
    for keyword in no_issue_keywords:
        if keyword in agent_output.upper():
            return findings

    blocks = re.split(r'\n(?=ISSUE:)', agent_output, flags=re.IGNORECASE)

    for block in blocks:
        if not block.strip():
            continue

        issue_match = re.search(r'ISSUE:\s*(.+)', block, re.IGNORECASE)
        sev_match   = re.search(r'SEVERITY:\s*(HIGH|MEDIUM|LOW)', block, re.IGNORECASE)
        conf_match  = re.search(r'CONFIDENCE:\s*(0\.\d+|1\.0)', block, re.IGNORECASE)

        if issue_match and sev_match and conf_match:
            findings.append({
                "description": "ISSUE: " + issue_match.group(1).strip(),
                "severity":    sev_match.group(1).upper(),
                "confidence":  float(conf_match.group(1)),
                "agent":       agent_type
            })

    return findings


def calculate_was(findings_list: list) -> list:
    if not findings_list:
        return []

    results = []
    for finding in findings_list:
        severity   = finding.get("severity", "LOW")
        confidence = finding.get("confidence", 0.5)
        agent_type = finding.get("agent", "security")
        Si         = SEVERITY_WEIGHTS.get(severity, 0.3)
        was_score  = round(confidence, 2)

        results.append({
            "description": finding.get("description", "Unknown"),
            "severity":    severity,
            "confidence":  confidence,
            "agent":       agent_type,
            "WAS":         was_score
        })

    results.sort(key=lambda x: x["WAS"], reverse=True)
    return results


def filter_findings(was_results: list) -> list:
    return [f for f in was_results if f["WAS"] >= 0.6]


def calculate_reliability(consistent_runs: int, total_runs: int) -> float:
    if total_runs == 0:
        return 0.0
    return round((consistent_runs / total_runs) * 100, 2)


def print_report(was_results: list, reliability: float):
    print("\n" + "="*60)
    print("         LIFESAVER - FINAL REPORT")
    print("="*60)

    if not was_results:
        print("\n[OK] No issues found.")
    else:
        print(f"\nTotal Issues: {len(was_results)}\n")
        print("-"*60)

        for i, r in enumerate(was_results, 1):
            print(f"\n#{i} [{r['agent'].upper()}] {r['severity']}")
            print(f"  {r['description']}")
            print(f"  WAS: {r['WAS']} | Confidence: {r['confidence']}")
            if r["WAS"] >= 0.6:
                print(f"  >> Act on this immediately")

    print(f"\nReliability : {reliability}%")
    print(f"Status      : {'RELIABLE' if reliability >= 85 else 'NEEDS MORE RUNS'}")
    print("="*60 + "\n")