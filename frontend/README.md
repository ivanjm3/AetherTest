# AetherTest — Data Flow Testing Frontend

Agentic data flow testing automation for warehouse pipelines.

## Quick Start

### 1. Configure AWS SSO (one-time setup)

```bash
aws configure sso --profile aethertest
```

When prompted:
- SSO start URL: `https://your-org.awsapps.com/start`
- SSO Region: `us-east-1`
- Account: select your account
- Role: select role with Bedrock + S3 + DynamoDB access
- Default region: `us-east-1`
- Default output: `json`

### 2. Login via SSO

```bash
aws sso login --profile aethertest
```

This opens a browser for authentication. Once done, creds stay valid for 8-12 hours — no more pasting temp keys!

### 3. Start Backend

```bash
cd frontend
pip install fastapi uvicorn boto3
python api-server.py
```

Server starts at http://localhost:8001. Check health: `GET /api/health`

### 4. Start Frontend

```bash
cd frontend
npm install
npm run dev
```

Opens at http://localhost:5174

## Architecture

```
Browser (React) → http://localhost:8001 → Bedrock (Claude Sonnet 4)
                                        → S3 / DynamoDB (future)
```

- **No temp keys in code or env files**
- **No long-lived static profile with rotating credentials**
- **SSO token auto-refreshes** as long as the session is active

## Environment Variables (Backend)

| Variable | Default | Purpose |
|----------|---------|---------|
| `AWS_PROFILE` | `aethertest` | AWS SSO profile name |
| `AWS_DEFAULT_REGION` | `us-east-1` | AWS region |
| `BEDROCK_MODEL_ID` | `us.anthropic.claude-sonnet-4-20250514-v1:0` | Claude model |
| `AETHERTEST_NO_SSL_VERIFY` | — | Set to `1` if behind corporate proxy |

## If SSO Expires

```bash
aws sso login --profile aethertest
```

Then restart api-server.py. No code changes needed.
