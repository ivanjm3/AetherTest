"""
AetherTest Bedrock Client
Centralised connection module for all Amazon Bedrock service calls.
Used by all Lambda handlers and agent components.
"""

import json
import os
import boto3
from botocore.config import Config

# ── Configuration ────────────────────────────────────────────────────────────

AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

# Claude Sonnet 4 — primary reasoning model for the Test Strategist Agent
# Uses cross-region inference profile (required for on-demand invocation)
CLAUDE_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID",
    "us.anthropic.claude-sonnet-4-20250514-v1:0"
)

# Retry config for transient Bedrock errors
BOTO_CONFIG = Config(
    region_name=AWS_REGION,
    retries={"max_attempts": 3, "mode": "adaptive"},
)

# SSL verification — disable behind corporate proxies
VERIFY_SSL = os.environ.get("AETHERTEST_NO_SSL_VERIFY", "").lower() not in ("1", "true", "yes")


# ── Client Factory ────────────────────────────────────────────────────────────

def get_bedrock_client():
    """Return a boto3 client for Amazon Bedrock (model management)."""
    return boto3.client("bedrock", config=BOTO_CONFIG)


def get_bedrock_runtime_client():
    """Return a boto3 client for Amazon Bedrock Runtime (model invocation)."""
    return boto3.client("bedrock-runtime", config=BOTO_CONFIG)


def get_bedrock_agent_client():
    """Return a boto3 client for Amazon Bedrock Agent Runtime (AgentCore / A2A)."""
    return boto3.client("bedrock-agent-runtime", config=BOTO_CONFIG)


def get_bedrock_knowledge_base_client():
    """Return a boto3 client for Amazon Bedrock Agent (Knowledge Base management)."""
    return boto3.client("bedrock-agent", config=BOTO_CONFIG)


# ── Core Invocation ───────────────────────────────────────────────────────────

def invoke_claude(
    prompt: str,
    system_prompt: str = None,
    max_tokens: int = 4096,
    temperature: float = 0.0,
) -> str:
    """
    Invoke Claude Sonnet 4 via Amazon Bedrock and return the text response.

    Args:
        prompt: The user message to send to Claude.
        system_prompt: Optional system-level instructions for the model.
        max_tokens: Maximum tokens in the response.
        temperature: Sampling temperature (0.0 = deterministic).

    Returns:
        The model's text response as a string.

    Raises:
        BedrockInvocationError: If the model call fails after retries.
    """
    client = get_bedrock_runtime_client()

    messages = [{"role": "user", "content": prompt}]

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
    }

    if system_prompt:
        body["system"] = system_prompt

    try:
        response = client.invoke_model(
            modelId=CLAUDE_MODEL_ID,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )
        result = json.loads(response["body"].read())
        return result["content"][0]["text"]

    except client.exceptions.AccessDeniedException as e:
        raise BedrockInvocationError(
            f"Access denied to model {CLAUDE_MODEL_ID}. "
            "Check IAM permissions and model access in AWS Console."
        ) from e
    except client.exceptions.ValidationException as e:
        raise BedrockInvocationError(f"Invalid request to Bedrock: {e}") from e
    except Exception as e:
        raise BedrockInvocationError(f"Bedrock invocation failed: {e}") from e


def invoke_claude_with_tools(
    prompt: str,
    tools: list[dict],
    system_prompt: str = None,
    max_tokens: int = 4096,
) -> dict:
    """
    Invoke Claude with tool definitions (for agentic tool-use workflows).

    Args:
        prompt: The user message.
        tools: List of tool definitions in Anthropic tool format.
        system_prompt: Optional system instructions.
        max_tokens: Maximum tokens in the response.

    Returns:
        Full response dict including tool_use blocks if the model calls a tool.
    """
    client = get_bedrock_runtime_client()

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": 0.0,
        "tools": tools,
        "messages": [{"role": "user", "content": prompt}],
    }

    if system_prompt:
        body["system"] = system_prompt

    try:
        response = client.invoke_model(
            modelId=CLAUDE_MODEL_ID,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )
        return json.loads(response["body"].read())

    except Exception as e:
        raise BedrockInvocationError(f"Bedrock tool-use invocation failed: {e}") from e


# ── Knowledge Base ────────────────────────────────────────────────────────────

def query_knowledge_base(
    knowledge_base_id: str,
    query: str,
    tenant_id: str,
    max_results: int = 5,
) -> list[dict]:
    """
    Query a Bedrock Knowledge Base with tenant-scoped filtering.

    Args:
        knowledge_base_id: The Bedrock Knowledge Base ID.
        query: Natural language query string.
        tenant_id: Tenant identifier for metadata filtering.
        max_results: Maximum number of results to return.

    Returns:
        List of retrieval results with text and metadata.
    """
    client = get_bedrock_agent_client()

    try:
        response = client.retrieve(
            knowledgeBaseId=knowledge_base_id,
            retrievalQuery={"text": query},
            retrievalConfiguration={
                "vectorSearchConfiguration": {
                    "numberOfResults": max_results,
                    "filter": {
                        "equals": {
                            "key": "tenant_id",
                            "value": tenant_id,
                        }
                    },
                }
            },
        )
        return response.get("retrievalResults", [])

    except Exception as e:
        raise BedrockKnowledgeBaseError(
            f"Knowledge Base query failed for tenant {tenant_id}: {e}"
        ) from e


def ingest_to_knowledge_base(
    knowledge_base_id: str,
    data_source_id: str,
) -> str:
    """
    Trigger a Knowledge Base ingestion job to sync new documents.

    Returns:
        The ingestion job ID.
    """
    client = get_bedrock_knowledge_base_client()

    try:
        response = client.start_ingestion_job(
            knowledgeBaseId=knowledge_base_id,
            dataSourceId=data_source_id,
        )
        return response["ingestionJob"]["ingestionJobId"]

    except Exception as e:
        raise BedrockKnowledgeBaseError(f"Knowledge Base ingestion failed: {e}") from e


# ── Health Check ──────────────────────────────────────────────────────────────

def verify_bedrock_connection() -> dict:
    """
    Verify that Bedrock is reachable and Claude is accessible.
    Call this at agent startup to fail fast on misconfiguration.

    Returns:
        Dict with 'status', 'region', 'model_id', and 'available_claude_models'.
    """
    try:
        client = get_bedrock_client()
        models = client.list_foundation_models()
        claude_models = [
            m["modelId"] for m in models["modelSummaries"]
            if "claude" in m["modelId"].lower()
        ]

        # Quick smoke test — invoke Claude with a minimal prompt
        response = invoke_claude("Reply with the single word: ready", max_tokens=10)
        is_responsive = "ready" in response.lower()

        return {
            "status": "connected" if is_responsive else "degraded",
            "region": AWS_REGION,
            "model_id": CLAUDE_MODEL_ID,
            "available_claude_models": claude_models,
            "smoke_test_passed": is_responsive,
        }

    except BedrockInvocationError as e:
        return {
            "status": "error",
            "region": AWS_REGION,
            "model_id": CLAUDE_MODEL_ID,
            "error": str(e),
        }
    except Exception as e:
        return {
            "status": "unreachable",
            "region": AWS_REGION,
            "error": str(e),
        }


# ── Exceptions ────────────────────────────────────────────────────────────────

class BedrockInvocationError(Exception):
    """Raised when a Bedrock model invocation fails."""
    pass


class BedrockKnowledgeBaseError(Exception):
    """Raised when a Bedrock Knowledge Base operation fails."""
    pass
