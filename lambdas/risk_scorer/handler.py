"""
Risk Scorer Lambda
Computes Risk_Score for each AUT component using change data,
deployment history, and historical defect patterns.
State: ComputeRiskScores in the Step Functions state machine.
"""

from __future__ import annotations
import os
import json
import boto3
from datetime import datetime, timezone

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../layers"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from serializer.models import AUTComponentGraph, RiskScoreRecord
from serializer.serializer import deserialize
from aethertest.observability import instrument_handler

dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"), verify=not os.environ.get("AETHERTEST_NO_SSL_VERIFY", ""))
DEFECT_PATTERNS_TABLE = os.environ.get("DEFECT_PATTERNS_TABLE", "aethertest-defect-patterns")

# Risk score weights
W_CHANGE = 0.4
W_DEFECT = 0.4
W_DEPLOY = 0.2
DEFAULT_SCORE = 50.0
HIGH_PRIORITY_THRESHOLD = 70.0


@instrument_handler("risk_scorer")
def handler(event: dict, context) -> dict:
    """
    Lambda handler for risk score computation.

    Expected event:
    {
        "tenant_id": "string",
        "graph": { ... },           # AUTComponentGraph JSON
        "change_set": [             # optional list of changed components
            {"component_id": "...", "changed_lines": 100, "total_lines": 500}
        ],
        "deploy_frequency": {       # optional deploy frequency per component
            "component_id": count
        }
    }
    """
    tenant_id = event.get("tenant_id", "")
    graph_data = event.get("graph", {})
    change_set = event.get("change_set", [])
    deploy_frequency = event.get("deploy_frequency", {})

    # Parse graph
    graph = AUTComponentGraph.model_validate(graph_data)

    # Build change map: component_id -> change ratio
    change_map = {}
    for change in change_set:
        cid = change.get("component_id")
        changed = change.get("changed_lines", 0)
        total = change.get("total_lines", 1)
        change_map[cid] = changed / max(total, 1)

    # Query defect history from DynamoDB
    defect_map = _get_defect_history(tenant_id, [c.component_id for c in graph.components])

    # Compute scores
    records = []
    for component in graph.components:
        cid = component.component_id
        has_history = cid in defect_map

        if not has_history:
            change_ratio = change_map.get(cid, 0.0)
            deploy_freq = deploy_frequency.get(cid, 0)
            change_score = change_ratio * 100
            deploy_score = min(deploy_freq / 5.0, 1.0) * 100
            if change_score > 0 or deploy_score > 0:
                raw_score = 0.6 * change_score + 0.4 * deploy_score
            else:
                raw_score = DEFAULT_SCORE
            record = RiskScoreRecord(
                component_id=cid,
                risk_score=round(max(0.0, min(100.0, raw_score)), 2),
                is_uncharacterized=True,
                change_weight=round(min(0.6 * change_score / 100, 1.0), 4),
                defect_weight=0.0,
                deployment_weight=round(min(0.4 * deploy_score / 100, 1.0), 4),
            )
        else:
            change_ratio = change_map.get(cid, 0.0)
            defect_count = defect_map.get(cid, 0)
            deploy_freq = deploy_frequency.get(cid, 0)

            change_score = change_ratio * 100
            defect_score = min(defect_count / 3.0, 1.0) * 100
            deploy_score = min(deploy_freq / 5.0, 1.0) * 100

            raw_score = (
                W_CHANGE * change_score +
                W_DEFECT * defect_score +
                W_DEPLOY * deploy_score
            )
            clamped = max(0.0, min(100.0, raw_score))

            record = RiskScoreRecord(
                component_id=cid,
                risk_score=round(clamped, 2),
                is_uncharacterized=False,
                change_weight=round(min(W_CHANGE * change_score / 100, 1.0), 4),
                defect_weight=round(min(W_DEFECT * defect_score / 100, 1.0), 4),
                deployment_weight=round(min(W_DEPLOY * deploy_score / 100, 1.0), 4),
            )

        records.append(record)

    # Sort descending by risk score
    records.sort(key=lambda r: r.risk_score, reverse=True)

    return {
        "statusCode": 200,
        "tenant_id": tenant_id,
        "risk_scores": [json.loads(r.model_dump_json()) for r in records],
        "high_priority_count": sum(1 for r in records if r.risk_score > HIGH_PRIORITY_THRESHOLD),
    }


def _get_defect_history(tenant_id: str, component_ids: list[str]) -> dict[str, int]:
    """
    Query DynamoDB for defect counts per component (last 3 cycles).
    Returns dict: component_id -> defect_count
    """
    table = dynamodb.Table(DEFECT_PATTERNS_TABLE)
    defect_map = {}

    for cid in component_ids:
        try:
            response = table.query(
                KeyConditionExpression=(
                    boto3.dynamodb.conditions.Key("PK").eq(f"TENANT#{tenant_id}") &
                    boto3.dynamodb.conditions.Key("SK").begins_with(f"COMPONENT#{cid}#")
                ),
                Limit=3,  # last 3 cycles
                ScanIndexForward=False,
            )
            items = response.get("Items", [])
            if items:
                defect_map[cid] = sum(
                    int(item.get("consecutive_failure_count", 1))
                    for item in items
                    if item.get("failure_type") in ("genuine_defect", "application_defect", "regression")
                )
        except Exception:
            pass  # component not found in history — will be uncharacterized

    return defect_map
