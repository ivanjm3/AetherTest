# AetherTest — Project Documentation

## Table of Contents

- [A. What This Project Does](#a-what-this-project-does)
- [B. Usage Guide for Third Parties](#b-usage-guide-for-third-parties)
- [C. Frontend Orientation](#c-frontend-orientation)
- [D. AWS Deployment (Terraform / SRE Best Practices)](#d-aws-deployment-terraform--sre-best-practices)

---

## A. What This Project Does

AetherTest is an **autonomous multi-agent AI testing platform** built on AWS. It uses Amazon Bedrock (Claude Sonnet 4) to replace manual test planning, authoring, execution, and maintenance with a system of six cooperating AI agents.

### Core Problem It Solves

Testing is expensive and labour-intensive. AetherTest automates the entire lifecycle:

1. **Application Understanding** — Analyzes the structure of an application under test (AUT), mapping components, APIs, UI pages, and dependencies.
2. **Risk-Based Prioritization** — Computes risk scores per component using change velocity, defect history, and deployment frequency, so testing effort focuses where it matters.
3. **Test Strategy Generation** — Produces a prioritized test plan allocating coverage targets to each component.
4. **Test Authoring (BDD)** — Converts plain-English user stories and acceptance criteria into Given/When/Then BDD test cases using Claude.
5. **Test Case Generation** — Claude generates additional functional, edge-case, and security tests for each component.
6. **Test Execution with Self-Healing** — Simulates browser/API interactions and auto-heals broken locators when UI elements change.
7. **Failure Analysis** — Classifies failures (real defect, environment noise, regression, false positive) and generates root-cause hypotheses with fix suggestions.
8. **Test Maintenance** — Detects AUT changes (renamed buttons, updated API schemas) and regenerates affected test steps.
9. **Coverage Mapping & Deployment Verdicts** — Computes per-component coverage and provides a `safe_to_deploy`, `deploy_with_caution`, or `do_not_deploy` verdict.

### The Six Agents

| # | Agent | Responsibility |
|---|-------|----------------|
| 1 | **Test Strategist** | AUT analysis, risk scoring, strategy generation |
| 2 | **Test Author** | Requirements → BDD test cases |
| 3 | **Test Executor** | Run tests, simulate interactions, self-heal |
| 4 | **Test Analyst** | Root-cause analysis, failure classification |
| 5 | **Test Maintenance** | Update tests when the AUT changes |
| 6 | **Coverage & Risk** | Coverage map, deployment verdict |

### Technology Stack

- **AI Engine:** Amazon Bedrock — Claude Sonnet 4 (`us.anthropic.claude-sonnet-4-20250514-v1:0`)
- **Compute:** AWS Lambda (serverless handlers per agent capability)
- **Orchestration:** AWS Step Functions (state machine for the test cycle)
- **Storage:** Amazon S3 (test artifacts, reports, graphs)
- **Metadata:** Amazon DynamoDB (strategies, defect patterns, execution state)
- **Events:** Amazon EventBridge (publish test-cycle completion events)
- **Alerts:** Amazon SNS (failure notifications)
- **Language:** Python 3.12, Pydantic v2, Boto3
- **Frontend:** Streamlit (single-page Python web app)

---

## B. Usage Guide for Third Parties

### Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python ≥ 3.12 | Required by the codebase |
| AWS Account | With Bedrock model access enabled for Claude Sonnet 4 |
| AWS CLI v2 | Configured with a profile that has the necessary IAM permissions |
| pip / pipx | To install Python dependencies |

### Step 1 — Clone and Install

```bash
git clone <repository-url>
cd aethertest

# Install the package and its dependencies
pip install -e .

# Install test/dev extras if needed
pip install -e ".[test,dev]"

# Install Streamlit for the UI
pip install streamlit
```

### Step 2 — Configure AWS Credentials

Option A — Use the included setup script (interactive):

```bash
python setup_aws.py
```

Option B — Configure manually using a named profile:

```bash
aws configure --profile aethertest
# Enter your Access Key, Secret Key, region (us-east-1)
```

### Step 3 — Verify Bedrock Access

```bash
AWS_PROFILE=aethertest python verify_bedrock.py
```

Expected output confirms Claude Sonnet 4 is reachable and lists available models.

### Step 4 — Provision AWS Resources

Before first use, create the required S3 bucket and DynamoDB tables:

```bash
AWS_PROFILE=aethertest python setup_aws.py
```

This creates:
- S3 bucket: `aethertest-artifacts-<account-id>`
- DynamoDB tables: `aethertest-strategies`, `aethertest-agent-assignments`, `aethertest-defect-patterns`, `aethertest-executions`

### Step 5 — Run the Demo

```bash
# Quick 2-minute demo (recommended first run)
AWS_PROFILE=aethertest python demo.py

# Full orchestrator pipeline
AWS_PROFILE=aethertest python orchestrator.py --fast
```

### Step 6 — Launch the Web UI

```bash
AWS_PROFILE=aethertest streamlit run ui/app.py
# Opens at http://localhost:8501
```

### Using Your Own Application

Create a JSON file describing your AUT:

```json
{
  "tenant_id": "your-org",
  "aut_id": "your-app",
  "aut_version": "1.0.0",
  "aut_metadata": {
    "components": [
      {
        "component_id": "login-service",
        "name": "Login Service",
        "component_type": "api_endpoint",
        "dependencies": [],
        "api_surface": ["/api/auth/login", "/api/auth/logout"],
        "ui_entry_points": ["/login"],
        "metadata": { "criticality": "critical" }
      }
    ]
  }
}
```

Run the pipeline against it:

```bash
AWS_PROFILE=aethertest python orchestrator.py --aut-file your_aut.json
```

### Writing Requirements for the Test Author

Supply requirements as a Python list or via the Streamlit UI:

```python
requirements = [
    {
        "id": "REQ-001",
        "type": "user_story",  # or "acceptance_criteria", "business_rule"
        "content": "As a user, I want to reset my password via email so I can recover my account",
        "component": "Login Service",
    }
]
```

The Test Author agent converts these to executable BDD test cases (Given/When/Then) stored in S3.

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `AWS_PROFILE` | — | AWS credential profile to use |
| `AWS_DEFAULT_REGION` | `us-east-1` | AWS region |
| `BEDROCK_MODEL_ID` | `us.anthropic.claude-sonnet-4-20250514-v1:0` | Claude model to use |
| `AETHERTEST_NO_SSL_VERIFY` | `""` | Set to `1` to disable SSL verification (corporate proxies) |

---

## C. Frontend Orientation

The frontend is a **Streamlit** application located in `ui/app.py`. Streamlit is a Python-native framework that renders interactive web apps from a single script — no JavaScript, HTML, or CSS required.

### Architecture

```
ui/
├── app.py              ← Single-file Streamlit application (all pages)
└── requirements.txt    ← UI-specific Python dependencies
```

The app is a **multi-page layout** using Streamlit's sidebar radio navigation. All pages live in one file and conditionally render based on the selected page.

### Pages

| Page | Route (Sidebar) | Purpose |
|------|-----------------|---------|
| Dashboard | 🏠 Dashboard | Platform overview, agent summary, quick-start commands |
| Requirements | ✍️ Requirements | Interactive form to write user stories and generate BDD tests with Claude in real time |
| Test Cases | 📋 Test Cases | Browse generated test cases stored in S3 by tenant |
| Test Results | 📊 Test Results | View pass/fail execution results, drill into failures |
| Coverage Report | 📈 Coverage Report | Component coverage map, deployment verdict display |
| Agent Activity | 🤖 Agent Activity | DynamoDB-backed log of what each agent did per run |

### Data Flow

```
┌─────────────┐       ┌──────────┐       ┌──────────────────┐
│  Streamlit  │──────▶│  Boto3   │──────▶│  S3 / DynamoDB   │
│  (app.py)   │◀──────│  Client  │◀──────│  (us-east-1)     │
└─────────────┘       └──────────┘       └──────────────────┘
       │
       │  (Requirements page only)
       ▼
┌──────────────────────────────────────┐
│  lambdas/test_author_agent/handler   │
│  → invokes Bedrock Claude directly   │
└──────────────────────────────────────┘
```

- Most pages are **read-only dashboards** pulling data from S3 and DynamoDB.
- The Requirements page is **interactive** — it calls the Test Author agent handler in-process to generate BDD tests.
- There is no separate backend API server; Streamlit acts as both server and renderer.

### Current Limitations

- No authentication or multi-user support built in.
- The "Run Demo" page is a placeholder — pipeline execution happens via CLI.
- All pages are in a single file (`app.py`) rather than using Streamlit's native multi-page app structure.
- No caching layer beyond Streamlit's built-in `st.session_state`.
- UI is functional/demo-quality, not production-polished.

### Running the Frontend

```bash
AWS_PROFILE=aethertest streamlit run ui/app.py
# Accessible at http://localhost:8501
# To specify a different port:
streamlit run ui/app.py --server.port 8502
```

---

## D. AWS Deployment (Terraform / SRE Best Practices)

This section outlines how to deploy AetherTest to AWS in a production-grade, SRE-aligned manner using Terraform (or OpenTofu) as the Infrastructure-as-Code tool.

### Target Architecture

```
                         ┌──────────────────────────────────┐
                         │        Route 53 / ALB            │
                         │   (HTTPS → Streamlit on ECS)     │
                         └───────────────┬──────────────────┘
                                         │
              ┌──────────────────────────┼──────────────────────────┐
              │                          │                          │
   ┌──────────▼──────────┐   ┌──────────▼──────────┐   ┌──────────▼──────┐
   │   ECS Fargate        │   │  Step Functions      │   │  EventBridge    │
   │   (Streamlit UI)     │   │  (Orchestration)     │   │  (Events/CRON)  │
   └──────────────────────┘   └──────────┬───────────┘   └─────────────────┘
                                         │
              ┌──────────┬───────────────┼───────────────┬───────────────┐
              │          │               │               │               │
   ┌──────────▼──┐ ┌────▼─────┐ ┌───────▼───────┐ ┌────▼────┐ ┌────────▼────────┐
   │  Lambda     │ │  Lambda  │ │   Lambda      │ │ Lambda  │ │  Lambda          │
   │  AUT Anlz.  │ │  Risk    │ │  Strategy Gen │ │ Author  │ │  Executor/Anlst  │
   └──────┬──────┘ └────┬─────┘ └───────┬───────┘ └────┬────┘ └────────┬─────────┘
          │              │               │               │               │
          └──────────────┴───────────────┼───────────────┴───────────────┘
                                         │
              ┌──────────────────────────┼──────────────────────────┐
              │                          │                          │
   ┌──────────▼──────────┐   ┌──────────▼──────────┐   ┌──────────▼──────┐
   │   Amazon Bedrock     │   │   S3 (Artifacts)    │   │   DynamoDB      │
   │   (Claude Sonnet 4)  │   │                     │   │   (Metadata)    │
   └──────────────────────┘   └─────────────────────┘   └─────────────────┘
```

### Proposed Terraform Module Structure

```
terraform/
├── environments/
│   ├── dev/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── terraform.tfvars
│   ├── staging/
│   └── prod/
├── modules/
│   ├── networking/           # VPC, subnets, security groups
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── lambda_agents/        # All Lambda functions + layers
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── step_functions/       # State machine definition
│   │   ├── main.tf
│   │   └── variables.tf
│   ├── storage/              # S3 bucket + DynamoDB tables
│   │   ├── main.tf
│   │   └── outputs.tf
│   ├── ecs_frontend/         # Fargate service for Streamlit
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── iam/                  # IAM roles and policies
│   │   ├── main.tf
│   │   └── outputs.tf
│   ├── monitoring/           # CloudWatch dashboards, alarms, X-Ray
│   │   ├── main.tf
│   │   └── variables.tf
│   └── secrets/              # Secrets Manager / Parameter Store
│       └── main.tf
├── backend.tf                # S3 + DynamoDB state backend
└── versions.tf               # Provider version constraints
```

### Key Terraform Resources

#### 1. Lambda Functions (one per agent handler)

```hcl
resource "aws_lambda_function" "aut_analyzer" {
  function_name = "${var.project}-aut-analyzer-${var.environment}"
  runtime       = "python3.12"
  handler       = "handler.handler"
  timeout       = 120
  memory_size   = 512

  filename         = data.archive_file.aut_analyzer.output_path
  source_code_hash = data.archive_file.aut_analyzer.output_base64sha256

  role = aws_iam_role.lambda_execution.arn

  layers = [aws_lambda_layer_version.serializer.arn]

  environment {
    variables = {
      AWS_DEFAULT_REGION     = var.aws_region
      BEDROCK_MODEL_ID       = var.bedrock_model_id
      ARTIFACTS_BUCKET       = aws_s3_bucket.artifacts.id
      STRATEGIES_TABLE       = aws_dynamodb_table.strategies.name
    }
  }

  tracing_config {
    mode = "Active"  # X-Ray tracing
  }
}
```

#### 2. Step Functions State Machine

```hcl
resource "aws_sfn_state_machine" "test_cycle" {
  name     = "${var.project}-test-cycle-${var.environment}"
  role_arn = aws_iam_role.step_functions.arn

  definition = templatefile("${path.module}/test_cycle.asl.json", {
    AUTAnalyzerLambdaArn      = aws_lambda_function.aut_analyzer.arn
    RiskScorerLambdaArn       = aws_lambda_function.risk_scorer.arn
    StrategyGeneratorLambdaArn = aws_lambda_function.strategy_generator.arn
    AgentDispatcherLambdaArn  = aws_lambda_function.agent_dispatcher.arn
    FailureTriageLambdaArn    = aws_lambda_function.failure_triage.arn
    ResultAggregatorLambdaArn = aws_lambda_function.result_aggregator.arn
    LearningUpdaterLambdaArn  = aws_lambda_function.learning_updater.arn
    SNSAlertTopicArn          = aws_sns_topic.alerts.arn
  })
}
```

#### 3. S3 + DynamoDB

```hcl
resource "aws_s3_bucket" "artifacts" {
  bucket = "${var.project}-artifacts-${data.aws_caller_identity.current.account_id}"

  tags = { Project = var.project, Environment = var.environment }
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_lifecycle_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    id     = "expire-old-artifacts"
    status = "Enabled"
    expiration { days = 90 }
  }
}

resource "aws_dynamodb_table" "strategies" {
  name         = "${var.project}-strategies"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"

  attribute { name = "PK"; type = "S" }
  attribute { name = "SK"; type = "S" }

  ttl { attribute_name = "ttl"; enabled = true }

  point_in_time_recovery { enabled = true }
}
```

#### 4. ECS Fargate (Streamlit Frontend)

```hcl
resource "aws_ecs_service" "frontend" {
  name            = "${var.project}-frontend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.frontend.arn
  desired_count   = var.environment == "prod" ? 2 : 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = module.networking.private_subnet_ids
    security_groups  = [aws_security_group.frontend.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.frontend.arn
    container_name   = "streamlit"
    container_port   = 8501
  }
}
```

### SRE Best Practices Checklist

#### Infrastructure

- [ ] **State management** — Store Terraform state in S3 with DynamoDB locking.
- [ ] **Environment parity** — Identical module structure for dev/staging/prod; only variables differ.
- [ ] **Least privilege IAM** — Each Lambda gets a narrowly scoped role (only the S3 prefixes and DynamoDB tables it needs).
- [ ] **Encryption at rest** — S3 SSE-S3 or SSE-KMS; DynamoDB encryption enabled by default.
- [ ] **Encryption in transit** — All internal AWS calls use HTTPS; ALB terminates TLS with ACM certificate.
- [ ] **VPC isolation** — Lambdas in private subnets with VPC endpoints for S3, DynamoDB, and Bedrock.
- [ ] **No hardcoded secrets** — Use AWS Secrets Manager or SSM Parameter Store; reference via environment variables.

#### Observability

- [ ] **Structured logging** — JSON logs from all Lambdas sent to CloudWatch Logs.
- [ ] **Distributed tracing** — AWS X-Ray enabled on all Lambdas and Step Functions.
- [ ] **Custom metrics** — CloudWatch metrics for: tests generated, pass rate, verdict distribution, Bedrock latency.
- [ ] **Dashboards** — CloudWatch dashboard per environment showing pipeline health.
- [ ] **Alarms** — Alarm on: Lambda errors > threshold, Step Functions failures, Bedrock throttling, DynamoDB throttling.
- [ ] **SLIs/SLOs** — Define: pipeline completion rate ≥ 99%, median pipeline duration ≤ 5 min, Bedrock error rate ≤ 1%.

#### CI/CD Pipeline

```
┌─────────┐     ┌──────────┐     ┌───────────┐     ┌──────────┐     ┌──────────┐
│  Push   │────▶│  Lint +  │────▶│ Terraform │────▶│ Deploy   │────▶│ Smoke    │
│  to Git │     │  Test    │     │   Plan    │     │  Apply   │     │  Test    │
└─────────┘     └──────────┘     └───────────┘     └──────────┘     └──────────┘
```

- **Lint + Test**: `ruff check`, `pytest`, validate Terraform (`terraform validate`).
- **Plan**: `terraform plan` on every PR; plan output posted as PR comment.
- **Apply**: Auto-apply to dev on merge; manual approval gate for staging/prod.
- **Smoke Test**: After deploy, invoke the demo pipeline in fast mode to confirm end-to-end health.

#### Deployment Strategy

- **Lambda versioning** — Publish versions; use aliases (`$LATEST`, `staging`, `prod`) for traffic shifting.
- **Canary deploys** — Use CodeDeploy with Lambda traffic shifting (10% → 100% over 10 minutes).
- **Rollback** — Automatic rollback if CloudWatch alarm fires during canary window.
- **Blue/green for Fargate** — ECS deployment circuit breaker with rollback enabled.

#### Cost Optimization

- **Lambda** — Right-size memory (Power Tuning); use ARM64 (Graviton) where supported.
- **DynamoDB** — Use PAY_PER_REQUEST for variable workloads; enable auto-scaling for steady-state.
- **S3** — Lifecycle rules to transition old artifacts to Infrequent Access after 30 days, expire after 90.
- **Bedrock** — Monitor token usage; cache repeated prompts where safe; use `temperature=0.0` to reduce variance.
- **Reserved capacity** — Consider Savings Plans for Fargate if running continuously.

#### Disaster Recovery

- **S3** — Versioning enabled; cross-region replication for prod.
- **DynamoDB** — Point-in-time recovery (PITR) enabled; on-demand backups before major changes.
- **State file** — Terraform state bucket with versioning and MFA delete.
- **Multi-region** — For DR, replicate the state machine and Lambdas to a secondary region; Bedrock supports cross-region inference profiles already.

### Minimal Terraform Quickstart

To get started with Terraform deployment:

```bash
# 1. Initialize Terraform
cd terraform/environments/dev
terraform init

# 2. Plan the deployment
terraform plan -out=tfplan

# 3. Apply
terraform apply tfplan

# 4. Verify
aws stepfunctions list-state-machines --region us-east-1
aws lambda list-functions --region us-east-1 | grep aethertest
```

### Alternative: AWS CDK

If Terraform isn't the team's preference, AWS CDK (Python) is a natural fit since the application is already Python. The same module structure applies — define constructs for each layer (storage, compute, orchestration, frontend).

---

## Summary

AetherTest is a serverless, AI-driven testing platform that slots into an existing AWS environment. For third-party adoption: clone, configure credentials, run the demo. For production deployment: use the Terraform module structure above with environment-specific variable files, proper IAM boundaries, and the full observability stack. The Streamlit frontend is lightweight and deployable on ECS Fargate behind an ALB with minimal overhead.
