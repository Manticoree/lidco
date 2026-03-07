"""Minimal reproduction generator — creates a standalone reproducer for a failing test."""
from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult


class ReproGeneratorTool(BaseTool):
    """Generate a minimal standalone pytest file that reproduces a test failure."""

    def __init__(self) -> None:
        self._llm: Any = None

    def set_llm(self, llm: Any) -> None:
        """Inject the LLM instance used for generating the repro."""
        self._llm = llm

    @property
    def name(self) -> str:
        return "generate_minimal_repro"

    @property
    def description(self) -> str:
        return "Generate a minimal standalone pytest file that reproduces a test failure."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="failing_test",
                type="string",
                description="test_file.py::test_name format",
                required=True,
            ),
            ToolParameter(
                name="output_path",
                type="string",
                description="Path to write the minimal repro file.",
                required=False,
                default=".lidco/minimal_repro.py",
            ),
        ]

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.ASK

    async def _run(self, **kwargs: Any) -> ToolResult:
        failing_test: str = kwargs["failing_test"]
        output_path: str = kwargs.get("output_path", ".lidco/minimal_repro.py")

        # Split test id into file path and test name
        parts = failing_test.split("::")
        test_file_path = parts[0]
        test_name = parts[1] if len(parts) > 1 else ""

        # Read the failing test file
        test_content = await self._read_test_file(test_file_path)
        if test_content is None:
            return ToolResult(
                output=f"Error: Could not read test file '{test_file_path}'",
                success=False,
                error=f"Test file not found: {test_file_path}",
                metadata={"output_path": output_path},
            )

        # Run the failing test to capture failure output
        failure_output = await self._capture_failure(failing_test)

        # Generate the repro content
        if self._llm is not None:
            repro_content = await self._generate_repro_via_llm(
                test_content, failure_output, failing_test
            )
        else:
            repro_content = self._generate_repro_template(
                test_content, test_name, test_file_path, failure_output
            )

        # Ensure output directory exists
        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(repro_content, encoding="utf-8")

        # Verify the repro by running it
        verification_status = await self._verify_repro(output_path)

        output_lines = [
            f"Minimal repro written to: {output_path}",
            f"Repro verification: {verification_status}",
        ]

        return ToolResult(
            output="\n".join(output_lines),
            success=True,
            metadata={"output_path": output_path},
        )

    async def _read_test_file(self, test_file_path: str) -> str | None:
        """Read the test file content, returning None if unreadable."""
        try:
            path = Path(test_file_path)
            if not path.exists():
                return None
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

    async def _capture_failure(self, failing_test: str) -> str:
        """Run the failing test and capture its output."""
        cmd = ["python", "-m", "pytest", failing_test, "--tb=long", "-x", "-q"]
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)
            output = stdout.decode("utf-8", errors="replace")
            err_output = stderr.decode("utf-8", errors="replace")
            return output + (f"\n[stderr]\n{err_output}" if err_output.strip() else "")
        except (asyncio.TimeoutError, FileNotFoundError, OSError):
            return "(could not capture failure output)"

    async def _generate_repro_via_llm(
        self,
        test_content: str,
        failure_output: str,
        failing_test: str,
    ) -> str:
        """Use the injected LLM to generate a minimal repro."""
        prompt = (
            f"Given this failing test:\n\n```python\n{test_content[:3000]}\n```\n\n"
            f"And this failure output:\n\n```\n{failure_output[:2000]}\n```\n\n"
            f"Generate a minimal standalone pytest file that reproduces the failure "
            f"for: {failing_test}\n\n"
            "Requirements:\n"
            "1. The file must be runnable standalone with `pytest`\n"
            "2. Include only the minimal imports needed\n"
            "3. Include only the specific failing test function\n"
            "4. Add any fixtures inline if needed\n"
            "5. Do NOT include any other tests\n\n"
            "Return ONLY the Python code, no explanation."
        )
        try:
            response = await self._llm.agenerate([prompt])
            return response.generations[0][0].text
        except Exception:
            # Fall back to template if LLM call fails
            parts = failing_test.split("::")
            test_name = parts[1] if len(parts) > 1 else ""
            return self._generate_repro_template(
                test_content, test_name, parts[0], failure_output
            )

    def _generate_repro_template(
        self,
        test_content: str,
        test_name: str,
        test_file_path: str,
        failure_output: str,
    ) -> str:
        """Extract the failing test function and write a minimal template."""
        extracted = self._extract_test_function(test_content, test_name)
        lines = [
            "\"\"\"Minimal reproduction generated by lidco ReproGeneratorTool.",
            f"Original test: {test_file_path}::{test_name}",
            f"Failure summary:",
        ]
        # Include first 10 lines of failure output as a comment
        for failure_line in failure_output.splitlines()[:10]:
            lines.append(f"  {failure_line}")
        lines.append('"""')
        lines.append("from __future__ import annotations")
        lines.append("")
        lines.append("import pytest")
        lines.append("")
        lines.append("")
        lines.append(extracted)
        return "\n".join(lines)

    def _extract_test_function(self, test_content: str, test_name: str) -> str:
        """Extract a single test function from the file content by name."""
        if not test_name:
            return test_content

        lines = test_content.splitlines()
        start_idx: int | None = None
        for i, line in enumerate(lines):
            stripped = line.strip()
            if re.match(rf"^(async\s+)?def\s+{re.escape(test_name)}\s*[\(:]", stripped):
                start_idx = i
                break

        if start_idx is None:
            # Could not locate the function; return a stub
            return f"def {test_name}():\n    pass  # could not extract from source\n"

        # Collect lines until we hit another top-level definition or EOF
        result_lines = [lines[start_idx]]
        for line in lines[start_idx + 1:]:
            # Stop at the next top-level function/class definition (unindented)
            if line and not line[0].isspace() and re.match(r"^(def |class |async def )", line):
                break
            result_lines.append(line)

        return "\n".join(result_lines)

    async def _verify_repro(self, output_path: str) -> str:
        """Run the generated repro file and return a status string."""
        cmd = ["python", "-m", "pytest", output_path, "-x", "-q"]
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _stdout, _stderr = await asyncio.wait_for(process.communicate(), timeout=60)
            # A non-zero exit code means tests failed, which is what we want
            if process.returncode != 0:
                return "FAILS ✓"
            return "PASSES (repro may be incomplete)"
        except (asyncio.TimeoutError, FileNotFoundError, OSError):
            return "UNKNOWN (could not verify)"
