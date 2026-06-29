"""
Local API server that wraps Lambda handlers and AWS calls for the React frontend.
This eliminates the need for deployed Lambda functions and avoids browser CORS issues
with direct AWS SDK calls. Mirrors what the Streamlit app did server-side.

Usage:
    $env:AWS_PROFILE = "kiro-dev"
    $env:AETHERTEST_NO_SSL_VERIFY = "1"
    python ui-react/api-server.py

Runs on http://localhost:8000
"""
from __future__ import annotations

import os
import sys
import json
import warnings
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Suppress SSL warnings
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

# Ensure correct env
os.environ.setdefault("AWS_PROFILE", "kiro-dev")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

# Add project paths so lambda handlers are importable
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "layers"))
sys.path.insert(0, ROOT)

import boto3
from decimal import Decimal

PORT = int(os.environ.get("API_PORT", "8000"))
REGION = "us-east-1"
BUCKET_NAME = "aethertest-artifacts-654654478821"

_no_ssl = os.environ.get("AETHERTEST_NO_SSL_VERIFY", "")
_verify = not bool(_no_ssl)

# AWS clients (server-side, no CORS issues)
s3_client = boto3.client("s3", region_name=REGION, verify=_verify)
dynamodb = boto3.resource("dynamodb", region_name=REGION, verify=_verify)


