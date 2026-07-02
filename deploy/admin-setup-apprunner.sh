#!/usr/bin/env bash
set -euo pipefail
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# AetherTest â€” App Runner Setup (REQUIRES IAM ADMIN / iam:PassRole)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#
# This script must be run by someone with iam:PassRole permission.
# It creates:
#   1. IAM roles (if they don't exist)
#   2. App Runner service pointing at ECR image
#
# After this runs once, the PowerUserAccess developer can redeploy
# via CodeBuild â†’ ECR push â†’ App Runner auto-deploys (no iam:PassRole needed).
#
# Usage:
#   aws sso login --profile <ADMIN_PROFILE>
#   bash deploy/admin-setup-apprunner.sh
#
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

# â”€â”€â”€ Configuration â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
AWS_ACCOUNT_ID="654654478821"
AWS_REGION="us-east-1"
AWS_PROFILE="${1:-PowerUserAccess-654654478821}"  # Pass profile as arg or use default

APP_NAME="aethertest"
ECR_REPO_NAME="${APP_NAME}-prod"
SERVICE_NAME="${APP_NAME}-prod"
PORT="8001"
CPU="1 vCPU"
MEMORY="2 GB"
HEALTH_PATH="/api/health"

# Role names
INSTANCE_ROLE_NAME="${APP_NAME}-apprunner-role"
ECR_ACCESS_ROLE_NAME="AppRunnerECRAccessRole"

ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}:latest"

echo "â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•"
echo "  AetherTest â€” Admin App Runner Setup"
echo "  Account: ${AWS_ACCOUNT_ID} | Region: ${AWS_REGION}"
echo "  Profile: ${AWS_PROFILE}"
echo "â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•"
echo ""

# â”€â”€â”€ Step 1: Create Instance Role (Bedrock/S3/Athena access) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
echo "[Step 1/3] Instance Role: ${INSTANCE_ROLE_NAME}"

if aws --no-verify-ssl iam get-role --role-name "${INSTANCE_ROLE_NAME}" \
    --profile "${AWS_PROFILE}" --region "${AWS_REGION}" &>/dev/null; then
    echo "  âœ… Role exists: ${INSTANCE_ROLE_NAME}"
else
    echo "  Creating role: ${INSTANCE_ROLE_NAME}..."

    # Trust policy â€” allow App Runner tasks to assume this role
    aws --no-verify-ssl iam create-role \
        --role-name "${INSTANCE_ROLE_NAME}" \
        --assume-role-policy-document '{
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "tasks.apprunner.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        }' \
        --profile "${AWS_PROFILE}" --region "${AWS_REGION}" > /dev/null

    # Attach permissions for Bedrock, S3, Athena, Glue, Step Functions
    aws --no-verify-ssl iam put-role-policy \
        --role-name "${INSTANCE_ROLE_NAME}" \
        --policy-name "${APP_NAME}-instance-policy" \
        --policy-document '{
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "bedrock:InvokeModel",
                        "bedrock:InvokeModelWithResponseStream"
                    ],
                    "Resource": "arn:aws:bedrock:*:*:foundation-model/*"
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetObject",
                        "s3:PutObject",
                        "s3:ListBucket",
                        "s3:DeleteObject"
                    ],
                    "Resource": [
                        "arn:aws:s3:::aethertest-*",
                        "arn:aws:s3:::aethertest-*/*"
                    ]
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "athena:StartQueryExecution",
                        "athena:GetQueryExecution",
                        "athena:GetQueryResults",
                        "athena:StopQueryExecution"
                    ],
                    "Resource": "*"
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "glue:GetDatabases",
                        "glue:GetTables",
                        "glue:GetTable",
                        "glue:GetPartitions"
                    ],
                    "Resource": "*"
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "states:DescribeStateMachine",
                        "states:ListStateMachines"
                    ],
                    "Resource": "*"
                }
            ]
        }' \
        --profile "${AWS_PROFILE}" --region "${AWS_REGION}"

    echo "  âœ… Created role with Bedrock/S3/Athena/Glue/SFN permissions"
fi

# â”€â”€â”€ Step 2: Create ECR Access Role â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
echo ""
echo "[Step 2/3] ECR Access Role: ${ECR_ACCESS_ROLE_NAME}"

