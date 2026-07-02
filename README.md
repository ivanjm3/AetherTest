

# AetherTest — Multi-Agent AI Testing Platform

**AWS-native intelligent testing solution powered by Claude Sonnet 4**

AetherTest is a production-ready multi-agent AI testing platform that uses Amazon Bedrock and Claude Sonnet 4 to automatically analyze applications, generate test strategies, author test cases from requirements, execute tests with self-healing, analyze failures, maintain tests, and provide deployment verdicts.

---

## What AetherTest Does

AetherTest replaces manual test planning, authoring, and maintenance with 6 intelligent AI agents that work together to:

1. **Understand your application** — Maps components, dependencies, and risk areas
2. **Generate test strategies** — Prioritizes testing based on risk scores and change history
3. **Author BDD tests from requirements** — Converts user stories to Given/When/Then test cases
4. **Generate comprehensive test cases** — Claude creates functional, edge case, and security tests
5. **Execute tests intelligently** — Simulates browser/API interactions with self-healing
6. **Analyze failures deeply** — Classifies defects vs. false positives with root cause analysis
7. **Maintain tests automatically** — Updates tests when UI elements or APIs change
8. **Report coverage and risk** — Provides deployment verdicts based on coverage and pass rates

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         AetherTest Platform                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  AGENT 1: Test Strategist (AUT Analysis + Risk + Strategy)  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│           │                                                         │
│           ├─► AUT Analyzer       → Maps application structure      │
│           ├─► Risk Scorer         → Computes component risk        │
│           └─► Strategy Generator  → Builds test strategy           │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  AGENT 2: Test Author (Requirements → BDD Tests)            │  │
│  └──────────────────────────────────────────────────────────────┘  │
│           │                                                         │
│           └─► Converts user stories to Given/When/Then tests       │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  AGENT 3: Test Executor (Run Tests + Self-Healing)          │  │
│  └──────────────────────────────────────────────────────────────┘  │
│           │                                                         │
│           └─► Executes tests, heals broken locators                │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  AGENT 4: Test Analyst (Failure Analysis + Root Cause)      │  │
│  └──────────────────────────────────────────────────────────────┘  │
│           │                                                         │
│           └─► Classifies failures, generates fix suggestions       │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  AGENT 5: Test Maintenance (AUT Change Detection)           │  │
│  └──────────────────────────────────────────────────────────────┘  │
│           │                                                         │
│           └─► Updates tests when UI/API changes                    │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  AGENT 6: Coverage & Risk (Coverage Map + Verdict)          │  │
│  └──────────────────────────────────────────────────────────────┘  │
│           │                                                         │
│           └─► Maps coverage, provides deployment verdict           │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                         AWS Services                                │
├─────────────────────────────────────────────────────────────────────┤
│  • Amazon Bedrock (Claude Sonnet 4)  — AI reasoning engine         │
│  • Amazon S3                          — Test artifacts storage      │
│  • Amazon DynamoDB                    — Metadata & learning data    │
│  • AWS Lambda (optional)              — Serverless execution        │
│  • AWS Step Functions (optional)      — Orchestration               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## The 6 Intelligent Agents

### 🧠 Agent 1: Test Strategist
**Components:** AUT Analyzer, Risk Scorer, Strategy Generator

- Maps application structure (components, dependencies, APIs, UI pages)
- Computes risk scores based on change history and defect patterns
- Generates prioritized test strategies (high/medium/low priority)
- Allocates test coverage based on risk

**Input:** AUT metadata (components, APIs, dependencies)  
**Output:** Test strategy with prioritized component coverage

---

### ✍️ Agent 2: Test Author
**Converts business requirements to executable BDD test cases**

- Understands plain text requirements and user stories
- Supports "As a... I want... So that..." format
- Generates Given/When/Then BDD test cases
- Covers happy paths, edge cases, and negative scenarios

**Input:** User stories, acceptance criteria  
**Output:** BDD test cases in Given/When/Then format

---

