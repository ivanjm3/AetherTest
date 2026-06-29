"""
AetherTest Quick Demo
A fast 2-minute demo using a pre-built e-commerce checkout AUT.
Shows all 6 agents working with colored terminal output.

Run with:
    AWS_PROFILE=kiro-dev python3 demo.py
"""

from __future__ import annotations
import os
import sys
import json
import uuid
import time
import warnings
from datetime import datetime, timezone

# Suppress SSL warnings when running behind corporate proxy
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

os.environ["AWS_PROFILE"] = "kiro-dev"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

# Add layers to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "layers"))
sys.path.insert(0, os.path.dirname(__file__))

# ── ANSI Colors ───────────────────────────────────────────────────────────────

class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    RED     = "\033[91m"
    BLUE    = "\033[94m"
    CYAN    = "\033[96m"
    MAGENTA = "\033[95m"
    WHITE   = "\033[97m"
    DIM     = "\033[2m"

def banner(text: str, color: str = C.CYAN):
    width = 68
    print(f"\n{color}{C.BOLD}{'─'*width}{C.RESET}")
    print(f"{color}{C.BOLD}  {text}{C.RESET}")
    print(f"{color}{C.BOLD}{'─'*width}{C.RESET}")

def step(num: int, total: int, agent: str, description: str):
    print(f"\n{C.BLUE}{C.BOLD}[{num}/{total}] {agent}{C.RESET}")
    print(f"  {C.DIM}{description}{C.RESET}")

def ok(msg: str):
    print(f"  {C.GREEN}✓{C.RESET} {msg}")

def warn(msg: str):
    print(f"  {C.YELLOW}⚠{C.RESET} {msg}")

def fail(msg: str):
    print(f"  {C.RED}✗{C.RESET} {msg}")

def info(msg: str):
    print(f"  {C.DIM}→{C.RESET} {msg}")

def thinking(msg: str):
    print(f"  {C.MAGENTA}◆{C.RESET} {C.MAGENTA}{msg}{C.RESET}")


# ── Pre-built Demo AUT: E-Commerce Checkout Flow ──────────────────────────────

DEMO_AUT = {
    "tenant_id": "demo-ecommerce",
    "aut_id": "checkout-flow",
    "aut_version": "3.0.0",
    "aut_metadata": {
        "components": [
            {
                "component_id": "product-listing",
                "name": "Product Listing",
                "component_type": "ui_page",
                "dependencies": [],
                "api_surface": ["/api/products", "/api/search"],
                "ui_entry_points": ["/products"],
                "metadata": {"criticality": "medium"},
            },
            {
                "component_id": "cart-service",
                "name": "Cart Service",
                "component_type": "api_endpoint",
                "dependencies": ["product-listing"],
                "api_surface": ["/api/cart/add", "/api/cart/remove", "/api/cart/total"],
                "ui_entry_points": ["/cart"],
                "metadata": {"criticality": "high"},
            },
            {
                "component_id": "checkout-flow",
                "name": "Checkout Flow",
                "component_type": "ui_page",
                "dependencies": ["cart-service", "payment-gateway"],
                "api_surface": ["/api/checkout/start", "/api/checkout/confirm"],
                "ui_entry_points": ["/checkout"],
                "metadata": {"criticality": "critical"},
            },
            {
                "component_id": "payment-gateway",
                "name": "Payment Gateway",
                "component_type": "service",
                "dependencies": [],
                "api_surface": ["/api/payments/charge", "/api/payments/verify"],
                "ui_entry_points": [],
                "metadata": {"criticality": "critical"},
            },
        ]
    },
}

DEMO_REQUIREMENTS = [
    {
        "id": "US-001",
        "type": "user_story",
        "content": "As a shopper, I want to add items to my cart so that I can buy multiple products",
        "component": "Cart Service",
    },
    {
        "id": "US-002",
        "type": "user_story",
        "content": "As a shopper, I want to pay with my credit card so that I can complete my purchase securely",
        "component": "Payment Gateway",
    },
]


