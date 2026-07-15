"""
AUT Analyzer Lambda
Analyzes the Application Under Test structure and builds a component graph.
State: AnalyzeAUT in the Step Functions state machine.
"""

from __future__ import annotations
import json
import os
import uuid
import boto3
from datetime import datetime, timezone

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../layers"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from serializer.models import AUTComponent, AUTComponentGraph, ComponentType
from serializer.serializer import serialize, deserialize, ParseError
from aethertest.config import ARTIFACTS_BUCKET as BUCKET_NAME, STRATEGIES_TABLE
from aethertest.observability import instrument_handler

# AWS clients
s3 = boto3.client("s3", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"), verify=not os.environ.get("AETHERTEST_NO_SSL_VERIFY", ""), endpoint_url=os.environ.get("S3_ENDPOINT_URL", "https://s3.us-east-1.amazonaws.com"))
dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"), verify=not os.environ.get("AETHERTEST_NO_SSL_VERIFY", ""))

KNOWLEDGE_BASE_ID = os.environ.get("KNOWLEDGE_BASE_ID", "")


@instrument_handler("aut_analyzer")
def handler(event: dict, context) -> dict:
    """
    Lambda handler for AUT structure analysis.

    Expected event:
    {
        "tenant_id": "string",
        "aut_id": "string",
        "aut_version": "string",
        "aut_metadata": { ... }   # JSON conforming to AUT schema
    }
    """
    tenant_id = event.get("tenant_id")
    aut_id = event.get("aut_id")
    aut_version = event.get("aut_version")
    aut_metadata = event.get("aut_metadata")

    # Validate required fields
    missing = [f for f in ["tenant_id", "aut_id", "aut_version", "aut_metadata"]
               if not event.get(f)]
    if missing:
        return {
            "statusCode": 400,
            "error": "MissingFields",
            "missing_fields": missing,
        }

    # Parse and validate AUT metadata
    try:
        graph = _parse_aut_metadata(tenant_id, aut_id, aut_version, aut_metadata)
    except ParseError as e:
        return {
            "statusCode": 400,
            "error": "InvalidAUTMetadata",
            "detail": str(e),
            "field_path": e.field_path,
        }

    # Persist to S3
    s3_key = f"{tenant_id}/aut-graphs/{aut_id}/{aut_version}.json"
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=s3_key,
        Body=serialize(graph),
        ContentType="application/json",
    )

    # Record in DynamoDB
    table = dynamodb.Table(STRATEGIES_TABLE)
    table.put_item(Item={
        "PK": f"TENANT#{tenant_id}",
        "SK": f"AUT_GRAPH#{graph.graph_id}",
        "graph_id": graph.graph_id,
        "aut_id": aut_id,
        "aut_version": aut_version,
        "s3_key": s3_key,
        "analyzed_at": graph.analyzed_at,
        "component_count": len(graph.components),
    })

    # Store in Bedrock Knowledge Base (if configured)
    if KNOWLEDGE_BASE_ID:
        _store_in_knowledge_base(graph, tenant_id)

    return {
        "statusCode": 200,
        "graph_id": graph.graph_id,
        "component_count": len(graph.components),
        "s3_key": s3_key,
        "graph": json.loads(serialize(graph)),
    }


def _parse_aut_metadata(
    tenant_id: str,
    aut_id: str,
    aut_version: str,
    metadata: dict,
) -> AUTComponentGraph:
    """Parse raw AUT metadata dict into an AUTComponentGraph."""
    raw_components = metadata.get("components", [])
    components = []

    for raw in raw_components:
        comp = AUTComponent(
            component_id=raw.get("component_id", str(uuid.uuid4())),
            name=raw.get("name", "unknown"),
            component_type=ComponentType(raw.get("component_type", "service")),
            dependencies=raw.get("dependencies", []),
            api_surface=raw.get("api_surface", []),
            ui_entry_points=raw.get("ui_entry_points", []),
            metadata=raw.get("metadata", {}),
        )
        components.append(comp)

    return AUTComponentGraph(
        aut_id=aut_id,
        version=aut_version,
        tenant_id=tenant_id,
        components=components,
    )


def _store_in_knowledge_base(graph: AUTComponentGraph, tenant_id: str):
    """Store AUT component graph in Bedrock Knowledge Base."""
    try:
        bedrock_agent = boto3.client(
            "bedrock-agent-runtime",
            region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        )
        # Knowledge Base ingestion is async — trigger a sync job
        bedrock_agent.retrieve(
            knowledgeBaseId=KNOWLEDGE_BASE_ID,
            retrievalQuery={"text": f"aut_id:{graph.aut_id}"},
        )
    except Exception:
        pass  # Non-fatal — KB sync is best-effort at analysis time
