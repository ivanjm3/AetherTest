#!/usr/bin/env bash
# â”€â”€â”€ AetherTest Deployment Configuration â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Adapt these values to your AWS account/region.

export APP_NAME="aethertest"
export AWS_ACCOUNT_ID="654654478821"
export AWS_REGION="us-east-1"
export AWS_PROFILE="PowerUserAccess-654654478821"

# ECR
export ECR_REPO_NAME="${APP_NAME}-prod"

# S3
export FRONTEND_BUCKET="${APP_NAME}-frontend-${AWS_ACCOUNT_ID}"
export CODEBUILD_ARTIFACT_BUCKET="${APP_NAME}-codebuild-artifacts-${AWS_ACCOUNT_ID}"

# App Runner
export APPRUNNER_SERVICE_NAME="${APP_NAME}-prod"
export APPRUNNER_PORT=8001
export APPRUNNER_CPU="1 vCPU"
export APPRUNNER_MEMORY="2 GB"
export APPRUNNER_HEALTH_PATH="/api/health"

# IAM Roles (pre-existing, reused â€” no IAM creation needed)
export APPRUNNER_INSTANCE_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/talk2data-apprunner-role"
export APPRUNNER_ECR_ACCESS_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/AppRunnerECRAccessRole"
export CODEBUILD_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/talk2data-codebuild-role"

# CodeBuild (reuse existing project to avoid iam:PassRole restriction)
export CODEBUILD_PROJECT_NAME="talk2data-build-talk2data-ui"
export CODEBUILD_FRONTEND_PROJECT="talk2data-build-talk2data-ui"

# Container env vars
# SSL verification (Zscaler/corporate proxy)
export AWS_CLI_EXTRA="--no-verify-ssl"

export CONTAINER_ENV_VARS="AWS_DEFAULT_REGION=${AWS_REGION},BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-20250514-v1:0,ATHENA_DATABASE=icebergtarget,ATHENA_OUTPUT_BUCKET=aethertest-athena-results-${AWS_ACCOUNT_ID}"
