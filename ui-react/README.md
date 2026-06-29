# AetherTest UI (React + TypeScript + Vite + Tailwind)

A modern frontend for the AetherTest Multi-Agent AI Testing Platform, replacing the legacy Streamlit interface.

## Prerequisites

- Node.js 20+
- AWS credentials with access to AetherTest resources (DynamoDB, S3, Lambda)

## Local Development

```bash
# 1. Install dependencies
npm install

# 2. Configure AWS credentials
cp .env.example .env
# Edit .env with your real AWS credentials

# 3. Start the dev server
npm run dev
```

The app runs at `http://localhost:5173` by default.

## AWS Credentials

The app needs the following environment variables (set in `.env`):

| Variable | Description |
|----------|-------------|
| `VITE_AWS_REGION` | AWS region (default: `us-east-1`) |
| `VITE_AWS_ACCESS_KEY_ID` | IAM access key with read access to DynamoDB/S3 and invoke access to Lambda |
| `VITE_AWS_SECRET_ACCESS_KEY` | Corresponding secret key |

The IAM user/role needs these permissions:
- `dynamodb:Scan` and `dynamodb:Query` on `aethertest-agent-assignments` and `aethertest-executions`
- `s3:GetObject` and `s3:ListBucket` on `aethertest-artifacts-*`
- `lambda:InvokeFunction` on `aethertest-test-author-agent`

## Pages

| Route | Page | Data Source |
|-------|------|-------------|
| `/` | Dashboard | DynamoDB `aethertest-agent-assignments` |
| `/requirements` | Requirements | Lambda `aethertest-test-author-agent` |
| `/test-cases` | Test Cases | S3 bucket |
| `/test-results` | Test Results | DynamoDB `aethertest-executions` |
| `/coverage` | Coverage Report | S3 bucket |
| `/agent-activity` | Agent Activity | DynamoDB `aethertest-agent-assignments` |

## Build for Production

```bash
npm run build
```

Output goes to `dist/`.

## Docker (ECS Fargate)

```bash
# Build the image (pass AWS creds as build args — they're baked into the static JS bundle)
docker build \
  --build-arg VITE_AWS_REGION=us-east-1 \
  --build-arg VITE_AWS_ACCESS_KEY_ID=AKIA... \
  --build-arg VITE_AWS_SECRET_ACCESS_KEY=... \
  -t aethertest-ui .

# Run locally
docker run -p 8080:80 aethertest-ui
```

The container serves the app on port 80 via nginx with SPA fallback routing.

## Tech Stack

- React 18 + TypeScript
- Vite 6
- Tailwind CSS 3 (dark mode via `class` strategy)
- AWS SDK v3 (DynamoDB, S3, Lambda)
- React Router 6
