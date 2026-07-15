"""
AetherTest End-to-End Pipeline Test
Tests the full flow: AUT Analysis → Risk Scoring → Strategy Generation
Uses real AWS DynamoDB and S3 — set AWS_PROFILE/AETHERTEST_BUCKET in the environment.

Run with:
    AWS_PROFILE=<your-profile> python3 tests/test_e2e_pipeline.py
"""

import json
import sys
import os
import uuid

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import boto3
from aethertest.config import ARTIFACTS_BUCKET, AWS_REGION

# ── Test Data ─────────────────────────────────────────────────────────────────

TENANT_ID = f"wipro-belron-test"
AUT_ID = "belron-booking-app"
AUT_VERSION = "v2.1.0"

# Simulated Belron booking app structure
AUT_METADATA = {
    "components": [
        {
            "name": "checkout-page",
            "component_type": "ui_page",
            "ui_entry_points": ["/checkout", "/checkout/confirm"],
            "api_surface": [],
            "dependencies": ["payment-service", "cart-service"],
            "metadata": {"team": "frontend", "criticality": "high"}
        },
        {
            "name": "payment-service",
            "component_type": "api_endpoint",
            "api_surface": ["/payment/confirm", "/payment/refund", "/payment/status"],
            "ui_entry_points": [],
            "dependencies": ["fraud-detector", "bank-gateway"],
            "metadata": {"team": "payments", "criticality": "critical"}
        },
        {
            "name": "login-page",
            "component_type": "ui_page",
            "ui_entry_points": ["/login", "/logout", "/forgot-password"],
            "api_surface": [],
            "dependencies": ["auth-service"],
            "metadata": {"team": "identity", "criticality": "high"}
        },
        {
            "name": "booking-form",
            "component_type": "ui_page",
            "ui_entry_points": ["/book", "/book/confirm"],
            "api_surface": [],
            "dependencies": ["availability-service", "pricing-service"],
            "metadata": {"team": "booking", "criticality": "high"}
        },
        {
            "name": "availability-service",
            "component_type": "service",
            "api_surface": ["/availability/check", "/availability/slots"],
            "ui_entry_points": [],
            "dependencies": [],
            "metadata": {"team": "booking", "criticality": "medium"}
        }
    ]
}

# Simulated change set — payment-service and checkout-page were modified
CHANGE_SET = [
    {"component_id": None, "changed_lines": 200, "total_lines": 400},  # payment-service
    {"component_id": None, "changed_lines": 50, "total_lines": 300},   # checkout-page
]


# ── Test Runner ───────────────────────────────────────────────────────────────

def print_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def print_step(step, msg):
    print(f"\n[Step {step}] {msg}")

def print_ok(msg):
    print(f"  ✓ {msg}")

def print_fail(msg):
    print(f"  ✗ {msg}")
    sys.exit(1)


