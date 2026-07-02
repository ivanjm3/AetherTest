#!/usr/bin/env bash
set -euo pipefail

# â”€â”€â”€ AetherTest Deploy Orchestrator â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Usage:
#   First time:           bash deploy/deploy.sh
#   Backend only:         bash deploy/deploy.sh --build-backend
#   Frontend only:        bash deploy/deploy.sh --build-frontend
#   Both:                 bash deploy/deploy.sh --build-all

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

# â”€â”€â”€ Disable SSL verify globally (Zscaler/corporate proxy) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Suppress Python InsecureRequestWarning spam
export PYTHONHTTPSVERIFY=0
export PYTHONWARNINGS="ignore::urllib3.exceptions.InsecureRequestWarning"
# Shorthand used in all aws calls below
NOSSL="--no-verify-ssl"

# â”€â”€â”€ Parse args â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
BUILD_BACKEND=false
BUILD_FRONTEND=false
FULL_DEPLOY=true

while [[ $# -gt 0 ]]; do
    case $1 in
        --build-backend)  BUILD_BACKEND=true; FULL_DEPLOY=false; shift ;;
        --build-frontend) BUILD_FRONTEND=true; FULL_DEPLOY=false; shift ;;
        --build-all)      BUILD_BACKEND=true; BUILD_FRONTEND=true; FULL_DEPLOY=false; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

echo "â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•"
echo "  AetherTest â€” AWS Deployment"
echo "  Account: ${AWS_ACCOUNT_ID} | Region: ${AWS_REGION}"
echo "  SSL verify: disabled (corporate proxy)"
echo "â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•"

# â”€â”€â”€ Helper: await CodeBuild â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
await_codebuild() {
    local build_id="$1"
    local project="$2"
    echo "  â³ Waiting for CodeBuild: ${build_id}..."
    while true; do
        status=$(command aws --no-verify-ssl codebuild batch-get-builds --ids "${build_id}" \
            --profile "${AWS_PROFILE}" --region "${AWS_REGION}" \
            --query 'builds[0].buildStatus' --output text 2>/dev/null)
        case "${status}" in
            SUCCEEDED) echo "  âœ… Build succeeded: ${project}"; return 0 ;;
            FAILED|FAULT|TIMED_OUT|STOPPED)
                echo "  âŒ Build ${status}: ${project}"
                echo "     Check logs: https://${AWS_REGION}.console.aws.amazon.com/codesuite/codebuild/projects/${project}/build/${build_id}"
                return 1 ;;
            *) sleep 10 ;;
        esac
    done
}

# â”€â”€â”€ Step 1: ECR Repository â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
create_ecr() {
    echo ""
    echo "[Step 1/6] ECR Repository"
    if command aws --no-verify-ssl ecr describe-repositories --repository-names "${ECR_REPO_NAME}" \
        --profile "${AWS_PROFILE}" --region "${AWS_REGION}" &>/dev/null; then
        echo "  âœ… ECR repo exists: ${ECR_REPO_NAME}"
    else
        command aws --no-verify-ssl ecr create-repository --repository-name "${ECR_REPO_NAME}" \
            --image-scanning-configuration scanOnPush=true \
            --profile "${AWS_PROFILE}" --region "${AWS_REGION}" > /dev/null 2>&1
        echo "  âœ… Created ECR repo: ${ECR_REPO_NAME}"
    fi
}

# â”€â”€â”€ Step 2: S3 Buckets â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
create_s3_buckets() {
    echo ""
    echo "[Step 2/6] S3 Buckets"
    for bucket in "${FRONTEND_BUCKET}" "${CODEBUILD_ARTIFACT_BUCKET}"; do
        if command aws --no-verify-ssl s3api head-bucket --bucket "${bucket}" \
            --profile "${AWS_PROFILE}" --region "${AWS_REGION}" 2>/dev/null; then
            echo "  âœ… Bucket exists: ${bucket}"
        else
            command aws --no-verify-ssl s3api create-bucket --bucket "${bucket}" \
                --profile "${AWS_PROFILE}" --region "${AWS_REGION}" > /dev/null 2>&1
            echo "  âœ… Created bucket: ${bucket}"
        fi
    done

    # Enable static website hosting on frontend bucket
    command aws --no-verify-ssl s3 website "s3://${FRONTEND_BUCKET}" \
        --index-document index.html --error-document index.html \
        --profile "${AWS_PROFILE}" --region "${AWS_REGION}" 2>/dev/null || true
}

