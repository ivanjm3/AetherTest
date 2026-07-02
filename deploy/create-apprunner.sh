#!/usr/bin/env bash
set -euo pipefail
# â”€â”€â”€ Standalone App Runner creation (use after first ECR push) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}:latest"

echo "Creating App Runner service: ${APPRUNNER_SERVICE_NAME}"
echo "  Image: ${ECR_URI}"
echo "  Port:  ${APPRUNNER_PORT}"

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

command aws --no-verify-ssl apprunner create-service \
    --service-name "${APPRUNNER_SERVICE_NAME}" \
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
    --instance-configuration "{
        \"Cpu\": \"${APPRUNNER_CPU}\",
        \"Memory\": \"${APPRUNNER_MEMORY}\",
        \"InstanceRoleArn\": \"${APPRUNNER_INSTANCE_ROLE_ARN}\"
    }" \
    --health-check-configuration "{
        \"Protocol\": \"HTTP\",
        \"Path\": \"${APPRUNNER_HEALTH_PATH}\",
        \"Interval\": 10,
        \"Timeout\": 5,
        \"HealthyThreshold\": 1,
        \"UnhealthyThreshold\": 5
    }" \
    --profile "${AWS_PROFILE}" --region "${AWS_REGION}"

echo "âœ… App Runner service created. Auto-deploys on ECR :latest push."
