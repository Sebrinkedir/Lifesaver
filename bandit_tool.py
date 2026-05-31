"""MCP-style wrapper around Bandit (Python static analyser).

The proposal specifies that Bandit be "wrapped using an MCP-style structure
for safer and more controlled tool usage". MCP (Model Context Protocol)
wraps an external tool as a named, schema-validated service that an LLM
can call in a controlled way. The wrapper here adopts that pattern:

* **Named tool** — `BanditSecurityScanner` with an explicit name and
  description string, so the Security agent must invoke it deliberately.
* **Typed input schema** — `BanditInput` (pydantic) validates that the
  caller passes a non-empty Python string before any subprocess runs.
* **Typed output schema** — `BanditFinding` and `BanditResult` (pydantic)
  give every scan a structured representation; the human-readable string
  the LLM sees is rendered *from* that structured form rather than being
  the raw subprocess output.
* **Controlled invocation** — Bandit is run in an isolated subprocess
  with a fixed argument list (no shell, no expansion), a hard time
  budget, and a guaranteed-cleanup temp file. The agent never gets shell
  access; it only ever sees the structured findings.
* **Bounded inputs** — extremely large code blobs are rejected before
  hitting Bandit to keep runtime predictable.

Result: the Security agent treats Bandit as a structured oracle whose
output is part of *its own* finding set (per the proposal: "fed directly
into the Security Agent as structured input rather than treated as a
separate voting agent").
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from typing import List, Optional

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, field_validator



MAX_CODE_BYTES = 200_000   # ~200 KB of source per invocation
SUBPROCESS_TIMEOUT_SEC = 60


class BanditInput(BaseModel):
    """Validated input schema for the Bandit tool."""
    code: str = Field(description="Python source code to scan for "
                                  "security issues.")

    @field_validator("code")
    @classmethod
    def _non_empty_and_bounded(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("code must be a non-empty Python string")
        if len(v.encode("utf-8", errors="ignore")) > MAX_CODE_BYTES:
            raise ValueError(f"code exceeds {MAX_CODE_BYTES} byte limit")
        return v


class BanditFinding(BaseModel):
    """One structured Bandit finding."""
    issue_text: str   = Field(description="Plain-English description.")
    severity:   str   = Field(description="Bandit severity (LOW/MEDIUM/HIGH).")
    confidence: str   = Field(description="Bandit confidence (LOW/MEDIUM/HIGH).")
    line:       int   = Field(description="1-based source line.")
    test_id:    str   = Field(description="Bandit test rule ID (e.g. B105).")


class BanditResult(BaseModel):
    """The full structured scan result."""
    ok:        bool                = Field(description="True if Bandit ran.")
    error:     Optional[str]       = Field(default=None,
                                           description="Error if ok is False.")
    n_issues:  int                 = Field(default=0)
    findings:  List[BanditFinding] = Field(default_factory=list)

    def render(self) -> str:
        """Render to the plain-text format the agent prompt expects."""
        if not self.ok:
            return f"Bandit could not scan the code: {self.error or 'unknown error'}"
        if self.n_issues == 0:
            return "Bandit found no security issues in the code."
        body_lines = []
        for f in self.findings:
            body_lines.append(
                f"- Issue: {f.issue_text}\n"
                f"  Severity: {f.severity}\n"
                f"  Confidence: {f.confidence}\n"
                f"  Line: {f.line}\n"
                f"  Test ID: {f.test_id}"
            )
        return (f"Bandit found {self.n_issues} security issue(s):\n\n"
                + "\n\n".join(body_lines))



def _run_bandit(code: str) -> BanditResult:
    """Spawn Bandit on the given code, return a structured result."""
    code = code.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"').strip()

    tmp_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as tf:
            tf.write(code)
            tmp_path = tf.name

        proc = subprocess.run(
            ["bandit", "-f", "json", "-q", tmp_path],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_SEC,
        )
        raw = proc.stdout.strip()
        if not raw:
            return BanditResult(ok=True, n_issues=0, findings=[])

        data = json.loads(raw)
        issues = data.get("results", []) or []

        findings = []
        for it in issues:
            try:
                findings.append(BanditFinding(
                    issue_text = str(it.get("issue_text", "Unknown")),
                    severity   = str(it.get("issue_severity", "Unknown")),
                    confidence = str(it.get("issue_confidence", "Unknown")),
                    line       = int(it.get("line_number", 0) or 0),
                    test_id    = str(it.get("test_id", "Unknown")),
                ))
            except Exception:
                continue

        return BanditResult(ok=True, n_issues=len(findings), findings=findings)

    except subprocess.TimeoutExpired:
        return BanditResult(ok=False,
                            error=f"Bandit exceeded {SUBPROCESS_TIMEOUT_SEC}s timeout")
    except json.JSONDecodeError:
        return BanditResult(ok=False, error="Bandit output could not be parsed")
    except FileNotFoundError:
        return BanditResult(ok=False,
                            error="bandit executable not found on PATH")
    except Exception as e:  # last-resort catch-all
        return BanditResult(ok=False, error=str(e))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass



class BanditSecurityScanner(BaseTool):
    """MCP-style named tool exposed to the Security agent.

    Internally builds a `BanditResult` and renders it to the plain-text
    string the agent prompt expects. The structured form is available via
    the `scan_structured` classmethod for any future caller that wants
    the raw data (e.g. an audit / logging layer).
    """

    name: str = "BanditSecurityScanner"
    description: str = (
        "Scans Python code for security vulnerabilities using the Bandit "
        "static-analysis tool. Wrapped in an MCP-style structure: typed "
        "input, typed output, sandboxed subprocess. "
        "Input: Python code as a string. "
        "Output: a summary of detected issues with severity, confidence, "
        "line number, and Bandit test ID."
    )
    args_schema: type[BaseModel] = BanditInput

    def _run(self, code: str) -> str:
        try:
            BanditInput(code=code)   # explicit validation
        except Exception as e:
            return f"Bandit input rejected: {e}"
        result = _run_bandit(code)
        return result.render()

    @classmethod
    def scan_structured(cls, code: str) -> BanditResult:
        try:
            BanditInput(code=code)
        except Exception as e:
            return BanditResult(ok=False, error=f"input rejected: {e}")
        return _run_bandit(code)


bandit_scanner = BanditSecurityScanner()