if aws --no-verify-ssl iam get-role --role-name "${ECR_ACCESS_ROLE_NAME}" \
    --profile "${AWS_PROFILE}" --region "${AWS_REGION}" &>/dev/null; then
    echo "  âœ… Role exists: ${ECR_ACCESS_ROLE_NAME}"
else
    echo "  Creating role: ${ECR_ACCESS_ROLE_NAME}..."

    aws --no-verify-ssl iam create-role \
        --role-name "${ECR_ACCESS_ROLE_NAME}" \
        --assume-role-policy-document '{
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "build.apprunner.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        }' \
        --profile "${AWS_PROFILE}" --region "${AWS_REGION}" > /dev/null

    aws --no-verify-ssl iam attach-role-policy \
        --role-name "${ECR_ACCESS_ROLE_NAME}" \
        --policy-arn "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess" \
        --profile "${AWS_PROFILE}" --region "${AWS_REGION}"

    echo "  âœ… Created role with ECR pull permissions"
fi

# â”€â”€â”€ Step 3: Create App Runner Service â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
echo ""
echo "[Step 3/3] App Runner Service: ${SERVICE_NAME}"

# Check if already exists
EXISTING_ARN=$(aws --no-verify-ssl apprunner list-services \
    --profile "${AWS_PROFILE}" --region "${AWS_REGION}" \
    --query "ServiceSummaryList[?ServiceName=='${SERVICE_NAME}'].ServiceArn" \
    --output text 2>/dev/null || echo "")

if [[ -n "${EXISTING_ARN}" && "${EXISTING_ARN}" != "None" ]]; then
    echo "  âœ… Service already exists: ${SERVICE_NAME}"
    echo "     ARN: ${EXISTING_ARN}"
else
    echo "  Creating App Runner service..."
    echo "    Image: ${ECR_URI}"
    echo "    Port:  ${PORT}"
    echo "    CPU:   ${CPU}"
    echo "    Mem:   ${MEMORY}"

    # Wait for roles to propagate
    echo "  â³ Waiting 10s for IAM role propagation..."
    sleep 10

    aws --no-verify-ssl apprunner create-service \
        --service-name "${SERVICE_NAME}" \
        --source-configuration "{
            \"ImageRepository\": {
                \"ImageIdentifier\": \"${ECR_URI}\",
                \"ImageRepositoryType\": \"ECR\",
                \"ImageConfiguration\": {
                    \"Port\": \"${PORT}\",
                    \"RuntimeEnvironmentVariables\": {
                        \"AWS_DEFAULT_REGION\": \"${AWS_REGION}\",
                        \"BEDROCK_MODEL_ID\": \"us.anthropic.claude-sonnet-4-20250514-v1:0\",
                        \"ATHENA_DATABASE\": \"icebergtarget\",
                        \"ATHENA_OUTPUT_BUCKET\": \"aethertest-athena-results-${AWS_ACCOUNT_ID}\"
                    }
                }
            },
            \"AutoDeploymentsEnabled\": true,
            \"AuthenticationConfiguration\": {
                \"AccessRoleArn\": \"arn:aws:iam::${AWS_ACCOUNT_ID}:role/${ECR_ACCESS_ROLE_NAME}\"
            }
        }" \
        --instance-configuration "{
            \"Cpu\": \"${CPU}\",
            \"Memory\": \"${MEMORY}\",
            \"InstanceRoleArn\": \"arn:aws:iam::${AWS_ACCOUNT_ID}:role/${INSTANCE_ROLE_NAME}\"
        }" \
        --health-check-configuration "{
            \"Protocol\": \"HTTP\",
            \"Path\": \"${HEALTH_PATH}\",
            \"Interval\": 10,
            \"Timeout\": 5,
            \"HealthyThreshold\": 1,
            \"UnhealthyThreshold\": 5
        }" \
        --profile "${AWS_PROFILE}" --region "${AWS_REGION}"

    echo ""
    echo "  âœ… App Runner service created!"
fi

echo ""
echo "â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•"
echo "  DONE â€” Admin setup complete."
echo ""
echo "  After this, the developer (PowerUserAccess) can redeploy via:"
echo "    bash deploy/deploy.sh --build-backend"
echo ""
echo "  ECR push â†’ App Runner auto-redeploys (no iam:PassRole needed)"
echo "â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•"
