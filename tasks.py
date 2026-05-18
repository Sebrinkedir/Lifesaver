from crewai import Task
from agents import security_agent, performance_agent, logic_agent


LANGUAGE_SIGNATURES = {
    "PHP":        ["<?php"],
    "C#":         ["namespace ", "using System"],
    "Java":       ["public class", "import java."],
    "Python":     ["def ", "import "],
    "Go":         ["func ", "package "],
    "Ruby":       ["def ", "end", "puts "],
    "C++":        ["#include", "std::"],
    "JavaScript": ["function ", "const ", "let ", "var ", "=>"],
}


def detect_language(code: str) -> str:
    code_lower = code.lower()
    if "<?php" in code_lower:
        return "PHP"
    scores = {}
    for lang, sigs in LANGUAGE_SIGNATURES.items():
        score = sum(1 for s in sigs if s.lower() in code_lower)
        if score > 0:
            scores[lang] = score
    return max(scores, key=scores.get) if scores else "Unknown"


def extract_functions(code: str, language: str) -> str:
    import re
    functions = []

    if language == "Python":
        matches = re.findall(r'def (\w+)\s*\(', code)
    elif language in ["JavaScript", "PHP"]:
        matches = re.findall(r'function (\w+)\s*\(', code)
    elif language == "Java":
        matches = re.findall(r'(?:public|private|protected|static)[\w\s]+\s+(\w+)\s*\(', code)
    elif language == "C#":
        matches = re.findall(r'(?:public|private|protected|static)[\w\s]+\s+(\w+)\s*\(', code)
    elif language == "Go":
        matches = re.findall(r'func (\w+)\s*\(', code)
    elif language == "Ruby":
        matches = re.findall(r'def (\w+)', code)
    elif language == "C++":
        matches = re.findall(r'(\w+)\s*\([^)]*\)\s*\{', code)
    else:
        matches = re.findall(r'(?:function|def|func)\s+(\w+)', code)

    functions = list(set(matches))
    if functions:
        return "Functions found: " + ", ".join(functions)
    return ""


def create_tasks(code: str):
    language  = detect_language(code)
    functions = extract_functions(code, language)

    bandit_step = (
        "Use BanditSecurityScanner tool first with the raw code. "
        "Then add your own findings Bandit may have missed."
        if language == "Python"
        else
        f"Bandit only works for Python. "
        f"Use your own expertise to find ALL security issues in this {language} code."
    )

    fmt = (
        "ISSUE: [clear description]\n"
        "SEVERITY: HIGH or MEDIUM or LOW\n"
        "CONFIDENCE: [0.0 to 1.0]\n"
        "LINE: [line number]\n"
        "REASON: [why this is a problem]\n"
    )

    security_task = Task(
        description=(
            f"You are a Senior Security Auditor.\n"
            f"Language: {language}\n"
            f"{functions}\n\n"
            f"{bandit_step}\n\n"
            f"Code:\n{code}\n\n"
            f"Find ALL of these security issues:\n"
            f"1. Hardcoded passwords, API keys, tokens, secrets in variables\n"
            f"2. SQL injection — queries built with string concatenation\n"
            f"3. Command injection — unsafe system/exec/shell calls\n"
            f"4. Unsafe deserialization — pickle, unserialize, ObjectInputStream\n"
            f"5. Shell injection — shell=True or shell_exec or system()\n"
            f"6. Weak random — Math.random or random module for security purposes\n"
            f"7. Path traversal — file open with unvalidated user input\n\n"
            f"Use this EXACT format for EVERY finding:\n"
            f"{fmt}\n"
            f"If no issues found: NO SECURITY ISSUES FOUND"
        ),
        expected_output=(
            "Each security finding in format:\n"
            "ISSUE / SEVERITY / CONFIDENCE / LINE / REASON\n"
            "Or: NO SECURITY ISSUES FOUND"
        ),
        agent=security_agent
    )

    performance_task = Task(
        description=(
            f"You are a Senior Performance Engineer.\n"
            f"Language: {language}\n"
            f"{functions}\n\n"
            f"IMPORTANT RULES:\n"
            f"- You find ONLY performance and efficiency problems\n"
            f"- You do NOT report security issues like SQL injection or hardcoded passwords\n"
            f"- You do NOT report logic errors\n"
            f"- If you see a security issue just ignore it\n\n"
            f"Code:\n{code}\n\n"
            f"Find ONLY these performance issues:\n"
            f"1. Nested loops O(n^2) or worse — always high severity\n"
            f"2. String concatenation inside loops — use join or StringBuilder\n"
            f"3. Inefficient data structure — list/array when set/map is O(1)\n"
            f"4. Repeated expensive computation not cached\n"
            f"5. Collection size called repeatedly inside loop condition\n"
            f"6. Unnecessary object creation inside loops\n\n"
            f"Use this EXACT format for EVERY finding:\n"
            f"{fmt}\n"
            f"If no issues found: NO PERFORMANCE ISSUES FOUND"
        ),
        expected_output=(
            "Each performance finding in format:\n"
            "ISSUE / SEVERITY / CONFIDENCE / LINE / REASON\n"
            "Or: NO PERFORMANCE ISSUES FOUND"
        ),
        agent=performance_agent
    )

    logic_task = Task(
        description=(
            f"You are a Senior Logic and Correctness Reviewer.\n"
            f"Language: {language}\n"
            f"{functions}\n\n"
            f"IMPORTANT RULES:\n"
            f"- You find ONLY logic errors and correctness bugs\n"
            f"- You do NOT report security issues like SQL injection or hardcoded passwords\n"
            f"- You do NOT report performance issues like slow loops\n"
            f"- If you see a security or performance issue just ignore it\n\n"
            f"Code:\n{code}\n\n"
            f"Find ONLY these logic issues:\n"
            f"1. Division by zero — any function dividing without checking denominator is zero\n"
            f"2. Empty collection crash — any function accessing index 0 without empty check\n"
            f"3. Missing return — function returns null/None/undefined for some code paths\n"
            f"4. Off by one error — wrong loop boundary or index\n"
            f"5. Null/None/undefined dereference — accessing property without null check\n"
            f"6. Incorrect condition — wrong comparison operator causing wrong behavior\n\n"
            f"Think step by step through EVERY function listed above.\n"
            f"For each function ask yourself:\n"
            f"- What happens if the input is empty or zero?\n"
            f"- Does this function always return a value?\n"
            f"- Can this crash with a specific input?\n\n"
            f"Use this EXACT format for EVERY finding:\n"
            f"{fmt}\n"
            f"If no issues found: NO LOGIC ISSUES FOUND"
        ),
        expected_output=(
            "Each logic finding in format:\n"
            "ISSUE / SEVERITY / CONFIDENCE / LINE / REASON\n"
            "Or: NO LOGIC ISSUES FOUND"
        ),
        agent=logic_agent
    )

    return [security_task, performance_task, logic_task]