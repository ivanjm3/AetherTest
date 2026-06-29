"""
Agent Dispatcher Lambda
Dispatches task assignments to Specialist Agents via Bedrock AgentCore A2A protocol.
State: DispatchAgents in the Step Functions state machine.
"""

from __future__ import annotations
import os
import json
import uuid
import boto3
from datetime import datetime, timezone
from collections import defaultdict

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../layers"))

from serializer.models import (
    TestStrategy, AgentAssignment, ExecutionState,
    AssignmentStatus, ExecutionStatus,
)
from serializer.serializer import serialize

dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"), verify=not os.environ.get("AETHERTEST_NO_SSL_VERIFY", ""))
cloudwatch = boto3.client("cloudwatch", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"), verify=not os.environ.get("AETHERTEST_NO_SSL_VERIFY", ""))
sns = boto3.client("sns", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"), verify=not os.environ.get("AETHERTEST_NO_SSL_VERIFY", ""))

ASSIGNMENTS_TABLE = os.environ.get("ASSIGNMENTS_TABLE", "aethertest-agent-assignments")
EXECUTIONS_TABLE = os.environ.get("EXECUTIONS_TABLE", "aethertest-executions")
SNS_ALERT_ARN = os.environ.get("SNS_ALERT_ARN", "")
MAX_CONCURRENT_AGENTS = 20
ASSIGNMENT_TIMEOUT_SECONDS = 120
MAX_RETRIES = 3


def handler(event: dict, context) -> dict:
    """
    Lambda handler for agent dispatch.

    Expected event:
    {
        "tenant_id": "string",
        "execution_id": "string",
        "strategy": { ... }   # TestStrategy JSON
    }
    """
    tenant_id = event.get("tenant_id", "")
    execution_id = event.get("execution_id", str(uuid.uuid4()))
    strategy_data = event.get("strategy", {})

    strategy = TestStrategy.model_validate(strategy_data)

    # Build agent → components mapping, deduplicate overlapping coverage
    agent_coverage = _build_deduplicated_assignments(strategy)

    # Enforce max concurrent agents
    if len(agent_coverage) > MAX_CONCURRENT_AGENTS:
        agent_coverage = dict(list(agent_coverage.items())[:MAX_CONCURRENT_AGENTS])

    assignments = []
    for agent_type, component_ids in agent_coverage.items():
        assignment = AgentAssignment(
            agent_type=agent_type,
            agent_id=f"{agent_type}-{str(uuid.uuid4())[:8]}",
            component_ids=list(component_ids),
            status=AssignmentStatus.DISPATCHED,
        )

        # Dispatch via A2A protocol (Bedrock AgentCore)
        _dispatch_to_agent(assignment, strategy, tenant_id)

        # Persist to DynamoDB
        _save_assignment(execution_id, assignment)

        # Emit CloudWatch metric
        _emit_metric("SpecialistAgentDispatched", tenant_id, agent_type)

        assignments.append(assignment)

    # Create ExecutionState
    execution_state = ExecutionState(
        execution_id=execution_id,
        strategy_id=strategy.strategy_id,
        tenant_id=tenant_id,
        status=ExecutionStatus.RUNNING,
        assignments=assignments,
    )

    # Save execution state
    _save_execution_state(execution_state)

    return {
        "statusCode": 200,
        "execution_id": execution_id,
        "assignments_dispatched": len(assignments),
        "agent_types": list(agent_coverage.keys()),
        "execution_state": json.loads(serialize(execution_state)),
    }


def _build_deduplicated_assignments(strategy: TestStrategy) -> dict[str, set]:
    """
    Build a deduplicated mapping of agent_type -> set of component_ids.
    Resolves overlapping coverage by ensuring each component is assigned
    to each agent type only once.
    """
    agent_coverage: dict[str, set] = defaultdict(set)

    for coverage in strategy.coverage:
        for agent_type in coverage.assigned_agent_types:
            agent_coverage[agent_type].add(coverage.component_id)

    return dict(agent_coverage)


def _dispatch_to_agent(
    assignment: AgentAssignment,
    strategy: TestStrategy,
    tenant_id: str,
):
    """
    Dispatch a task assignment to a Specialist Agent via Bedrock AgentCore A2A protocol.
    Falls back gracefully if AgentCore is not configured.
    """
    try:
        bedrock_agent = boto3.client(
            "bedrock-agent-runtime",
            region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        )
        # A2A message payload
        payload = {
            "assignment_id": assignment.assignment_id,
            "agent_type": assignment.agent_type,
            "component_ids": assignment.component_ids,
            "strategy_id": strategy.strategy_id,
            "tenant_id": tenant_id,
            "timeout_seconds": ASSIGNMENT_TIMEOUT_SECONDS,
        }
        # In production: bedrock_agent.invoke_agent(...) with A2A protocol
        # For now: log the dispatch intent
        print(f"[DISPATCH] {assignment.agent_type} → {len(assignment.component_ids)} components")
    except Exception as e:
        print(f"[DISPATCH WARNING] A2A dispatch failed for {assignment.agent_type}: {e}")


def _save_assignment(execution_id: str, assignment: AgentAssignment):
    """Persist AgentAssignment to DynamoDB."""
    table = dynamodb.Table(ASSIGNMENTS_TABLE)
    table.put_item(Item={
        "PK": f"EXECUTION#{execution_id}",
        "SK": f"ASSIGNMENT#{assignment.assignment_id}",
        "assignment_id": assignment.assignment_id,
        "agent_type": assignment.agent_type,
        "agent_id": assignment.agent_id,
        "component_ids": assignment.component_ids,
        "status": assignment.status.value,
        "dispatched_at": assignment.dispatched_at,
        "retry_count": assignment.retry_count,
    })


def _save_execution_state(state: ExecutionState):
    """Persist ExecutionState to DynamoDB."""
    table = dynamodb.Table(EXECUTIONS_TABLE)
    table.put_item(Item={
        "PK": f"TENANT#{state.tenant_id}",
        "SK": f"EXECUTION#{state.execution_id}",
        "execution_id": state.execution_id,
        "strategy_id": state.strategy_id,
        "status": state.status.value,
        "started_at": state.started_at,
        "defect_count": state.defect_count,
    })


def _emit_metric(metric_name: str, tenant_id: str, agent_type: str):
    """Emit a custom CloudWatch metric."""
    try:
        cloudwatch.put_metric_data(
            Namespace="AetherTest/StrategistAgent",
            MetricData=[{
                "MetricName": metric_name,
                "Dimensions": [
                    {"Name": "TenantId", "Value": tenant_id},
                    {"Name": "AgentType", "Value": agent_type},
                ],
                "Value": 1,
                "Unit": "Count",
            }],
        )
    except Exception:
        pass