### ▶️ Agent 3: Test Executor
**Executes tests with intelligent simulation and self-healing**

- Simulates browser interactions for UI tests
- Makes real HTTP calls for API tests (if endpoint provided)
- Self-heals broken locators by finding semantically similar elements
- Reports pass/fail with detailed evidence

**Input:** Test cases  
**Output:** Execution results with pass/fail status and evidence

---

### 🔍 Agent 4: Test Analyst
**Deep failure analysis with root cause hypotheses**

- Classifies failures: `application_defect`, `test_data_issue`, `environment_instability`, `regression`
- Correlates failures with recent code changes
- Generates root cause hypotheses and fix suggestions
- Reduces false positives by checking consistency across runs

**Input:** Failed tests, recent changes, run history  
**Output:** Failure classifications with root cause analysis

---

### 🔧 Agent 5: Test Maintenance
**Automatically updates tests when the application changes**

- Detects UI element changes (button IDs, locators)
- Detects API schema changes (endpoints, request/response formats)
- Regenerates affected test steps using Claude
- Retires obsolete tests when features are removed
- Flags coverage gaps for new features

**Input:** AUT changes, existing test suite  
**Output:** Updated test suite with maintenance report

---

### 📊 Agent 6: Coverage & Risk
**Maps test coverage and provides deployment verdicts**

- Computes per-component test coverage
- Identifies undertested critical paths
- Generates coverage quality scores
- Provides deployment verdict: `safe_to_deploy`, `deploy_with_caution`, `do_not_deploy`
- Recommends actions to improve coverage

**Input:** Test results, AUT graph, risk scores  
**Output:** Coverage report with deployment verdict

---

## AWS Services Used

### Amazon Bedrock
- **Model:** `us.anthropic.claude-sonnet-4-20250514-v1:0`
- **Usage:** All AI reasoning (test generation, failure analysis, maintenance)
- **Region:** us-east-1

### Amazon S3
- **Bucket:** `aethertest-artifacts-654654478821`
- **Contents:**
  - `{tenant_id}/aut-graphs/` — AUT component graphs
  - `{tenant_id}/strategies/` — Test strategies
  - `{tenant_id}/test-cases/` — Generated test cases
  - `{tenant_id}/authored-tests/` — BDD tests from requirements
  - `{tenant_id}/executor-results/` — Test execution results
  - `{tenant_id}/analysis/` — Failure analysis reports
  - `{tenant_id}/coverage/` — Coverage reports
  - `{tenant_id}/maintenance/` — Maintenance reports

### Amazon DynamoDB
- **Tables:**
  - `aethertest-strategies` — Test strategies and metadata
  - `aethertest-agent-assignments` — Agent execution tracking
  - `aethertest-defect-patterns` — Historical defect data (90-day TTL)
  - `aethertest-executions` — Execution state tracking

---

## Quick Start

### Prerequisites
- Python 3.9+
- AWS CLI configured with profile `kiro-dev`
- Access to Amazon Bedrock (Claude Sonnet 4 enabled)
- AWS Account: `654654478821`
- Region: `us-east-1`

### Installation

```bash
# Clone the repository
cd /Users/ra20481785/multiagent_data_testing

# Install dependencies
pip install boto3 pydantic streamlit requests

# Verify Bedrock connection
AWS_PROFILE=kiro-dev python3 verify_bedrock.py
```

---

## Running the Demo

### Option 1: Quick 2-Minute Demo (Recommended)

```bash
AWS_PROFILE=kiro-dev python3 demo.py
```

**What it does:**
- Uses a pre-built e-commerce checkout flow AUT
- Runs all 6 agents in sequence
- Limits to 3 tests per component (fast mode)
- Shows colored terminal output
- Completes in ~2 minutes

