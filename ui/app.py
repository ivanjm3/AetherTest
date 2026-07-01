"""
AetherTest Streamlit Demo UI
Interactive web interface to explore test results, coverage, and agent activity.

Run with:
    AWS_PROFILE=kiro-dev streamlit run ui/app.py
"""

from __future__ import annotations
import os
import sys
import json
import boto3
import streamlit as st
from datetime import datetime

os.environ.setdefault("AWS_PROFILE", "kiro-dev")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../layers"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# AWS clients
_no_ssl = os.environ.get("AETHERTEST_NO_SSL_VERIFY", "")
s3 = boto3.client("s3", region_name="us-east-1", verify=not _no_ssl, endpoint_url=os.environ.get("S3_ENDPOINT_URL", "https://s3.us-east-1.amazonaws.com"))
dynamodb = boto3.resource("dynamodb", region_name="us-east-1", verify=not _no_ssl)

BUCKET_NAME = "aethertest-artifacts-654654478821"
STRATEGIES_TABLE = "aethertest-strategies"
ASSIGNMENTS_TABLE = "aethertest-agent-assignments"

# ── Page Config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AetherTest Platform",
    page_icon=" ",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar Navigation ────────────────────────────────────────────────────────

st.sidebar.title("  AetherTest")
st.sidebar.markdown("**Multi-Agent AI Testing Platform**")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigation",
    ["🏠 Dashboard", "✍️ Requirements", "📋 Test Cases", "📊 Test Results", "📈 Coverage Report", "🤖 Agent Activity"],
)

st.sidebar.markdown("---")
st.sidebar.markdown("**AWS Resources**")
st.sidebar.markdown(f"**Region:** us-east-1")
st.sidebar.markdown(f"**Profile:** kiro-dev")
st.sidebar.markdown(f"**S3 Bucket:** {BUCKET_NAME}")

# ── Helper Functions ──────────────────────────────────────────────────────────

def list_s3_objects(prefix: str, max_keys: int = 100) -> list:
    """List objects in S3 with a given prefix."""
    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix, MaxKeys=max_keys)
        return response.get("Contents", [])
    except Exception as e:
        st.error(f"Failed to list S3 objects: {e}")
        return []


def get_s3_object(key: str) -> dict:
    """Get and parse a JSON object from S3."""
    try:
        response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
        return json.loads(response["Body"].read())
    except Exception as e:
        st.error(f"Failed to get S3 object {key}: {e}")
        return {}