# â”€â”€â”€ Step 3: Docker Image (via CodeBuild) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
build_backend() {
    echo ""
    echo "[Step 3/6] Backend Docker Image (CodeBuild)"

    # Zip source â†’ S3
    local zip_key="source/${APP_NAME}-backend-$(date +%s).zip"
    echo "  ðŸ“¦ Zipping source..."
    (cd "${SCRIPT_DIR}/.." && zip -qr "/tmp/${APP_NAME}-backend.zip" \
        aethertest/ lambdas/ layers/ frontend/api-server.py frontend/package.json \
        frontend/tsconfig.json frontend/vite.config.ts frontend/index.html \
        frontend/src/ frontend/public/ \
        orchestrator.py pyproject.toml Dockerfile deploy/buildspec-backend.yml \
        -x "**/__pycache__/*" "**/node_modules/*" "**/.git/*" "**/dist/*")
    # Add package-lock.json if it exists
    (cd "${SCRIPT_DIR}/.." && [ -f frontend/package-lock.json ] && \
        zip -qg "/tmp/${APP_NAME}-backend.zip" frontend/package-lock.json || true)

    command aws --no-verify-ssl s3 cp "/tmp/${APP_NAME}-backend.zip" \
        "s3://${CODEBUILD_ARTIFACT_BUCKET}/${zip_key}" \
        --profile "${AWS_PROFILE}" --region "${AWS_REGION}" > /dev/null 2>&1
    echo "  âœ… Source uploaded: s3://${CODEBUILD_ARTIFACT_BUCKET}/${zip_key}"

    # Ensure CodeBuild project exists
    ensure_codebuild_backend

    # Trigger build with source override
    local build_id
    build_id=$(command aws --no-verify-ssl codebuild start-build \
        --project-name "${CODEBUILD_PROJECT_NAME}" \
        --source-type-override S3 \
        --source-location-override "${CODEBUILD_ARTIFACT_BUCKET}/${zip_key}" \
        --buildspec-override "deploy/buildspec-backend.yml" \
        --environment-variables-override "[{\"name\":\"AWS_ACCOUNT_ID\",\"value\":\"${AWS_ACCOUNT_ID}\",\"type\":\"PLAINTEXT\"},{\"name\":\"AWS_DEFAULT_REGION\",\"value\":\"${AWS_REGION}\",\"type\":\"PLAINTEXT\"},{\"name\":\"ECR_REPO_NAME\",\"value\":\"${ECR_REPO_NAME}\",\"type\":\"PLAINTEXT\"}]" \
        --profile "${AWS_PROFILE}" --region "${AWS_REGION}" \
        --query 'build.id' --output text 2>/dev/null)

    await_codebuild "${build_id}" "${CODEBUILD_PROJECT_NAME}"
}

# â”€â”€â”€ Step 4: App Runner Service â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
create_apprunner() {
    echo ""
    echo "[Step 4/6] App Runner Service"

    # Check if service already exists
    local service_arn
    service_arn=$(command aws --no-verify-ssl apprunner list-services \
        --profile "${AWS_PROFILE}" --region "${AWS_REGION}" \
        --query "ServiceSummaryList[?ServiceName=='${APPRUNNER_SERVICE_NAME}'].ServiceArn" \
        --output text 2>/dev/null || echo "")

    if [[ -n "${service_arn}" && "${service_arn}" != "None" ]]; then
        echo "  âœ… App Runner service exists: ${APPRUNNER_SERVICE_NAME}"
        echo "     ARN: ${service_arn}"
        return 0
    fi

    local ecr_uri="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}:latest"

    # Build env var config for App Runner (must be JSON object, not array)
    local env_json="{"
    IFS=',' read -ra ENV_PAIRS <<< "${CONTAINER_ENV_VARS}"
    local first=true
    for pair in "${ENV_PAIRS[@]}"; do
        local key="${pair%%=*}"
        local val="${pair#*=}"
        if [[ "${first}" == "true" ]]; then
            first=false
        else
            env_json+=","
        fi
        env_json+="\"${key}\":\"${val}\""
    done
    env_json+="}"

    command aws --no-verify-ssl apprunner create-service \
        --service-name "${APPRUNNER_SERVICE_NAME}" \
        --source-configuration "{
            \"ImageRepository\": {
                \"ImageIdentifier\": \"${ecr_uri}\",
                \"ImageRepositoryType\": \"ECR\",
                \"ImageConfiguration\": {
                    \"Port\": \"${APPRUNNER_PORT}\",
                    \"RuntimeEnvironmentVariables\": ${env_json}
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
        --profile "${AWS_PROFILE}" --region "${AWS_REGION}" > /dev/null 2>&1

    echo "  âœ… Created App Runner service: ${APPRUNNER_SERVICE_NAME}"
    echo "     Image: ${ecr_uri}"
    echo "     Port: ${APPRUNNER_PORT}"
}

