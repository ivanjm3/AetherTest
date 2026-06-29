"""
AetherTest Master Orchestrator
Runs the complete multi-agent testing pipeline end-to-end.

Usage:
    AWS_PROFILE=kiro-dev python3 orchestrator.py
    AWS_PROFILE=kiro-dev python3 orchestrator.py --aut-file my_aut.json
"""

from __future__ import annotations
import os
import sys
import json
import uuid
import argparse
from datetime import datetime, timezone

os.environ["AWS_PROFILE"] = "kiro-dev"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

# Add layers to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "layers"))
sys.path.insert(0, os.path.dirname(__file__))

# Import all agent handlers
from lambdas.aut_analyzer.handler import handler as aut_analyzer
from lambdas.risk_scorer.handler import handler as risk_scorer
from lambdas.strategy_generator.handler import handler as strategy_generator
from lambdas.test_case_generator.handler import handler as test_case_generator
from lambdas.test_author_agent.handler import handler as test_author_agent
from lambdas.test_executor_agent.handler import handler as test_executor_agent
from lambdas.test_analyst_agent.handler import handler as test_analyst_agent
from lambdas.coverage_risk_agent.handler import handler as coverage_risk_agent
from lambdas.learning_updater.handler import handler as learning_updater

# ── Default sample AUT ────────────────────────────────────────────────────────

DEFAULT_AUT = {
    "tenant_id": "demo-tenant",
    "aut_id": "ecommerce-platform",
    "aut_version": "2.1.0",
    "aut_metadata": {
        "components": [
            {
                "component_id": "product-catalog",
                "name": "Product Catalog",
                "component_type": "ui_page",
                "dependencies": [],
                "api_surface": ["/api/products", "/api/products/{id}", "/api/categories"],
                "ui_entry_points": ["/products", "/products/{id}"],
                "metadata": {"criticality": "high"},
            },
            {
                "component_id": "shopping-cart",
                "name": "Shopping Cart",
                "component_type": "ui_page",
                "dependencies": ["product-catalog"],
                "api_surface": ["/api/cart", "/api/cart/items", "/api/cart/clear"],
                "ui_entry_points": ["/cart"],
                "metadata": {"criticality": "critical"},
            },
            {
                "component_id": "checkout",
                "name": "Checkout",
                "component_type": "ui_page",
                "dependencies": ["shopping-cart", "payment-service"],
                "api_surface": ["/api/checkout", "/api/checkout/validate"],
                "ui_entry_points": ["/checkout"],
                "metadata": {"criticality": "critical"},
            },
            {
                "component_id": "payment-service",
                "name": "Payment Service",
                "component_type": "api_endpoint",
                "dependencies": [],
                "api_surface": ["/api/payments/process", "/api/payments/refund"],
                "ui_entry_points": [],
                "metadata": {"criticality": "critical"},
            },
            {
                "component_id": "user-auth",
                "name": "User Authentication",
                "component_type": "service",
                "dependencies": [],
                "api_surface": ["/api/auth/login", "/api/auth/logout", "/api/auth/register"],
                "ui_entry_points": ["/login", "/register"],
                "metadata": {"criticality": "high"},
            },
        ]
    },
}

DEFAULT_REQUIREMENTS = [
    {
        "id": "REQ-001",
        "type": "user_story",
        "content": "As a user, I want to call GET / and receive a Hello World JSON response",
        "component": "Hello World API",
    },
]



