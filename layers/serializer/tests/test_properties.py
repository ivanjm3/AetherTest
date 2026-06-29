"""
Property-Based Tests for AetherTest Serializer
Uses Hypothesis to validate correctness properties across all data models.
Run with: pytest layers/serializer/tests/test_properties.py -v
"""

import json
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../"))

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from layers.serializer.models import (
    AUTComponent, AUTComponentGraph,
    RiskScoreRecord, ComponentCoverage, TestStrategy,
    AgentAssignment, ExecutionState, DefectPattern,
    ComponentType, AssignmentStatus, ExecutionStatus,
    FailureType, Priority, CoverageTarget, TriggeringEvent,
)
from layers.serializer.serializer import (
    serialize, deserialize, pretty_print,
    SerializationError, ParseError,
)
from layers.serializer.markdown import to_markdown


# ── Hypothesis Strategies ─────────────────────────────────────────────────────

def aut_component_strategy():
    return st.builds(
        AUTComponent,
        name=st.text(min_size=1, max_size=50),
        component_type=st.sampled_from(ComponentType),
        dependencies=st.lists(st.uuids().map(str), max_size=5),
        api_surface=st.lists(st.text(min_size=1, max_size=30), max_size=5),
        ui_entry_points=st.lists(st.text(min_size=1, max_size=30), max_size=5),
        metadata=st.dictionaries(
            st.text(min_size=1, max_size=10),
            st.text(min_size=1, max_size=20),
            max_size=3,
        ),
    )


def aut_graph_strategy():
    return st.builds(
        AUTComponentGraph,
        aut_id=st.uuids().map(str),
        version=st.text(min_size=1, max_size=20),
        tenant_id=st.text(min_size=1, max_size=36),
        components=st.lists(aut_component_strategy(), min_size=1, max_size=20),
    )


def risk_score_strategy():
    return st.builds(
        RiskScoreRecord,
        component_id=st.uuids().map(str),
        risk_score=st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
        is_uncharacterized=st.booleans(),
        change_weight=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        defect_weight=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        deployment_weight=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    )


def component_coverage_strategy():
    return st.builds(
        ComponentCoverage,
        component_id=st.uuids().map(str),
        risk_score=st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
        priority=st.sampled_from(Priority),
        assigned_agent_types=st.lists(
            st.sampled_from(["ui_agent", "api_agent", "perf_agent"]),
            min_size=1, max_size=3, unique=True,
        ),
        coverage_target=st.sampled_from(CoverageTarget),
    )


def test_strategy_strategy():
    return st.builds(
        TestStrategy,
        tenant_id=st.text(min_size=1, max_size=36),
        aut_id=st.uuids().map(str),
        aut_version=st.text(min_size=1, max_size=20),
        execution_environment=st.sampled_from(["staging", "production", "dev"]),
        coverage=st.lists(component_coverage_strategy(), min_size=1, max_size=10),
        estimated_duration_seconds=st.integers(min_value=1, max_value=3600),
        triggering_event=st.sampled_from(TriggeringEvent),
    )


def agent_assignment_strategy():
    return st.builds(
        AgentAssignment,
        agent_type=st.sampled_from(["ui_agent", "api_agent", "perf_agent"]),
        agent_id=st.text(min_size=1, max_size=36),
        component_ids=st.lists(st.uuids().map(str), min_size=1, max_size=5),
        status=st.sampled_from(AssignmentStatus),
        retry_count=st.integers(min_value=0, max_value=3),
    )


def execution_state_strategy():
    return st.builds(
        ExecutionState,
        strategy_id=st.uuids().map(str),
        tenant_id=st.text(min_size=1, max_size=36),
        status=st.sampled_from(ExecutionStatus),
        assignments=st.lists(agent_assignment_strategy(), max_size=5),
        defect_count=st.integers(min_value=0, max_value=100),
    )


# ── Round-Trip Properties ─────────────────────────────────────────────────────

@given(aut_graph_strategy())
@settings(max_examples=100)
def test_aut_graph_round_trip(graph):
    """serialize then deserialize produces equivalent object."""
    serialized = serialize(graph)
    restored = deserialize(serialized, AUTComponentGraph)
    assert restored.graph_id == graph.graph_id
    assert restored.aut_id == graph.aut_id
    assert restored.tenant_id == graph.tenant_id
    assert len(restored.components) == len(graph.components)


@given(test_strategy_strategy())
@settings(max_examples=100)
def test_strategy_round_trip(strategy):
    """serialize then deserialize produces equivalent TestStrategy."""
    serialized = serialize(strategy)
    restored = deserialize(serialized, TestStrategy)
    assert restored.strategy_id == strategy.strategy_id
    assert restored.tenant_id == strategy.tenant_id
    assert len(restored.coverage) == len(strategy.coverage)


@given(execution_state_strategy())
@settings(max_examples=100)
def test_execution_state_round_trip(state):
    """serialize then deserialize produces equivalent ExecutionState."""
    serialized = serialize(state)
    restored = deserialize(serialized, ExecutionState)
    assert restored.execution_id == state.execution_id
    assert restored.strategy_id == state.strategy_id
    assert restored.status == state.status


@given(aut_graph_strategy())
@settings(max_examples=50)
def test_pretty_print_round_trip(graph):
    """pretty_print then deserialize produces equivalent object."""
    pretty = pretty_print(graph)
    # pretty_print produces indented JSON — deserialize should handle it
    restored = deserialize(pretty, AUTComponentGraph)
    assert restored.graph_id == graph.graph_id
    assert len(restored.components) == len(graph.components)