# â”€â”€â”€ Step 5: CodeBuild Projects â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
ensure_codebuild_backend() {
    if command aws --no-verify-ssl codebuild batch-get-projects --names "${CODEBUILD_PROJECT_NAME}" \
        --profile "${AWS_PROFILE}" --region "${AWS_REGION}" \
        --query 'projects[0].name' --output text 2>/dev/null | grep -q "${CODEBUILD_PROJECT_NAME}"; then
        return 0
    fi

    echo "  ðŸ”¨ Creating CodeBuild project: ${CODEBUILD_PROJECT_NAME}"
    if ! command aws --no-verify-ssl codebuild create-project \
        --name "${CODEBUILD_PROJECT_NAME}" \
        --source "{\"type\":\"S3\",\"location\":\"${CODEBUILD_ARTIFACT_BUCKET}/source/placeholder.zip\"}" \
        --artifacts "{\"type\":\"NO_ARTIFACTS\"}" \
        --environment "{
            \"type\":\"LINUX_CONTAINER\",
            \"image\":\"aws/codebuild/standard:7.0\",
            \"computeType\":\"BUILD_GENERAL1_MEDIUM\",
            \"privilegedMode\":true,
            \"environmentVariables\":[
                {\"name\":\"AWS_ACCOUNT_ID\",\"value\":\"${AWS_ACCOUNT_ID}\"},
                {\"name\":\"AWS_DEFAULT_REGION\",\"value\":\"${AWS_REGION}\"},
                {\"name\":\"ECR_REPO_NAME\",\"value\":\"${ECR_REPO_NAME}\"}
            ]
        }" \
        --service-role "${CODEBUILD_ROLE_ARN}" \
        --profile "${AWS_PROFILE}" --region "${AWS_REGION}"; then
        echo "  âŒ Failed to create CodeBuild project: ${CODEBUILD_PROJECT_NAME}"
        echo "     Check that role exists: ${CODEBUILD_ROLE_ARN}"
        echo "     You may need iam:PassRole permission."
        return 1
    fi
    echo "  âœ… Created CodeBuild project: ${CODEBUILD_PROJECT_NAME}"
}

ensure_codebuild_frontend() {
    if command aws --no-verify-ssl codebuild batch-get-projects --names "${CODEBUILD_FRONTEND_PROJECT}" \
        --profile "${AWS_PROFILE}" --region "${AWS_REGION}" \
        --query 'projects[0].name' --output text 2>/dev/null | grep -q "${CODEBUILD_FRONTEND_PROJECT}"; then
        return 0
    fi

    echo "  ðŸ”¨ Creating CodeBuild project: ${CODEBUILD_FRONTEND_PROJECT}"
    if ! command aws --no-verify-ssl codebuild create-project \
        --name "${CODEBUILD_FRONTEND_PROJECT}" \
        --source "{\"type\":\"S3\",\"location\":\"${CODEBUILD_ARTIFACT_BUCKET}/source/placeholder.zip\"}" \
        --artifacts "{\"type\":\"NO_ARTIFACTS\"}" \
        --environment "{
            \"type\":\"LINUX_CONTAINER\",
            \"image\":\"aws/codebuild/standard:7.0\",
            \"computeType\":\"BUILD_GENERAL1_SMALL\",
            \"environmentVariables\":[
                {\"name\":\"FRONTEND_BUCKET\",\"value\":\"${FRONTEND_BUCKET}\"},
                {\"name\":\"VITE_API_BASE\",\"value\":\"\"}
            ]
        }" \
        --service-role "${CODEBUILD_ROLE_ARN}" \
        --profile "${AWS_PROFILE}" --region "${AWS_REGION}"; then
        echo "  âŒ Failed to create CodeBuild project: ${CODEBUILD_FRONTEND_PROJECT}"
        echo "     Check that role exists: ${CODEBUILD_ROLE_ARN}"
        return 1
    fi
    echo "  âœ… Created CodeBuild project: ${CODEBUILD_FRONTEND_PROJECT}"
}

# â”€â”€â”€ Step 6: Initial Build Trigger â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
initial_build_trigger() {
    echo ""
    echo "[Step 6/6] Initial Build Trigger"

    # Check if ECR has images
    local image_count
    image_count=$(command aws --no-verify-ssl ecr list-images --repository-name "${ECR_REPO_NAME}" \
        --profile "${AWS_PROFILE}" --region "${AWS_REGION}" \
        --query 'length(imageIds)' --output text 2>/dev/null || echo "0")

    if [[ "${image_count}" == "0" || "${image_count}" == "None" ]]; then
        echo "  ðŸ“¦ ECR empty â€” triggering initial backend build..."
        build_backend
    else
        echo "  âœ… ECR has ${image_count} image(s), skipping initial build"
    fi
}

# â”€â”€â”€ Frontend Build (via CodeBuild) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
build_frontend() {
    echo ""
    echo "  Frontend Build (CodeBuild)"

    # Zip frontend source â†’ S3
    local zip_key="source/${APP_NAME}-frontend-$(date +%s).zip"
    echo "  ðŸ“¦ Zipping frontend..."
    (cd "${SCRIPT_DIR}/../frontend" && zip -qr "/tmp/${APP_NAME}-frontend.zip" \
        src/ public/ index.html package.json package-lock.json \
        tsconfig.json vite.config.ts \
        -x "**/node_modules/*" "**/dist/*")

    # Include buildspec
    (cd "${SCRIPT_DIR}/.." && zip -qg "/tmp/${APP_NAME}-frontend.zip" deploy/buildspec-frontend.yml)

    command aws --no-verify-ssl s3 cp "/tmp/${APP_NAME}-frontend.zip" \
        "s3://${CODEBUILD_ARTIFACT_BUCKET}/${zip_key}" \
        --profile "${AWS_PROFILE}" --region "${AWS_REGION}" > /dev/null 2>&1
    echo "  âœ… Frontend source uploaded"

    ensure_codebuild_frontend

    local build_id
    build_id=$(command aws --no-verify-ssl codebuild start-build \
        --project-name "${CODEBUILD_FRONTEND_PROJECT}" \
        --source-type-override S3 \
        --source-location-override "${CODEBUILD_ARTIFACT_BUCKET}/${zip_key}" \
        --buildspec-override "deploy/buildspec-frontend.yml" \
        --environment-variables-override "[{\"name\":\"FRONTEND_BUCKET\",\"value\":\"${FRONTEND_BUCKET}\",\"type\":\"PLAINTEXT\"},{\"name\":\"VITE_API_BASE\",\"value\":\"\",\"type\":\"PLAINTEXT\"}]" \
        --profile "${AWS_PROFILE}" --region "${AWS_REGION}" \
        --query 'build.id' --output text 2>/dev/null)

    await_codebuild "${build_id}" "${CODEBUILD_FRONTEND_PROJECT}"
}

# â”€â”€â”€ Execute â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

if [[ "${FULL_DEPLOY}" == "true" ]]; then
    create_ecr
    create_s3_buckets
    build_backend
    create_apprunner
    ensure_codebuild_backend
    ensure_codebuild_frontend
    initial_build_trigger
    echo ""
    echo "â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•"
    echo "  âœ… Full deployment complete!"
    echo "â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•"
else
    if [[ "${BUILD_BACKEND}" == "true" ]]; then
        build_backend
    fi
    if [[ "${BUILD_FRONTEND}" == "true" ]]; then
        build_frontend
    fi
    echo ""
    echo "  âœ… Build(s) triggered. App Runner auto-deploys on ECR push."
fi
