"""
Coverage and Risk Agent (Agent 6)
Maps test coverage against all AUT components.
Identifies undertested critical paths.
Computes coverage percentage per component.
Generates coverage report with recommendations.
Stores coverage data in DynamoDB.
"""

from __future__ import annotations
import os
import sys
import json
import uuid
import boto3
from datetime import datetime, timezone

os.environ.setdefault("AWS_PROFILE", "kiro-dev")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../layers"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

s3 = boto3.client("s3", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"), verify=not os.environ.get("AETHERTEST_NO_SSL_VERIFY", ""), endpoint_url=os.environ.get("S3_ENDPOINT_URL", "https://s3.us-east-1.amazonaws.com"))
dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"), verify=not os.environ.get("AETHERTEST_NO_SSL_VERIFY", ""))

BUCKET_NAME = os.environ.get("AETHERTEST_BUCKET", "aethertest-artifacts-654654478821")
STRATEGIES_TABLE = os.environ.get("STRATEGIES_TABLE", "aethertest-strategies")
DEFECT_PATTERNS_TABLE = os.environ.get("DEFECT_PATTERNS_TABLE", "aethertest-defect-patterns")
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")

COVERAGE_SYSTEM_PROMPT = """You are a test coverage analyst for the AetherTest platform.
Analyze the test coverage data and generate actionable recommendations.

Return a JSON object:
{
  "overall_health": "excellent|good|fair|poor",
  "coverage_score": 0-100,
  "critical_gaps": [
    {
      "component": "name",
      "gap_type": "no_tests|insufficient_tests|missing_edge_cases|missing_security_tests",
      "risk_level": "critical|high|medium|low",
      "recommendation": "specific action to take"
    }
  ],
  "well_covered_components": ["component names"],
  "recommendations": [
    {
      "priority": "immediate|short_term|long_term",
      "action": "specific recommendation",
      "expected_impact": "what this will improve"
    }
  ],
  "deployment_verdict": "safe_to_deploy|deploy_with_caution|do_not_deploy",
  "verdict_rationale": "explanation of the deployment verdict"
}"""


def handler(event: dict, context) -> dict:
    """
    Lambda handler for Coverage and Risk Agent.

    Expected event:
    {
        "tenant_id": "string",
        "execution_id": "string",
        "aut_graph": {
            "components": [
                {"component_id": "...", "name": "...", "component_type": "..."}
            ]
        },
        "test_suite": {
            "test_cases": [...]
        },
        "execution_results": {
            "summary": {"total": 10, "passed": 8, "failed": 2},
            "results": [...]
        },
        "risk_scores": [
            {"component_id": "...", "risk_score": 75.0}
        ]
    }
    """
    tenant_id = event.get("tenant_id", "demo-tenant")
    execution_id = event.get("execution_id", str(uuid.uuid4()))
    aut_graph = event.get("aut_graph", {})
    test_suite = event.get("test_suite", {})
    execution_results = event.get("execution_results", {})
    risk_scores_raw = event.get("risk_scores", [])

    components = aut_graph.get("components", [])
    test_cases = test_suite.get("test_cases", [])
    results = execution_results.get("results", [])

    # Build risk score map
    risk_map = {r.get("component_id", ""): r.get("risk_score", 50.0) for r in risk_scores_raw}

    print(f"\n[COVERAGE AGENT] Analyzing coverage for {len(components)} components, {len(test_cases)} tests...")

    # Compute per-component coverage
    component_coverage = _compute_component_coverage(components, test_cases, results, risk_map)

    # Generate AI-powered recommendations
    ai_analysis = _generate_coverage_analysis(component_coverage, risk_map)

    # Compute overall metrics
    total_components = len(components)
    covered_components = sum(1 for c in component_coverage.values() if c["test_count"] > 0)
    overall_coverage_pct = round(covered_components / total_components * 100, 1) if total_components else 0

    total_tests = len(test_cases)
    passed_tests = execution_results.get("summary", {}).get("passed", 0)
    failed_tests = execution_results.get("summary", {}).get("failed", 0)
    executed_tests = passed_tests + failed_tests
    pass_rate = round(passed_tests / executed_tests * 100, 1) if executed_tests else 0

    # Build full coverage report
    report_id = str(uuid.uuid4())
    coverage_report = {
        "report_id": report_id,
        "execution_id": execution_id,
        "tenant_id": tenant_id,
        "agent": "coverage_risk_agent",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metrics": {
            "total_components": total_components,
            "covered_components": covered_components,
            "uncovered_components": total_components - covered_components,
            "overall_coverage_pct": overall_coverage_pct,
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "pass_rate": pass_rate,
        },
        "component_coverage": component_coverage,
        "ai_analysis": ai_analysis,
        "risk_scores": risk_scores_raw,
    }

    # Save to S3
    s3_key = f"{tenant_id}/coverage/{execution_id}/coverage-report.json"
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=s3_key,
        Body=json.dumps(coverage_report, indent=2),
        ContentType="application/json",
    )

    # Store in DynamoDB
    table = dynamodb.Table(STRATEGIES_TABLE)
    table.put_item(Item={
        "PK": f"TENANT#{tenant_id}",
        "SK": f"COVERAGE#{report_id}",
        "report_id": report_id,
        "execution_id": execution_id,
        "overall_coverage_pct": str(overall_coverage_pct),
        "pass_rate": str(pass_rate),
        "deployment_verdict": ai_analysis.get("deployment_verdict", "deploy_with_caution"),
        "s3_key": s3_key,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "agent": "coverage_risk_agent",
    })

    # Also store per-component coverage in defect patterns table for learning
    _store_coverage_metrics(tenant_id, execution_id, component_coverage)

    verdict = ai_analysis.get("deployment_verdict", "deploy_with_caution")
    print(f"\n  Coverage: {overall_coverage_pct}% | Pass Rate: {pass_rate}% | Verdict: {verdict.upper()}")

    return {
        "statusCode": 200,
        "report_id": report_id,
        "metrics": coverage_report["metrics"],
        "deployment_verdict": verdict,
        "verdict_rationale": ai_analysis.get("verdict_rationale", ""),
        "critical_gaps": ai_analysis.get("critical_gaps", []),
        "recommendations": ai_analysis.get("recommendations", []),
        "coverage_s3_key": s3_key,
        "coverage_report": coverage_report,
    }


