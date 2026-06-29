"""
AetherTest Serializer
Handles JSON serialization, deserialization, and pretty-printing
for all AetherTest data models with round-trip integrity guarantees.
"""

from __future__ import annotations
import json
import re
from typing import Type, TypeVar, Union

from pydantic import ValidationError

from .models import (
    AUTComponentGraph,
    TestStrategy,
    ExecutionState,
    DefectPattern,
    RiskScoreRecord,
)

T = TypeVar("T", AUTComponentGraph, TestStrategy, ExecutionState, DefectPattern, RiskScoreRecord)

# Fields to scrub from any log output (credential guard)
_SENSITIVE_PATTERN = re.compile(
    r"(password|secret|token|key|credential|api_key|access_key)", re.IGNORECASE
)


# ── Exceptions ────────────────────────────────────────────────────────────────

class SerializationError(Exception):
    """Raised when serialization of a model object fails."""
    pass


class ParseError(Exception):
    """Raised when deserialization fails due to schema violation."""
    def __init__(self, message: str, field_path: str = ""):
        self.field_path = field_path
        super().__init__(message)


# ── Core Functions ────────────────────────────────────────────────────────────

def serialize(obj: T) -> str:
    """
    Serialize a model object to a compact JSON string.

    Args:
        obj: Any AetherTest Pydantic model instance.

    Returns:
        Compact JSON string representation.

    Raises:
        SerializationError: If serialization fails.
    """
    try:
        return obj.model_dump_json(exclude_none=False)
    except Exception as e:
        raise SerializationError(f"Failed to serialize {type(obj).__name__}: {e}") from e


def deserialize(json_str: str, target_type: Type[T]) -> T:
    """
    Deserialize a JSON string into a typed model object.

    For ExecutionState, unknown fields are captured in the warnings list
    rather than raising an error (forward-compatibility).

    Args:
        json_str: JSON string to deserialize.
        target_type: The target Pydantic model class.

    Returns:
        Typed model instance.

    Raises:
        ParseError: If the JSON does not conform to the schema,
                    with field_path identifying the offending field.
    """
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ParseError(f"Invalid JSON: {e}", field_path="<root>") from e

    # For ExecutionState: capture unknown fields in warnings
    if target_type is ExecutionState:
        known_fields = set(ExecutionState.model_fields.keys())
        unknown = [k for k in data.keys() if k not in known_fields and k != "warnings"]
        if unknown:
            data.setdefault("warnings", [])
            data["warnings"].extend([f"Unknown field: '{f}'" for f in unknown])

    try:
        return target_type.model_validate(data)
    except ValidationError as e:
        errors = e.errors()
        if errors:
            first = errors[0]
            field_path = ".".join(str(p) for p in first["loc"])
            msg = first["msg"]
            raise ParseError(
                f"Schema validation failed at '{field_path}': {msg}",
                field_path=field_path,
            ) from e
        raise ParseError(f"Schema validation failed: {e}") from e


def pretty_print(obj: T) -> str:
    """
    Format a model object as indented, human-readable JSON.

    Args:
        obj: Any AetherTest Pydantic model instance.

    Returns:
        JSON string with 4-space indentation and sorted keys.
    """
    try:
        data = obj.model_dump()
        return json.dumps(data, indent=4, sort_keys=True, default=str)
    except Exception as e:
        raise SerializationError(f"Failed to pretty-print {type(obj).__name__}: {e}") from e


def scrub_sensitive(data: dict) -> dict:
    """
    Remove sensitive fields from a dict before logging.
    Strips any key matching password/secret/token/key/credential patterns.

    Args:
        data: Dictionary to scrub.

    Returns:
        New dictionary with sensitive values replaced by '***REDACTED***'.
    """
    result = {}
    for k, v in data.items():
        if _SENSITIVE_PATTERN.search(str(k)):
            result[k] = "***REDACTED***"
        elif isinstance(v, dict):
            result[k] = scrub_sensitive(v)
        else:
            result[k] = v
    return result
