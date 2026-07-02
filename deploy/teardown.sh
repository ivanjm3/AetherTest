#!/usr/bin/env bash
set -euo pipefail
# â”€â”€â”€ AetherTest Teardown â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

echo "â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•"
echo "  AetherTest â€” TEARDOWN"
echo "  Account: ${AWS_ACCOUNT_ID} | Region: ${AWS_REGION}"
echo "â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•"
echo ""
echo "  This will DELETE:"
echo "    â€¢ App Runner service: ${APPRUNNER_SERVICE_NAME}"
echo "    â€¢ S3 contents: ${FRONTEND_BUCKET}"
echo "    â€¢ S3 contents: ${CODEBUILD_ARTIFACT_BUCKET}"
echo "    â€¢ ECR images: ${ECR_REPO_NAME}"
echo ""
echo "  IAM roles will NOT be deleted (shared/pre-existing)."
echo ""
read -p "  Type 'destroy' to confirm: " CONFIRM

if [[ "${CONFIRM}" != "destroy" ]]; then
    echo "  Aborted."
    exit 0
fi

echo ""

# App Runner
SERVICE_ARN=$(command aws --no-verify-ssl apprunner list-services \
    --profile "${AWS_PROFILE}" --region "${AWS_REGION}" \
    --query "ServiceSummaryList[?ServiceName=='${APPRUNNER_SERVICE_NAME}'].ServiceArn" \
    --output text 2>/dev/null || echo "")

if [[ -n "${SERVICE_ARN}" && "${SERVICE_ARN}" != "None" ]]; then
    echo "  ðŸ—‘ï¸  Deleting App Runner: ${APPRUNNER_SERVICE_NAME}..."
    command aws --no-verify-ssl apprunner delete-service --service-arn "${SERVICE_ARN}" \
        --profile "${AWS_PROFILE}" --region "${AWS_REGION}" > /dev/null 2>&1
    echo "  âœ… App Runner deletion initiated"
else
    echo "  â­ï¸  App Runner not found, skipping"
fi

# S3 â€” empty buckets
for bucket in "${FRONTEND_BUCKET}" "${CODEBUILD_ARTIFACT_BUCKET}"; do
    if command aws --no-verify-ssl s3api head-bucket --bucket "${bucket}" \
        --profile "${AWS_PROFILE}" --region "${AWS_REGION}" 2>/dev/null; then
        echo "  ðŸ—‘ï¸  Emptying bucket: ${bucket}..."
        command aws --no-verify-ssl s3 rm "s3://${bucket}" --recursive \
            --profile "${AWS_PROFILE}" --region "${AWS_REGION}" > /dev/null 2>&1
        echo "  âœ… Emptied: ${bucket}"
    else
        echo "  â­ï¸  Bucket not found: ${bucket}"
    fi
done

# ECR â€” delete all images
if command aws --no-verify-ssl ecr describe-repositories --repository-names "${ECR_REPO_NAME}" \
    --profile "${AWS_PROFILE}" --region "${AWS_REGION}" &>/dev/null; then
    echo "  ðŸ—‘ï¸  Deleting ECR images: ${ECR_REPO_NAME}..."
    IMAGE_IDS=$(command aws --no-verify-ssl ecr list-images --repository-name "${ECR_REPO_NAME}" \
        --profile "${AWS_PROFILE}" --region "${AWS_REGION}" \
        --query 'imageIds[*]' --output json 2>/dev/null)
    if [[ "${IMAGE_IDS}" != "[]" && "${IMAGE_IDS}" != "null" ]]; then
        command aws --no-verify-ssl ecr batch-delete-image --repository-name "${ECR_REPO_NAME}" \
            --image-ids "${IMAGE_IDS}" \
            --profile "${AWS_PROFILE}" --region "${AWS_REGION}" > /dev/null 2>&1
    fi
    echo "  âœ… ECR images cleared"
else
    echo "  â­ï¸  ECR repo not found"
fi

echo ""
echo "âœ… Teardown complete. S3 buckets + ECR repo still exist (empty)."
echo "   Delete them manually if desired:"
echo "     aws --no-verify-ssl s3api delete-bucket --bucket ${FRONTEND_BUCKET} --profile ${AWS_PROFILE}"
echo "     aws --no-verify-ssl s3api delete-bucket --bucket ${CODEBUILD_ARTIFACT_BUCKET} --profile ${AWS_PROFILE}"
echo "     aws --no-verify-ssl ecr delete-repository --repository-name ${ECR_REPO_NAME} --profile ${AWS_PROFILE}"
