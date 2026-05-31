import json
import re

SEVERITY_WEIGHTS = {
    "CRITICAL": 1.0,
    "MODERATE": 0.6,
    "MINOR":    0.2,
}

SEVERITY_ALIASES = {
    "HIGH":   "CRITICAL",
    "MEDIUM": "MODERATE",
    "LOW":    "MINOR",
}


def _canon_severity(value) -> str:
    s = str(value or "").strip().upper()
    s = SEVERITY_ALIASES.get(s, s)
    return s if s in SEVERITY_WEIGHTS else "MODERATE"

AGENT_WEIGHTS = {
    "security":    0.5,
    "performance": 0.3,
    "logic":       0.2,
}

BANDIT_BONUS = 0.15

LABELS = "ISSUE|SEVERITY|CONFIDENCE|LINE|REASON"


def clean_output(text: str) -> str:
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.DOTALL | re.IGNORECASE)

    text = re.sub(r'<think(?:ing)?>.*$', '', text, flags=re.DOTALL | re.IGNORECASE)

    text = re.sub(r'^.*?</think(?:ing)?>', '', text, flags=re.DOTALL | re.IGNORECASE)

    text = re.sub(r'```[a-zA-Z]*', '', text)
    text = text.replace('```', '')
    return text.strip()


def parse_confidence(block: str, severity: str) -> float:
    m = re.search(r'CONFIDENCE:\s*([01]?\.\d+|[01](?:\.0+)?)', block, re.IGNORECASE)
    if m:
        try:
            return max(0.0, min(1.0, float(m.group(1))))
        except ValueError:
            pass

    m = re.search(r'CONFIDENCE:\s*(\d{1,3})\s*(?:%|percent)', block, re.IGNORECASE)
    if m:
        return max(0.0, min(1.0, int(m.group(1)) / 100.0))

    m = re.search(
        r'CONFIDENCE:\s*(CRITICAL|MODERATE|MINOR|HIGH|MEDIUM|LOW)',
        block, re.IGNORECASE,
    )
    if m:
        return SEVERITY_WEIGHTS.get(_canon_severity(m.group(1)), 0.6)

    m = re.search(r'CONFIDENCE:\s*(\d{1,3})\b', block, re.IGNORECASE)
    if m:
        v = int(m.group(1))
        return float(v) if v <= 1 else max(0.0, min(1.0, v / 100.0))

    return SEVERITY_WEIGHTS.get(severity.upper(), 0.6)


def normalize_labels(text: str) -> str:
    return re.sub(
        r'[*_`]{0,3}[ \t]*\n?[ \t]*(' + LABELS + r')\s*[*_`]{0,3}\s*:',
        lambda m: '\n' + m.group(1).upper() + ':',
        text,
        flags=re.IGNORECASE,
    )


def _normalize_severity(value) -> str:
    return _canon_severity(value)


def coerce_json_findings(text: str, agent_type: str) -> list:
    for opener, closer in (("{", "}"), ("[", "]")):
        i = text.find(opener)
        j = text.rfind(closer)
        if i == -1 or j == -1 or j <= i:
            continue
        try:
            data = json.loads(text[i:j + 1])
        except (ValueError, TypeError):
            continue

        items = None
        if isinstance(data, dict):
            if any(str(k).upper() == "ISSUE" for k in data):
                items = [data]
            else:
                items = next(
                    (v for v in data.values() if isinstance(v, list)), None
                )
        elif isinstance(data, list):
            items = data
        if not items:
            continue

        results = []
        for it in items:
            if not isinstance(it, dict):
                continue
            low = {str(k).lower(): v for k, v in it.items()}
            if "issue" not in low:
                continue
            severity = _normalize_severity(low.get("severity", "MEDIUM"))
            try:
                confidence = float(low.get("confidence"))
            except (TypeError, ValueError):
                confidence = SEVERITY_WEIGHTS.get(severity, 0.6)
            confidence = max(0.0, min(1.0, confidence))
            results.append({
                "description": str(low.get("issue", "")).strip(),
                "severity":    severity,
                "confidence":  confidence,
                "line":        str(low.get("line", "Unknown")),
                "reason":      str(low.get("reason", "No details")).strip(),
                "agent":       agent_type,
            })
        if results:
            return results
    return []


NEGATIVE_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in (
        r'\bnot present\b',
        r'\bis not used\b',
        r'\bare not used\b',
        r'\bno use of\b',
        r'\bnot vulnerable\b',
        r'\bnot applicable\b',
        r'\bno (?:security|performance|logic) '
        r'(?:issue|issues|vulnerab\w*|concern\w*|risk\w*|problem\w*)',
        r'\bno issues? (?:found|present|detected)\b',
    )
]

DOMAIN_KEYWORDS = {
    "security": (
        "sql injection", "command injection", "shell injection",
        "code injection", "injection", "hardcoded", "hard-coded",
        "password", "secret", "api token", "api key", "credential",
        "deserializ", "unserialize", "pickle", "path traversal", "xss",
        "csrf", "weak random", "insecure random", "unsafe", "rce",
        "remote code",
    ),
    "performance": (
        "o(n^2)", "o(n2)", "o(n²)", "quadratic", "nested loop",
        "time complexity", "string concatenation", "stringbuilder",
        "inefficient", "performance", "memoiz", "cache", "expensive",
        "data structure", "slow",
    ),
    "logic": (
        "division by zero", "divide by zero", "div by zero", "empty list",
        "empty array", "empty collection", "index out of",
        "indexoutofbound", "out of range", "null", "none", "undefined",
        "missing return", "off by one", "off-by-one", "edge case",
        "dereference",
    ),
}


