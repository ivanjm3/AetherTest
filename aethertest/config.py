"""
AetherTest centralized configuration.
Single source of truth for bucket/table names and region — every Lambda handler,
script, and the API server import from here instead of hardcoding defaults.

No AWS account ID or profile name is baked in. Set these via environment
variables (locally via `.env`/shell export, in Lambda/App Runner via the
runtime environment configuration).
"""

from __future__ import annotations
import os

AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
VERIFY_SSL = os.environ.get("AETHERTEST_NO_SSL_VERIFY", "").lower() not in ("1", "true", "yes")

BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0"
)

ARTIFACTS_BUCKET = os.environ.get("AETHERTEST_BUCKET", "aethertest-artifacts")
STRATEGIES_TABLE = os.environ.get("STRATEGIES_TABLE", "aethertest-strategies")
ASSIGNMENTS_TABLE = os.environ.get("ASSIGNMENTS_TABLE", "aethertest-agent-assignments")
DEFECT_PATTERNS_TABLE = os.environ.get("DEFECT_PATTERNS_TABLE", "aethertest-defect-patterns")
EXECUTIONS_TABLE = os.environ.get("EXECUTIONS_TABLE", "aethertest-executions")
IDEMPOTENCY_TABLE = os.environ.get("IDEMPOTENCY_TABLE", "aethertest-idempotency")

ATHENA_DATABASE = os.environ.get("ATHENA_DATABASE", "default")
ATHENA_OUTPUT_BUCKET = os.environ.get("ATHENA_OUTPUT_BUCKET", "aethertest-athena-results")
ATHENA_WORKGROUP = os.environ.get("ATHENA_WORKGROUP", "primary")