def run_e2e_test():
    print_header("AetherTest End-to-End Pipeline Test")
    print(f"  Tenant:  {TENANT_ID}")
    print(f"  AUT:     {AUT_ID} {AUT_VERSION}")
    print(f"  Region:  {AWS_REGION}")
    print(f"  Bucket:  {ARTIFACTS_BUCKET}")

    # ── Step 1: Verify AWS connectivity ──────────────────────────────────────
    print_step(1, "Verifying AWS connectivity")
    try:
        sts = boto3.client("sts", region_name="us-east-1")
        identity = sts.get_caller_identity()
        print_ok(f"Connected as: {identity['Arn']}")
    except Exception as e:
        print_fail(f"AWS connection failed: {e}")

    # ── Step 2: Verify DynamoDB tables exist ─────────────────────────────────
    print_step(2, "Verifying DynamoDB tables")
    dynamodb = boto3.client("dynamodb", region_name="us-east-1")
    required_tables = [
        "aethertest-executions",
        "aethertest-strategies",
        "aethertest-defect-patterns",
        "aethertest-agent-assignments",
    ]
    for table in required_tables:
        try:
            resp = dynamodb.describe_table(TableName=table)
            status = resp["Table"]["TableStatus"]
            print_ok(f"Table '{table}' — {status}")
        except Exception as e:
            print_fail(f"Table '{table}' not found: {e}")

    # ── Step 3: Verify S3 bucket exists ──────────────────────────────────────
    print_step(3, "Verifying S3 bucket")
    s3 = boto3.client("s3", region_name="us-east-1")
    try:
        s3.head_bucket(Bucket=ARTIFACTS_BUCKET)
        print_ok(f"S3 bucket '{ARTIFACTS_BUCKET}' exists")
    except Exception as e:
        print_fail(f"S3 bucket not found: {e}")

    # ── Step 4: Run AUT Analyzer ─────────────────────────────────────────────
    print_step(4, "Running AUT Analyzer")
    from lambdas.aut_analyzer.handler import handler as analyze

    aut_event = {
        "tenant_id": TENANT_ID,
        "aut_id": AUT_ID,
        "aut_version": AUT_VERSION,
        "aut_metadata": AUT_METADATA,
    }

    try:
        aut_result = analyze(aut_event, None)
        if aut_result.get("statusCode") != 200:
            print_fail(f"AUT Analyzer failed: {aut_result}")

        graph_id = aut_result["graph_id"]
        component_count = aut_result["component_count"]
        s3_key = aut_result["s3_key"]

        print_ok(f"Graph ID: {graph_id}")
        print_ok(f"Components found: {component_count}")
        print_ok(f"Stored in S3: {s3_key}")

        # Verify S3 object was created
        s3.head_object(Bucket=ARTIFACTS_BUCKET, Key=s3_key)
        print_ok("S3 object verified")

        # Verify DynamoDB record was created
        db = boto3.resource("dynamodb", region_name="us-east-1")
        table = db.Table("aethertest-strategies")
        item = table.get_item(Key={
            "PK": f"TENANT#{TENANT_ID}",
            "SK": f"AUT_GRAPH#{graph_id}"
        })
        if "Item" not in item:
            print_fail("DynamoDB record not found for AUT graph")
        print_ok("DynamoDB record verified")

    except Exception as e:
        print_fail(f"AUT Analyzer error: {e}")

    # ── Step 5: Run Risk Scorer ───────────────────────────────────────────────
    print_step(5, "Running Risk Scorer")
    from lambdas.risk_scorer.handler import handler as score

    # Attach component IDs to change set
    graph_components = aut_result["graph"]["components"]
    change_set = []
    for i, comp in enumerate(graph_components[:2]):  # first 2 components changed
        change_set.append({
            "component_id": comp["component_id"],
            "changed_lines": [200, 50][i],
            "total_lines": [400, 300][i],
        })

    score_event = {
        "tenant_id": TENANT_ID,
        "graph": aut_result["graph"],
        "change_set": change_set,
    }

    try:
        score_result = score(score_event, None)
        if score_result.get("statusCode") != 200:
            print_fail(f"Risk Scorer failed: {score_result}")

        risk_scores = score_result["risk_scores"]
        high_count = score_result["high_priority_count"]

        print_ok(f"Risk scores computed for {len(risk_scores)} components")
        print_ok(f"High priority components (score > 80): {high_count}")
        print("\n  Risk Score Breakdown:")
        for r in risk_scores:
            bar = "🔴" if r["risk_score"] > 80 else "🟡" if r["risk_score"] >= 50 else "🟢"
            # Find component name
            name = next((c["name"] for c in graph_components
                        if c["component_id"] == r["component_id"]), r["component_id"][:8])
            print(f"    {bar} {name:<25} Score: {r['risk_score']:>6.1f}  "
                  f"{'(uncharacterized)' if r['is_uncharacterized'] else ''}")

    except Exception as e:
        print_fail(f"Risk Scorer error: {e}")

    # ── Step 6: Run Strategy Generator ───────────────────────────────────────
    print_step(6, "Running Strategy Generator")
    from lambdas.strategy_generator.handler import handler as generate

    strategy_event = {
        "tenant_id": TENANT_ID,
        "aut_id": AUT_ID,
        "aut_version": AUT_VERSION,
        "execution_environment": "staging",
        "triggering_event": "cicd",
        "risk_scores": score_result["risk_scores"],
        "format_markdown": True,
    }

    try:
        strategy_result = generate(strategy_event, None)
        if strategy_result.get("statusCode") != 200:
            print_fail(f"Strategy Generator failed: {strategy_result}")

        strategy_id = strategy_result["strategy_id"]
        strategy_s3_key = strategy_result["s3_key"]
        component_count = strategy_result["component_count"]
        duration = strategy_result["estimated_duration_seconds"]

        print_ok(f"Strategy ID: {strategy_id}")
        print_ok(f"Components in strategy: {component_count}")
        print_ok(f"Estimated test duration: {duration}s ({duration//60}m {duration%60}s)")
        print_ok(f"Stored in S3: {strategy_s3_key}")

        # Verify S3 strategy object
        s3.head_object(Bucket=ARTIFACTS_BUCKET, Key=strategy_s3_key)
        print_ok("Strategy JSON verified in S3")

        # Verify DynamoDB strategy record
        db = boto3.resource("dynamodb", region_name="us-east-1")
        table = db.Table("aethertest-strategies")
        item = table.get_item(Key={
            "PK": f"TENANT#{TENANT_ID}",
            "SK": f"STRATEGY#{strategy_id}#V#1"
        })
        if "Item" not in item:
            print_fail("DynamoDB record not found for strategy")
        print_ok("Strategy record verified in DynamoDB")

        # Print Markdown strategy
        print("\n" + "─"*60)
        print(strategy_result["markdown"])
        print("─"*60)

    except Exception as e:
        import traceback
        traceback.print_exc()
        print_fail(f"Strategy Generator error: {e}")

    # ── Step 7: Verify round-trip serialization ───────────────────────────────
    print_step(7, "Verifying round-trip serialization")
    try:
        from layers.serializer.serializer import serialize, deserialize
        from layers.serializer.models import TestStrategy

        strategy_obj = TestStrategy.model_validate(strategy_result["strategy"])
        serialized = serialize(strategy_obj)
        restored = deserialize(serialized, TestStrategy)

        assert restored.strategy_id == strategy_obj.strategy_id
        assert len(restored.coverage) == len(strategy_obj.coverage)
        print_ok("Round-trip: serialize → deserialize ✓")

        # Verify high-priority components have >= 2 agents
        high_priority = [c for c in restored.coverage if c.risk_score > 80]
        for c in high_priority:
            assert len(c.assigned_agent_types) >= 2, \
                f"Component {c.component_id} has score {c.risk_score} but only {len(c.assigned_agent_types)} agents"
        print_ok(f"High-priority agent assignment rule verified ({len(high_priority)} components)")

    except Exception as e:
        print_fail(f"Serialization verification failed: {e}")

    # ── Final Summary ─────────────────────────────────────────────────────────
    print_header("TEST RESULTS")
    print(f"""
  ✅ AWS Connection         — OK
  ✅ DynamoDB Tables (4)    — OK
  ✅ S3 Bucket              — OK
  ✅ AUT Analysis           — {component_count} components extracted
  ✅ Risk Scoring           — {len(risk_scores)} scores computed, {high_count} high priority
  ✅ Strategy Generation    — {component_count} components planned
  ✅ S3 Persistence         — Strategy JSON saved
  ✅ DynamoDB Persistence   — Records written
  ✅ Round-Trip Integrity   — Serialization verified

  Strategy ID : {strategy_id}
  S3 Key      : {strategy_s3_key}
  Duration    : ~{duration}s estimated

  🎉 All tests passed! The Test Strategist Agent pipeline is working.
    """)


if __name__ == "__main__":
    run_e2e_test()