def is_negative_finding(finding: dict) -> bool:
    blob = f"{finding.get('description', '')} {finding.get('reason', '')}"
    return any(p.search(blob) for p in NEGATIVE_PATTERNS)


def in_agent_lane(finding: dict, agent_type: str) -> bool:
    if agent_type not in DOMAIN_KEYWORDS:
        return True
    text = f"{finding.get('description', '')} {finding.get('reason', '')}".lower()
    domains = {
        d for d, kws in DOMAIN_KEYWORDS.items()
        if any(k in text for k in kws)
    }
    return (not domains) or (agent_type in domains)


def _dedupe_key(finding: dict) -> tuple:
    desc = finding.get("description", "").lower()
    desc = re.sub(r'\(\s*duplicate\s*\)', ' ', desc)
    desc = re.sub(r'[^a-z0-9]+', ' ', desc).strip()
    return (finding.get("agent", ""), str(finding.get("line", "")), desc)


def deduplicate_findings(findings: list) -> list:
    best, order = {}, []
    for f in findings:
        key = _dedupe_key(f)
        if key not in best:
            best[key] = f
            order.append(key)
        elif f.get("confidence", 0) > best[key].get("confidence", 0):
            best[key] = f
    return [best[k] for k in order]


_NO_LINE = {"", "unknown", "n/a", "none"}
_NO_REASON = {"", "no details"}


def is_actionable(finding: dict) -> bool:
    line = str(finding.get("line", "")).strip().lower()
    reason = str(finding.get("reason", "")).strip().lower()
    return not (line in _NO_LINE and reason in _NO_REASON)


def _postprocess(findings: list, agent_type: str) -> list:
    kept = [
        f for f in findings
        if is_actionable(f)
        and not is_negative_finding(f)
        and in_agent_lane(f, agent_type)
    ]
    return deduplicate_findings(kept)


def parse_findings(agent_output: str, agent_type: str) -> list:
    findings = []

    if not agent_output:
        return findings

    cleaned_text = clean_output(agent_output)

    json_findings = coerce_json_findings(cleaned_text, agent_type)
    if json_findings:
        return _postprocess(json_findings, agent_type)

    cleaned_text = normalize_labels(cleaned_text)

    blocks = re.findall(
        r'(ISSUE:.*?)(?=ISSUE:|$)',
        cleaned_text,
        flags=re.DOTALL | re.IGNORECASE
    )

    for block in blocks:
        if not block.strip():
            continue

        issue_match  = re.search(r'ISSUE:\s*(.+)', block, re.IGNORECASE)
        sev_match    = re.search(
            r'SEVERITY:\s*(CRITICAL|MODERATE|MINOR|HIGH|MEDIUM|LOW)',
            block, re.IGNORECASE,
        )
        line_match   = re.search(r'LINE:\s*(\d+)',  block, re.IGNORECASE)
        reason_match = re.search(r'REASON:\s*(.+)', block, re.IGNORECASE)

        if issue_match and sev_match:
            severity = _canon_severity(sev_match.group(1))
            findings.append({
                "description": issue_match.group(1).strip(),
                "severity":    severity,
                "confidence":  parse_confidence(block, severity),
                "line":        line_match.group(1) if line_match else "Unknown",
                "reason":      reason_match.group(1).strip() if reason_match else "No details",
                "agent":       agent_type
            })

    return _postprocess(findings, agent_type)


def calculate_was(findings_list: list) -> list:
    """Compute the Weighted Agreement Score per finding.

    Proposal formula:

        WAS(i) = sum( wa * Sa * Ca )  /  sum( wa )

    For a single-agent finding (the common case in this pipeline because
    findings are kept per-agent rather than merged across agents), the
    sum collapses to one term and wa cancels:

        WAS = Sa * Ca

    The +0.15 Bandit bonus is then added for findings from the Security
    agent (which integrates Bandit on Python code), and the result is
    clamped to [0, 1].
    """
    if not findings_list:
        return []

    results = []
    for finding in findings_list:
        severity   = str(finding.get("severity", "LOW")).upper()
        try:
            confidence = float(finding.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        agent_type = finding.get("agent", "security")

        Sa = SEVERITY_WEIGHTS.get(severity, 0.3)
        Ca = max(0.0, min(1.0, confidence))
        wa = AGENT_WEIGHTS.get(agent_type, 0.3)  # noqa: F841

        was_score = Sa * Ca
        if agent_type == "security":
            was_score += BANDIT_BONUS

        was_score = round(max(0.0, min(1.0, was_score)), 2)

        results.append({
            "description": finding.get("description", "Unknown"),
            "severity":    severity,
            "confidence":  confidence,
            "line":        finding.get("line", "Unknown"),
            "reason":      finding.get("reason", ""),
            "agent":       agent_type,
            "WAS":         was_score,
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
        print("\n[OK] No issues passed the WAS filter threshold.")
    else:
        print(f"\nTotal Issues: {len(was_results)}\n")
        print("-"*60)

        for i, r in enumerate(was_results, 1):
            print(f"\n#{i} [{r['agent'].upper()}] {r['severity']}")
            print(f"  ISSUE : {r['description']} (Line {r['line']})")
            print(f"  WAS   : {r['WAS']} | Confidence: {r['confidence']}")
            print(f"  REASON: {r['reason']}")

    print(f"\nReliability : {reliability}%")
    print(f"Status      : {'RELIABLE' if reliability >= 85 else 'NEEDS MORE RUNS'}")
    print("="*60 + "\n")