class DecimalEncoder(json.JSONEncoder):
    """Handle DynamoDB Decimal types."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            if obj % 1 == 0:
                return int(obj)
            return float(obj)
        return super().default(obj)


def json_dumps(data) -> str:
    return json.dumps(data, cls=DecimalEncoder, default=str)


class Handler(BaseHTTPRequestHandler):
    """Routes requests to lambda handlers or AWS services."""

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)

        if path == "/api/dynamodb/scan":
            self._handle_dynamo_scan(params)
        elif path == "/api/dynamodb/query":
            self._handle_dynamo_query(params)
        elif path == "/api/s3/list":
            self._handle_s3_list(params)
        elif path == "/api/s3/get":
            self._handle_s3_get(params)
        else:
            self._respond(404, {"error": f"Unknown GET endpoint: {path}"})

    def do_POST(self):
        path = self.path.rstrip("/")

        if path == "/api/test-author":
            self._handle_test_author()
        elif path == "/api/run-pipeline":
            self._handle_run_pipeline()
        else:
            self._respond(404, {"error": f"Unknown POST endpoint: {path}"})

    # ── Lambda Handlers ───────────────────────────────────────────────────────

    def _handle_test_author(self):
        try:
            body = self._read_body()
            from lambdas.test_author_agent.handler import handler as test_author_handler
            result = test_author_handler(body, None)
            self._respond(200, result)
        except Exception as e:
            self._respond(500, {"error": str(e)})

    def _handle_run_pipeline(self):
        """POST /api/run-pipeline — run the full orchestrator pipeline."""
        try:
            body = self._read_body()
            from orchestrator import run_pipeline
            aut_config = body.get("aut_config", None)
            fast_mode = body.get("fast_mode", True)
            # Allow custom requirements
            custom_requirements = body.get("requirements", None)
            if custom_requirements:
                import lambdas.test_author_agent.handler  # noqa: ensure module loaded
                # Patch DEFAULT_REQUIREMENTS in orchestrator temporarily
                import orchestrator
                original_reqs = orchestrator.DEFAULT_REQUIREMENTS
                orchestrator.DEFAULT_REQUIREMENTS = custom_requirements
                try:
                    results = run_pipeline(aut_config=aut_config, fast_mode=fast_mode)
                finally:
                    orchestrator.DEFAULT_REQUIREMENTS = original_reqs
            else:
                results = run_pipeline(aut_config=aut_config, fast_mode=fast_mode)
            self._respond(200, results)
        except Exception as e:
            self._respond(500, {"error": str(e)})

    # ── DynamoDB ──────────────────────────────────────────────────────────────

    def _handle_dynamo_scan(self, params: dict):
        """GET /api/dynamodb/scan?table=NAME&limit=50"""
        try:
            table_name = params.get("table", [""])[0]
            limit = int(params.get("limit", ["50"])[0])
            if not table_name:
                self._respond(400, {"error": "Missing 'table' parameter"})
                return

            table = dynamodb.Table(table_name)
            response = table.scan(Limit=limit)
            items = response.get("Items", [])
            self._respond(200, {"items": items})
        except Exception as e:
            self._respond(500, {"error": f"DynamoDB scan failed: {e}"})

    def _handle_dynamo_query(self, params: dict):
        """GET /api/dynamodb/query?table=NAME&pk=VALUE&limit=20"""
        try:
            import boto3.dynamodb.conditions as conditions

            table_name = params.get("table", [""])[0]
            pk = params.get("pk", [""])[0]
            limit = int(params.get("limit", ["20"])[0])

            if not table_name or not pk:
                self._respond(400, {"error": "Missing 'table' or 'pk' parameter"})
                return

            table = dynamodb.Table(table_name)
            response = table.query(
                KeyConditionExpression=conditions.Key("PK").eq(pk),
                Limit=limit,
                ScanIndexForward=False,
            )
            items = response.get("Items", [])
            self._respond(200, {"items": items})
        except Exception as e:
            self._respond(500, {"error": f"DynamoDB query failed: {e}"})

    # ── S3 ────────────────────────────────────────────────────────────────────

    def _handle_s3_list(self, params: dict):
        """GET /api/s3/list?prefix=demo-ecommerce/test-cases/&maxKeys=100"""
        try:
            prefix = params.get("prefix", [""])[0]
            max_keys = int(params.get("maxKeys", ["100"])[0])

            response = s3_client.list_objects_v2(
                Bucket=BUCKET_NAME, Prefix=prefix, MaxKeys=max_keys
            )
            contents = response.get("Contents", [])
            # Serialize - only return key, size, last modified
            items = [
                {
                    "Key": obj["Key"],
                    "Size": obj.get("Size", 0),
                    "LastModified": obj.get("LastModified", ""),
                }
                for obj in contents
            ]
            self._respond(200, {"contents": items})
        except Exception as e:
            self._respond(500, {"error": f"S3 list failed: {e}"})

    def _handle_s3_get(self, params: dict):
        """GET /api/s3/get?key=demo-ecommerce/test-cases/suite.json"""
        try:
            key = params.get("key", [""])[0]
            if not key:
                self._respond(400, {"error": "Missing 'key' parameter"})
                return

            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=key)
            body = response["Body"].read().decode("utf-8")
            data = json.loads(body)
            self._respond(200, data)
        except s3_client.exceptions.NoSuchKey:
            self._respond(404, {"error": f"Object not found: {key}"})
        except Exception as e:
            self._respond(500, {"error": f"S3 get failed: {e}"})

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _read_body(self) -> dict:
        content_length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(content_length)
        return json.loads(raw) if raw else {}

    def _respond(self, status: int, data):
        body = json_dumps(data).encode("utf-8")
        self.send_response(status)
        self._cors_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, format, *args):
        print(f"[api] {args[0]}")


def main():
    print(f"AetherTest Local API Server")
    print(f"  Listening on http://localhost:{PORT}")
    print(f"  Endpoints:")
    print(f"    POST /api/test-author          →  Test Author Agent handler")
    print(f"    POST /api/run-pipeline         →  Full orchestrator pipeline")
    print(f"    GET  /api/dynamodb/scan        →  DynamoDB Scan")
    print(f"    GET  /api/dynamodb/query       →  DynamoDB Query")
    print(f"    GET  /api/s3/list              →  S3 ListObjectsV2")
    print(f"    GET  /api/s3/get               →  S3 GetObject (JSON)")
    print(f"  AWS Profile: {os.environ.get('AWS_PROFILE', 'default')}")
    print(f"  S3 Bucket: {BUCKET_NAME}")
    print()

    server = HTTPServer(("0.0.0.0", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