**Expected output:**
```
╔══════════════════════════════════════════════════════════════╗
║          AetherTest — AI-Powered Multi-Agent Testing         ║
║              E-Commerce Checkout Flow Demo                   ║
╚══════════════════════════════════════════════════════════════╝

[1/7] AUT Analyzer
  ✓ Mapped 4 components

[2/7] Risk Scorer
  ✓ Scored 4 components | 2 high-priority

[3/7] Strategy Generator
  ✓ Strategy created | Est. 180s

[4/7] Test Author Agent
  ✓ Authored 6 BDD test cases from 2 requirements

[5/7] Test Case Generator
  ✓ Generated 12 test cases + 6 BDD tests

[6/7] Test Executor Agent
  ✓ Executed 18 tests | Passed: 15 | Failed: 3 | Pass Rate: 83.3%

[7/7] Test Analyst Agent
  ✓ Analyzed failures | Real defects: 2 | False positives: 1

═══════════════════════════════════════════════════════════════
  AETHERTEST DEMO COMPLETE
═══════════════════════════════════════════════════════════════

  Deployment Verdict:  🟡  DEPLOY WITH CAUTION

  Pass Rate:    83.3%
  Coverage:     100%
  Tests Run:    18
  Failures:     3
  Demo Time:    127.3s
```

---

### Option 2: Full Orchestrator (All Steps)

```bash
AWS_PROFILE=kiro-dev python3 orchestrator.py
```

**What it does:**
- Runs the complete 9-step pipeline
- Includes learning update and defect pattern storage
- Saves full results to JSON file
- Takes ~3-5 minutes

**Fast mode:**
```bash
AWS_PROFILE=kiro-dev python3 orchestrator.py --fast
```

**Custom AUT:**
```bash
AWS_PROFILE=kiro-dev python3 orchestrator.py --aut-file my_aut.json
```

---

### Option 3: Streamlit Web UI

```bash
AWS_PROFILE=kiro-dev streamlit run ui/app.py
```

**Features:**
- 🏠 Dashboard — Platform overview
- ▶️ Run Demo — Trigger pipeline runs
- 📋 Test Cases — Browse generated tests
- 📊 Test Results — View execution results
- 📈 Coverage Report — Coverage map and verdicts
- 🤖 Agent Activity — See what each agent did

**Access:** http://localhost:8501

---

## Viewing Results in AWS

### S3 Bucket
```bash
aws s3 ls s3://aethertest-artifacts-654654478821/demo-ecommerce/ --recursive --profile kiro-dev
```

### DynamoDB Tables
```bash
# View strategies
aws dynamodb query \
  --table-name aethertest-strategies \
  --key-condition-expression "PK = :pk" \
  --expression-attribute-values '{":pk":{"S":"TENANT#demo-ecommerce"}}' \
  --profile kiro-dev

# View defect patterns
aws dynamodb query \
  --table-name aethertest-defect-patterns \
  --key-condition-expression "PK = :pk" \
  --expression-attribute-values '{":pk":{"S":"TENANT#demo-ecommerce"}}' \
  --profile kiro-dev
```

### Bedrock Model Access
```bash
aws bedrock list-foundation-models \
  --region us-east-1 \
  --profile kiro-dev \
  --query 'modelSummaries[?contains(modelId, `claude`)]'
```

---

## Testing Guide

### Step-by-Step Testing

1. **Verify AWS Access**
   ```bash
   aws sts get-caller-identity --profile kiro-dev
   ```

2. **Verify Bedrock Access**
   ```bash
   AWS_PROFILE=kiro-dev python3 verify_bedrock.py
   ```

3. **Run Quick Demo**
   ```bash
   AWS_PROFILE=kiro-dev python3 demo.py
   ```

4. **Check S3 for Results**
   ```bash
   aws s3 ls s3://aethertest-artifacts-654654478821/demo-ecommerce/ --recursive --profile kiro-dev
   ```

5. **Launch Web UI**
   ```bash
   AWS_PROFILE=kiro-dev streamlit run ui/app.py
   ```

6. **Run Full Orchestrator**
   ```bash
   AWS_PROFILE=kiro-dev python3 orchestrator.py --fast
   ```