def query_dynamodb_table(table_name: str, pk: str, limit: int = 10) -> list:
    """Query DynamoDB table by partition key."""
    try:
        table = dynamodb.Table(table_name)
        response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("PK").eq(pk),
            Limit=limit,
            ScanIndexForward=False,
        )
        return response.get("Items", [])
    except Exception as e:
        st.error(f"Failed to query DynamoDB: {e}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1: DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

if page == "🏠 Dashboard":
    st.title("🏠 AetherTest Dashboard")
    st.markdown("**Welcome to the AetherTest Multi-Agent AI Testing Platform**")
    st.markdown("---")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Agents", "6", help="Test Strategist + 5 Specialist Agents")
    with col2:
        st.metric("AWS Region", "us-east-1")
    with col3:
        st.metric("Bedrock Model", "Claude Sonnet 4")

    st.markdown("### Platform Overview")
    st.markdown("""
    AetherTest is an AWS-native multi-agent AI testing solution that uses Claude Sonnet 4 to:
    - **Analyze** application structure and compute risk scores
    - **Generate** test strategies and test cases from requirements
    - **Execute** tests with self-healing capabilities
    - **Analyze** failures with root cause analysis
    - **Maintain** tests when the application changes
    - **Report** coverage and provide deployment verdicts
    """)

    st.markdown("### 6 Intelligent Agents")
    agents = [
        ("🧠 Test Strategist", "AUT analysis, risk scoring, strategy generation"),
        ("✍️ Test Author", "Converts requirements to BDD test cases"),
        ("▶️ Test Executor", "Runs tests with self-healing"),
        ("🔍 Test Analyst", "Root cause analysis and failure classification"),
        ("🔧 Test Maintenance", "Updates tests when AUT changes"),
        ("📊 Coverage & Risk", "Coverage mapping and deployment verdicts"),
    ]

    for name, desc in agents:
        st.markdown(f"**{name}** — {desc}")

    st.markdown("---")
    st.markdown("### Quick Start")
    st.code("AWS_PROFILE=kiro-dev python3 demo.py", language="bash")
    st.code("AWS_PROFILE=kiro-dev python3 orchestrator.py --fast", language="bash")
    st.code("AWS_PROFILE=kiro-dev streamlit run ui/app.py", language="bash")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2: RUN DEMO
# ══════════════════════════════════════════════════════════════════════════════

elif page == "▶️ Run Demo":
    st.title("▶️ Run Demo")
    st.markdown("Trigger a full AetherTest pipeline run from the UI")
    st.markdown("---")

    st.warning("⚠️ Running the full pipeline from the UI is not yet implemented. Use the CLI for now:")
    st.code("AWS_PROFILE=kiro-dev python3 demo.py", language="bash")
    st.code("AWS_PROFILE=kiro-dev python3 orchestrator.py --fast", language="bash")

    st.markdown("### What the demo does:")
    st.markdown("""
    1. **AUT Analysis** — Maps 4 e-commerce components
    2. **Risk Scoring** — Computes risk scores based on change history
    3. **Strategy Generation** — Builds prioritized test strategy
    4. **Test Authoring** — Converts user stories to BDD tests
    5. **Test Generation** — Claude generates comprehensive test cases
    6. **Test Execution** — Runs tests with simulated failures
    7. **Failure Analysis** — Classifies failures and generates root causes
    8. **Coverage Report** — Maps coverage and provides deployment verdict
    """)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2: REQUIREMENTS
# ══════════════════════════════════════════════════════════════════════════════

elif page == "✍️ Requirements":
    st.title("✍️ Write Requirements")
    st.markdown("Describe your application and requirements in plain English. Claude will generate BDD test cases automatically — no coding needed.")
    st.markdown("---")

    # ── Step 1: Application Details ───────────────────────────────────────────
    st.markdown("### Step 1: Your Application")
    col1, col2, col3 = st.columns(3)
    with col1:
        app_name = st.text_input("Application Name", value="My Application", placeholder="e.g. E-Commerce Platform")
    with col2:
        app_version = st.text_input("Version", value="1.0.0", placeholder="e.g. 2.1.0")
    with col3:
        req_tenant_id = st.text_input("Tenant ID", value="my-tenant", placeholder="e.g. belron-uat")

    st.markdown("**Application Components** — list the parts of your application, one per line")
    components_text = st.text_area(
        "Components",
        value="Login Page\nDashboard\nCheckout\nPayment Service",
        height=100,
        label_visibility="collapsed",
        placeholder="Login Page\nShopping Cart\nCheckout\nPayment Service",
    )
    components = [c.strip() for c in components_text.strip().split("\n") if c.strip()]
    if components:
        st.caption(f"Detected {len(components)} components: {', '.join(components)}")

    st.markdown("---")

    # ── Step 2: Requirements ──────────────────────────────────────────────────
    st.markdown("### Step 2: Write Your Requirements")
    st.markdown("Write each requirement in plain English. Use user stories (*As a... I want... So that...*), acceptance criteria, or any business language.")

    if "requirements" not in st.session_state:
        st.session_state.requirements = [
            {"id": "REQ-001", "type": "user_story", "content": "As a customer, I want to log in with my email and password so that I can access my account securely"},
            {"id": "REQ-002", "type": "user_story", "content": "As a customer, I want to add items to my shopping cart so that I can purchase multiple products at once"},
            {"id": "REQ-003", "type": "acceptance_criteria", "content": "Payment processing must complete within 5 seconds and display a confirmation number to the user"},
        ]

    for i, req in enumerate(st.session_state.requirements):
        with st.container():
            col_id, col_type, col_del = st.columns([1.2, 2, 0.5])
            with col_id:
                new_id = st.text_input("ID", value=req["id"], key=f"req_id_{i}")
            with col_type:
                type_options = ["user_story", "acceptance_criteria", "business_rule"]
                cur_type = req.get("type", "user_story")
                cur_idx = type_options.index(cur_type) if cur_type in type_options else 0
                new_type = st.selectbox("Type", type_options, index=cur_idx, key=f"req_type_{i}")
            with col_del:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🗑️", key=f"del_req_{i}", help="Remove this requirement"):
                    st.session_state.requirements.pop(i)
                    st.rerun()

            new_content = st.text_area(
                f"Requirement {i + 1}",
                value=req["content"],
                key=f"req_content_{i}",
                height=80,
                label_visibility="collapsed",
                placeholder="Describe the requirement in plain English...",
            )
            st.session_state.requirements[i] = {"id": new_id, "type": new_type, "content": new_content}
            st.markdown("")

    if st.button("➕ Add Another Requirement"):
        n = len(st.session_state.requirements) + 1
        st.session_state.requirements.append({"id": f"REQ-{n:03d}", "type": "user_story", "content": ""})
        st.rerun()

    st.markdown("---")

    # ── Step 3: Generate ──────────────────────────────────────────────────────
    st.markdown("### Step 3: Generate Test Cases with AI")
    st.markdown(f"Claude will read your **{len(st.session_state.requirements)} requirement(s)** and generate complete BDD test cases with Given / When / Then steps.")

    if st.button("🤖 Generate Test Cases with Claude", type="primary", use_container_width=True):
        valid_reqs = [r for r in st.session_state.requirements if r.get("content", "").strip()]
        if not valid_reqs:
            st.error("Please write at least one requirement before generating.")
        else:
            with st.spinner(f"Claude is reading your {len(valid_reqs)} requirement(s) and generating BDD test cases..."):
                try:
                    from lambdas.test_author_agent.handler import handler as _test_author_agent
                    result = _test_author_agent({
                        "tenant_id": req_tenant_id,
                        "requirements": valid_reqs,
                        "aut_context": {
                            "name": app_name,
                            "version": app_version,
                            "components": components,
                        },
                    }, None)
                    st.session_state["req_result"] = result
                    st.session_state["req_app_name"] = app_name
                except Exception as e:
                    st.error(f"Generation failed: {e}")
                    st.stop()

    # ── Step 4: Results ───────────────────────────────────────────────────────
    if "req_result" in st.session_state:
        result = st.session_state["req_result"]
        used_app_name = st.session_state.get("req_app_name", "Application")

        suite = result.get("test_suite", {})
        test_cases = suite.get("test_cases", [])
        total = result.get("total_tests_authored", len(test_cases))

        st.markdown("---")
        st.success(f"Claude generated **{total} BDD test cases** for **{used_app_name}**")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Tests Generated", total)
        with col2:
            st.metric("High Priority", sum(1 for tc in test_cases if tc.get("priority") == "high"))
        with col3:
            st.metric("Medium Priority", sum(1 for tc in test_cases if tc.get("priority") == "medium"))
        with col4:
            st.metric("Low Priority", sum(1 for tc in test_cases if tc.get("priority") == "low"))

        if result.get("s3_key"):
            st.info(f"Saved to S3: `{result['s3_key']}`")

        st.markdown("---")
        st.markdown("### Generated BDD Test Cases")

        type_filter = st.multiselect(
            "Filter by test type",
            ["functional", "security", "performance", "usability"],
            default=["functional", "security", "performance", "usability"],
        )

        shown = 0
        for tc in test_cases:
            if tc.get("test_type", "functional") not in type_filter:
                continue
            shown += 1
            priority = tc.get("priority", "medium")
            priority_icon = "🔴" if priority == "high" else "🟡" if priority == "medium" else "🟢"
            tc_type = tc.get("test_type", "functional")

            with st.expander(f"{priority_icon} Test {shown}: {tc.get('test_name', 'Unknown')}  [{tc_type.upper()}]"):
                st.markdown(
                    f"**ID:** `{tc.get('test_id', 'N/A')}` &nbsp;|&nbsp; "
                    f"**Priority:** {priority.upper()} &nbsp;|&nbsp; "
                    f"**Requirement:** {tc.get('requirement_ref', 'N/A')}"
                )
                if tc.get("description"):
                    st.markdown(f"**Description:** {tc['description']}")
                st.markdown("")
                col_left, col_right = st.columns(2)
                with col_left:
                    if tc.get("given"):
                        st.markdown("**Given:**")
                        for g in tc["given"]:
                            st.markdown(f"- {g}")
                    if tc.get("when"):
                        st.markdown("**When:**")
                        for w in tc["when"]:
                            st.markdown(f"- {w}")
                with col_right:
                    if tc.get("then"):
                        st.markdown("**Then:**")
                        for t in tc["then"]:
                            st.markdown(f"- {t}")
                    if tc.get("acceptance_criteria"):
                        st.markdown(f"**Acceptance Criteria:** {tc['acceptance_criteria']}")
                if tc.get("tags"):
                    st.markdown(f"**Tags:** {' '.join(f'`{t}`' for t in tc['tags'])}")

        if shown == 0:
            st.info("No test cases match the selected filter.")

        st.markdown("---")
        st.download_button(
            label="⬇️ Download All Test Cases as JSON",
            data=json.dumps(suite, indent=2),
            file_name=f"test_cases_{used_app_name.lower().replace(' ', '_')}.json",
            mime="application/json",
            use_container_width=True,
        )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3: TEST CASES
# ══════════════════════════════════════════════════════════════════════════════

elif page == "📋 Test Cases":
    st.title("📋 Test Cases")
    st.markdown("Browse generated test cases from S3")
    st.markdown("---")

    tc_tenant = st.text_input(
        "Tenant ID",
        value="demo-ecommerce",
        help="Enter the tenant ID you used when generating test cases",
    )

    if st.button("🔍 Find Test Cases"):
        test_case_objects = list_s3_objects(f"{tc_tenant}/test-cases/", max_keys=50)
        test_case_objects.extend(list_s3_objects(f"{tc_tenant}/authored-tests/", max_keys=50))
        st.session_state["tc_objects"] = test_case_objects
        st.session_state["tc_tenant"] = tc_tenant

    test_case_objects = st.session_state.get("tc_objects", [])

    if not test_case_objects:
        st.info("Enter your Tenant ID above and click 'Find Test Cases'. Use `demo-ecommerce` for the demo run or `demo-tenant` for the orchestrator run.")
    else:
        st.success(f"Found {len(test_case_objects)} test case files")

        # Select a test suite
        test_suite_keys = [obj["Key"] for obj in test_case_objects if obj["Key"].endswith(".json")]
        if test_suite_keys:
            selected_key = st.selectbox("Select Test Suite", test_suite_keys)

            if st.button("Load Test Suite"):
                test_suite = get_s3_object(selected_key)

                if test_suite:
                    st.markdown(f"**Suite ID:** {test_suite.get('test_suite_id', test_suite.get('suite_id', 'N/A'))}")
                    st.markdown(f"**Generated At:** {test_suite.get('generated_at', test_suite.get('authored_at', 'N/A'))}")
                    st.markdown(f"**Total Tests:** {test_suite.get('total_test_cases', test_suite.get('total_tests', 0))}")

                    test_cases = test_suite.get("test_cases", [])

                    if test_cases:
                        st.markdown("---")
                        st.markdown("### Test Cases")

                        for i, tc in enumerate(test_cases[:20], 1):
                            with st.expander(f"Test {i}: {tc.get('test_name', 'Unknown')}"):
                                st.json(tc)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4: TEST RESULTS
# ══════════════════════════════════════════════════════════════════════════════

elif page == "📊 Test Results":
    st.title("📊 Test Results")
    st.markdown("View test execution results and pass/fail breakdown")
    st.markdown("---")

    res_tenant = st.text_input(
        "Tenant ID",
        value="demo-ecommerce",
        help="Enter the tenant ID used during the test run",
    )

    if st.button("🔍 Find Results"):
        result_objects = list_s3_objects(f"{res_tenant}/executor-results/", max_keys=50)
        result_objects.extend(list_s3_objects(f"{res_tenant}/test-results/", max_keys=50))
        st.session_state["res_objects"] = result_objects
        st.session_state["res_tenant"] = res_tenant

    result_objects = st.session_state.get("res_objects", [])

    if not result_objects:
        st.info("Enter your Tenant ID above and click 'Find Results'. Use `demo-ecommerce` for the demo run or `demo-tenant` for the orchestrator run.")
    else:
        st.success(f"Found {len(result_objects)} result files")

        result_keys = [obj["Key"] for obj in result_objects if obj["Key"].endswith(".json")]
        if result_keys:
            selected_key = st.selectbox("Select Execution Results", result_keys)

            if st.button("Load Results"):
                results = get_s3_object(selected_key)

                if results:
                    summary = results.get("summary", {})

                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Tests", summary.get("total", 0))
                    with col2:
                        st.metric("Passed", summary.get("passed", 0), delta_color="normal")
                    with col3:
                        st.metric("Failed", summary.get("failed", 0), delta_color="inverse")
                    with col4:
                        st.metric("Pass Rate", f"{summary.get('pass_rate', 0)}%")

                    st.markdown("---")

                    # Show failed tests
                    failed_tests = results.get("failed_tests", [])
                    if failed_tests:
                        st.markdown("### ❌ Failed Tests")
                        for ft in failed_tests:
                            with st.expander(f"❌ {ft.get('test_name', 'Unknown')}"):
                                st.markdown(f"**Component:** {ft.get('component', 'N/A')}")
                                st.markdown(f"**Failure Reason:** {ft.get('failure_reason', 'N/A')}")
                                st.markdown(f"**Failure Type:** {ft.get('failure_type', 'N/A')}")
                                st.json(ft.get("evidence", {}))

                    # Show all results
                    st.markdown("### All Test Results")
                    all_results = results.get("results", [])
                    for r in all_results[:20]:
                        status = r.get("status", "unknown")
                        icon = "✅" if status == "passed" else "❌" if status == "failed" else "⊘"
                        with st.expander(f"{icon} {r.get('test_name', 'Unknown')} — {status.upper()}"):
                            st.json(r)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 5: COVERAGE REPORT
# ══════════════════════════════════════════════════════════════════════════════

elif page == "📈 Coverage Report":
    st.title("📈 Coverage Report")
    st.markdown("View test coverage map and deployment verdict")
    st.markdown("---")

    cov_tenant = st.text_input(
        "Tenant ID",
        value="demo-ecommerce",
        help="Enter the tenant ID used during the test run",
    )

    if st.button("🔍 Find Coverage Reports"):
        coverage_objects = list_s3_objects(f"{cov_tenant}/coverage/", max_keys=50)
        st.session_state["cov_objects"] = coverage_objects
        st.session_state["cov_tenant"] = cov_tenant

    coverage_objects = st.session_state.get("cov_objects", [])

    if not coverage_objects:
        st.info("Enter your Tenant ID above and click 'Find Coverage Reports'.")
    else:
        st.success(f"Found {len(coverage_objects)} coverage reports")

        coverage_keys = [obj["Key"] for obj in coverage_objects if obj["Key"].endswith(".json")]
        if coverage_keys:
            selected_key = st.selectbox("Select Coverage Report", coverage_keys)

            if st.button("Load Coverage Report"):
                report = get_s3_object(selected_key)

                if report:
                    metrics = report.get("metrics", {})
                    ai_analysis = report.get("ai_analysis", {})
                    verdict = ai_analysis.get("deployment_verdict", "unknown")

                    # Metrics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Coverage", f"{metrics.get('overall_coverage_pct', 0)}%")
                    with col2:
                        st.metric("Pass Rate", f"{metrics.get('pass_rate', 0)}%")
                    with col3:
                        st.metric("Total Tests", metrics.get("total_tests", 0))
                    with col4:
                        st.metric("Failed Tests", metrics.get("failed_tests", 0))

                    st.markdown("---")

                    # Deployment Verdict
                    st.markdown("### 🎯 Deployment Verdict")
                    if verdict == "safe_to_deploy":
                        st.success(f"🟢 **SAFE TO DEPLOY**")
                    elif verdict == "deploy_with_caution":
                        st.warning(f"🟡 **DEPLOY WITH CAUTION**")
                    else:
                        st.error(f"🔴 **DO NOT DEPLOY**")

                    st.markdown(f"**Rationale:** {ai_analysis.get('verdict_rationale', 'N/A')}")

                    st.markdown("---")

                    # Component Coverage
                    st.markdown("### Component Coverage")
                    comp_coverage = report.get("component_coverage", {})
                    for comp_name, data in comp_coverage.items():
                        with st.expander(f"{comp_name} — {data.get('test_count', 0)} tests"):
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Tests", data.get("test_count", 0))
                            with col2:
                                st.metric("Pass Rate", f"{data.get('pass_rate', 0)}%")
                            with col3:
                                st.metric("Risk Score", f"{data.get('risk_score', 0):.0f}/100")

                    # Critical Gaps
                    critical_gaps = ai_analysis.get("critical_gaps", [])
                    if critical_gaps:
                        st.markdown("---")
                        st.markdown("### ⚠️ Critical Gaps")
                        for gap in critical_gaps:
                            st.warning(f"**{gap.get('component', 'Unknown')}** — {gap.get('recommendation', 'N/A')}")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 6: AGENT ACTIVITY
# ══════════════════════════════════════════════════════════════════════════════

elif page == "🤖 Agent Activity":
    st.title("🤖 Agent Activity")
    st.markdown("View what each agent did in recent runs")
    st.markdown("---")

    # Query DynamoDB for recent agent activity
    tenant_id = st.selectbox("Select Tenant", ["demo-ecommerce", "demo-tenant"])

    if st.button("Load Agent Activity"):
        items = query_dynamodb_table(STRATEGIES_TABLE, f"TENANT#{tenant_id}", limit=20)

        if not items:
            st.info(f"No agent activity found for tenant: {tenant_id}")
        else:
            st.success(f"Found {len(items)} activity records")

            for item in items:
                sk = item.get("SK", "")
                agent = item.get("agent", "unknown")

                if "AUTHORED_SUITE" in sk:
                    with st.expander(f"✍️ Test Author — {item.get('authored_at', 'N/A')}"):
                        st.json(item)
                elif "COVERAGE" in sk:
                    with st.expander(f"📊 Coverage Agent — {item.get('generated_at', 'N/A')}"):
                        st.json(item)
                elif "MAINTENANCE" in sk:
                    with st.expander(f"🔧 Maintenance Agent — {item.get('maintained_at', 'N/A')}"):
                        st.json(item)
                elif "STRATEGY" in sk:
                    with st.expander(f"🧠 Strategy Generator — {item.get('created_at', 'N/A')}"):
                        st.json(item)
                elif "TEST_SUITE" in sk:
                    with st.expander(f"  Test Case Generator — {item.get('generated_at', 'N/A')}"):
                        st.json(item)
                else:
                    with st.expander(f"🤖 {agent} — {sk}"):
                        st.json(item)

    st.markdown("---")
    st.markdown("### Agent Summary")
    st.markdown("""
    - **Test Strategist**: AUT analysis, risk scoring, strategy generation
    - **Test Author**: Converts requirements to BDD test cases
    - **Test Executor**: Runs tests with self-healing
    - **Test Analyst**: Root cause analysis and failure classification
    - **Test Maintenance**: Updates tests when AUT changes
    - **Coverage & Risk**: Coverage mapping and deployment verdicts
    """)
