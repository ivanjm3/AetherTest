#!/usr/bin/env bash
set -euo pipefail
# ─── IAM Permission Validation ────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

echo "════════════════════════════════════════════════════════════"
echo "  AetherTest — IAM Permission Validation"
echo "════════════════════════════════════════════════════════════"
echo ""

ERRORS=0

check_role() {
    local role_arn="$1"
    local role_name="${role_arn##*/}"
    local purpose="$2"

    if command aws --no-verify-ssl iam get-role --role-name "${role_name}" \
        --profile "${AWS_PROFILE}" --region "${AWS_REGION}" &>/dev/null; then
        echo "  ✅ ${role_name} — ${purpose}"
    else
        echo "  ❌ ${role_name} — NOT FOUND (${purpose})"
        ((ERRORS++))
    fi
}

echo "[IAM Roles]"
check_role "${APPRUNNER_INSTANCE_ROLE_ARN}" "App Runner instance role (Bedrock/S3/Athena access)"
check_role "${APPRUNNER_ECR_ACCESS_ROLE_ARN}" "ECR image pull for App Runner"
check_role "${CODEBUILD_ROLE_ARN}" "CodeBuild service role"

echo ""
echo "[Caller Identity]"
command aws --no-verify-ssl sts get-caller-identity --profile "${AWS_PROFILE}" --region "${AWS_REGION}" \
    --output table 2>/dev/null || { echo "  ❌ Cannot assume identity. Run: aws sso login --profile ${AWS_PROFILE}"; ((ERRORS++)); }

echo ""
if [[ ${ERRORS} -eq 0 ]]; then
    echo "✅ All IAM prerequisites met. Ready to deploy."
else
    echo "❌ ${ERRORS} issue(s) found. Fix before deploying."
    exit 1
fi
