import subprocess
import tempfile
import json
import os
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class BanditInput(BaseModel):
    code: str = Field(description="Python code to scan for security issues")


class BanditSecurityScanner(BaseTool):
    name: str = "BanditSecurityScanner"
    description: str = (
        "Scans Python code for security vulnerabilities using Bandit. "
        "Checks for dangerous patterns, hardcoded passwords, "
        "unsafe imports, and injection risks. "
        "Input: Python code as a string. "
        "Output: A summary of security issues found."
    )
    args_schema: type[BaseModel] = BanditInput

    def _run(self, code: str) -> str:

        code = code.replace("\\n", "\n")
        code = code.replace("\\t", "\t")
        code = code.replace('\\"', '"')
        code = code.strip()

        if not code:
            return "No code provided to scan."

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
            encoding="utf-8"
        ) as temp_file:
            temp_file.write(code)
            temp_path = temp_file.name

        try:
            result = subprocess.run(
                ["bandit", "-f", "json", "-q", temp_path],
                capture_output=True,
                text=True
            )

            output = result.stdout.strip()

            if not output:
                return "Bandit found no security issues in the code."

            data = json.loads(output)
            issues = data.get("results", [])

            if not issues:
                return "Bandit found no security issues in the code."

            findings = []
            for issue in issues:
                finding = (
                    f"- Issue: {issue.get('issue_text', 'Unknown')}\n"
                    f"  Severity: {issue.get('issue_severity', 'Unknown')}\n"
                    f"  Confidence: {issue.get('issue_confidence', 'Unknown')}\n"
                    f"  Line: {issue.get('line_number', 'Unknown')}\n"
                    f"  Test ID: {issue.get('test_id', 'Unknown')}"
                )
                findings.append(finding)

            summary = f"Bandit found {len(issues)} security issue(s):\n\n"
            summary += "\n\n".join(findings)
            return summary

        except json.JSONDecodeError:
            return "Bandit scan completed but output could not be parsed."

        except Exception as e:
            return f"Bandit scan failed with error: {str(e)}"

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


bandit_scanner = BanditSecurityScanner()
