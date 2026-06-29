"""
AWS Credentials Setup Script for AetherTest
Run this once to configure your AWS credentials locally.
Usage: python3 setup_aws.py
"""

import os
import sys

def setup_aws_credentials():
    aws_dir = os.path.expanduser("~/.aws")
    os.makedirs(aws_dir, exist_ok=True)

    print("=== AetherTest AWS Credentials Setup ===\n")
    print("Enter your AWS credentials (input is hidden for security):\n")

    import getpass
    access_key = getpass.getpass("AWS Access Key ID: ").strip()
    secret_key = getpass.getpass("AWS Secret Access Key: ").strip()
    region = input("AWS Region (press Enter for us-east-1): ").strip() or "us-east-1"

    # Write credentials file
    credentials_path = os.path.join(aws_dir, "credentials")
    with open(credentials_path, "w") as f:
        f.write(f"[default]\n")
        f.write(f"aws_access_key_id = {access_key}\n")
        f.write(f"aws_secret_access_key = {secret_key}\n")
    os.chmod(credentials_path, 0o600)  # secure permissions

    # Write config file
    config_path = os.path.join(aws_dir, "config")
    with open(config_path, "w") as f:
        f.write(f"[default]\n")
        f.write(f"region = {region}\n")
        f.write(f"output = json\n")
    os.chmod(config_path, 0o600)

    print(f"\n✓ Credentials saved to {credentials_path}")
    print(f"✓ Config saved to {config_path}")
    print(f"✓ Region set to: {region}")

    # Verify connection
    print("\nVerifying Bedrock connection...")
    try:
        import boto3
        client = boto3.client("bedrock", region_name=region)
        models = client.list_foundation_models()
        claude_models = [
            m["modelId"] for m in models["modelSummaries"]
            if "claude" in m["modelId"].lower()
        ]
        if claude_models:
            print(f"✓ Connected to Amazon Bedrock successfully!")
            print(f"✓ Claude models available: {len(claude_models)} found")
            print(f"  First model: {claude_models[0]}")
        else:
            print("⚠ Connected but no Claude models found. Check model access in AWS Console.")
    except ImportError:
        print("⚠ boto3 not installed. Run: pip3 install boto3")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        print("  Check your credentials and region, then try again.")
        sys.exit(1)

    print("\n=== Setup Complete. You can now run the AetherTest tasks. ===")

if __name__ == "__main__":
    setup_aws_credentials()
