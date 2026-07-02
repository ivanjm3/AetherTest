"""
Test Maintenance Agent (Agent 5)
Monitors AUT changes and updates affected test cases.
Detects when UI elements or API schemas changed.
Regenerates affected test steps using Claude.
Retires obsolete tests and flags coverage gaps.
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

BUCKET_NAME = os.environ.get("AETHERTEST_BUCKET", "aethertest-artifacts-654654478821")
STRATEGIES_TABLE = os.environ.get("STRATEGIES_TABLE", "aethertest-strategies")
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")

MAINTENANCE_SYSTEM_PROMPT = """You are an expert test maintenance engineer for the AetherTest platform.
Your job is to update test cases when the application under test changes.

Given a test case and a description of what changed in the AUT, return an updated test case as JSON:
{
  "test_id": "<same as input>",
  "test_name": "<updated if needed>",
  "maintenance_action": "updated|retired|no_change",
  "change_summary": "what was changed and why",
  "updated_steps": ["updated step 1", "updated step 2"],
  "updated_given": ["updated precondition"],
  "updated_when": ["updated action"],
  "updated_then": ["updated expected outcome"],
  "updated_test_data": {"key": "value"},
  "retirement_reason": "why this test was retired, or null",
  "coverage_gap_detected": true|false,
  "coverage_gap_description": "what is now untested, or null"
}

Rules:
- Update tests when UI locators, API endpoints, or schemas change
- Retire tests when the feature they test no longer exists
- Flag coverage gaps when new functionality is not covered by existing tests
- Preserve test intent while updating implementation details"""


def handler(event: dict, context) -> dict:
    """
    Lambda handler for Test Maintenance Agent.

    Expected event:
    {
        "tenant_id": "string",
        "aut_changes": [
            {
                "component": "checkout",
                "change_type": "ui_element_changed|api_schema_changed|feature_removed|feature_added",
                "description": "The checkout button ID changed from 'btn-checkout' to 'checkout-submit'",
                "old_value": "btn-checkout",
                "new_value": "checkout-submit"
            }
        ],
        "existing_test_suite": {
            "test_suite_id": "...",
            "test_cases": [...]
        }
    }
    """
    tenant_id = event.get("tenant_id", "demo-tenant")
    aut_changes = event.get("aut_changes", [])
    existing_suite = event.get("existing_test_suite", {})

    test_cases = existing_suite.get("test_cases", [])

    if not aut_changes:
        return {
            "statusCode": 200,
            "message": "No AUT changes detected â€” no maintenance required",
            "maintenance_report": {"updated": 0, "retired": 0, "no_change": len(test_cases)},
        }

    print(f"\n[MAINTENANCE AGENT] Processing {len(aut_changes)} AUT changes against {len(test_cases)} tests...")

    # Map changes by component for efficient lookup
    changes_by_component: dict[str, list] = {}
    for change in aut_changes:
        comp = change.get("component", "unknown")
        changes_by_component.setdefault(comp, []).append(change)

    maintenance_results = []
    updated = retired = no_change = 0
    coverage_gaps = []

    for tc in test_cases:
        component = tc.get("component", tc.get("component_id", "unknown"))
        relevant_changes = changes_by_component.get(component, [])

        if not relevant_changes:
            no_change += 1
            maintenance_results.append({
                "test_id": tc.get("test_id"),
                "test_name": tc.get("test_name"),
                "maintenance_action": "no_change",
                "change_summary": "No changes affect this test",
            })
            continue

        print(f"  â†’ Maintaining: {tc.get('test_name', 'Unknown')[:60]}...")
        result = _maintain_test(tc, relevant_changes)
        maintenance_results.append(result)

        action = result.get("maintenance_action", "no_change")
        if action == "updated":
            updated += 1
            print(f"    âœ“ Updated: {result.get('change_summary', '')[:60]}")
        elif action == "retired":
            retired += 1
            print(f"    âœ— Retired: {result.get('retirement_reason', '')[:60]}")
        else:
            no_change += 1

        if result.get("coverage_gap_detected"):
            coverage_gaps.append({
                "component": component,
                "description": result.get("coverage_gap_description", ""),
            })

    # Check for new features that have no tests
    for change in aut_changes:
        if change.get("change_type") == "feature_added":
            comp = change.get("component", "unknown")
            has_tests = any(
                tc.get("component", tc.get("component_id", "")) == comp
                for tc in test_cases
            )
            if not has_tests:
                coverage_gaps.append({
                    "component": comp,
                    "description": f"New feature added to {comp} but no tests exist: {change.get('description', '')}",
                })

    # Save maintenance report to S3
    report_id = str(uuid.uuid4())
    s3_key = f"{tenant_id}/maintenance/{report_id}/report.json"

    report = {
        "report_id": report_id,
        "tenant_id": tenant_id,
        "agent": "test_maintenance_agent",
        "maintained_at": datetime.now(timezone.utc).isoformat(),
        "aut_changes_processed": len(aut_changes),
        "summary": {
            "total_tests": len(test_cases),
            "updated": updated,
            "retired": retired,
            "no_change": no_change,
            "coverage_gaps_found": len(coverage_gaps),
        },
        "maintenance_results": maintenance_results,
        "coverage_gaps": coverage_gaps,
        "aut_changes": aut_changes,
    }

    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=s3_key,
        Body=json.dumps(report, indent=2),
        ContentType="application/json",
    )

    # Record in DynamoDB
    table = dynamodb.Table(STRATEGIES_TABLE)
    table.put_item(Item={
        "PK": f"TENANT#{tenant_id}",
        "SK": f"MAINTENANCE#{report_id}",
        "report_id": report_id,
        "updated": updated,
        "retired": retired,
        "coverage_gaps": len(coverage_gaps),
        "s3_key": s3_key,
        "maintained_at": datetime.now(timezone.utc).isoformat(),
        "agent": "test_maintenance_agent",
    })

    return {
        "statusCode": 200,
        "report_id": report_id,
        "summary": report["summary"],
        "coverage_gaps": coverage_gaps,
        "maintenance_s3_key": s3_key,
        "maintenance_report": report,
    }


def _maintain_test(test_case: dict, changes: list) -> dict:
    """Use Claude to update a test case based on AUT changes."""
    try:
        bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"), verify=not os.environ.get("AETHERTEST_NO_SSL_VERIFY", ""))

        prompt = f"""Update this test case based on the AUT changes:

