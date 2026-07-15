"""
AetherTest Full Agent Test
Complete end-to-end flow:
  1. AUT Analysis
  2. Risk Scoring
  3. Strategy Generation
  4. Test Case Generation (Claude writes actual test cases)
  5. Test Execution (Claude simulates running them)
  6. Failure Triage (Claude classifies failures)
  7. Learning Update (stores outcomes for next cycle)

Run with:
    AWS_PROFILE=<your-profile> python3 tests/test_full_agent.py
"""

import json
import sys
import os
import uuid

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from aethertest.config import ARTIFACTS_BUCKET

import boto3

# ── Helpers ───────────────────────────────────────────────────────────────────

def banner(title):
    print(f"\n{'═'*65}")
    print(f"  {title}")
    print(f"{'═'*65}")

def step(n, title):
    print(f"\n{'─'*65}")
    print(f"  STEP {n}: {title}")
    print(f"{'─'*65}")

def ok(msg):   print(f"  ✅ {msg}")
def info(msg): print(f"  ℹ  {msg}")
def warn(msg): print(f"  ⚠️  {msg}")
def fail(msg):
    print(f"  ❌ {msg}")
    sys.exit(1)


# ── Test Configuration ────────────────────────────────────────────────────────

TENANT_ID = "wipro-belron-demo"
AUT_ID = "belron-booking-app"
AUT_VERSION = "v2.3.0"
EXECUTION_ID = str(uuid.uuid4())

# Belron booking app — simulating a deployment where payment-service changed
AUT_METADATA = {
    "components": [
        {
            "name": "payment-service",
            "component_type": "api_endpoint",
            "api_surface": [
                "/api/payment/confirm",
                "/api/payment/refund",
                "/api/payment/status/{id}",
                "/api/payment/methods"
            ],
            "ui_entry_points": [],
            "dependencies": ["fraud-detector", "bank-gateway"],
            "metadata": {"team": "payments", "criticality": "critical"}
        },
        {
            "name": "checkout-page",
            "component_type": "ui_page",
            "api_surface": [],
            "ui_entry_points": ["/checkout", "/checkout/review", "/checkout/confirm"],
            "dependencies": ["payment-service", "cart-service"],
            "metadata": {"team": "frontend", "criticality": "high"}
        },
        {
            "name": "login-page",
            "component_type": "ui_page",
            "api_surface": [],
            "ui_entry_points": ["/login", "/logout"],
            "dependencies": ["auth-service"],
            "metadata": {"team": "identity", "criticality": "medium"}
        },
    ]
}

# payment-service changed significantly in this deployment
CHANGE_SET_COMPONENTS = ["payment-service", "checkout-page"]

# Simulate payment-service failing during test execution
SIMULATE_FAILURES = ["payment-service"]


# ── Main Test Flow ────────────────────────────────────────────────────────────

