# AetherTest — Admin Command (iam:PassRole Required)

Only **one command** needed. All IAM roles already exist from prior projects.
This creates the App Runner service reusing existing roles.

**Account:** 654654478821  
**Region:** us-east-1  
**Replace** `<ADMIN_PROFILE>` with your IAM profile name.  
**Add** `--no-verify-ssl` if behind corporate proxy.

---

## Single Command: Create App Runner Service

```bash
aws apprunner create-service \
  --service-name aethertest-prod \
  --source-configuration '{"ImageRepository":{"ImageIdentifier":"654654478821.dkr.ecr.us-east-1.amazonaws.com/aethertest-prod:latest","ImageRepositoryType":"ECR","ImageConfiguration":{"Port":"8001","RuntimeEnvironmentVariables":{"AWS_DEFAULT_REGION":"us-east-1","BEDROCK_MODEL_ID":"us.anthropic.claude-sonnet-4-20250514-v1:0","ATHENA_DATABASE":"icebergtarget","ATHENA_OUTPUT_BUCKET":"aethertest-athena-results-654654478821"}}},"AutoDeploymentsEnabled":true,"AuthenticationConfiguration":{"AccessRoleArn":"arn:aws:iam::654654478821:role/AppRunnerECRAccessRole"}}' \
  --instance-configuration '{"Cpu":"1 vCPU","Memory":"2 GB","InstanceRoleArn":"arn:aws:iam::654654478821:role/talk2data-apprunner-role"}' \
  --health-check-configuration '{"Protocol":"HTTP","Path":"/api/health","Interval":10,"Timeout":5,"HealthyThreshold":1,"UnhealthyThreshold":5}' \
  --profile <ADMIN_PROFILE> --region us-east-1
```

---

## What This Does

- Creates App Runner service `aethertest-prod` pointing at ECR image `aethertest-prod:latest`
- Port 8001, 1 vCPU, 2 GB RAM
- Health check at `/api/health`
- Auto-deploys when new image is pushed to ECR
- Reuses existing roles (no new IAM resources created):
  - `AppRunnerECRAccessRole` — pulls images from ECR
  - `talk2data-apprunner-role` — runtime access (Bedrock/S3/Athena)

---

## Verification

```bash
aws apprunner list-services \
  --profile <ADMIN_PROFILE> --region us-east-1 \
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
