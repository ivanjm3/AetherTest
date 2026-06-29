"""
Centralized AWS client factory for AetherTest.
Handles SSL issues behind corporate proxies by reading AETHERTEST_NO_SSL_VERIFY env var.
"""

import os
import boto3

AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
VERIFY_SSL = os.environ.get("AETHERTEST_NO_SSL_VERIFY", "").lower() not in ("1", "true", "yes")


def get_s3_client():
    return boto3.client("s3", region_name=AWS_REGION, verify=VERIFY_SSL)


def get_dynamodb_resource():
    return boto3.resource("dynamodb", region_name=AWS_REGION, verify=VERIFY_SSL)


def get_cloudwatch_client():
    return boto3.client("cloudwatch", region_name=AWS_REGION, verify=VERIFY_SSL)


def get_sns_client():
    return boto3.client("sns", region_name=AWS_REGION, verify=VERIFY_SSL)
