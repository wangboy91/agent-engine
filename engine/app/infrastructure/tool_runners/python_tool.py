"""Python tool runner primitives."""

import asyncio
import json
import os
import sys

from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate

from app.domain.errors import AgentEngineError
from app.domain.tool import Tool, ToolExecutionContext, ToolExecutionResult


class ToolExecutionError(AgentEngineError):
    """Raised when a Tool cannot be executed successfully."""


class PythonToolRunner:
    async def execute(
        self,
        tool: Tool,
        arguments: dict[str, object],
        context: ToolExecutionContext,
    ) -> ToolExecutionResult:
        self._validate_input(tool, arguments)
        if tool.entry is None:
            raise ToolExecutionError("PYTHON_TOOL_FAILED", f"Tool {tool.id} has no entry")
        if tool.package_path is None:
            raise ToolExecutionError("PYTHON_TOOL_FAILED", f"Tool {tool.id} has no package_path")

        tool_dir = tool.package_path.resolve()
        entry_path = (tool_dir / tool.entry).resolve()
        if not entry_path.exists():
            raise ToolExecutionError("PYTHON_TOOL_FAILED", f"Python entry not found: {entry_path}")

        artifact_dir = context.artifact_dir.resolve()
        artifact_dir.mkdir(parents=True, exist_ok=True)
        env = {
            **os.environ,
            "AGENT_RUN_ID": context.run_id,
            "AGENT_TOOL_CALL_ID": context.tool_call_id,
            "AGENT_ARTIFACT_DIR": str(artifact_dir),
        }

        process = await asyncio.create_subprocess_exec(
            sys.executable,
            str(entry_path),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=tool_dir,
            env=env,
        )

        payload = json.dumps(arguments, ensure_ascii=False).encode("utf-8")
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(payload),
                timeout=tool.runtime.timeout_seconds,
            )
        except TimeoutError as exc:
            process.kill()
            await process.wait()
            raise ToolExecutionError(
                "PYTHON_TOOL_TIMEOUT",
                f"Python tool {tool.id} timed out after {tool.runtime.timeout_seconds}s",
            ) from exc

        stderr_text = stderr.decode("utf-8", errors="replace")
        stdout_text = stdout.decode("utf-8", errors="replace").strip()

        if process.returncode != 0:
            raise ToolExecutionError(
                "PYTHON_TOOL_FAILED",
                f"Python tool {tool.id} exited with code {process.returncode}",
                {"stderr": stderr_text},
            )

        try:
            output = json.loads(stdout_text)
        except json.JSONDecodeError as exc:
            raise ToolExecutionError(
                "PYTHON_TOOL_FAILED",
                f"Python tool {tool.id} did not return JSON on stdout",
                {"stdout": stdout_text, "stderr": stderr_text},
            ) from exc

        if not isinstance(output, dict):
            raise ToolExecutionError("TOOL_OUTPUT_SCHEMA_INVALID", "Tool output must be an object")

        self._validate_output(tool, output)
        return ToolExecutionResult(output=output, stderr=stderr_text)

    def _validate_input(self, tool: Tool, arguments: dict[str, object]) -> None:
        try:
            validate(instance=arguments, schema=tool.input_schema)
        except JsonSchemaValidationError as exc:
            raise ToolExecutionError(
                "TOOL_INPUT_SCHEMA_INVALID",
                f"Invalid input for tool {tool.id}: {exc.message}",
            ) from exc

    def _validate_output(self, tool: Tool, output: dict[str, object]) -> None:
        try:
            validate(instance=output, schema=tool.output_schema)
        except JsonSchemaValidationError as exc:
            raise ToolExecutionError(
                "TOOL_OUTPUT_SCHEMA_INVALID",
                f"Invalid output from tool {tool.id}: {exc.message}",
            ) from exc