def _compute_component_coverage(
    components: list,
    test_cases: list,
    results: list,
    risk_map: dict,
) -> dict:
    """Compute per-component test coverage metrics."""
    # Map results by test_id for quick lookup
    result_map = {r.get("test_id", ""): r for r in results}

    # Map test cases by component
    tests_by_component: dict[str, list] = {}
    for tc in test_cases:
        comp = tc.get("component", tc.get("component_id", "unknown"))
        tests_by_component.setdefault(comp, []).append(tc)

    coverage = {}
    for comp in components:
        comp_id = comp.get("component_id", "")
        comp_name = comp.get("name", comp_id)
        comp_tests = tests_by_component.get(comp_name, tests_by_component.get(comp_id, []))

        passed = 0
        failed = 0
        for tc in comp_tests:
            r = result_map.get(tc.get("test_id", ""))
            if r:
                if r.get("status") == "passed":
                    passed += 1
                elif r.get("status") == "failed":
                    failed += 1

        test_count = len(comp_tests)
        risk_score = risk_map.get(comp_id, 50.0)

        # Coverage quality score: more tests + higher pass rate = better
        if test_count == 0:
            quality_score = 0.0
        else:
            pass_rate = passed / test_count if test_count > 0 else 0
            # Penalize if high-risk component has few tests
            test_adequacy = min(test_count / max(risk_score / 20, 1), 1.0)
            quality_score = round((pass_rate * 0.6 + test_adequacy * 0.4) * 100, 1)

        coverage[comp_name] = {
            "component_id": comp_id,
            "component_name": comp_name,
            "component_type": comp.get("component_type", "service"),
            "test_count": test_count,
            "passed": passed,
            "failed": failed,
            "pass_rate": round(passed / (passed + failed) * 100, 1) if (passed + failed) > 0 else 0,
            "risk_score": risk_score,
            "coverage_quality_score": quality_score,
            "is_covered": test_count > 0,
            "needs_more_tests": test_count < 3 and risk_score > 60,
        }

    return coverage


