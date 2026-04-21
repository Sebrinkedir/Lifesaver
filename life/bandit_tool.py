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
        "Returns structured JSON output with detected issues."
    )
    args_schema: type[BaseModel] = BanditInput

    def _run(self, code: str) -> str:

        # Step 1 - Write code to a temporary file
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
            encoding="utf-8"
        ) as temp_file:
            temp_file.write(code)
            temp_path = temp_file.name

        try:
            # Step 2 - Run Bandit
            result = subprocess.run(
                ["bandit", "-f", "json", "-q", temp_path],
                capture_output=True,
                text=True
            )

            output = result.stdout.strip()

            # If Bandit returns nothing, return empty JSON structure
            if not output:
                return json.dumps({"results": []})

            # Step 3 - Parse JSON safely
            try:
                data = json.loads(output)
            except json.JSONDecodeError:
                return json.dumps({"results": []})

            # Ensure "results" key exists
            if "results" not in data:
                data["results"] = []

            return json.dumps(data)

        except Exception as e:
            return json.dumps({
                "results": [],
                "error": str(e)
            })

        finally:
            # Step 4 - Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)


# Create reusable instance
bandit_scanner = BanditSecurityScanner()