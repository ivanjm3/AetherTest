"""
Strategy Generator Lambda
Generates a structured TestStrategy from risk scores and persists it to S3/DynamoDB.
State: GenerateStrategy in the Step Functions state machine.
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

from serializer.models import (
    TestStrategy, ComponentCoverage, RiskScoreRecord,
    Priority, CoverageTarget, TriggeringEvent,
)
from serializer.serializer import serialize
from serializer.markdown import to_markdown
from aethertest.config import ARTIFACTS_BUCKET as BUCKET_NAME, STRATEGIES_TABLE
from aethertest.observability import instrument_handler

s3 = boto3.client("s3", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"), verify=not os.environ.get("AETHERTEST_NO_SSL_VERIFY", ""), endpoint_url=os.environ.get("S3_ENDPOINT_URL", "https://s3.us-east-1.amazonaws.com"))
dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"), verify=not os.environ.get("AETHERTEST_NO_SSL_VERIFY", ""))
cloudwatch = boto3.client("cloudwatch", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"), verify=not os.environ.get("AETHERTEST_NO_SSL_VERIFY", ""))

HIGH_THRESHOLD = 70.0
MEDIUM_THRESHOLD = 50.0

# Agent type assignments by priority
HIGH_PRIORITY_AGENTS = ["ui_agent", "api_agent"]
MEDIUM_PRIORITY_AGENTS = ["api_agent"]
LOW_PRIORITY_AGENTS = ["ui_agent"]


@instrument_handler("strategy_generator")
def handler(event: dict, context) -> dict:
    """
    Lambda handler for test strategy generation.

    Expected event:
    {
        "tenant_id": "string",
        "aut_id": "string",
        "aut_version": "string",
        "execution_environment": "string",
        "triggering_event": "cicd|manual|self_heal",
        "risk_scores": [ { RiskScoreRecord fields } ],
        "format_markdown": false   # optional: return Markdown too
    }
    """
    tenant_id = event.get("tenant_id", "")
    aut_id = event.get("aut_id", "")
    aut_version = event.get("aut_version", "")
    environment = event.get("execution_environment", "staging")
    triggering = event.get("triggering_event", "manual")
    risk_scores_raw = event.get("risk_scores", [])
    format_markdown = event.get("format_markdown", False)

    # Parse risk score records
    risk_scores = [RiskScoreRecord.model_validate(r) for r in risk_scores_raw]

    # Build coverage plan
    coverage = []
    for record in risk_scores:
        if record.risk_score > HIGH_THRESHOLD:
            priority = Priority.HIGH
            agents = HIGH_PRIORITY_AGENTS.copy()
            target = CoverageTarget.FULL
        elif record.risk_score >= MEDIUM_THRESHOLD:
            priority = Priority.MEDIUM
            agents = MEDIUM_PRIORITY_AGENTS.copy()
            target = CoverageTarget.SMOKE
        else:
            priority = Priority.LOW
            agents = LOW_PRIORITY_AGENTS.copy()
            target = CoverageTarget.REGRESSION

        coverage.append(ComponentCoverage(
            component_id=record.component_id,
            risk_score=record.risk_score,
            priority=priority,
            assigned_agent_types=agents,
            coverage_target=target,
        ))

    # Estimate duration: 60s per high, 30s per medium, 15s per low
    estimated_duration = sum(
        60 if c.priority == Priority.HIGH else
        30 if c.priority == Priority.MEDIUM else 15
        for c in coverage
    )

    strategy_id = str(uuid.uuid4())
    s3_key = f"{tenant_id}/strategies/{strategy_id}.json"

    strategy = TestStrategy(
        strategy_id=strategy_id,
        tenant_id=tenant_id,
        aut_id=aut_id,
        aut_version=aut_version,
        execution_environment=environment,
        coverage=coverage,
        estimated_duration_seconds=estimated_duration,
        s3_key=s3_key,
        triggering_event=TriggeringEvent(triggering),
    )

    # Persist to S3
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=s3_key,
        Body=serialize(strategy),
        ContentType="application/json",
    )

    # Record in DynamoDB
    table = dynamodb.Table(STRATEGIES_TABLE)
    table.put_item(Item={
        "PK": f"TENANT#{tenant_id}",
        "SK": f"STRATEGY#{strategy_id}#V#1",
        "strategy_id": strategy_id,
        "aut_id": aut_id,
        "s3_key": s3_key,
        "created_at": strategy.created_at,
        "version": 1,
        "component_count": len(coverage),
        "high_priority_count": sum(1 for c in coverage if c.priority == Priority.HIGH),
    })

    # Emit CloudWatch metric
    _emit_metric("StrategyGenerationCompleted", tenant_id, aut_id)

    result = {
        "statusCode": 200,
        "strategy_id": strategy_id,
        "s3_key": s3_key,
        "component_count": len(coverage),
        "estimated_duration_seconds": estimated_duration,
        "strategy": json.loads(serialize(strategy)),
    }

    if format_markdown:
        result["markdown"] = to_markdown(strategy)

    return result


def _emit_metric(metric_name: str, tenant_id: str, aut_id: str):
    """Emit a custom CloudWatch metric."""
    try:
        cloudwatch.put_metric_data(
            Namespace="AetherTest/StrategistAgent",
            MetricData=[{
                "MetricName": metric_name,
                "Dimensions": [
                    {"Name": "TenantId", "Value": tenant_id},
                    {"Name": "AUTId", "Value": aut_id},
                ],
                "Value": 1,
                "Unit": "Count",
            }],
        )
    except Exception:
        pass  # Non-fatal — metrics are best-effort
