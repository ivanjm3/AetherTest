"""
Test Author Agent (Agent 2)
Converts business requirements and user stories into executable BDD-style test cases.
Supports plain text requirements and "As a... I want... So that..." user story format.
Stores generated tests in S3 and DynamoDB.
"""

from __future__ import annotations
import os
import sys
import json
import uuid
import boto3
from datetime import datetime, timezone

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../layers"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

s3 = boto3.client("s3", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"), verify=not os.environ.get("AETHERTEST_NO_SSL_VERIFY", ""), endpoint_url=os.environ.get("S3_ENDPOINT_URL", "https://s3.us-east-1.amazonaws.com"))
dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"), verify=not os.environ.get("AETHERTEST_NO_SSL_VERIFY", ""))

from aethertest.config import (
    ARTIFACTS_BUCKET as BUCKET_NAME,
    STRATEGIES_TABLE,
    BEDROCK_MODEL_ID as MODEL_ID,
)
from aethertest.observability import instrument_handler

AUTHOR_SYSTEM_PROMPT = """You are an expert QA engineer and BDD practitioner.
Convert business requirements and user stories into executable BDD-style test cases.

For each requirement, generate test cases in Given/When/Then format.

Return ONLY a valid JSON array. Each test case must have:
{
  "test_id": "TC-<unique 6-char alphanumeric>",
  "test_name": "descriptive name",
  "requirement_ref": "REQ-001 or story title",
  "test_type": "functional|security|performance|usability",
  "priority": "high|medium|low",
  "description": "what this test verifies",
  "given": ["precondition 1", "precondition 2"],
  "when": ["action 1", "action 2"],
  "then": ["expected outcome 1", "expected outcome 2"],
  "test_data": {"key": "value"},
  "tags": ["smoke", "regression", "bdd"],
  "acceptance_criteria": "the original acceptance criterion being tested"
}

Generate thorough tests covering happy paths, edge cases, and negative scenarios."""


@instrument_handler("test_author_agent")
def handler(event: dict, context) -> dict:
    """
    Lambda handler for Test Author Agent.

    Expected event:
    {
        "tenant_id": "string",
        "requirements": [
            {
                "id": "REQ-001",
                "type": "user_story|plain_text|acceptance_criteria",
                "content": "As a customer I want to add items to cart so that I can purchase them",
                "component": "shopping_cart"
            }
        ],
        "aut_context": {
            "name": "E-Commerce Platform",
            "components": ["cart", "checkout", "payment"]
        }
    }
    """
    tenant_id = event.get("tenant_id", "demo-tenant")
    requirements = event.get("requirements", [])
    aut_context = event.get("aut_context", {})

    if not requirements:
        return {"statusCode": 400, "error": "No requirements provided"}

    all_test_cases = []
    authoring_log = []

    print(f"\n[TEST AUTHOR] Processing {len(requirements)} requirements...")

    for req in requirements:
        req_id = req.get("id", f"REQ-{str(uuid.uuid4())[:6].upper()}")
        req_type = req.get("type", "plain_text")
        content = req.get("content", "")
        component = req.get("component", "unknown")

        print(f"  â†’ Authoring tests for {req_id}: {content[:60]}...")

        test_cases = _author_test_cases(
            req_id=req_id,
            req_type=req_type,
            content=content,
            component=component,
            aut_context=aut_context,
        )

        all_test_cases.extend(test_cases)
        authoring_log.append({
            "requirement_id": req_id,
            "type": req_type,
            "component": component,
            "tests_authored": len(test_cases),
        })
        print(f"    âœ“ Generated {len(test_cases)} BDD test cases")

    # Save to S3
    suite_id = str(uuid.uuid4())
    s3_key = f"{tenant_id}/authored-tests/{suite_id}.json"

    authored_suite = {
        "suite_id": suite_id,
        "tenant_id": tenant_id,
        "authored_at": datetime.now(timezone.utc).isoformat(),
        "authored_by": "test_author_agent",
        "total_tests": len(all_test_cases),
        "requirements_processed": len(requirements),
        "test_cases": all_test_cases,
        "authoring_log": authoring_log,
        "aut_context": aut_context,
    }

    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=s3_key,
        Body=json.dumps(authored_suite, indent=2),
        ContentType="application/json",
    )

    # Record in DynamoDB
    table = dynamodb.Table(STRATEGIES_TABLE)
    table.put_item(Item={
        "PK": f"TENANT#{tenant_id}",
        "SK": f"AUTHORED_SUITE#{suite_id}",
        "suite_id": suite_id,
        "total_tests": len(all_test_cases),
        "requirements_count": len(requirements),
        "s3_key": s3_key,
        "authored_at": datetime.now(timezone.utc).isoformat(),
        "agent": "test_author_agent",
    })

    return {
        "statusCode": 200,
        "suite_id": suite_id,
        "total_tests_authored": len(all_test_cases),
        "requirements_processed": len(requirements),
        "s3_key": s3_key,
        "authoring_log": authoring_log,
        "test_suite": authored_suite,
    }


def _author_test_cases(
    req_id: str,
    req_type: str,
    content: str,
    component: str,
    aut_context: dict,
) -> list[dict]:
    """Use Claude to convert a requirement into BDD test cases."""
    try:
        bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"), verify=not os.environ.get("AETHERTEST_NO_SSL_VERIFY", ""))

        aut_name = aut_context.get("name", "the application")
        components = aut_context.get("components", [])

        prompt = f"""Convert this requirement into BDD test cases:

Requirement ID: {req_id}
Type: {req_type}
Component: {component}
Application: {aut_name}
Related Components: {', '.join(components) if components else 'N/A'}

Requirement:
{content}

Generate 3-5 BDD test cases covering the happy path, at least one edge case, and one negative test.
Return ONLY a valid JSON array."""

        response = bedrock.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "temperature": 0.3,
                "system": AUTHOR_SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": prompt}],
            }),
            contentType="application/json",
            accept="application/json",
        )

        result = json.loads(response["body"].read())
        raw_text = result["content"][0]["text"].strip()

        # Strip markdown code fences if present
        if "```" in raw_text:
            parts = raw_text.split("```")
            raw_text = parts[1] if len(parts) > 1 else raw_text
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        raw_text = raw_text.strip()

        test_cases = json.loads(raw_text)

        # Enrich each test case
        for tc in test_cases:
            tc.setdefault("test_id", f"TC-{str(uuid.uuid4())[:6].upper()}")
            tc["component"] = component
            tc["requirement_id"] = req_id
            tc["authored_by"] = "test_author_agent"
            tc["format"] = "bdd"
            tc["status"] = "ready"

        return test_cases

    except Exception as e:
        print(f"[WARNING] Claude authoring failed for {req_id}: {e}")
        # Fallback BDD test case
        return [
            {
                "test_id": f"TC-{str(uuid.uuid4())[:6].upper()}",
                "test_name": f"Verify {component} - {req_id}",
                "requirement_ref": req_id,
                "test_type": "functional",
                "priority": "medium",
                "description": f"Verify requirement: {content[:100]}",
                "given": ["The application is running", f"The {component} is accessible"],
                "when": ["The user performs the required action"],
                "then": ["The expected outcome is achieved", "No errors are displayed"],
                "test_data": {},
                "tags": ["smoke", "auto-generated"],
                "acceptance_criteria": content[:200],
                "component": component,
                "requirement_id": req_id,
                "authored_by": "test_author_agent_fallback",
                "format": "bdd",
                "status": "ready",
            }
        ]