def run():
    banner("AetherTest — Full Agent Demonstration")
    print(f"""
  Scenario: Developer deployed v2.3.0 of Belron booking app.
  Payment service was modified (200 lines changed).
  The Test Strategist Agent will:
    1. Analyze the app structure
    2. Identify payment-service as HIGH risk
    3. Generate a test strategy
    4. Use Claude to write actual test cases
    5. Execute the tests
    6. Detect a failure in payment-service
    7. Triage it as a genuine defect
    8. Block the deployment
  """)

    # ── Step 1: AUT Analysis ──────────────────────────────────────────────────
    step(1, "AUT Structure Analysis")
    info("Agent is reading the Belron booking app structure...")

    from lambdas.aut_analyzer.handler import handler as analyze
    aut_result = analyze({
        "tenant_id": TENANT_ID,
        "aut_id": AUT_ID,
        "aut_version": AUT_VERSION,
        "aut_metadata": AUT_METADATA,
    }, None)

    if aut_result.get("statusCode") != 200:
        fail(f"AUT Analysis failed: {aut_result}")

    graph = aut_result["graph"]
    components = graph["components"]
    ok(f"Extracted {len(components)} components from Belron app")
    for c in components:
        info(f"  → {c['name']} ({c['component_type']})")
    ok(f"AUT graph saved to S3: {aut_result['s3_key']}")

    # ── Step 2: Risk Scoring ──────────────────────────────────────────────────
    step(2, "Risk-Based Prioritization")
    info("Agent is computing risk scores based on change data...")

    from lambdas.risk_scorer.handler import handler as score

    # Map changed component names to IDs
    change_set = []
    for comp in components:
        if comp["name"] in CHANGE_SET_COMPONENTS:
            lines = 200 if comp["name"] == "payment-service" else 50
            change_set.append({
                "component_id": comp["component_id"],
                "changed_lines": lines,
                "total_lines": 400,
            })

    score_result = score({
        "tenant_id": TENANT_ID,
        "graph": graph,
        "change_set": change_set,
        "deploy_frequency": {
            comp["component_id"]: 8
            for comp in components
            if comp["name"] == "payment-service"
        },
    }, None)

    risk_scores = score_result["risk_scores"]
    ok(f"Risk scores computed for {len(risk_scores)} components:")
    for r in risk_scores:
        name = next((c["name"] for c in components if c["component_id"] == r["component_id"]), "unknown")
        icon = "🔴 HIGH  " if r["risk_score"] > 80 else "🟡 MEDIUM" if r["risk_score"] >= 50 else "🟢 LOW   "
        unchar = " (no history yet)" if r["is_uncharacterized"] else ""
        info(f"  {icon}  {name:<25} Score: {r['risk_score']:>5.1f}{unchar}")

    # ── Step 3: Strategy Generation ───────────────────────────────────────────
    step(3, "Test Strategy Generation")
    info("Agent is generating the test strategy...")

    from lambdas.strategy_generator.handler import handler as generate
    strategy_result = generate({
        "tenant_id": TENANT_ID,
        "aut_id": AUT_ID,
        "aut_version": AUT_VERSION,
        "execution_environment": "staging",
        "triggering_event": "cicd",
        "risk_scores": risk_scores,
        "format_markdown": True,
    }, None)

    strategy = strategy_result["strategy"]
    ok(f"Strategy generated: {strategy_result['strategy_id']}")
    ok(f"Estimated test duration: {strategy_result['estimated_duration_seconds']}s")
    ok(f"Strategy saved to S3: {strategy_result['s3_key']}")
    print()
    print(strategy_result["markdown"])

    # ── Step 4: Test Case Generation ──────────────────────────────────────────
    step(4, "Test Case Generation (Claude writing test cases)")
    info("Claude Sonnet 4 is writing actual test cases for each component...")
    info("This may take 20-30 seconds...")

    from lambdas.test_case_generator.handler import handler as generate_tests
    test_gen_result = generate_tests({
        "tenant_id": TENANT_ID,
        "strategy": strategy,
        "aut_graph": graph,
    }, None)

    test_suite = test_gen_result["test_suite"]
    total_tests = test_gen_result["total_test_cases"]

    ok(f"Claude generated {total_tests} test cases!")
    ok(f"Test suite saved to S3: {test_gen_result['s3_key']}")
    print()
    info("Generated test cases by component:")
    for summary in test_gen_result["generation_summary"]:
        info(f"  → {summary['component']:<25} {summary['test_cases_generated']} tests ({summary['priority']} priority)")

    # Show sample test cases
    print()
    info("Sample test cases generated by Claude:")
    for tc in test_suite["test_cases"][:3]:
        print(f"""
  📋 {tc.get('test_name', 'N/A')}
     Component : {tc.get('component', 'N/A')}
     Type      : {tc.get('test_type', 'N/A')}
     Priority  : {tc.get('priority', 'N/A')}
     Description: {tc.get('description', 'N/A')}
     Steps     : {' → '.join(tc.get('steps', [])[:3])}
     Expected  : {tc.get('expected_result', 'N/A')}""")

    # ── Step 5: Test Execution ─────────────────────────────────────────────────
    step(5, "Test Execution (Claude simulating test runs)")
    info(f"Executing {total_tests} test cases against staging environment...")
    info(f"Simulating a failure in: {', '.join(SIMULATE_FAILURES)}")
    info("This may take 30-60 seconds...")

    from lambdas.test_executor.handler import handler as execute
    exec_result = execute({
        "tenant_id": TENANT_ID,
        "execution_id": EXECUTION_ID,
        "test_suite": test_suite,
        "simulate_failures": SIMULATE_FAILURES,
    }, None)

    summary = exec_result["summary"]
    ok(f"Execution complete!")
    print(f"""
  📊 Execution Summary:
     Total tests : {summary['total']}
     ✅ Passed   : {summary['passed']}
     ❌ Failed   : {summary['failed']}
     ⊘  Skipped  : {summary['skipped']}
     Pass rate   : {summary['pass_rate']}%
  """)
    ok(f"Results saved to S3: {exec_result['results_s3_key']}")

    # ── Step 6: Failure Triage ─────────────────────────────────────────────────
    step(6, "Failure Triage (Claude classifying failures)")
    failed_tests = exec_result.get("failed_tests", [])

    if not failed_tests:
        ok("No failures to triage — all tests passed!")
    else:
        info(f"Triaging {len(failed_tests)} failed test(s)...")
        from lambdas.failure_triage.handler import handler as triage

        triage_results = []
        for failed_test in failed_tests:
            triage_result = triage({
                "tenant_id": TENANT_ID,
                "execution_id": EXECUTION_ID,
                "component_id": failed_test.get("component", "unknown"),
                "failure_evidence": {
                    "error_message": failed_test.get("failure_reason", "Unknown error"),
                    "test_name": failed_test.get("test_name", ""),
                    "consecutive_count": 1,
                },
                "risk_score_at_failure": next(
                    (r["risk_score"] for r in risk_scores
                     if r["component_id"] in failed_test.get("component", "")),
                    50.0
                ),
            }, None)
            triage_results.append(triage_result)

            icon = "🐛" if triage_result["classification"] == "genuine_defect" else "🌩️" if triage_result["classification"] == "env_noise" else "🔄"
            ok(f"{icon} {failed_test.get('test_name', 'Test')}")
            info(f"   Classification: {triage_result['classification'].upper()}")
            info(f"   Rationale: {triage_result.get('rationale', 'N/A')}")
            if triage_result.get("escalated"):
                warn("   ESCALATED via SNS — consecutive failures exceeded threshold")

    # ── Step 7: Learning Update ────────────────────────────────────────────────
    step(7, "Closed-Loop Learning Update")
    info("Agent is storing outcomes to improve future test cycles...")

    from lambdas.learning_updater.handler import handler as learn
    from layers.serializer.models import ExecutionState, ExecutionStatus, AgentAssignment, AssignmentStatus

    # Build execution state from results
    assignments = []
    for r in exec_result["execution_report"]["results"]:
        assignments.append({
            "assignment_id": str(uuid.uuid4()),
            "agent_type": "api_agent",
            "agent_id": "api-agent-001",
            "component_ids": [r.get("component", "unknown")],
            "status": "completed" if r["status"] == "passed" else "failed",
            "dispatched_at": datetime.now_str(),
            "retry_count": 0,
        })

    learn_result = learn({
        "tenant_id": TENANT_ID,
        "execution_state": {
            "execution_id": EXECUTION_ID,
            "strategy_id": strategy_result["strategy_id"],
            "tenant_id": TENANT_ID,
            "step_functions_arn": "",
            "status": "completed",
            "assignments": assignments,
            "started_at": datetime.now_str(),
            "defect_count": summary["failed"],
        },
        "previous_defect_densities": {},
    }, None)

    ok(f"Learning data stored for {learn_result['components_updated']} components")
    ok(f"Outcomes saved to S3: {learn_result['outcome_s3_key']}")
    if learn_result.get("flagged_for_increased_coverage"):
        warn(f"Components flagged for increased coverage next cycle: {learn_result['flagged_for_increased_coverage']}")

    # ── Final Verdict ──────────────────────────────────────────────────────────
    banner("AGENT VERDICT")

    deployment_approved = summary["failed"] == 0

    if deployment_approved:
        print("""
  ✅ DEPLOYMENT APPROVED

  All tests passed. The CI/CD pipeline will receive:
  EventBridge → "TestCycleCompleted" → status: PASSED
  → Deployment proceeds automatically
        """)
    else:
        print(f"""
  ❌ DEPLOYMENT BLOCKED

  {summary['failed']} defect(s) found. The CI/CD pipeline will receive:
  EventBridge → "TestCycleCompleted" → status: FAILED
  → Deployment is blocked until defects are fixed

  Failing components:
  {chr(10).join(f"  • {t.get('component', 'unknown')}: {t.get('failure_reason', 'N/A')}" for t in failed_tests[:5])}
        """)

    banner("WHAT WAS STORED IN AWS")
    print(f"""
  DynamoDB Tables:
  ├── aethertest-strategies
  │   ├── AUT Graph record    (PK: TENANT#{TENANT_ID})
  │   ├── Strategy record     (strategy_id: {strategy_result['strategy_id'][:8]}...)
  │   └── Test Suite record   (test_suite_id: {test_gen_result['test_suite_id'][:8]}...)
  └── aethertest-defect-patterns
      └── Defect records      ({summary['failed']} failures recorded)

  S3 Bucket: {ARTIFACTS_BUCKET}
  ├── {TENANT_ID}/aut-graphs/{AUT_ID}/{AUT_VERSION}.json
  ├── {TENANT_ID}/strategies/{strategy_result['strategy_id'][:8]}....json
  ├── {TENANT_ID}/test-cases/{strategy_result['strategy_id'][:8]}.../{test_gen_result['test_suite_id'][:8]}....json
  ├── {TENANT_ID}/test-results/{EXECUTION_ID[:8]}.../results.json
  └── {TENANT_ID}/learning/outcomes/{EXECUTION_ID[:8]}....json

  You can view all of this in:
  → AWS Console → DynamoDB → Tables → aethertest-strategies → Explore items
  → AWS Console → S3 → {ARTIFACTS_BUCKET} → {TENANT_ID}/
    """)


class datetime:
    @staticmethod
    def now_str():
        from datetime import datetime as dt, timezone
        return dt.now(timezone.utc).isoformat()


if __name__ == "__main__":
    run()
