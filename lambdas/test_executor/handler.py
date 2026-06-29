"""
Test Executor Lambda
Simulates executing test cases against the AUT and reporting results.
In production this would invoke real browser/API test runners.
Uses Claude to simulate intelligent test execution and result analysis.
"""

from __future__ import annotations
import os
import json
import uuid
import random
import boto3
from datetime import datetime, timezone

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../layers"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

s3 = boto3.client("s3", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"), verify=not os.environ.get("AETHERTEST_NO_SSL_VERIFY", ""), endpoint_url=os.environ.get("S3_ENDPOINT_URL", "https://s3.us-east-1.amazonaws.com"))
dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"), verify=not os.environ.get("AETHERTEST_NO_SSL_VERIFY", ""))

BUCKET_NAME = os.environ.get("AETHERTEST_BUCKET", "aethertest-artifacts-654654478821")
ASSIGNMENTS_TABLE = os.environ.get("ASSIGNMENTS_TABLE", "aethertest-agent-assignments")
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")

EXECUTION_SYSTEM_PROMPT = """You are a test execution simulator for the AetherTest platform.
Given a test case, simulate its execution and return a realistic result.

For each test case, return a JSON object:
{
  "test_id": "same as input",
  "status": "passed|failed|skipped",
  "duration_ms": <number>,
  "actual_result": "what actually happened",
  "failure_reason": "only if failed - specific error message",
  "failure_type": "only if failed - genuine_defect|env_noise|aut_change",
  "evidence": {
    "screenshot_url": "s3://... (if UI test)",
    "response_body": "... (if API test)",
    "error_log": "... (if failed)"
  },
  "assertions": [
    {"assertion": "status code is 200", "result": "passed|failed"}
  ]
}

Make results realistic - most tests should pass, but occasionally fail with meaningful errors."""


def handler(event: dict, context) -> dict:
    """
    Lambda handler for test execution.

    Expected event:
    {
        "tenant_id": "string",
        "execution_id": "string",
        "test_suite": { ... },
        "simulate_failures": ["component_name"]  # optional: force failures for demo
    }
    """
    tenant_id = event.get("tenant_id", "")
    execution_id = event.get("execution_id", str(uuid.uuid4()))
    test_suite = event.get("test_suite", {})
    simulate_failures = event.get("simulate_failures", [])

    test_cases = test_suite.get("test_cases", [])
    results = []
    passed = 0
    failed = 0
    skipped = 0

    print(f"\n[EXECUTOR] Running {len(test_cases)} test cases...")

    for i, test_case in enumerate(test_cases):
        print(f"  [{i+1}/{len(test_cases)}] {test_case.get('test_name', 'Unknown test')}...")

        # Execute test case using Claude
        result = _execute_test_case(
            test_case=test_case,
            force_fail=test_case.get("component_id") in simulate_failures,
        )

        results.append(result)

        if result["status"] == "passed":
            passed += 1
            print(f"    ✓ PASSED ({result['duration_ms']}ms)")
        elif result["status"] == "failed":
            failed += 1
            print(f"    ✗ FAILED: {result.get('failure_reason', 'Unknown error')}")
        else:
            skipped += 1
            print(f"    ⊘ SKIPPED")

    # Save execution results to S3
    results_key = f"{tenant_id}/test-results/{execution_id}/results.json"
    execution_report = {
        "execution_id": execution_id,
        "tenant_id": tenant_id,
        "test_suite_id": test_suite.get("test_suite_id"),
        "strategy_id": test_suite.get("strategy_id"),
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total": len(test_cases),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "pass_rate": round(passed / len(test_cases) * 100, 1) if test_cases else 0,
        },
        "results": results,
        "failed_tests": [r for r in results if r["status"] == "failed"],
    }

    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=results_key,
        Body=json.dumps(execution_report, indent=2),
        ContentType="application/json",
    )

    # Save to DynamoDB
    table = dynamodb.Table(ASSIGNMENTS_TABLE)
    table.put_item(Item={
        "PK": f"EXECUTION#{execution_id}",
        "SK": f"RESULTS#SUMMARY",
        "total": len(test_cases),
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "results_s3_key": results_key,
        "executed_at": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "statusCode": 200,
        "execution_id": execution_id,
        "summary": execution_report["summary"],
        "results_s3_key": results_key,
        "failed_tests": execution_report["failed_tests"],
        "execution_report": execution_report,
    }


def _execute_test_case(test_case: dict, force_fail: bool = False) -> dict:
    """Use Claude to simulate test execution."""
    try:
        bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"), verify=not os.environ.get("AETHERTEST_NO_SSL_VERIFY", ""))

        force_instruction = ""
        if force_fail:
            force_instruction = "\nIMPORTANT: This test MUST fail with a genuine_defect. Simulate a realistic bug."

        prompt = f"""Execute this test case and return the result:{force_instruction}

{json.dumps(test_case, indent=2)}

Return ONLY a valid JSON object with the execution result."""

        response = bedrock.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "temperature": 0.5,
                "system": EXECUTION_SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": prompt}],
            }),
            contentType="application/json",
            accept="application/json",
        )
        result = json.loads(response["body"].read())
        raw_text = result["content"][0]["text"].strip()

        # Extract JSON
        if "```" in raw_text:
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        raw_text = raw_text.strip()

        execution_result = json.loads(raw_text)
        execution_result["test_id"] = test_case.get("test_id", str(uuid.uuid4()))
        execution_result["test_name"] = test_case.get("test_name", "")
        execution_result["component"] = test_case.get("component", "")
        return execution_result

    except Exception as e:
        # Fallback result
        status = "failed" if force_fail else "passed"
        return {
            "test_id": test_case.get("test_id", str(uuid.uuid4())),
            "test_name": test_case.get("test_name", ""),
            "component": test_case.get("component", ""),
            "status": status,
            "duration_ms": random.randint(100, 2000),
            "actual_result": "Test executed via fallback" if not force_fail else "Simulated failure",
            "failure_reason": "Simulated defect for demo" if force_fail else None,
            "failure_type": "genuine_defect" if force_fail else None,
            "evidence": {},
            "assertions": [],
        }
