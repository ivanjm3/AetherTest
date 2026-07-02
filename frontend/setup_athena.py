"""
One-time setup: Create Athena output bucket if it doesn't exist.
Run: python frontend/setup_athena.py
"""

import os
import boto3
from botocore.config import Config
import urllib3

# Suppress InsecureRequestWarning when SSL verification is disabled
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

AWS_PROFILE = os.environ.get("AWS_PROFILE", "aethertest")
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
sts = session.client("sts", verify=False)
account_id = sts.get_caller_identity()["Account"]

BUCKET_NAME = f"aethertest-athena-results-poc-{account_id}"

s3 = session.client("s3", verify=False)

print(f"Account: {account_id}")
print(f"Bucket:  {BUCKET_NAME}")

try:
    s3.head_bucket(Bucket=BUCKET_NAME)
    print("✅ Bucket already exists")
except Exception:
    print("Creating bucket...")
    if AWS_REGION == "us-east-1":
        s3.create_bucket(Bucket=BUCKET_NAME)
    else:
        s3.create_bucket(
            Bucket=BUCKET_NAME,
            CreateBucketConfiguration={"LocationConstraint": AWS_REGION},
        )
    print(f"✅ Created: s3://{BUCKET_NAME}/")

print("\nDone. Set env var if different from default:")
print(f"  export ATHENA_OUTPUT_BUCKET={BUCKET_NAME}")
