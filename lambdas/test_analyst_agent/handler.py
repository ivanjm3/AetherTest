"""
Test Analyst Agent (Agent 4)
Analyzes test failures using Claude.
Classifies: application_defect, test_data_issue, environment_instability, regression.
Correlates failures with recent code changes.
Generates root cause hypotheses.
Reduces false positives by checking consistency across runs.
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

BUCKET_NAME = os.environ.get("AETHERTEST_BUCKET", "aethertest-artifacts-654654478821")
ASSIGNMENTS_TABLE = os.environ.get("ASSIGNMENTS_TABLE", "aethertest-agent-assignments")
DEFECT_PATTERNS_TABLE = os.environ.get("DEFECT_PATTERNS_TABLE", "aethertest-defect-patterns")
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")

# Lazy-initialized clients â€” created on first use, not at import time.
# This avoids boto3 session creation during import (which fails in containers
# if AWS_PROFILE env var points to a non-existent SSO profile).
_s3 = None
_dynamodb = None


def _get_s3():
    global _s3
    if _s3 is None:
        _s3 = boto3.client(
            "s3",
            region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
            verify=not os.environ.get("AETHERTEST_NO_SSL_VERIFY", ""),
            endpoint_url=os.environ.get("S3_ENDPOINT_URL", "https://s3.us-east-1.amazonaws.com"),
        )
    return _s3


def _get_dynamodb():
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource(
            "dynamodb",
            region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
            verify=not os.environ.get("AETHERTEST_NO_SSL_VERIFY", ""),
        )
    return _dynamodb

ANALYST_SYSTEM_PROMPT = """You are an expert test failure analyst for the AetherTest platform.
Analyze test failures and provide deep root cause analysis.

For each failure, return a JSON object:
{
  "failure_id": "<same as input>",
  "classification": "application_defect|test_data_issue|environment_instability|regression",
  "confidence": 0.0-1.0,
  "root_cause_hypothesis": "specific, actionable explanation of why this failed",
  "contributing_factors": ["factor 1", "factor 2"],
  "is_false_positive": true|false,
  "false_positive_reason": "why this might be a false positive, or null",
  "correlated_changes": ["recent change that may have caused this"],
  "recommended_action": "fix_code|update_test_data|retry|investigate_environment|update_test",
  "severity": "critical|high|medium|low",
  "affected_components": ["component names"],
  "reproduction_steps": ["step 1", "step 2"],
  "fix_suggestion": "specific suggestion for fixing the issue"
}

Classification guide:
- application_defect: Bug in the application code
- test_data_issue: Test data is stale, missing, or incorrect
- environment_instability: Infrastructure/network/timeout issues
- regression: Previously working feature broke due to a code change"""


def handler(event: dict, context) -> dict:
    """
    Lambda handler for Test Analyst Agent.

    Expected event:
    {
        "tenant_id": "string",
        "execution_id": "string",
        "failed_tests": [
            {
                "test_id": "...",
                "test_name": "...",
                "component": "...",
                "failure_reason": "...",
                "failure_type": "...",
                "evidence": {...}
            }
        ],
        "recent_changes": ["changed component A", "deployed v2.1"],
        "run_history": [{"execution_id": "...", "pass_rate": 0.95}]
    }
    """
    tenant_id = event.get("tenant_id", "demo-tenant")
    execution_id = event.get("execution_id", str(uuid.uuid4()))
    failed_tests = event.get("failed_tests", [])
    recent_changes = event.get("recent_changes", [])
    run_history = event.get("run_history", [])

    if not failed_tests:
        return {
            "statusCode": 200,
            "execution_id": execution_id,
            "message": "No failures to analyze",
            "analyses": [],
            "summary": {"total_failures": 0, "false_positives": 0, "real_defects": 0},
        }

    print(f"\n[ANALYST AGENT] Analyzing {len(failed_tests)} failures...")

    analyses = []
    for failure in failed_tests:
        test_id = failure.get("test_id", str(uuid.uuid4()))
        test_name = failure.get("test_name", "Unknown test")
        print(f"  Ã¢â€ â€™ Analyzing: {test_name[:60]}...")

        analysis = _analyze_failure(
            failure=failure,
            recent_changes=recent_changes,
            run_history=run_history,
        )
        analyses.append(analysis)

        classification = analysis.get("classification", "unknown")
        confidence = analysis.get("confidence", 0)
        fp = " [FALSE POSITIVE]" if analysis.get("is_false_positive") else ""
        print(f"    Ã¢â€ â€™ {classification} (confidence: {confidence:.0%}){fp}")

    # Aggregate summary
    real_defects = [a for a in analyses if not a.get("is_false_positive") and a.get("classification") == "application_defect"]
    regressions = [a for a in analyses if a.get("classification") == "regression"]
    false_positives = [a for a in analyses if a.get("is_false_positive")]
    env_issues = [a for a in analyses if a.get("classification") == "environment_instability"]

    summary = {
        "total_failures": len(failed_tests),
        "real_defects": len(real_defects),
        "regressions": len(regressions),
        "false_positives": len(false_positives),
        "environment_issues": len(env_issues),
        "test_data_issues": len([a for a in analyses if a.get("classification") == "test_data_issue"]),
        "critical_count": len([a for a in analyses if a.get("severity") == "critical"]),
    }

    # Save analysis report to S3
    s3_key = f"{tenant_id}/analysis/{execution_id}/failure-analysis.json"
    report = {
        "execution_id": execution_id,
        "tenant_id": tenant_id,
        "agent": "test_analyst_agent",
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "analyses": analyses,
        "recent_changes_considered": recent_changes,
    }

    _get_s3().put_object(
        Bucket=BUCKET_NAME,
        Key=s3_key,
        Body=json.dumps(report, indent=2),
        ContentType="application/json",
    )

    # Store defect patterns for real defects
    _store_defect_patterns(tenant_id, execution_id, analyses)

    return {
        "statusCode": 200,
        "execution_id": execution_id,
        "summary": summary,
        "analyses": analyses,
        "analysis_s3_key": s3_key,
        "requires_immediate_attention": [
            a for a in analyses
            if a.get("severity") == "critical" and not a.get("is_false_positive")
        ],
    }


def _analyze_failure(failure: dict, recent_changes: list, run_history: list) -> dict:
    """Use Claude to analyze a single test failure."""
    try:
        bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"), verify=not os.environ.get("AETHERTEST_NO_SSL_VERIFY", ""))

        prompt = f"""Analyze this test failure:

Test: {failure.get('test_name', 'Unknown')}
Component: {failure.get('component', 'Unknown')}
Failure Reason: {failure.get('failure_reason', 'Unknown')}
Failure Type: {failure.get('failure_type', 'Unknown')}
Evidence: {json.dumps(failure.get('evidence', {}), indent=2)}

Recent Changes: {json.dumps(recent_changes) if recent_changes else 'None provided'}
Run History (last {len(run_history)} runs): {json.dumps(run_history) if run_history else 'No history'}

Provide a thorough root cause analysis. Return ONLY a valid JSON object."""

        response = bedrock.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "temperature": 0.2,
                "system": ANALYST_SYSTEM_PROMPT,
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

        analysis = json.loads(raw_text)
        analysis["failure_id"] = failure.get("test_id", str(uuid.uuid4()))
        analysis["test_name"] = failure.get("test_name", "")
        analysis["component"] = failure.get("component", "")
        return analysis

    except Exception as e:
        print(f"[WARNING] Analysis failed: {e}")
        # Heuristic fallback
        error_msg = str(failure.get("failure_reason", "")).lower()
        if any(k in error_msg for k in ["timeout", "connection", "network", "503"]):
            classification = "environment_instability"
        elif any(k in error_msg for k in ["not found", "element", "stale", "locator"]):
            classification = "regression"
        elif any(k in error_msg for k in ["data", "null", "empty", "missing"]):
            classification = "test_data_issue"
        else:
            classification = "application_defect"

        return {
            "failure_id": failure.get("test_id", str(uuid.uuid4())),
            "test_name": failure.get("test_name", ""),
            "component": failure.get("component", ""),
            "classification": classification,
            "confidence": 0.6,
            "root_cause_hypothesis": f"Failure in {failure.get('component', 'component')}: {failure.get('failure_reason', 'Unknown error')}",
            "contributing_factors": ["Automated heuristic classification"],
            "is_false_positive": False,
            "false_positive_reason": None,
            "correlated_changes": recent_changes[:2] if recent_changes else [],
            "recommended_action": "investigate_environment" if classification == "environment_instability" else "fix_code",
            "severity": "medium",
            "affected_components": [failure.get("component", "unknown")],
            "reproduction_steps": ["Re-run the failing test", "Check application logs"],
            "fix_suggestion": "Review the error and check recent code changes",
        }


def _store_defect_patterns(tenant_id: str, execution_id: str, analyses: list):
    """Store real defect patterns in DynamoDB for learning."""
    table = _get_dynamodb().Table(DEFECT_PATTERNS_TABLE)
    import time

    for analysis in analyses:
        if analysis.get("is_false_positive"):
            continue
        if analysis.get("classification") not in ("application_defect", "regression"):
            continue

        try:
            component_name = analysis.get("component", "unknown")
            component_id = component_name.lower().replace(" ", "-")
            table.put_item(Item={
                "PK": f"TENANT#{tenant_id}",
                "SK": f"COMPONENT#{component_id}#EXEC#{execution_id}",
                "tenant_id": tenant_id,
                "component_id": component_id,
                "execution_id": execution_id,
                "failure_type": analysis.get("classification", "application_defect"),
                "root_cause": analysis.get("root_cause_hypothesis", ""),
                "severity": analysis.get("severity", "medium"),
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "ttl": int(time.time()) + 7_776_000,  # 90 days
            })
        except Exception as e:
            print(f"[WARNING] Failed to store defect pattern: {e}")