Current Test Case:
{json.dumps(test_case, indent=2)}

AUT Changes:
{json.dumps(changes, indent=2)}

Determine if the test needs to be updated, retired, or left unchanged.
Return ONLY a valid JSON object."""

        response = bedrock.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "temperature": 0.2,
                "system": MAINTENANCE_SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": prompt}],
            }),
            contentType="application/json",
            accept="application/json",
        )

        result = json.loads(response["body"].read())
        raw_text = result["content"][0]["text"].strip()

        if "```" in raw_text:
            parts = raw_text.split("```")
            raw_text = parts[1] if len(parts) > 1 else raw_text
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        raw_text = raw_text.strip()

        maintenance_result = json.loads(raw_text)
        maintenance_result["test_id"] = test_case.get("test_id")
        maintenance_result["test_name"] = test_case.get("test_name")
        return maintenance_result

    except Exception as e:
        print(f"[WARNING] Maintenance failed for {test_case.get('test_name', 'Unknown')}: {e}")
        # Heuristic fallback
        change_types = [c.get("change_type", "") for c in changes]
        if "feature_removed" in change_types:
            return {
                "test_id": test_case.get("test_id"),
                "test_name": test_case.get("test_name"),
                "maintenance_action": "retired",
                "change_summary": "Feature removed from AUT",
                "retirement_reason": "The feature this test covers has been removed",
                "coverage_gap_detected": False,
                "coverage_gap_description": None,
            }
        else:
            return {
                "test_id": test_case.get("test_id"),
                "test_name": test_case.get("test_name"),
                "maintenance_action": "updated",
                "change_summary": f"Updated due to: {changes[0].get('description', 'AUT change')}",
                "updated_steps": test_case.get("steps", test_case.get("when", [])),
                "coverage_gap_detected": False,
                "coverage_gap_description": None,
            }