def run_demo():
    """Run the 2-minute AetherTest demo."""
    execution_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    # ── Header ────────────────────────────────────────────────────────────────
    print(f"\n{C.CYAN}{C.BOLD}")
    print("  ╔══════════════════════════════════════════════════════════════╗")
    print("  ║          AetherTest — AI-Powered Multi-Agent Testing         ║")
    print("  ║              E-Commerce Checkout Flow Demo                   ║")
    print("  ╚══════════════════════════════════════════════════════════════╝")
    print(C.RESET)
    print(f"  {C.DIM}Execution ID: {execution_id}{C.RESET}")
    print(f"  {C.DIM}AUT: E-Commerce Checkout Flow v3.0.0{C.RESET}")
    print(f"  {C.DIM}Components: 4 | Mode: Fast Demo (3 tests/component){C.RESET}")
    print(f"  {C.DIM}Started: {datetime.now().strftime('%H:%M:%S')}{C.RESET}")

    results = {}

    # ── Agent 0: AUT Analyzer ─────────────────────────────────────────────────
    banner("AGENT 1: Test Strategist — AUT Analysis + Risk Scoring", C.BLUE)
    step(1, 7, "AUT Analyzer", "Mapping application structure and component dependencies")

    try:
        from lambdas.aut_analyzer.handler import handler as aut_analyzer
        r = aut_analyzer(DEMO_AUT, None)
        graph = r.get("graph", {})
        components = graph.get("components", [])
        ok(f"Mapped {len(components)} components")
        for comp in components:
            info(f"{comp.get('name')} [{comp.get('component_type')}]")
        results["graph"] = graph
        results["aut_ok"] = True
    except Exception as e:
        warn(f"AUT Analyzer: {e}")
        results["graph"] = {
            "aut_id": DEMO_AUT["aut_id"],
            "version": DEMO_AUT["aut_version"],
            "tenant_id": DEMO_AUT["tenant_id"],
            **DEMO_AUT["aut_metadata"],
        }
        results["aut_ok"] = False

    # ── Risk Scorer ───────────────────────────────────────────────────────────
    step(2, 7, "Risk Scorer", "Computing risk scores based on change history and defect patterns")
    thinking("Analyzing recent deployments and change velocity...")

    try:
        from lambdas.risk_scorer.handler import handler as risk_scorer
        r = risk_scorer({
            "tenant_id": DEMO_AUT["tenant_id"],
            "graph": results["graph"],
            "change_set": [
                {"component_id": "checkout-flow", "changed_lines": 200, "total_lines": 500},
                {"component_id": "payment-gateway", "changed_lines": 120, "total_lines": 350},
            ],
            "deploy_frequency": {"checkout-flow": 4, "payment-gateway": 3},
        }, None)
        risk_scores = r.get("risk_scores", [])
        ok(f"Scored {len(risk_scores)} components | {r.get('high_priority_count', 0)} high-priority")
        for rs in risk_scores[:4]:
            score = rs.get("risk_score", 0)
            color = C.RED if score > 70 else C.YELLOW if score > 40 else C.GREEN
            info(f"{rs.get('component_id', 'unknown'):25s} Risk: {color}{score:.0f}/100{C.RESET}")
        results["risk_scores"] = risk_scores
    except Exception as e:
        warn(f"Risk Scorer: {e}")
        results["risk_scores"] = [
            {"component_id": "checkout-flow", "risk_score": 75.0, "is_uncharacterized": False},
            {"component_id": "payment-gateway", "risk_score": 68.0, "is_uncharacterized": False},
            {"component_id": "cart-service", "risk_score": 45.0, "is_uncharacterized": True},
            {"component_id": "product-listing", "risk_score": 30.0, "is_uncharacterized": True},
        ]

    # ── Strategy Generator ────────────────────────────────────────────────────
    step(3, 7, "Strategy Generator", "Building prioritized test strategy")
    thinking("Allocating test coverage based on risk scores...")

    try:
        from lambdas.strategy_generator.handler import handler as strategy_generator
        r = strategy_generator({
            "tenant_id": DEMO_AUT["tenant_id"],
            "aut_id": DEMO_AUT["aut_id"],
            "aut_version": DEMO_AUT["aut_version"],
            "execution_environment": "staging",
            "triggering_event": "manual",
            "risk_scores": results["risk_scores"],
        }, None)
        strategy = r.get("strategy", {})
        ok(f"Strategy created | Est. {r.get('estimated_duration_seconds', 0)}s")
        for cov in strategy.get("coverage", []):
            priority = cov.get("priority", "low")
            color = C.RED if priority == "high" else C.YELLOW if priority == "medium" else C.GREEN
            info(f"{cov.get('component_id', ''):25s} Priority: {color}{priority.upper()}{C.RESET}")
        results["strategy"] = strategy
    except Exception as e:
        warn(f"Strategy Generator: {e}")
        results["strategy"] = {
            "strategy_id": str(uuid.uuid4()),
            "tenant_id": DEMO_AUT["tenant_id"],
            "aut_id": DEMO_AUT["aut_id"],
            "aut_version": DEMO_AUT["aut_version"],
            "execution_environment": "staging",
            "estimated_duration_seconds": 120,
            "coverage": [],
        }

    # ── Agent 2: Test Author ──────────────────────────────────────────────────
    banner("AGENT 2: Test Author — BDD Test Generation from Requirements", C.MAGENTA)
    step(4, 7, "Test Author Agent", "Converting user stories to Given/When/Then test cases")
    thinking("Parsing user stories and generating BDD scenarios...")

    try:
        from lambdas.test_author_agent.handler import handler as test_author_agent
        r = test_author_agent({
            "tenant_id": DEMO_AUT["tenant_id"],
            "requirements": DEMO_REQUIREMENTS,
            "aut_context": {
                "name": "E-Commerce Checkout Flow",
                "components": ["Cart Service", "Checkout Flow", "Payment Gateway"],
            },
        }, None)
        authored_tests = r.get("test_suite", {}).get("test_cases", [])
        ok(f"Authored {r.get('total_tests_authored', 0)} BDD test cases from {len(DEMO_REQUIREMENTS)} requirements")
        for log in r.get("authoring_log", []):
            info(f"{log.get('requirement_id')}: {log.get('tests_authored')} tests for {log.get('component')}")
        # Show a sample BDD test
        if authored_tests:
            sample = authored_tests[0]
            print(f"\n  {C.DIM}Sample BDD Test:{C.RESET}")
            print(f"  {C.CYAN}  Test: {sample.get('test_name', '')[:60]}{C.RESET}")
            for g in sample.get("given", [])[:2]:
                print(f"  {C.DIM}    Given: {g[:60]}{C.RESET}")
            for w in sample.get("when", [])[:2]:
                print(f"  {C.DIM}    When:  {w[:60]}{C.RESET}")
            for t in sample.get("then", [])[:2]:
                print(f"  {C.DIM}    Then:  {t[:60]}{C.RESET}")
        results["authored_tests"] = authored_tests
    except Exception as e:
        warn(f"Test Author Agent: {e}")
        results["authored_tests"] = []

    # ── Test Case Generator (Claude-powered) ──────────────────────────────────
    step(5, 7, "Test Case Generator", "Generating comprehensive test cases with Claude AI")
    thinking("Claude is generating test scenarios for each component...")

    try:
        from lambdas.test_case_generator.handler import handler as test_case_generator
        r = test_case_generator({
            "tenant_id": DEMO_AUT["tenant_id"],
            "strategy": results["strategy"],
            "aut_graph": results["graph"],
        }, None)
        test_suite = r.get("test_suite", {})
        # Merge authored tests
        if results["authored_tests"]:
            test_suite.setdefault("test_cases", []).extend(results["authored_tests"])
        ok(f"Generated {r.get('total_test_cases', 0)} test cases + {len(results['authored_tests'])} BDD tests")
        for gen in r.get("generation_summary", []):
            info(f"{gen.get('component'):25s} {gen.get('test_cases_generated')} tests [{gen.get('priority')}]")
        results["test_suite"] = test_suite
    except Exception as e:
        warn(f"Test Case Generator: {e}")
        results["test_suite"] = {"test_cases": results["authored_tests"], "test_suite_id": str(uuid.uuid4())}

    # ── Agent 3: Test Executor ────────────────────────────────────────────────
    banner("AGENT 3: Test Executor — Running Tests (Fast Mode: 3/component)", C.GREEN)
    step(6, 7, "Test Executor Agent", "Executing tests with Claude simulation + self-healing")
    thinking("Running test cases against simulated application...")

    try:
        from lambdas.test_executor_agent.handler import handler as test_executor_agent
        r = test_executor_agent({
            "tenant_id": DEMO_AUT["tenant_id"],
            "execution_id": execution_id,
            "test_suite": results["test_suite"],
            "simulate_failures": ["payment-gateway"],  # Realistic demo failure
            "fast_mode": True,
        }, None)
        exec_summary = r.get("summary", {})
        exec_report = r.get("execution_report", {})

        total = exec_summary.get("total", 0)
        passed = exec_summary.get("passed", 0)
        failed = exec_summary.get("failed", 0)
        pass_rate = exec_summary.get("pass_rate", 0)
        healed = exec_summary.get("self_healed", 0)

        if pass_rate >= 90:
            rate_color = C.GREEN
        elif pass_rate >= 70:
            rate_color = C.YELLOW
        else:
            rate_color = C.RED

        ok(f"Executed {total} tests | "
           f"{C.GREEN}Passed: {passed}{C.RESET} | "
           f"{C.RED}Failed: {failed}{C.RESET} | "
           f"Pass Rate: {rate_color}{pass_rate}%{C.RESET}")

        if healed > 0:
            ok(f"Self-healed {healed} broken locators automatically")

        # Show failed tests
        for ft in r.get("failed_tests", [])[:3]:
            fail(f"{ft.get('test_name', 'Unknown')[:50]} — {ft.get('failure_reason', '')[:50]}")

        results["execution_report"] = exec_report
        results["failed_tests"] = r.get("failed_tests", [])
        results["exec_summary"] = exec_summary
    except Exception as e:
        warn(f"Test Executor Agent: {e}")
        results["execution_report"] = {}
        results["failed_tests"] = []
        results["exec_summary"] = {"total": 0, "passed": 0, "failed": 0, "pass_rate": 0}

    # ── Agent 4: Test Analyst ─────────────────────────────────────────────────
    banner("AGENT 4: Test Analyst — Root Cause Analysis", C.YELLOW)
    step(7, 7, "Test Analyst Agent", "Classifying failures and generating root cause hypotheses")
    thinking("Correlating failures with recent code changes...")

    failed_tests = results.get("failed_tests", [])
    if failed_tests:
        try:
            from lambdas.test_analyst_agent.handler import handler as test_analyst_agent
            r = test_analyst_agent({
                "tenant_id": DEMO_AUT["tenant_id"],
                "execution_id": execution_id,
                "failed_tests": failed_tests,
                "recent_changes": [
                    "payment-gateway: Updated Stripe SDK from v3 to v4",
                    "checkout-flow: Added new address validation step",
                ],
                "run_history": [{"execution_id": "prev-run", "pass_rate": 0.94}],
            }, None)
            analysis_summary = r.get("summary", {})
            ok(f"Analyzed {len(failed_tests)} failures")
            info(f"Real defects:    {analysis_summary.get('real_defects', 0)}")
            info(f"Regressions:     {analysis_summary.get('regressions', 0)}")
            info(f"False positives: {analysis_summary.get('false_positives', 0)}")
            info(f"Env issues:      {analysis_summary.get('environment_issues', 0)}")

            for analysis in r.get("analyses", [])[:2]:
                classification = analysis.get("classification", "unknown")
                color = C.RED if classification == "application_defect" else C.YELLOW
                print(f"\n  {C.DIM}Root Cause Analysis:{C.RESET}")
                print(f"  {color}  [{classification.upper()}]{C.RESET} {analysis.get('test_name', '')[:50]}")
                print(f"  {C.DIM}  Hypothesis: {analysis.get('root_cause_hypothesis', '')[:80]}{C.RESET}")
                print(f"  {C.DIM}  Fix: {analysis.get('fix_suggestion', '')[:80]}{C.RESET}")

            results["analysis_summary"] = analysis_summary
        except Exception as e:
            warn(f"Test Analyst Agent: {e}")
            results["analysis_summary"] = {}
    else:
        ok("No failures to analyze — all tests passed!")
        results["analysis_summary"] = {}

    # ── Agent 5: Test Maintenance (brief demo) ────────────────────────────────
    banner("AGENT 5: Test Maintenance — Detecting AUT Changes", C.CYAN)
    thinking("Checking for UI element changes and API schema updates...")

    try:
        from lambdas.test_maintenance_agent.handler import handler as test_maintenance_agent
        r = test_maintenance_agent({
            "tenant_id": DEMO_AUT["tenant_id"],
            "aut_changes": [
                {
                    "component": "checkout-flow",
                    "change_type": "ui_element_changed",
                    "description": "Checkout button ID changed from 'btn-checkout' to 'checkout-submit-btn'",
                    "old_value": "btn-checkout",
                    "new_value": "checkout-submit-btn",
                }
            ],
            "existing_test_suite": results.get("test_suite", {"test_cases": []}),
        }, None)
        maint_summary = r.get("summary", {})
        ok(f"Maintenance complete | Updated: {maint_summary.get('updated', 0)} | "
           f"Retired: {maint_summary.get('retired', 0)} | "
           f"Gaps found: {maint_summary.get('coverage_gaps_found', 0)}")
        for gap in r.get("coverage_gaps", [])[:2]:
            warn(f"Coverage gap: {gap.get('description', '')[:70]}")
    except Exception as e:
        warn(f"Test Maintenance Agent: {e}")

    # ── Agent 6: Coverage & Risk ──────────────────────────────────────────────
    banner("AGENT 6: Coverage & Risk — Final Coverage Report", C.WHITE)
    thinking("Computing coverage map and generating deployment verdict...")

    try:
        from lambdas.coverage_risk_agent.handler import handler as coverage_risk_agent
        r = coverage_risk_agent({
            "tenant_id": DEMO_AUT["tenant_id"],
            "execution_id": execution_id,
            "aut_graph": results["graph"],
            "test_suite": results.get("test_suite", {"test_cases": []}),
            "execution_results": results.get("execution_report", {}),
            "risk_scores": results.get("risk_scores", []),
        }, None)
        metrics = r.get("metrics", {})
        verdict = r.get("deployment_verdict", "deploy_with_caution")
        rationale = r.get("verdict_rationale", "")

        ok(f"Coverage: {metrics.get('overall_coverage_pct', 0)}% | "
           f"Pass Rate: {metrics.get('pass_rate', 0)}%")

        # Per-component coverage
        coverage_report = r.get("coverage_report", {})
        comp_coverage = coverage_report.get("component_coverage", {})
        for comp_name, data in list(comp_coverage.items())[:4]:
            tests = data.get("test_count", 0)
            pr = data.get("pass_rate", 0)
            risk = data.get("risk_score", 0)
            color = C.GREEN if pr >= 80 else C.YELLOW if pr >= 60 else C.RED
            info(f"{comp_name:25s} Tests: {tests:2d} | Pass: {color}{pr:.0f}%{C.RESET} | Risk: {risk:.0f}")

        # Critical gaps
        for gap in r.get("critical_gaps", [])[:2]:
            warn(f"Gap [{gap.get('risk_level', 'medium').upper()}]: {gap.get('recommendation', '')[:60]}")

        results["coverage_metrics"] = metrics
        results["deployment_verdict"] = verdict
        results["verdict_rationale"] = rationale
    except Exception as e:
        warn(f"Coverage Risk Agent: {e}")
        results["deployment_verdict"] = "deploy_with_caution"
        results["verdict_rationale"] = "Coverage analysis unavailable"
        results["coverage_metrics"] = {}

    # ── Final Verdict ─────────────────────────────────────────────────────────
    elapsed = time.time() - start_time
    verdict = results.get("deployment_verdict", "deploy_with_caution")
    exec_summary = results.get("exec_summary", {})
    coverage_metrics = results.get("coverage_metrics", {})

    print(f"\n{C.BOLD}{'═'*68}{C.RESET}")
    print(f"{C.BOLD}  AETHERTEST DEMO COMPLETE{C.RESET}")
    print(f"{C.BOLD}{'═'*68}{C.RESET}")

    if verdict == "safe_to_deploy":
        verdict_display = f"{C.GREEN}{C.BOLD}🟢  SAFE TO DEPLOY{C.RESET}"
    elif verdict == "deploy_with_caution":
        verdict_display = f"{C.YELLOW}{C.BOLD}🟡  DEPLOY WITH CAUTION{C.RESET}"
    else:
        verdict_display = f"{C.RED}{C.BOLD}🔴  DO NOT DEPLOY{C.RESET}"

    print(f"\n  Deployment Verdict:  {verdict_display}")
    print(f"\n  Pass Rate:    {C.GREEN}{exec_summary.get('pass_rate', 0)}%{C.RESET}")
    print(f"  Coverage:     {coverage_metrics.get('overall_coverage_pct', 'N/A')}%")
    print(f"  Tests Run:    {exec_summary.get('total', 0)}")
    print(f"  Failures:     {exec_summary.get('failed', 0)}")
    print(f"  Demo Time:    {elapsed:.1f}s")
    print(f"\n  {C.DIM}Rationale: {results.get('verdict_rationale', '')[:80]}{C.RESET}")

    print(f"\n{C.DIM}  Data stored in:{C.RESET}")
    print(f"  {C.DIM}  S3:       s3://aethertest-artifacts-654654478821/{DEMO_AUT['tenant_id']}/{C.RESET}")
    print(f"  {C.DIM}  DynamoDB: aethertest-strategies, aethertest-agent-assignments{C.RESET}")
    print(f"  {C.DIM}  Region:   us-east-1 | Profile: kiro-dev{C.RESET}")

    print(f"\n{C.CYAN}  To explore results:{C.RESET}")
    print(f"  {C.DIM}  streamlit run ui/app.py{C.RESET}")
    print(f"  {C.DIM}  python3 orchestrator.py --fast{C.RESET}")
    print(f"\n{C.BOLD}{'═'*68}{C.RESET}\n")

    return results


if __name__ == "__main__":
    run_demo()