---

## Expected Outputs

### Demo Output
- **Duration:** ~2 minutes
- **Tests Run:** 15-20 (3 per component in fast mode)
- **Pass Rate:** 80-90% (with simulated failures)
- **Deployment Verdict:** Usually "deploy_with_caution" (realistic demo)

### Orchestrator Output
- **Duration:** ~3-5 minutes
- **Tests Run:** 30-50 (full coverage)
- **Pass Rate:** 85-95%
- **Files Created:**
  - `pipeline_results_{execution_id}.json` — Full pipeline results
  - S3 artifacts in `s3://aethertest-artifacts-654654478821/`
  - DynamoDB records in all 4 tables

### Streamlit UI
- **Pages:** 6 interactive pages
- **Data Source:** Real S3 and DynamoDB data
- **Refresh:** Re-run queries to see latest results

---

## Showcasing to Others

### 1. Live Demo Script

```bash
# Terminal 1: Run the demo
AWS_PROFILE=kiro-dev python3 demo.py

# Terminal 2: Launch the UI
AWS_PROFILE=kiro-dev streamlit run ui/app.py

# Terminal 3: Show AWS resources
aws s3 ls s3://aethertest-artifacts-654654478821/demo-ecommerce/ --recursive --profile kiro-dev
```

### 2. Key Talking Points

- **6 AI agents** working together, each with a specialized role
- **Claude Sonnet 4** powers all reasoning and generation
- **AWS-native** — uses Bedrock, S3, DynamoDB (no external dependencies)
- **Self-healing tests** — automatically fixes broken locators
- **BDD from requirements** — converts user stories to Given/When/Then
- **Root cause analysis** — not just "test failed" but "why it failed"
- **Deployment verdicts** — safe_to_deploy, deploy_with_caution, do_not_deploy
- **Closed-loop learning** — learns from past failures to improve future runs

### 3. Demo Flow

1. **Show the architecture** — 6 agents, AWS services
2. **Run `demo.py`** — watch colored output, explain each agent
3. **Open Streamlit UI** — browse test cases, results, coverage
4. **Show S3 bucket** — real artifacts stored in AWS
5. **Show DynamoDB** — metadata and learning data
6. **Explain the verdict** — how coverage + pass rate = deployment decision

---

## File Structure

```
aethertest/
├── aethertest/
│   ├── __init__.py
│   └── bedrock_client.py          ← Bedrock connection module
├── layers/
│   └── serializer/
│       ├── models.py               ← Pydantic data models
│       ├── serializer.py           ← JSON serialization
│       └── markdown.py             ← Markdown formatting
├── lambdas/
│   ├── aut_analyzer/handler.py    ← AUT structure analysis
│   ├── risk_scorer/handler.py     ← Risk score computation
│   ├── strategy_generator/handler.py ← Test strategy generation
│   ├── test_case_generator/handler.py ← Claude test generation
│   ├── test_author_agent/handler.py   ← Requirements → BDD tests
│   ├── test_executor_agent/handler.py ← Test execution + self-healing
│   ├── test_analyst_agent/handler.py  ← Failure analysis
│   ├── test_maintenance_agent/handler.py ← Test maintenance
│   ├── coverage_risk_agent/handler.py    ← Coverage + verdict
│   ├── agent_dispatcher/handler.py       ← Agent dispatch
│   ├── failure_triage/handler.py         ← Failure classification
│   ├── learning_updater/handler.py       ← Closed-loop learning
│   └── result_aggregator/handler.py      ← Result aggregation
├── ui/
│   ├── app.py                     ← Streamlit web UI
│   └── requirements.txt           ← UI dependencies
├── orchestrator.py                ← Master pipeline runner
├── demo.py                        ← Quick 2-minute demo
├── verify_bedrock.py              ← Bedrock connection test
├── setup_aws.py                   ← AWS resource setup
└── README.md                      ← This file
```

---

## Troubleshooting