def run_pipeline(aut_config: dict = None, fast_mode: bool = False) -> dict:
    """
    Run the complete AetherTest pipeline.

    Args:
        aut_config: AUT configuration dict. Uses DEFAULT_AUT if not provided.
        fast_mode: If True, limits test cases per component for faster execution.

    Returns:
        Final pipeline results dict.
    """
    config = aut_config or DEFAULT_AUT
    tenant_id = config.get("tenant_id", "demo-tenant")
    execution_id = str(uuid.uuid4())

    print("\n" + "="*70)
    print("  AetherTest — Multi-Agent AI Testing Platform")
    print(f"  Execution ID: {execution_id}")
    print(f"  Tenant: {tenant_id}")
    print(f"  Started: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("="*70)

    pipeline_results = {
        "execution_id": execution_id,
        "tenant_id": tenant_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "steps": {},
    }

    # ── Step 1: AUT Analysis ──────────────────────────────────────────────────
    print("\n[STEP 1/9] AUT Analysis — Mapping application structure...")
    step1 = aut_analyzer(config, None)
    pipeline_results["steps"]["aut_analysis"] = {
        "status": "completed",
        "component_count": step1.get("component_count", 0),
        "graph_id": step1.get("graph_id", ""),
    }
    graph = step1.get("graph", {})
    print(f"  ✓ Analyzed {step1.get('component_count', 0)} components")

    # ── Step 2: Risk Scoring ──────────────────────────────────────────────────
    print("\n[STEP 2/9] Risk Scoring — Computing component risk scores...")
    step2 = risk_scorer({
        "tenant_id": tenant_id,
        "graph": graph,
        "change_set": [
            {"component_id": "checkout", "changed_lines": 150, "total_lines": 400},
            {"component_id": "payment-service", "changed_lines": 80, "total_lines": 300},
        ],
        "deploy_frequency": {"checkout": 3, "payment-service": 2},
    }, None)
    pipeline_results["steps"]["risk_scoring"] = {
        "status": "completed",
        "high_priority_count": step2.get("high_priority_count", 0),
        "risk_scores": step2.get("risk_scores", []),
    }
    risk_scores = step2.get("risk_scores", [])
    print(f"  ✓ Scored {len(risk_scores)} components | {step2.get('high_priority_count', 0)} high-priority")

    # ── Step 3: Strategy Generation ───────────────────────────────────────────
    print("\n[STEP 3/9] Strategy Generation — Building test strategy...")
    step3 = strategy_generator({
        "tenant_id": tenant_id,
        "aut_id": config.get("aut_id", ""),
        "aut_version": config.get("aut_version", ""),
        "execution_environment": "staging",
        "triggering_event": "manual",
        "risk_scores": risk_scores,
    }, None)
    pipeline_results["steps"]["strategy_generation"] = {
        "status": "completed",
        "strategy_id": step3.get("strategy_id", ""),
        "estimated_duration_seconds": step3.get("estimated_duration_seconds", 0),
    }
    strategy = step3.get("strategy", {})
    print(f"  ✓ Strategy created | Est. duration: {step3.get('estimated_duration_seconds', 0)}s")

    # ── Step 4: Test Case Generation ──────────────────────────────────────────
    print("\n[STEP 4/9] Test Case Generation — Generating test cases with Claude...")
    step4 = test_case_generator({
        "tenant_id": tenant_id,
        "strategy": strategy,
        "aut_graph": graph,
    }, None)
    pipeline_results["steps"]["test_case_generation"] = {
        "status": "completed",
        "test_suite_id": step4.get("test_suite_id", ""),
        "total_test_cases": step4.get("total_test_cases", 0),
    }
    test_suite = step4.get("test_suite", {})
    print(f"  ✓ Generated {step4.get('total_test_cases', 0)} test cases")

    # ── Step 4b: Test Author Agent (BDD from requirements) ────────────────────
    print("\n[STEP 4b/9] Test Author Agent — Converting requirements to BDD tests...")
    step4b = test_author_agent({
        "tenant_id": tenant_id,
        "requirements": DEFAULT_REQUIREMENTS,
        "aut_context": {
            "name": config.get("aut_id", "Application"),
            "components": [c.get("name", "") for c in graph.get("components", [])],
        },
    }, None)
    pipeline_results["steps"]["test_authoring"] = {
        "status": "completed",
        "suite_id": step4b.get("suite_id", ""),
        "total_tests_authored": step4b.get("total_tests_authored", 0),
    }
    # Merge authored tests into the test suite
    authored_tests = step4b.get("test_suite", {}).get("test_cases", [])
    if authored_tests:
        test_suite.setdefault("test_cases", []).extend(authored_tests)
    print(f"  ✓ Authored {step4b.get('total_tests_authored', 0)} BDD test cases from requirements")

    # ── Step 5: Test Execution ────────────────────────────────────────────────
    print("\n[STEP 5/9] Test Execution — Running tests with Claude simulation...")
    step5 = test_executor_agent({
        "tenant_id": tenant_id,
        "execution_id": execution_id,
        "test_suite": test_suite,
        "simulate_failures": ["payment-service"],  # Simulate a realistic failure
        "fast_mode": fast_mode,
    }, None)
    pipeline_results["steps"]["test_execution"] = {
        "status": "completed",
        "summary": step5.get("summary", {}),
        "results_s3_key": step5.get("results_s3_key", ""),
    }
    execution_report = step5.get("execution_report", {})
    summary = step5.get("summary", {})
    print(f"  ✓ Executed {summary.get('total', 0)} tests | "
          f"Passed: {summary.get('passed', 0)} | "
          f"Failed: {summary.get('failed', 0)} | "
          f"Pass Rate: {summary.get('pass_rate', 0)}%")

    # ── Step 6: Failure Analysis ──────────────────────────────────────────────
    failed_tests = step5.get("failed_tests", [])
    print(f"\n[STEP 6/9] Failure Analysis — Analyzing {len(failed_tests)} failures...")
    step6 = test_analyst_agent({
        "tenant_id": tenant_id,
        "execution_id": execution_id,
        "failed_tests": failed_tests,
        "recent_changes": [
            "Deployed payment-service v2.1 — updated Stripe SDK",
            "Refactored checkout flow — new validation logic",
        ],
        "run_history": [
            {"execution_id": "prev-1", "pass_rate": 0.95},
            {"execution_id": "prev-2", "pass_rate": 0.92},
        ],
    }, None)
    pipeline_results["steps"]["failure_analysis"] = {
        "status": "completed",
        "summary": step6.get("summary", {}),
        "analysis_s3_key": step6.get("analysis_s3_key", ""),
    }
    analysis_summary = step6.get("summary", {})
    print(f"  ✓ Analyzed failures | "
          f"Real defects: {analysis_summary.get('real_defects', 0)} | "
          f"False positives: {analysis_summary.get('false_positives', 0)}")

    # ── Step 7: Coverage Report ───────────────────────────────────────────────
    print("\n[STEP 7/9] Coverage Report — Mapping test coverage and risk...")
    step7 = coverage_risk_agent({
        "tenant_id": tenant_id,
        "execution_id": execution_id,
        "aut_graph": graph,
        "test_suite": test_suite,
        "execution_results": execution_report,
        "risk_scores": risk_scores,
    }, None)
    pipeline_results["steps"]["coverage_report"] = {
        "status": "completed",
        "metrics": step7.get("metrics", {}),
        "deployment_verdict": step7.get("deployment_verdict", ""),
        "coverage_s3_key": step7.get("coverage_s3_key", ""),
    }
    coverage_metrics = step7.get("metrics", {})
    verdict = step7.get("deployment_verdict", "unknown")
    print(f"  ✓ Coverage: {coverage_metrics.get('overall_coverage_pct', 0)}% | "
          f"Verdict: {verdict.upper()}")

    # ── Step 8: Learning Update ───────────────────────────────────────────────
    print("\n[STEP 8/9] Learning Update — Updating defect patterns for future runs...")
    from serializer.models import ExecutionState, AgentAssignment, AssignmentStatus
    exec_state = ExecutionState(
        execution_id=execution_id,
        strategy_id=strategy.get("strategy_id", ""),
        tenant_id=tenant_id,
        assignments=[
            AgentAssignment(
                agent_type="test_executor_agent",
                agent_id="executor-1",
                component_ids=[c.get("component_id", "") for c in graph.get("components", [])],
                status=AssignmentStatus.COMPLETED if summary.get("pass_rate", 0) >= 80 else AssignmentStatus.FAILED,
            )
        ],
    )
    step8 = learning_updater({
        "tenant_id": tenant_id,
        "execution_state": json.loads(exec_state.model_dump_json()),
        "previous_defect_densities": {},
    }, None)
    pipeline_results["steps"]["learning_update"] = {
        "status": "completed",
        "components_updated": step8.get("components_updated", 0),
    }
    print(f"  ✓ Updated learning data for {step8.get('components_updated', 0)} components")

    # ── Step 9: Final Verdict ─────────────────────────────────────────────────
    print("\n[STEP 9/9] Final Verdict")
    pipeline_results["completed_at"] = datetime.now(timezone.utc).isoformat()
    pipeline_results["final_verdict"] = {
        "deployment_verdict": verdict,
        "pass_rate": summary.get("pass_rate", 0),
        "coverage_pct": coverage_metrics.get("overall_coverage_pct", 0),
        "real_defects": analysis_summary.get("real_defects", 0),
        "critical_gaps": len(step7.get("critical_gaps", [])),
        "recommendations": step7.get("recommendations", [])[:3],
    }

    _print_final_verdict(pipeline_results["final_verdict"])

    return pipeline_results


def _print_final_verdict(verdict: dict):
    """Print a formatted final verdict."""
    dv = verdict.get("deployment_verdict", "unknown")
    pass_rate = verdict.get("pass_rate", 0)
    coverage = verdict.get("coverage_pct", 0)
    defects = verdict.get("real_defects", 0)

    print("\n" + "="*70)
    print("  FINAL VERDICT")
    print("="*70)

    if dv == "safe_to_deploy":
        print(f"  🟢 SAFE TO DEPLOY")
    elif dv == "deploy_with_caution":
        print(f"  🟡 DEPLOY WITH CAUTION")
    else:
        print(f"  🔴 DO NOT DEPLOY")

    print(f"\n  Pass Rate:    {pass_rate}%")
    print(f"  Coverage:     {coverage}%")
    print(f"  Real Defects: {defects}")

    recs = verdict.get("recommendations", [])
    if recs:
        print("\n  Top Recommendations:")
        for i, rec in enumerate(recs[:3], 1):
            action = rec.get("action", str(rec)) if isinstance(rec, dict) else str(rec)
            print(f"  {i}. {action[:70]}")

    print("="*70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AetherTest Master Orchestrator")
    parser.add_argument("--aut-file", help="Path to AUT config JSON file")
    parser.add_argument("--fast", action="store_true", help="Fast mode: 3 tests per component")
    args = parser.parse_args()

    aut_config = None
    if args.aut_file:
        with open(args.aut_file) as f:
            aut_config = json.load(f)

    results = run_pipeline(aut_config=aut_config, fast_mode=args.fast)

    # Save full results
    output_file = f"pipeline_results_{results['execution_id'][:8]}.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Full results saved to: {output_file}")
