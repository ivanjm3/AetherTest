"""
Failure Triage Lambda
Classifies test failures as genuine_defect, env_noise, or aut_change.
State: TriageFailures in the Step Functions state machine.
"""

from __future__ import annotations
import os
import json
import boto3
from datetime import datetime, timezone

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../layers"))

from serializer.models import DefectPattern, FailureType
from serializer.serializer import serialize

dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"), verify=not os.environ.get("AETHERTEST_NO_SSL_VERIFY", ""))
cloudwatch = boto3.client("cloudwatch", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"), verify=not os.environ.get("AETHERTEST_NO_SSL_VERIFY", ""))
sns = boto3.client("sns", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"), verify=not os.environ.get("AETHERTEST_NO_SSL_VERIFY", ""))

DEFECT_PATTERNS_TABLE = os.environ.get("DEFECT_PATTERNS_TABLE", "aethertest-defect-patterns")
SNS_ALERT_ARN = os.environ.get("SNS_ALERT_ARN", "")
CONSECUTIVE_FAILURE_THRESHOLD = 3

# Triage prompt for Claude
TRIAGE_SYSTEM_PROMPT = """You are a test failure triage expert for the AetherTest platform.
Classify the given test failure into exactly one of:
- genuine_defect: A real bug in the application code
- env_noise: A transient infrastructure or environment issue (network, timeout, resource contention)
- aut_change: The application structure changed and the test is now outdated

Respond with a JSON object: {"classification": "<type>", "rationale": "<one sentence explanation>"}"""


def handler(event: dict, context) -> dict:
    """
    Lambda handler for failure triage.

    Expected event:
    {
        "tenant_id": "string",
        "execution_id": "string",
        "component_id": "string",
        "failure_evidence": {
            "error_message": "string",
            "stack_trace": "string",
            "test_name": "string",
            "consecutive_count": 1
        },
        "risk_score_at_failure": 75.0
    }
    """
    tenant_id = event.get("tenant_id", "")
    execution_id = event.get("execution_id", "")
    component_id = event.get("component_id", "")
    failure_evidence = event.get("failure_evidence", {})
    risk_score = float(event.get("risk_score_at_failure", 50.0))
    consecutive_count = int(failure_evidence.get("consecutive_count", 1))

    # Classify the failure using Claude
    classification, rationale = _classify_failure(failure_evidence, tenant_id)

    # Handle based on classification
    if classification == FailureType.GENUINE_DEFECT:
        _handle_genuine_defect(
            tenant_id, execution_id, component_id,
            risk_score, consecutive_count, failure_evidence,
        )
    elif classification == FailureType.ENV_NOISE:
        _handle_env_noise(tenant_id, component_id, rationale)
    elif classification == FailureType.AUT_CHANGE:
        _handle_aut_change(tenant_id, component_id)

    # Escalate if consecutive failures exceed threshold
    if consecutive_count >= CONSECUTIVE_FAILURE_THRESHOLD:
        _escalate_via_sns(tenant_id, component_id, classification, consecutive_count)

    # Emit CloudWatch metric
    _emit_metric("FailureTriageCompleted", tenant_id, classification.value)

    return {
        "statusCode": 200,
        "classification": classification.value,
        "rationale": rationale,
        "component_id": component_id,
        "escalated": consecutive_count >= CONSECUTIVE_FAILURE_THRESHOLD,
        "trigger_self_heal": classification == FailureType.AUT_CHANGE,
    }


def _classify_failure(failure_evidence: dict, tenant_id: str) -> tuple[FailureType, str]:
    """Use Claude to classify the failure. Falls back to heuristics if Bedrock unavailable."""
    try:
        from aethertest.bedrock_client import invoke_claude
        prompt = f"Classify this test failure:\n{json.dumps(failure_evidence, indent=2)}"
        response = invoke_claude(prompt, system_prompt=TRIAGE_SYSTEM_PROMPT, max_tokens=200)
        result = json.loads(response)
        classification = FailureType(result.get("classification", "env_noise"))
        rationale = result.get("rationale", "")
        return classification, rationale
    except Exception:
        # Heuristic fallback
        error_msg = str(failure_evidence.get("error_message", "")).lower()
        if any(k in error_msg for k in ["timeout", "connection", "network", "503", "502"]):
            return FailureType.ENV_NOISE, "Network/timeout error detected — likely environmental"
        elif any(k in error_msg for k in ["element not found", "no such element", "stale element"]):
            return FailureType.AUT_CHANGE, "UI element not found — likely AUT structural change"
        else:
            return FailureType.GENUINE_DEFECT, "Unrecognized error pattern — classified as defect"


def _handle_genuine_defect(
    tenant_id: str, execution_id: str, component_id: str,
    risk_score: float, consecutive_count: int, evidence: dict,
):
    """Create a DefectPattern record in DynamoDB."""
    pattern = DefectPattern(
        tenant_id=tenant_id,
        component_id=component_id,
        execution_id=execution_id,
        failure_type=FailureType.GENUINE_DEFECT,
        risk_score_at_failure=risk_score,
        consecutive_failure_count=consecutive_count,
    )
    table = dynamodb.Table(DEFECT_PATTERNS_TABLE)
    item = json.loads(serialize(pattern))
    item["PK"] = f"TENANT#{tenant_id}"
    item["SK"] = f"COMPONENT#{component_id}#EXEC#{execution_id}"
    # 90-day TTL
    import time
    item["ttl"] = int(time.time()) + 7_776_000
    table.put_item(Item=item)


def _handle_env_noise(tenant_id: str, component_id: str, rationale: str):
    """Log env noise classification to CloudWatch."""
    print(json.dumps({
        "level": "INFO",
        "event": "FailureClassifiedAsEnvNoise",
        "tenant_id": tenant_id,
        "component_id": component_id,
        "rationale": rationale,
    }))


def _handle_aut_change(tenant_id: str, component_id: str):
    """Signal that self-healing should be triggered."""
    print(json.dumps({
        "level": "INFO",
        "event": "AUTChangeDetected",
        "tenant_id": tenant_id,
        "component_id": component_id,
        "action": "self_heal_triggered",
    }))


def _escalate_via_sns(
    tenant_id: str, component_id: str,
    classification: FailureType, consecutive_count: int,
):
    """Publish escalation alert to SNS."""
    if not SNS_ALERT_ARN:
        return
    try:
        sns.publish(
            TopicArn=SNS_ALERT_ARN,
            Subject=f"AetherTest Alert: {consecutive_count} consecutive failures",
            Message=json.dumps({
                "tenant_id": tenant_id,
                "component_id": component_id,
                "classification": classification.value,
                "consecutive_failure_count": consecutive_count,
            }),
        )
    except Exception as e:
        print(f"[SNS WARNING] Failed to publish escalation: {e}")


def _emit_metric(metric_name: str, tenant_id: str, failure_type: str):
    try:
        cloudwatch.put_metric_data(
            Namespace="AetherTest/StrategistAgent",
            MetricData=[{
                "MetricName": metric_name,
                "Dimensions": [
                    {"Name": "TenantId", "Value": tenant_id},
                    {"Name": "FailureType", "Value": failure_type},
                ],
                "Value": 1,
                "Unit": "Count",
            }],
        )
    except Exception:
        pass
