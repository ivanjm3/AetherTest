# AetherTest

AetherTest is an AWS-native, multi-agent testing platform that uses Amazon Bedrock (Claude) to automate the test lifecycle for a target application: mapping its structure, scoring risk, generating and authoring test cases, executing them in a real headless browser, triaging failures, and issuing a deployment verdict (`safe_to_deploy` / `deploy_with_caution` / `do_not_deploy`). Each pipeline stage is an independent AWS Lambda handler orchestrated either by a local Python orchestrator (for demos) or an AWS Step Functions state machine (for production), with results persisted to S3 and DynamoDB and surfaced through a React/FastAPI web app.

This README is the single source of truth for the project — architecture, setup, and design decisions all live here.

## Features

- 6-stage agent pipeline: AUT analysis, risk scoring, strategy generation, test authoring/generation, real browser execution, failure triage
- Real test execution: Claude generates a Playwright script per test case, it runs in a real headless browser, and the trace is uploaded to S3 — not just an LLM guessing pass/fail. Falls back to LLM-simulated execution (clearly tagged `execution_mode: "llm_simulated"` in every result) only when Playwright isn't installed or no target URL was given.
- BDD test authoring from plain-English user stories (Given/When/Then)
- Deployment verdicts derived from coverage + pass rate + defect classification
- Closed-loop learning: defect patterns feed back into future risk scoring
- Athena-backed query interface for ad hoc analysis of stored results
- Same Lambda handlers run three ways: in-process (orchestrator/API server), as deployed Lambdas, or as Step Functions tasks
- Every handler is wrapped with structured JSON logging, CloudWatch metrics, retry-with-backoff on transient AWS errors, and idempotent replay keyed on `execution_id` (`aethertest/observability.py`)

## Architecture

```
┌────────────────────────┐        ┌──────────────────────────┐
│  React + Vite frontend │──HTTP─▶│   FastAPI (api-server.py) │
│  (Zustand, TS, Tailwind)│◀──────│   single container         │
└────────────────────────┘        └────────────┬──────────────┘
                                                │ invokes handlers
                                                │ in-process, or
                                                │ triggers Step Functions
                    ┌───────────────────────────┼───────────────────────────┐
                    │                           │                           │
         ┌──────────▼─────────┐     ┌───────────▼──────────┐     ┌─────────▼─────────┐
         │ AUT Analyzer        │     │ Test Executor          │     │ Coverage & Risk    │
         │ Risk Scorer          │────▶│ (Playwright, real)     │────▶│ (verdict)          │
         │ Strategy Generator   │     │ Test Analyst           │     │ Learning Updater   │
         │ Test Author/Case Gen │     │ (failure triage)       │     │                    │
         └──────────┬─────────┘     └───────────┬──────────┘     └─────────┬─────────┘
                    │                           │                           │
                    └───────────────┬───────────┴───────────────┬───────────┘
                                    │                           │
                         ┌──────────▼──────────┐     ┌──────────▼──────────┐
                         │ Amazon Bedrock       │     │ S3 (artifacts) +     │
                         │ (Claude, reasoning)  │     │ DynamoDB (state)     │
                         └──────────────────────┘     └──────────────────────┘
```

Each box under "AUT Analyzer / Risk Scorer / ..." is a standalone Lambda handler (`lambdas/*/handler.py`) sharing a common serializer layer. `orchestrator.py` calls them directly for local runs; `statemachine/test_cycle.asl.json` wires the same ARNs into a Step Functions definition for production.

## Tech Stack

**Backend:** Python 3.12, FastAPI, boto3, Pydantic v2, AWS Lambda, AWS Step Functions
**Frontend:** React 19, TypeScript, Vite, Zustand, Tailwind CSS, Vitest
**AI:** Amazon Bedrock (`us.anthropic.claude-sonnet-4-20250514-v1:0`)
**Execution:** Playwright (real headless-browser test execution, `pip install -e ".[execution]"`)
**Data:** Amazon S3 (artifacts, traces), DynamoDB (strategies, assignments, defect patterns, executions, idempotency), Athena (ad hoc querying)
**Deploy:** Docker (multi-stage: Node build → Python runtime), AWS App Runner, ECR, CloudFront, CodeBuild
**Observability:** Structured JSON logs + CloudWatch custom metrics + retry/idempotency, all via `aethertest/observability.py`
**Testing:** pytest, hypothesis, moto (AWS mocking)

## Installation

```bash
git clone <repository-url>
cd AetherTest

# Backend
pip install -e .
pip install -e ".[test,dev]"        # optional: pytest, ruff, black
pip install -e ".[execution]"       # optional: Playwright, for real browser test execution
playwright install chromium         # only needed if you installed the execution extra

# Frontend
cd frontend
npm install
```

## Configuration

AWS credentials are required (Bedrock, S3, DynamoDB, Step Functions, Athena). Locally this project uses an AWS SSO profile; in App Runner it uses the instance role. No AWS account ID or profile name is hardcoded anywhere in the codebase — set these in your own environment.

