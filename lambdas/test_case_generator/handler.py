"""
Test Case Generator Lambda
Uses Claude Sonnet 4 to generate actual executable test cases
for each component in the Test Strategy.
"""

from __future__ import annotations
import os
import json
import uuid
import boto3
from datetime import datetime, timezone

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../layers"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from serializer.models import TestStrategy, Priority
from aethertest.config import (
    ARTIFACTS_BUCKET as BUCKET_NAME,
    STRATEGIES_TABLE,
    BEDROCK_MODEL_ID as MODEL_ID,
)
from aethertest.observability import instrument_handler

s3 = boto3.client("s3", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"), verify=not os.environ.get("AETHERTEST_NO_SSL_VERIFY", ""), endpoint_url=os.environ.get("S3_ENDPOINT_URL", "https://s3.us-east-1.amazonaws.com"))
dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"), verify=not os.environ.get("AETHERTEST_NO_SSL_VERIFY", ""))

SYSTEM_PROMPT = """You are an expert QA engineer specializing in generating comprehensive test cases.
For each component provided, generate specific, executable test cases covering:
- Happy path (valid inputs, expected success)
- Edge cases (boundary values, empty inputs)
- Error cases (invalid inputs, missing fields, unauthorized access)
- Integration scenarios (how this component interacts with dependencies)

Return ONLY a valid JSON array of test cases. Each test case must have:
{
  "test_id": "unique string",
  "test_name": "descriptive name",
  "component": "component name",
  "test_type": "api|ui|integration",
  "priority": "high|medium|low",
  "description": "what this test verifies",
  "preconditions": ["list of setup steps"],
  "steps": ["step 1", "step 2", ...],
  "expected_result": "what should happen",
  "test_data": {"key": "value"},
  "tags": ["smoke", "regression", "security"]
}"""


@instrument_handler("test_case_generator")
def handler(event: dict, context) -> dict:
    """
    Lambda handler for test case generation.

    Expected event:
    {
        "tenant_id": "string",
        "strategy": { TestStrategy JSON },
        "aut_graph": { AUTComponentGraph JSON }
    }
    """
    tenant_id = event.get("tenant_id", "")
    strategy_data = event.get("strategy", {})
    aut_graph = event.get("aut_graph", {})

    strategy = TestStrategy.model_validate(strategy_data)
    components_map = {
        c["component_id"]: c
        for c in aut_graph.get("components", [])
    }

    all_test_cases = []
    generation_summary = []

    # Generate test cases per component grouped by priority
    high_priority = [c for c in strategy.coverage if c.priority == Priority.HIGH]
    medium_priority = [c for c in strategy.coverage if c.priority == Priority.MEDIUM]
    low_priority = [c for c in strategy.coverage if c.priority == Priority.LOW]

    for priority_group, label in [
        (high_priority, "HIGH"),
        (medium_priority, "MEDIUM"),
        (low_priority, "LOW"),
    ]:
        for coverage in priority_group:
            component = components_map.get(coverage.component_id, {})
            component_name = component.get("name", coverage.component_id[:8])
            component_type = component.get("component_type", "service")
            api_surface = component.get("api_surface", [])
            ui_entry_points = component.get("ui_entry_points", [])
            dependencies = component.get("dependencies", [])

            # Generate test cases using Claude
            test_cases = _generate_test_cases_with_claude(
                component_name=component_name,
                component_type=component_type,
                api_surface=api_surface,
                ui_entry_points=ui_entry_points,
                dependencies=dependencies,
                priority=label,
                agent_types=coverage.assigned_agent_types,
                coverage_target=coverage.coverage_target.value,
            )

            all_test_cases.extend(test_cases)
            generation_summary.append({
                "component": component_name,
                "priority": label,
                "test_cases_generated": len(test_cases),
            })

    # Save all test cases to S3
    test_suite_id = str(uuid.uuid4())
    s3_key = f"{tenant_id}/test-cases/{strategy.strategy_id}/{test_suite_id}.json"

    test_suite = {
        "test_suite_id": test_suite_id,
        "strategy_id": strategy.strategy_id,
        "tenant_id": tenant_id,
        "aut_id": strategy.aut_id,
        "aut_version": strategy.aut_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_test_cases": len(all_test_cases),
        "test_cases": all_test_cases,
        "generation_summary": generation_summary,
    }

    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=s3_key,
        Body=json.dumps(test_suite, indent=2),
        ContentType="application/json",
    )

    # Record in DynamoDB
    table = dynamodb.Table(STRATEGIES_TABLE)
    table.put_item(Item={
        "PK": f"TENANT#{tenant_id}",
        "SK": f"TEST_SUITE#{test_suite_id}",
        "test_suite_id": test_suite_id,
        "strategy_id": strategy.strategy_id,
        "total_test_cases": len(all_test_cases),
        "s3_key": s3_key,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "statusCode": 200,
        "test_suite_id": test_suite_id,
        "total_test_cases": len(all_test_cases),
        "s3_key": s3_key,
        "generation_summary": generation_summary,
        "test_suite": test_suite,
    }


def _generate_test_cases_with_claude(
    component_name: str,
    component_type: str,
    api_surface: list,
    ui_entry_points: list,
    dependencies: list,
    priority: str,
    agent_types: list,
    coverage_target: str,
) -> list[dict]:
    """Use Claude Sonnet 4 to generate test cases for a component."""

    prompt = f"""Generate test cases for the following component:

Component Name: {component_name}
Component Type: {component_type}
Priority: {priority}
Coverage Target: {coverage_target}
Agent Types: {', '.join(agent_types)}
API Endpoints: {json.dumps(api_surface) if api_surface else 'None'}
UI Entry Points: {json.dumps(ui_entry_points) if ui_entry_points else 'None'}
Dependencies: {json.dumps(dependencies) if dependencies else 'None'}

Generate {'5-8' if priority == 'HIGH' else '3-5' if priority == 'MEDIUM' else '2-3'} test cases.
Focus on {'all scenarios including security and edge cases' if priority == 'HIGH' else 'main flows and key edge cases' if priority == 'MEDIUM' else 'basic smoke tests'}.

Return ONLY a valid JSON array."""

    try:
        bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"), verify=not os.environ.get("AETHERTEST_NO_SSL_VERIFY", ""))
        response = bedrock.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "temperature": 0.3,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": prompt}],
            }),
            contentType="application/json",
            accept="application/json",
        )
        result = json.loads(response["body"].read())
        raw_text = result["content"][0]["text"].strip()

        # Extract JSON array from response
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        raw_text = raw_text.strip()

        test_cases = json.loads(raw_text)

        # Add component metadata to each test case
        for tc in test_cases:
            tc["component_id"] = component_name
            tc["generated_by"] = "claude-sonnet-4"
            tc["status"] = "pending"

        return test_cases

    except Exception as e:
        # Fallback: return a basic test case if Claude fails
        print(f"[WARNING] Claude generation failed for {component_name}: {e}")
        return [{
            "test_id": str(uuid.uuid4()),
            "test_name": f"Basic smoke test for {component_name}",
            "component": component_name,
            "component_id": component_name,
            "test_type": "api" if api_surface else "ui",
            "priority": priority.lower(),
            "description": f"Verify {component_name} is accessible and returns expected response",
            "preconditions": ["Application is deployed", "Test environment is available"],
            "steps": [
                f"Navigate to {ui_entry_points[0] if ui_entry_points else api_surface[0] if api_surface else component_name}",
                "Verify the component loads successfully",
                "Check response status is 200",
            ],
            "expected_result": f"{component_name} responds successfully",
            "test_data": {},
            "tags": ["smoke", "auto-generated"],
            "generated_by": "fallback",
            "status": "pending",
        }]