### Issue: "Access denied to Bedrock model"
**Solution:**
```bash
# Check IAM permissions
aws iam get-user --profile kiro-dev

# Verify model access in Bedrock console
# https://console.aws.amazon.com/bedrock/home?region=us-east-1#/modelaccess
```

### Issue: "S3 bucket not found"
**Solution:**
```bash
# Verify bucket exists
aws s3 ls s3://aethertest-artifacts-654654478821 --profile kiro-dev

# If missing, run setup
AWS_PROFILE=kiro-dev python3 setup_aws.py
```

### Issue: "DynamoDB table not found"
**Solution:**
```bash
# List tables
aws dynamodb list-tables --profile kiro-dev

# If missing, run setup
AWS_PROFILE=kiro-dev python3 setup_aws.py
```

### Issue: "Claude response parsing error"
**Solution:**
- Claude occasionally returns malformed JSON
- All agents have fallback logic for this case
- Check CloudWatch logs for details

### Issue: "Streamlit won't start"
**Solution:**
```bash
# Install dependencies
pip install streamlit boto3 pydantic

# Check port 8501 is available
lsof -i :8501

# Run with explicit port
streamlit run ui/app.py --server.port 8502
```

---

## Advanced Usage

### Custom AUT Configuration

Create a JSON file with your AUT structure:

```json
{
  "tenant_id": "my-company",
  "aut_id": "my-app",
  "aut_version": "1.0.0",
  "aut_metadata": {
    "components": [
      {
        "component_id": "user-service",
        "name": "User Service",
        "component_type": "api_endpoint",
        "dependencies": [],
        "api_surface": ["/api/users", "/api/users/{id}"],
        "ui_entry_points": [],
        "metadata": {"criticality": "high"}
      }
    ]
  }
}
```

Run with:
```bash
AWS_PROFILE=kiro-dev python3 orchestrator.py --aut-file my_aut.json
```

### Custom Requirements

Create a requirements list:

```python
requirements = [
    {
        "id": "REQ-001",
        "type": "user_story",
        "content": "As a user, I want to log in with my email so that I can access my account",
        "component": "User Service",
    }
]
```

### Programmatic Usage

```python
from orchestrator import run_pipeline

results = run_pipeline(aut_config=my_aut, fast_mode=True)
print(results["final_verdict"])
```

---

## Performance

- **Demo mode:** ~2 minutes (3 tests/component)
- **Fast mode:** ~3-5 minutes (5 tests/component)
- **Full mode:** ~10-15 minutes (8 tests/component)

**Bottlenecks:**
- Claude API calls (1-3s per call)
- S3 uploads (minimal)
- DynamoDB writes (minimal)

**Optimization:**
- Use fast mode for demos
- Batch Claude calls where possible
- Cache AUT graphs and strategies

---

## Future Enhancements

- [ ] Real browser automation (Selenium/Playwright integration)
- [ ] Real API testing (actual HTTP calls)
- [ ] Visual regression testing (screenshot comparison)
- [ ] Performance testing (load/stress tests)
- [ ] Security testing (OWASP Top 10)
- [ ] CI/CD integration (GitHub Actions, GitLab CI)
- [ ] Slack/Teams notifications
- [ ] Multi-tenant isolation
- [ ] Cost tracking and optimization
- [ ] A/B testing for test strategies

---

## Support

For issues or questions:
- Check the troubleshooting section above
- Review CloudWatch logs for Lambda errors
- Check S3 and DynamoDB for data consistency
- Verify Bedrock model access in AWS Console

---

## License

Proprietary — Internal use only

---

## Credits

Built with:
- **Amazon Bedrock** — Claude Sonnet 4 AI reasoning
- **AWS Lambda** — Serverless compute
- **Amazon S3** — Artifact storage
- **Amazon DynamoDB** — Metadata and learning data
- **Streamlit** — Web UI framework
- **Pydantic** — Data validation
- **Boto3** — AWS SDK for Python

---

**AetherTest** — Intelligent testing, powered by AI  
