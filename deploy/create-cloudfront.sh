#!/usr/bin/env bash
set -euo pipefail
# â”€â”€â”€ CloudFront CDN in front of App Runner (Zscaler-friendly URL) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

# Get App Runner service URL
SERVICE_URL=$(command aws --no-verify-ssl apprunner list-services \
    --profile "${AWS_PROFILE}" --region "${AWS_REGION}" \
    --query "ServiceSummaryList[?ServiceName=='${APPRUNNER_SERVICE_NAME}'].ServiceUrl" \
    --output text 2>/dev/null)

if [[ -z "${SERVICE_URL}" || "${SERVICE_URL}" == "None" ]]; then
    echo "âŒ App Runner service not found: ${APPRUNNER_SERVICE_NAME}"
    exit 1
fi

echo "Creating CloudFront distribution"
echo "  Origin: ${SERVICE_URL}"

CALLER_REF="aethertest-$(date +%s)"

DIST_ID=$(command aws --no-verify-ssl cloudfront create-distribution \
    --profile "${AWS_PROFILE}" \
    --distribution-config "{
        \"CallerReference\": \"${CALLER_REF}\",
        \"Comment\": \"AetherTest App Runner CDN\",
        \"Enabled\": true,
        \"Origins\": {
            \"Quantity\": 1,
            \"Items\": [{
                \"Id\": \"apprunner\",
                \"DomainName\": \"${SERVICE_URL}\",
                \"CustomOriginConfig\": {
                    \"HTTPPort\": 80,
                    \"HTTPSPort\": 443,
                    \"OriginProtocolPolicy\": \"https-only\",
                    \"OriginSslProtocols\": {\"Quantity\": 1, \"Items\": [\"TLSv1.2\"]}
                }
            }]
        },
        \"DefaultCacheBehavior\": {
            \"TargetOriginId\": \"apprunner\",
            \"ViewerProtocolPolicy\": \"redirect-to-https\",
            \"CachePolicyId\": \"4135ea2d-6df8-44a3-9df3-4b5a84be39ad\",
            \"AllowedMethods\": {\"Quantity\": 7, \"Items\": [\"GET\",\"HEAD\",\"OPTIONS\",\"PUT\",\"PATCH\",\"POST\",\"DELETE\"], \"CachedMethods\": {\"Quantity\": 2, \"Items\": [\"GET\",\"HEAD\"]}},
            \"Compress\": true
        },
        \"PriceClass\": \"PriceClass_100\",
        \"ViewerCertificate\": {\"CloudFrontDefaultCertificate\": true}
    }" \
    --query 'Distribution.Id' --output text 2>/dev/null)

CF_DOMAIN=$(command aws --no-verify-ssl cloudfront get-distribution --id "${DIST_ID}" \
    --profile "${AWS_PROFILE}" \
    --query 'Distribution.DomainName' --output text 2>/dev/null)

echo ""
echo "âœ… CloudFront distribution created"
echo "   ID:     ${DIST_ID}"
echo "   Domain: https://${CF_DOMAIN}"
echo "   Status: Deploying (takes ~5-10 min)"