```bash
aws configure sso --profile <your-profile>
aws sso login --profile <your-profile>
```

All configuration is centralized in `aethertest/config.py`; every handler and script imports from there instead of hardcoding a default. Key environment variables it reads (see also `frontend/.env.example` and `deploy/config.sh`):

| Variable | Default | Purpose |
|---|---|---|
| `AWS_PROFILE` | — | Local SSO profile (must be empty/unset in containers) |
| `AWS_DEFAULT_REGION` | `us-east-1` | AWS region |
| `BEDROCK_MODEL_ID` | `us.anthropic.claude-sonnet-4-20250514-v1:0` | Claude model used by every agent |
| `AETHERTEST_BUCKET` | `aethertest-artifacts` | S3 bucket for artifacts and Playwright traces |
| `STRATEGIES_TABLE` / `ASSIGNMENTS_TABLE` / `DEFECT_PATTERNS_TABLE` / `EXECUTIONS_TABLE` / `IDEMPOTENCY_TABLE` | `aethertest-*` | DynamoDB table names |
| `ATHENA_DATABASE` / `ATHENA_OUTPUT_BUCKET` | — | Athena query target and results bucket |
| `AETHERTEST_NO_SSL_VERIFY` | unset | Disable TLS verification behind corporate proxies |

`setup_aws.py` only writes local AWS credentials to `~/.aws/credentials` and verifies Bedrock connectivity — it does **not** provision infrastructure. Before first use, create the S3 bucket and the five DynamoDB tables (`aethertest-strategies`, `aethertest-agent-assignments`, `aethertest-defect-patterns`, `aethertest-executions`, `aethertest-idempotency`) yourself, e.g. via the AWS Console or CLI. See [Future Improvements](#future-improvements) — this is exactly the kind of manual step Terraform/CDK should own.

```bash
python setup_aws.py    # writes ~/.aws/credentials, checks Bedrock access
```

## Running locally

```bash
# Verify Bedrock connectivity
AWS_PROFILE=aethertest python verify_bedrock.py

# Backend API (FastAPI, serves the built frontend too)
AWS_PROFILE=aethertest python frontend/api-server.py    # http://localhost:8001

# Frontend dev server (separate terminal, hot reload against the API)
cd frontend && npm run dev                                # http://localhost:5173
```

CLI-only runs, no server needed:

```bash
AWS_PROFILE=aethertest python demo.py                      # ~2 min, canned e-commerce AUT
AWS_PROFILE=aethertest python orchestrator.py --fast       # full 9-step pipeline
```

## Example usage

Run the full pipeline against a custom application description:

```bash
AWS_PROFILE=aethertest python orchestrator.py --aut-file my_aut.json
```

```python
from orchestrator import run_pipeline

results = run_pipeline(aut_config=my_aut, fast_mode=True)
print(results["final_verdict"])
# {"deployment_verdict": "deploy_with_caution", "pass_rate": 83.3, "coverage_pct": 100, ...}
```

Authoring BDD tests from a user story (same call the API server makes):

```python
requirements = [{
    "id": "REQ-001",
    "type": "user_story",
    "content": "As a user, I want to reset my password via email so I can recover my account",
    "component": "Login Service",
}]
```

## Project Structure

```
aethertest/            config.py (single source of truth for bucket/table/region config),
                       observability.py (structured logging + metrics + retry + idempotency,
                       applied to every handler), bedrock_client.py, aws_clients.py
layers/serializer/    Pydantic models, JSON serializer, markdown formatter — the shared
                       data contract between agents (deployed as a Lambda layer in prod)
lambdas/               One directory per agent capability, each a standalone Lambda handler:
                       aut_analyzer, risk_scorer, strategy_generator, test_case_generator,
                       test_author_agent, test_executor_agent (+ playwright_runner.py for
                       real browser execution), test_analyst_agent, coverage_risk_agent,
                       learning_updater, agent_dispatcher, failure_triage, result_aggregator
statemachine/          Step Functions ASL definition (test_cycle.asl.json) wiring the
                       Lambda handlers into the production orchestration graph
frontend/              React/Vite/TypeScript SPA + api-server.py (FastAPI backend that
                       invokes the Lambda handlers in-process and proxies Step
                       Functions/Athena calls); built together into one container
deploy/                Shell scripts + CodeBuild specs for App Runner, ECR, CloudFront
tests/                 End-to-end and full-agent integration tests (pytest)
orchestrator.py         Local/demo pipeline runner — chains all agent handlers in sequence
demo.py                 Fast, narrated 2-minute demo against a canned e-commerce AUT
setup_aws.py            Provisions the S3 bucket and DynamoDB tables
verify_bedrock.py       Standalone Bedrock connectivity/model-access check
```

## Design Decisions

- **Handlers as the unit of reuse, not a framework.** Every agent is a plain `handler(event, context)` function with no Lambda-specific dependencies. That's why the same code runs three ways — imported directly by `orchestrator.py`, imported directly by `api-server.py`, or deployed as an actual Lambda behind Step Functions — without a shim layer.
- **Cross-cutting reliability via one decorator, not copy-pasted into every handler.** `@instrument_handler("<agent_name>")` (in `aethertest/observability.py`) wraps every agent's `handler()` and adds structured JSON logging, CloudWatch metrics, retry-with-backoff on transient AWS errors, and idempotent replay keyed on `execution_id` — all in one place instead of thirteen near-identical copies.
- **Real execution first, LLM simulation as an explicit fallback.** The Test Executor's primary path is Planner → Claude generates a Playwright script → the script runs in a real headless browser → the trace is uploaded to S3. It only falls back to LLM-simulated pass/fail — and every such result is tagged `execution_mode: "llm_simulated"` so it's never silently mistaken for a real result — when Playwright isn't installed or no target URL was supplied.
- **Step Functions for production orchestration, Python script for everything else.** The ASL state machine gives retries, catch blocks, and visual execution history for free once this runs unattended; the plain-Python orchestrator is faster to iterate on and is what demos/tests actually exercise.
- **DynamoDB single-table-per-concern, not one megatable.** Strategies, assignments, defect patterns, execution state, and idempotency records are separate tables because their access patterns and TTL/retention needs (defect patterns expire in 90 days; idempotency records in 7; execution state doesn't) differ enough that sharing a table would mean fighting the partition key design.
- **S3 as the artifact system of record, DynamoDB as the index.** Large agent outputs (test suites, coverage reports, Playwright traces) go to S3 under a `{tenant_id}/...` prefix; DynamoDB only stores what's needed to look them up and drive verdicts, keeping table items small and cheap to scan.
- **One container, two build stages.** The Dockerfile builds the React app in a Node stage and copies only the static output into the Python runtime stage, so the deployed image has no Node/npm surface area and one process (`uvicorn`) serves both the API and the SPA.

## Challenges

- **Non-deterministic LLM output inside a pipeline.** Claude occasionally returns malformed JSON where structured output is required (test cases, risk scores); every handler needs fallback/repair logic rather than trusting the model's output shape. The same is true one level up for Playwright script generation — a bad script fails the subprocess run rather than corrupting the pipeline, and that failure is reported as a normal test failure, not swallowed.
- **At-least-once Lambda/Step Functions delivery vs. side effects.** A retried Step Functions task or a re-invoked Lambda would otherwise double-write S3 artifacts and DynamoDB records. `instrument_handler`'s idempotency cache (keyed on `execution_id` + agent name) makes retries safe to replay instead of re-running side effects.
- **Docs drift.** A previous version of this README and a since-removed `DOCUMENTATION.md` described a Streamlit UI that was never the shipped frontend (the actual frontend is a React/TypeScript SPA behind FastAPI). The fix was deleting the stale doc rather than trying to keep two documents in sync — this README is now the only one.

## Future Improvements

- Real HTTP test execution against live endpoints for API-type test cases (today only UI/browser tests get the real Playwright path; API tests still go through LLM simulation)
- Infrastructure as code (Terraform/CDK) instead of hand-run shell scripts in `deploy/` — today S3/DynamoDB provisioning isn't automated at all; `setup_aws.py` only writes local credentials
- CI/CD pipeline: lint + test + plan on PR, auto-deploy to a dev environment on merge
- X-Ray tracing and per-agent latency/error dashboards on top of the CloudWatch metrics `instrument_handler` already emits
- Multi-tenant isolation and auth on the FastAPI/React app (currently none)

## Screenshots

_Not yet captured — placeholders below._

| Dashboard | Test Results | Coverage & Verdict |
|---|---|---|
| _screenshot pending_ | _screenshot pending_ | _screenshot pending_ |

## Resume Bullet Points

- Designed and implemented a 6-stage LLM-agent pipeline (Amazon Bedrock/Claude) with shared handler contracts that run identically in-process, as AWS Lambda functions, and as Step Functions tasks — eliminating a separate "production" code path.
- Built a real test-execution pipeline where Claude generates a Playwright script per test case and it runs in a real headless browser with trace capture, falling back to explicitly-tagged LLM simulation only when no real target is available — not an LLM guessing pass/fail as the platform's core signal.
- Built a single cross-cutting decorator (structured logging, CloudWatch metrics, retry-with-backoff, execution_id-keyed idempotency) applied to every agent Lambda, replacing what would otherwise be reliability boilerplate copy-pasted into thirteen handlers.
- Built a dual-mode orchestration layer (local Python runner for fast iteration, Step Functions state machine with retry/catch semantics for production) sharing the same Lambda handlers, cutting agent development cycle time while keeping production fault tolerance.
- Shipped a multi-stage Docker build that compiles a React/TypeScript SPA and serves it from a single FastAPI/uvicorn process behind AWS App Runner, reducing deployed surface area to one container with no Node runtime in production.