def _generate_coverage_analysis(component_coverage: dict, risk_map: dict) -> dict:
    """Use Claude to generate coverage analysis and recommendations."""
    try:
        bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"), verify=not os.environ.get("AETHERTEST_NO_SSL_VERIFY", ""))

        # Build a compact summary for Claude
        summary_data = []
        for name, data in component_coverage.items():
            summary_data.append({
                "component": name,
                "tests": data["test_count"],
                "pass_rate": data["pass_rate"],
                "risk_score": data["risk_score"],
                "covered": data["is_covered"],
            })

        prompt = f"""Analyze this test coverage data and provide recommendations:

Component Coverage Summary:
{json.dumps(summary_data, indent=2)}

Identify critical gaps, well-covered areas, and provide a deployment verdict.
Return ONLY a valid JSON object."""

        response = bedrock.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "temperature": 0.2,
                "system": COVERAGE_SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": prompt}],
            }),
            contentType="application/json",
            accept="application/json",
        )

        result = json.loads(response["body"].read())
        raw_text = result["content"][0]["text"].strip()

        if "```" in raw_text:
            parts = raw_text.split("```")
            raw_text = parts[1] if len(parts) > 1 else raw_text
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        raw_text = raw_text.strip()

        return json.loads(raw_text)

    except Exception as e:
        print(f"[WARNING] Coverage analysis failed: {e}")
        # Heuristic fallback
        uncovered = [name for name, data in component_coverage.items() if not data["is_covered"]]
        high_risk_low_coverage = [
            name for name, data in component_coverage.items()
            if data["risk_score"] > 70 and data["test_count"] < 3
        ]

        all_pass_rates = [d["pass_rate"] for d in component_coverage.values() if d["test_count"] > 0]
        avg_pass_rate = sum(all_pass_rates) / len(all_pass_rates) if all_pass_rates else 0

        if uncovered or high_risk_low_coverage:
            verdict = "deploy_with_caution"
        elif avg_pass_rate >= 90:
            verdict = "safe_to_deploy"
        else:
            verdict = "deploy_with_caution"

        return {
            "overall_health": "good" if avg_pass_rate >= 80 else "fair",
            "coverage_score": round(avg_pass_rate),
            "critical_gaps": [
                {
                    "component": name,
                    "gap_type": "no_tests",
                    "risk_level": "high",
                    "recommendation": f"Add test cases for {name}",
                }
                for name in uncovered[:3]
            ],
            "well_covered_components": [
                name for name, data in component_coverage.items()
                if data["test_count"] >= 3 and data["pass_rate"] >= 80
            ],
            "recommendations": [
                {
                    "priority": "immediate",
                    "action": f"Add tests for uncovered components: {', '.join(uncovered[:3])}",
                    "expected_impact": "Increase coverage and reduce deployment risk",
                }
            ] if uncovered else [
                {
                    "priority": "short_term",
                    "action": "Increase test depth for high-risk components",
                    "expected_impact": "Better defect detection before production",
                }
            ],
            "deployment_verdict": verdict,
            "verdict_rationale": f"Average pass rate: {avg_pass_rate:.1f}%. {len(uncovered)} uncovered components.",
        }


def _store_coverage_metrics(tenant_id: str, execution_id: str, component_coverage: dict):
    """Store per-component coverage metrics in DynamoDB."""
    table = dynamodb.Table(DEFECT_PATTERNS_TABLE)
    import time

    for comp_name, data in component_coverage.items():
        try:
            table.put_item(Item={
                "PK": f"TENANT#{tenant_id}",
                "SK": f"COVERAGE#{data['component_id']}#EXEC#{execution_id}",
                "tenant_id": tenant_id,
                "component_id": data["component_id"],
                "component_name": comp_name,
                "execution_id": execution_id,
                "test_count": data["test_count"],
                "pass_rate": str(data["pass_rate"]),
                "risk_score": str(data["risk_score"]),
                "coverage_quality_score": str(data["coverage_quality_score"]),
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "ttl": int(time.time()) + 7_776_000,
            })
        except Exception as e:
            print(f"[WARNING] Failed to store coverage metric for {comp_name}: {e}")
