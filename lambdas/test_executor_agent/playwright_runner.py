"""
Real browser test execution.

Planner (test case) -> Claude generates a Playwright script -> script runs in a
real headless browser -> trace is collected and uploaded to S3 -> pass/fail
result flows into Coverage & Risk for the deployment verdict.

This is the real-execution path. It is used whenever Playwright is installed
in the runtime; `handler._execute_test` falls back to LLM-simulated execution
(clearly tagged `execution_mode: "llm_simulated"` in the result) only when
Playwright is unavailable or the test case has no reachable target URL.
"""

from __future__ import annotations
import json
import os
import subprocess
import sys
import tempfile
import uuid

from aethertest.bedrock_client import invoke_claude
from aethertest.aws_clients import get_s3_client
from aethertest.config import ARTIFACTS_BUCKET
from aethertest.observability import log_event, retry_call

PLAYWRIGHT_SYSTEM_PROMPT = """You are a senior QA automation engineer.
Given a test case (Given/When/Then or a step list) and a target base URL, write a single
self-contained Python script using `playwright.sync_api` that:

- Launches Chromium headless
- Creates a browsing context with tracing enabled (context.tracing.start(screenshots=True, snapshots=True, sources=True))
- Navigates to the base URL and executes the described steps
- Asserts the expected result described in the test case
- Always stops tracing and saves it to the path in the TRACE_PATH environment variable
  (context.tracing.stop(path=os.environ["TRACE_PATH"])), even if an assertion fails
- Exits with code 0 if every assertion passed, exit code 1 otherwise
- Prints exactly one final stdout line: "RESULT: PASSED" or "RESULT: FAILED: <short reason>"

Return ONLY the Python script — no markdown fences, no commentary, no explanation."""


def is_playwright_available() -> bool:
    try:
        import playwright.sync_api  # noqa: F401
        return True
    except ImportError:
        return False


def generate_script(test_case: dict, base_url: str) -> str:
    """Planner step: ask Claude to turn a test case into an executable Playwright script."""
    prompt = f"""Base URL: {base_url}

Test case:
{json.dumps(test_case, indent=2)}"""

    script = retry_call(
        invoke_claude,
        prompt,
        system_prompt=PLAYWRIGHT_SYSTEM_PROMPT,
        max_tokens=2048,
        temperature=0.0,
    ).strip()

    if "```" in script:
        parts = script.split("```")
        script = parts[1] if len(parts) > 1 else script
        if script.startswith("python"):
            script = script[len("python"):]
    return script.strip()


def run_script(script: str, test_id: str, timeout_seconds: int = 60) -> dict:
    """Run a generated Playwright script as a subprocess and collect its trace."""
    with tempfile.TemporaryDirectory() as tmp:
        script_path = os.path.join(tmp, f"test_{test_id}.py")
        trace_path = os.path.join(tmp, f"trace_{test_id}.zip")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script)

        env = {**os.environ, "TRACE_PATH": trace_path}
        try:
            proc = subprocess.run(
                [sys.executable, script_path],
                capture_output=True, text=True, timeout=timeout_seconds, env=env,
            )
            stdout, stderr, returncode = proc.stdout, proc.stderr, proc.returncode
        except subprocess.TimeoutExpired as e:
            stdout = (e.stdout or "") if isinstance(e.stdout, str) else ""
            stderr = (e.stderr or "") if isinstance(e.stderr, str) else ""
            return {
                "status": "failed",
                "failure_reason": f"Playwright script timed out after {timeout_seconds}s",
                "stdout": stdout,
                "stderr": stderr,
                "trace_s3_key": None,
            }

        passed = returncode == 0 and "RESULT: PASSED" in stdout
        failure_reason = None
        if not passed:
            for line in stdout.splitlines():
                if line.startswith("RESULT: FAILED"):
                    failure_reason = line.split(":", 2)[-1].strip()
            if failure_reason is None:
                failure_reason = (stderr or "Playwright script exited non-zero without a RESULT line")[-500:]

        trace_s3_key = None
        if os.path.exists(trace_path):
            trace_s3_key = f"traces/{test_id}/{uuid.uuid4().hex[:8]}.zip"
            try:
                retry_call(get_s3_client().upload_file, trace_path, ARTIFACTS_BUCKET, trace_s3_key)
            except Exception as e:
                log_event("WARNING", "trace_upload_failed", test_id=test_id, error=str(e))
                trace_s3_key = None

        return {
            "status": "passed" if passed else "failed",
            "failure_reason": failure_reason,
            "stdout": stdout[-2000:],
            "stderr": stderr[-2000:],
            "trace_s3_key": trace_s3_key,
        }


def execute_real(test_case: dict, base_url: str, timeout_seconds: int = 60) -> dict | None:
    """
    Full real-execution pipeline: Planner -> Generate Playwright -> Run Playwright
    -> Collect trace. Returns None if Playwright isn't installed in this runtime
    so the caller can fall back to LLM-simulated execution.
    """
    if not is_playwright_available():
        return None

    test_id = test_case.get("test_id", str(uuid.uuid4()))
    try:
        script = generate_script(test_case, base_url)
        run_result = run_script(script, test_id, timeout_seconds=timeout_seconds)
    except Exception as e:
        log_event("ERROR", "playwright_execution_pipeline_failed", test_id=test_id, error=str(e))
        return None

    return {
        "test_id": test_id,
        "test_name": test_case.get("test_name", ""),
        "component": test_case.get("component", test_case.get("component_id", "")),
        "status": run_result["status"],
        "duration_ms": None,
        "execution_steps": [],
        "actual_result": run_result["stdout"],
        "failure_reason": run_result.get("failure_reason"),
        "failure_type": "genuine_defect" if run_result["status"] == "failed" else None,
        "self_healed": False,
        "self_heal_detail": None,
        "evidence": {
            "stdout": run_result["stdout"],
            "stderr": run_result["stderr"],
            "trace_s3_key": run_result.get("trace_s3_key"),
        },
        "assertions": [],
        "execution_mode": "playwright_real",
    }
