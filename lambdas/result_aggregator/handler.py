"""
Result Aggregator Lambda
Aggregates all Specialist Agent results and produces the final ExecutionState.
State: AggregateResults in the Step Functions state machine.
"""

from __future__ import annotations
import os
import json
import boto3
from datetime import datetime, timezone

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../layers"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from serializer.models import ExecutionState, ExecutionStatus
from serializer.serializer import serialize
from aethertest.config import ARTIFACTS_BUCKET as BUCKET_NAME, EXECUTIONS_TABLE, ASSIGNMENTS_TABLE
from aethertest.observability import instrument_handler

dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"), verify=not os.environ.get("AETHERTEST_NO_SSL_VERIFY", ""))
s3 = boto3.client("s3", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"), verify=not os.environ.get("AETHERTEST_NO_SSL_VERIFY", ""), endpoint_url=os.environ.get("S3_ENDPOINT_URL", "https://s3.us-east-1.amazonaws.com"))


@instrument_handler("result_aggregator")
def handler(event: dict, context) -> dict:
    """
    Lambda handler for result aggregation.

    Expected event:
    {
        "tenant_id": "string",
        "execution_id": "string",
        "strategy_id": "string"
    }
    """
    tenant_id = event.get("tenant_id", "")
    execution_id = event.get("execution_id", "")
    strategy_id = event.get("strategy_id", "")

    # Load all assignments for this execution
    assignments_table = dynamodb.Table(ASSIGNMENTS_TABLE)
    response = assignments_table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("PK").eq(
            f"EXECUTION#{execution_id}"
        )
    )
    items = response.get("Items", [])

    total = len(items)
    completed = sum(1 for i in items if i.get("status") == "completed")
    failed = sum(1 for i in items if i.get("status") == "failed")
    timed_out = sum(1 for i in items if i.get("status") == "timed_out")

    final_status = ExecutionStatus.COMPLETED if failed == 0 and timed_out == 0 else ExecutionStatus.FAILED
    completed_at = datetime.now(timezone.utc).isoformat()

    # Update execution record in DynamoDB
    executions_table = dynamodb.Table(EXECUTIONS_TABLE)
    executions_table.update_item(
        Key={
            "PK": f"TENANT#{tenant_id}",
            "SK": f"EXECUTION#{execution_id}",
        },
        UpdateExpression="SET #status = :status, completed_at = :completed_at, defect_count = :defect_count",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": final_status.value,
            ":completed_at": completed_at,
            ":defect_count": failed,
        },
    )

    # Persist summary to S3
    summary = {
        "execution_id": execution_id,
        "strategy_id": strategy_id,
        "tenant_id": tenant_id,
        "status": final_status.value,
        "total_assignments": total,
        "completed": completed,
        "failed": failed,
        "timed_out": timed_out,
        "completed_at": completed_at,
    }
    summary_key = f"{tenant_id}/artifacts/{execution_id}/summary.json"
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=summary_key,
        Body=json.dumps(summary, indent=2),
        ContentType="application/json",
    )

    return {
        "statusCode": 200,
        "execution_id": execution_id,
        "status": final_status.value,
        "total_assignments": total,
        "completed": completed,
        "failed": failed,
        "timed_out": timed_out,
        "summary_s3_key": summary_key,
        "deployment_approved": final_status == ExecutionStatus.COMPLETED,
    }
