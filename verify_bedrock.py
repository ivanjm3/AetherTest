"""
Quick Bedrock connection verification for AetherTest.
Run this after setting up credentials to confirm everything works.
Usage: python3 verify_bedrock.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

def main():
    print("=== AetherTest — Bedrock Connection Verification ===\n")

    # Check boto3
    try:
        import boto3
        print(f"✓ boto3 installed: {boto3.__version__}")
    except ImportError:
        print("✗ boto3 not installed. Run: pip3 install boto3")
        sys.exit(1)

    # Check credentials exist
    creds_path = os.path.expanduser("~/.aws/credentials")
    config_path = os.path.expanduser("~/.aws/config")

    if os.path.exists(creds_path):
        print(f"✓ AWS credentials file found: {creds_path}")
    else:
        print(f"✗ No credentials file at {creds_path}")
        print("  Run: python3 setup_aws.py")
        sys.exit(1)

    if os.path.exists(config_path):
        print(f"✓ AWS config file found: {config_path}")
    else:
        print(f"⚠ No config file at {config_path} (will use defaults)")

    # Test Bedrock connection
    print("\nTesting Amazon Bedrock connection...")
    try:
        from aethertest.bedrock_client import verify_bedrock_connection
        result = verify_bedrock_connection()

        if result["status"] == "connected":
            print(f"✓ Connected to Amazon Bedrock!")
            print(f"  Region:    {result['region']}")
            print(f"  Model ID:  {result['model_id']}")
            print(f"  Claude models available: {len(result.get('available_claude_models', []))}")
            print(f"  Smoke test: {'passed' if result.get('smoke_test_passed') else 'failed'}")
            print("\n✓ All checks passed. Ready to run AetherTest tasks!")
        elif result["status"] == "degraded":
            print(f"⚠ Connected but smoke test failed.")
            print(f"  Error: {result.get('error', 'unknown')}")
        else:
            print(f"✗ Connection failed: {result.get('error', 'unknown')}")
            print("\nTroubleshooting:")
            print("  1. Check your Access Key ID and Secret Access Key")
            print("  2. Ensure your IAM user has bedrock:InvokeModel permission")
            print("  3. Verify region is correct (us-east-1 or us-west-2)")
            sys.exit(1)

    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
