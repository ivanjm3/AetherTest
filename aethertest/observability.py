"""
Cross-cutting reliability/observability for every agent Lambda handler.

`instrument_handler` wraps a plain `handler(event, context)` function and adds,
in one place instead of copy-pasted into every agent:

  - Structured JSON logs (start/end/error) — CloudWatch Logs ingests Lambda
    stdout directly, so a JSON line per log event is enough for CloudWatch
    Logs Insights queries without any extra agent.
  - CloudWatch custom metrics (invocation count, duration, error count) under
    the `AetherTest/Agents` namespace, dimensioned by agent name.
  - Retry with exponential backoff on transient AWS errors (throttling,
    5xx) — NOT on validation/business errors, which fail fast.
  - Idempotency: if the event carries an `execution_id`, the result of a
    successful run is cached in DynamoDB keyed on (agent, execution_id) so a
    Step Functions retry (or an at-least-once Lambda re-invoke) replays the
    cached result instead of re-running side effects (double S3 writes,
    double Bedrock spend, double DynamoDB records).
"""

from __future__ import annotations
import functools
import json
import logging
import time
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

from aethertest.config import AWS_REGION, VERIFY_SSL

RETRIABLE_ERROR_CODES = {
    "ThrottlingException",
    "TooManyRequestsException",
    "ProvisionedThroughputExceededException",
    "RequestLimitExceeded",
    "InternalServerError",
    "ServiceUnavailable",
    "ServiceUnavailableException",
}

_logger = logging.getLogger("aethertest")
if not _logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)

_cloudwatch = None
_dynamodb = None


def _cw():
    global _cloudwatch
    if _cloudwatch is None:
        _cloudwatch = boto3.client("cloudwatch", region_name=AWS_REGION, verify=VERIFY_SSL)
    return _cloudwatch


def _ddb():
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION, verify=VERIFY_SSL)
    return _dynamodb


def log_event(level: str, message: str, **fields):
    """Emit one structured JSON log line. CloudWatch Logs picks up Lambda stdout."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "message": message,
        **fields,
    }
    line = json.dumps(record, default=str)
    if level == "ERROR":
        _logger.error(line)
    elif level == "WARNING":
        _logger.warning(line)
    else:
        _logger.info(line)


def emit_metric(metric_name: str, value: float = 1, unit: str = "Count", **dimensions):
    """Best-effort CloudWatch custom metric. Never raises — a metrics outage must not fail the pipeline."""
    try:
        _cw().put_metric_data(
            Namespace="AetherTest/Agents",
            MetricData=[{
                "MetricName": metric_name,
                "Dimensions": [{"Name": k, "Value": str(v)} for k, v in dimensions.items()],
                "Value": value,
                "Unit": unit,
            }],
        )
    except Exception as e:
        log_event("WARNING", "metric_emit_failed", metric_name=metric_name, error=str(e))


def retry_call(fn, *args, max_attempts: int = 3, base_delay: float = 0.5, **kwargs):
    """Call fn(*args, **kwargs) with exponential backoff on transient AWS errors."""
    attempt = 0
    while True:
        attempt += 1
        try:
            return fn(*args, **kwargs)
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code not in RETRIABLE_ERROR_CODES or attempt >= max_attempts:
                raise
            delay = base_delay * (2 ** (attempt - 1))
            log_event("WARNING", "retrying_after_transient_error", error_code=code, attempt=attempt, delay_seconds=delay)
            time.sleep(delay)


def _idempotency_key(agent_name: str, execution_id: str) -> dict:
    return {"PK": f"IDEMPOTENCY#{agent_name}", "SK": f"EXECUTION#{execution_id}"}


def _load_cached_result(table_name: str, agent_name: str, execution_id: str) -> dict | None:
    table = _ddb().Table(table_name)
    item = table.get_item(Key=_idempotency_key(agent_name, execution_id)).get("Item")
    if item and "result_json" in item:
        return json.loads(item["result_json"])
    return None


def _store_result(table_name: str, agent_name: str, execution_id: str, result: dict):
    table = _ddb().Table(table_name)
    table.put_item(Item={
        **_idempotency_key(agent_name, execution_id),
        "result_json": json.dumps(result, default=str),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "ttl": int(time.time()) + 7 * 24 * 3600,
    })


def instrument_handler(agent_name: str, *, idempotency_table: str | None = None, max_attempts: int = 3):
    """
    Decorator for a Lambda `handler(event, context)`. Adds structured logging,
    CloudWatch metrics, retry-with-backoff, and (when the event carries an
    `execution_id`) idempotent replay of the cached result.

    idempotency_table defaults to aethertest.config.EXECUTIONS_TABLE's sibling
    idempotency table name if not supplied.
    """
    from aethertest.config import IDEMPOTENCY_TABLE
    table_name = idempotency_table or IDEMPOTENCY_TABLE

    def decorator(fn):
        @functools.wraps(fn)
        def wrapped(event: dict, context):
            invocation_id = str(uuid.uuid4())[:8]
            execution_id = (event or {}).get("execution_id")
            tenant_id = (event or {}).get("tenant_id", "")

            log_event("INFO", "agent_invocation_start", agent=agent_name,
                      invocation_id=invocation_id, execution_id=execution_id, tenant_id=tenant_id)

            if execution_id:
                try:
                    cached = _load_cached_result(table_name, agent_name, execution_id)
                except Exception as e:
                    cached = None
                    log_event("WARNING", "idempotency_lookup_failed", agent=agent_name, error=str(e))
                if cached is not None:
                    log_event("INFO", "agent_invocation_replayed_cached_result", agent=agent_name,
                              invocation_id=invocation_id, execution_id=execution_id)
                    emit_metric("AgentIdempotentReplay", agent=agent_name)
                    return cached

            start = time.monotonic()
            try:
                result = retry_call(fn, event, context, max_attempts=max_attempts)
                duration_ms = round((time.monotonic() - start) * 1000, 1)

                log_event("INFO", "agent_invocation_succeeded", agent=agent_name,
                          invocation_id=invocation_id, execution_id=execution_id,
                          duration_ms=duration_ms, status_code=result.get("statusCode") if isinstance(result, dict) else None)
                emit_metric("AgentInvocationSucceeded", agent=agent_name)
                emit_metric("AgentInvocationDurationMs", value=duration_ms, unit="Milliseconds", agent=agent_name)

                if execution_id and isinstance(result, dict) and result.get("statusCode") == 200:
                    try:
                        _store_result(table_name, agent_name, execution_id, result)
                    except Exception as e:
                        log_event("WARNING", "idempotency_store_failed", agent=agent_name, error=str(e))

                return result

            except Exception as e:
                duration_ms = round((time.monotonic() - start) * 1000, 1)
                log_event("ERROR", "agent_invocation_failed", agent=agent_name,
                          invocation_id=invocation_id, execution_id=execution_id,
                          duration_ms=duration_ms, error=str(e), error_type=type(e).__name__)
                emit_metric("AgentInvocationFailed", agent=agent_name)
                raise

        return wrapped
    return decorator
