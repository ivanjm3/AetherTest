#!/usr/bin/env bash
set -euo pipefail
# â”€â”€â”€ Update App Runner env vars / image without re-passing IAM roles â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

# Find service ARN
SERVICE_ARN=$(command aws --no-verify-ssl apprunner list-services \
    --profile "${AWS_PROFILE}" --region "${AWS_REGION}" \
    --query "ServiceSummaryList[?ServiceName=='${APPRUNNER_SERVICE_NAME}'].ServiceArn" \
    --output text 2>/dev/null)

if [[ -z "${SERVICE_ARN}" || "${SERVICE_ARN}" == "None" ]]; then
    echo "âŒ Service not found: ${APPRUNNER_SERVICE_NAME}"
    exit 1
fi

echo "Updating App Runner: ${APPRUNNER_SERVICE_NAME}"
echo "  ARN: ${SERVICE_ARN}"

ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}:latest"

# Build env vars as JSON object {"KEY":"VALUE",...}
ENV_JSON="{"
IFS=',' read -ra ENV_PAIRS <<< "${CONTAINER_ENV_VARS}"
FIRST=true
for pair in "${ENV_PAIRS[@]}"; do
    KEY="${pair%%=*}"
    VAL="${pair#*=}"
    [[ "${FIRST}" == "true" ]] && FIRST=false || ENV_JSON+=","
    ENV_JSON+="\"${KEY}\":\"${VAL}\""
done
ENV_JSON+="}"

command aws --no-verify-ssl apprunner update-service \
    --service-arn "${SERVICE_ARN}" \
    --source-configuration "{
        \"ImageRepository\": {
            \"ImageIdentifier\": \"${ECR_URI}\",
            \"ImageRepositoryType\": \"ECR\",
            \"ImageConfiguration\": {
                \"Port\": \"${APPRUNNER_PORT}\",
                \"RuntimeEnvironmentVariables\": ${ENV_JSON}
            }
        },
        \"AutoDeploymentsEnabled\": true,
        \"AuthenticationConfiguration\": {
            \"AccessRoleArn\": \"${APPRUNNER_ECR_ACCESS_ROLE_ARN}\"
        }
    }" \
    --profile "${AWS_PROFILE}" --region "${AWS_REGION}"

echo "âœ… Service update initiated. Takes ~2-3 min to stabilize."