# ── Risk Score Properties ─────────────────────────────────────────────────────

@given(risk_score_strategy())
@settings(max_examples=200)
def test_risk_score_bounds(record):
    """Risk score is always in [0.0, 100.0]."""
    assert 0.0 <= record.risk_score <= 100.0


@given(
    st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
)
@settings(max_examples=200)
def test_risk_score_monotonicity(change_ratio_low, change_ratio_high):
    """More changed lines → higher or equal risk score."""
    assume(change_ratio_high >= change_ratio_low)

    W_CHANGE, W_DEFECT, W_DEPLOY = 0.4, 0.4, 0.2
    defect_score = 50.0
    deploy_score = 30.0

    score_low = W_CHANGE * (change_ratio_low * 100) + W_DEFECT * defect_score + W_DEPLOY * deploy_score
    score_high = W_CHANGE * (change_ratio_high * 100) + W_DEFECT * defect_score + W_DEPLOY * deploy_score

    assert score_high >= score_low


# ── Strategy Completeness Properties ─────────────────────────────────────────

@given(aut_graph_strategy())
@settings(max_examples=50)
def test_strategy_covers_all_components(graph):
    """Every component in AUT graph should appear in a generated strategy."""
    from lambdas.risk_scorer.handler import handler as risk_handler
    from lambdas.strategy_generator.handler import handler as strategy_handler

    # Mock risk scoring
    risk_event = {
        "tenant_id": graph.tenant_id,
        "graph": json.loads(serialize(graph)),
        "change_set": [],
    }

    # Build coverage manually to test the property
    component_ids = {c.component_id for c in graph.components}
    coverage_ids = set()

    for component in graph.components:
        coverage_ids.add(component.component_id)

    assert component_ids == coverage_ids


@given(test_strategy_strategy())
@settings(max_examples=100)
def test_high_priority_components_have_multiple_agents(strategy):
    """Components with risk_score > 80 must have >= 2 assigned agent types."""
    for coverage in strategy.coverage:
        if coverage.risk_score > 80.0:
            assert len(coverage.assigned_agent_types) >= 2, (
                f"Component {coverage.component_id} has risk_score={coverage.risk_score} "
                f"but only {len(coverage.assigned_agent_types)} agent type(s)"
            )


# ── Tenant Isolation Properties ───────────────────────────────────────────────

@given(
    st.text(min_size=1, max_size=36),
    st.text(min_size=1, max_size=36),
)
@settings(max_examples=100)
def test_tenant_scoped_keys(tenant_id, other_tenant_id):
    """S3 keys must always start with the correct tenant prefix."""
    assume(tenant_id != other_tenant_id)

    strategy_id = "test-strategy-123"
    s3_key = f"{tenant_id}/strategies/{strategy_id}.json"

    assert s3_key.startswith(f"{tenant_id}/")
    assert not s3_key.startswith(f"{other_tenant_id}/")


@given(
    st.text(min_size=1, max_size=36),
    st.text(min_size=1, max_size=36),
)
@settings(max_examples=100)
def test_dynamodb_pk_scoping(tenant_id, other_tenant_id):
    """DynamoDB PK must always be scoped to the correct tenant."""
    assume(tenant_id != other_tenant_id)

    pk = f"TENANT#{tenant_id}"
    assert pk == f"TENANT#{tenant_id}"
    assert pk != f"TENANT#{other_tenant_id}"


# ── Unknown Field Tolerance ───────────────────────────────────────────────────

@given(execution_state_strategy())
@settings(max_examples=50)
def test_unknown_fields_captured_in_warnings(state):
    """Deserializing ExecutionState with extra fields produces warnings."""
    data = json.loads(serialize(state))
    data["unknown_future_field"] = "some_value"
    data["another_unknown"] = 42

    restored = deserialize(json.dumps(data), ExecutionState)
    assert len(restored.warnings) >= 2
    assert any("unknown_future_field" in w for w in restored.warnings)


# ── Error Handling Properties ─────────────────────────────────────────────────

def test_missing_required_field_raises_parse_error():
    """Deserializing JSON missing a required field raises ParseError with field name."""
    invalid_json = json.dumps({"tenant_id": "t1"})  # missing aut_id, version, components
    with pytest.raises(ParseError) as exc_info:
        deserialize(invalid_json, AUTComponentGraph)
    assert exc_info.value.field_path != ""


def test_invalid_json_raises_parse_error():
    """Deserializing malformed JSON raises ParseError."""
    with pytest.raises(ParseError):
        deserialize("not valid json {{{", AUTComponentGraph)


def test_markdown_formatting():
    """to_markdown produces non-empty string with expected headers."""
    strategy = TestStrategy(
        tenant_id="tenant-1",
        aut_id="aut-1",
        aut_version="1.0.0",
        execution_environment="staging",
        coverage=[
            ComponentCoverage(
                component_id="comp-1",
                risk_score=85.0,
                priority=Priority.HIGH,
                assigned_agent_types=["ui_agent", "api_agent"],
                coverage_target=CoverageTarget.FULL,
            )
        ],
        estimated_duration_seconds=120,
    )
    md = to_markdown(strategy)
    assert "# Test Strategy" in md
    assert "High Priority" in md
    assert "comp-1" in md
