"""
Learning Updater Lambda
Extracts outcome signals from completed test cycles and updates
DynamoDB defect patterns and Bedrock Knowledge Base for closed-loop learning.
State: UpdateLearning in the Step Functions state machine.
"""

from __future__ import annotations
import os
import json
import time
import boto3
from datetime import datetime, timezone

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../layers"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from serializer.models import ExecutionState, DefectPattern, FailureType
from serializer.serializer import serialize, deserialize
from aethertest.config import ARTIFACTS_BUCKET as BUCKET_NAME, DEFECT_PATTERNS_TABLE
from aethertest.observability import instrument_handler

dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"), verify=not os.environ.get("AETHERTEST_NO_SSL_VERIFY", ""))
s3 = boto3.client("s3", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"), verify=not os.environ.get("AETHERTEST_NO_SSL_VERIFY", ""), endpoint_url=os.environ.get("S3_ENDPOINT_URL", "https://s3.us-east-1.amazonaws.com"))

KNOWLEDGE_BASE_ID = os.environ.get("KNOWLEDGE_BASE_ID", "")
TTL_90_DAYS = 7_776_000  # seconds
DEFECT_DENSITY_INCREASE_THRESHOLD = 0.20  # 20%


@instrument_handler("learning_updater")
def handler(event: dict, context) -> dict:
    """
    Lambda handler for closed-loop learning update.

    Expected event:
    {
        "tenant_id": "string",
        "execution_state": { ... },   # ExecutionState JSON
        "previous_defect_densities": { "component_id": density_float }
    }
    """
    tenant_id = event.get("tenant_id", "")
    execution_data = event.get("execution_state", {})
    previous_densities = event.get("previous_defect_densities", {})

    state = ExecutionState.model_validate(execution_data)

    # Extract outcome signals
    outcomes = _extract_outcomes(state)

    # Store outcome signals as DefectPattern records
    flagged_components = []
    for component_id, signals in outcomes.items():
        _store_defect_pattern(tenant_id, state.execution_id, component_id, signals)

        # Check for defect density increase > 20%
        prev_density = previous_densities.get(component_id, 0.0)
        curr_density = signals.get("defect_density", 0.0)
        if prev_density > 0 and curr_density > prev_density * (1 + DEFECT_DENSITY_INCREASE_THRESHOLD):
            flagged_components.append(component_id)

    # Persist learning outcome to S3
    outcome_key = f"{tenant_id}/learning/outcomes/{state.execution_id}.json"
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=outcome_key,
        Body=json.dumps({
            "execution_id": state.execution_id,
            "tenant_id": tenant_id,
            "outcomes": outcomes,
            "flagged_for_increased_coverage": flagged_components,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }),
        ContentType="application/json",
    )

    # Update Bedrock Knowledge Base
    if KNOWLEDGE_BASE_ID:
        _update_knowledge_base(tenant_id, state.execution_id)

    return {
        "statusCode": 200,
        "execution_id": state.execution_id,
        "components_updated": len(outcomes),
        "flagged_for_increased_coverage": flagged_components,
        "outcome_s3_key": outcome_key,
    }


def _extract_outcomes(state: ExecutionState) -> dict:
    """Extract per-component outcome signals from ExecutionState."""
    component_results: dict[str, dict] = {}

    for assignment in state.assignments:
        for cid in assignment.component_ids:
            if cid not in component_results:
                component_results[cid] = {"passed": 0, "failed": 0, "total": 0}

            component_results[cid]["total"] += 1
            if assignment.status.value == "completed":
                component_results[cid]["passed"] += 1
            elif assignment.status.value == "failed":
                component_results[cid]["failed"] += 1

    # Compute defect density per component
    outcomes = {}
    for cid, results in component_results.items():
        total = results["total"]
        failed = results["failed"]
        outcomes[cid] = {
            "pass_rate": results["passed"] / total if total > 0 else 0.0,
            "defect_density": failed / total if total > 0 else 0.0,
            "total_tests": total,
        }

    return outcomes


def _store_defect_pattern(
    tenant_id: str, execution_id: str,
    component_id: str, signals: dict,
):
    """Store outcome signals as a DefectPattern record with 90-day TTL."""
    table = dynamodb.Table(DEFECT_PATTERNS_TABLE)
    table.put_item(Item={
        "PK": f"TENANT#{tenant_id}",
        "SK": f"COMPONENT#{component_id}#EXEC#{execution_id}",
        "tenant_id": tenant_id,
        "component_id": component_id,
        "execution_id": execution_id,
        "failure_type": FailureType.GENUINE_DEFECT.value,
        "defect_density": str(signals.get("defect_density", 0.0)),
        "pass_rate": str(signals.get("pass_rate", 1.0)),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "ttl": int(time.time()) + TTL_90_DAYS,
    })


def _update_knowledge_base(tenant_id: str, execution_id: str):
    """Trigger Bedrock Knowledge Base ingestion to sync new learning data."""
    try:
        bedrock_agent = boto3.client(
            "bedrock-agent",
            region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        )
        data_source_id = os.environ.get("KB_DATA_SOURCE_ID", "")
        if data_source_id:
            bedrock_agent.start_ingestion_job(
                knowledgeBaseId=KNOWLEDGE_BASE_ID,
                dataSourceId=data_source_id,
            )
    except Exception as e:
        print(f"[KB WARNING] Knowledge Base update failed: {e}")
