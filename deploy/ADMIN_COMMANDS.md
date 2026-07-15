# AetherTest — Admin Command (iam:PassRole Required)

Only **one command** needed. All IAM roles already exist from prior projects.
This creates the App Runner service reusing existing roles.

**Account:** <your-account-id>  
**Region:** us-east-1  
**Add** `--no-verify-ssl` if behind corporate proxy.

---

## Single Command: Create App Runner Service

```bash
aws apprunner create-service \
  --service-name "aethertest-prod" \
  --source-configuration '{"AuthenticationConfiguration": {"AccessRoleArn": "arn:aws:iam::<your-account-id>:role/AppRunnerECRAccessRole"},"AutoDeploymentsEnabled": true,"ImageRepository": {"ImageIdentifier": "<your-account-id>.dkr.ecr.us-east-1.amazonaws.com/aethertest-prod:latest","ImageRepositoryType": "ECR","ImageConfiguration": {"Port": "8001","RuntimeEnvironmentVariables": {"AWS_DEFAULT_REGION": "us-east-1","BEDROCK_MODEL_ID": "us.anthropic.claude-sonnet-4-20250514-v1:0","ATHENA_DATABASE": "icebergtarget","ATHENA_OUTPUT_BUCKET": "aethertest-athena-results-<your-account-id>"}}}}' \
  --instance-configuration '{"Cpu": "1 vCPU","Memory": "2 GB","InstanceRoleArn": "arn:aws:iam::<your-account-id>:role/aethertest-apprunner-role"}' \
  --health-check-configuration '{"Protocol": "HTTP","Path": "/api/health","Interval": 10,"Timeout": 5,"HealthyThreshold": 1,"UnhealthyThreshold": 5}' \
  --region us-east-1
```

---

## What This Does

- Creates App Runner service `aethertest-prod` pointing at ECR image `aethertest-prod:latest`
- Port 8001, 1 vCPU, 2 GB RAM
- Health check at `/api/health`
- Auto-deploys when new image is pushed to ECR
- Reuses existing roles (no new IAM resources created):
  - `AppRunnerECRAccessRole` — pulls images from ECR
  - `aethertest-apprunner-role` — runtime access (Bedrock/S3/Athena)

---

## Verification

```bash
aws apprunner list-services \
  --region us-east-1 \
  --query 'ServiceSummaryList[?ServiceName==`aethertest-prod`].[ServiceName,Status,ServiceUrl]' \
  --output table
```

---

## After This

The developer (PowerUserAccess) can redeploy independently:
```
bash deploy/deploy.sh --build-backend
```
CodeBuild pushes to ECR → App Runner auto-redeploys. No further admin action needed.
