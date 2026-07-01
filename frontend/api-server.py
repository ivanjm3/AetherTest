"""
AetherTest Data Flow Testing — API Server
FastAPI backend with real Bedrock (Claude) + Step Functions + Athena integration.
Uses AWS SSO for authentication — no temp keys needed.

Setup:
    1. Configure SSO: aws configure sso --profile aethertest
    2. Login: aws sso login --profile aethertest
    3. Run: python frontend/api-server.py
"""

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.config import Config
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add project root + layers to path so we can import agent handlers
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)
sys.path.insert(0, os.path.join(_PROJECT_ROOT, "layers"))

from lambdas.test_analyst_agent.handler import handler as test_analyst_handler

# ─── AWS Configuration (SSO-based) ────────────────────────────────────────────

AWS_PROFILE = os.environ.get("AWS_PROFILE", "aethertest")
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
VERIFY_SSL = os.environ.get("AETHERTEST_NO_SSL_VERIFY", "").lower() not in ("1", "true", "yes")

CLAUDE_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID",
    "us.anthropic.claude-sonnet-4-20250514-v1:0"
)

# Athena config
ATHENA_OUTPUT_BUCKET = os.environ.get("ATHENA_OUTPUT_BUCKET", "aethertest-athena-results-654654478821")
ATHENA_DATABASE = os.environ.get("ATHENA_DATABASE", "default")
ATHENA_WORKGROUP = os.environ.get("ATHENA_WORKGROUP", "primary")

BOTO_CONFIG = Config(
    region_name=AWS_REGION,
    retries={"max_attempts": 3, "mode": "adaptive"},
)


def get_boto_session():
    """Create boto3 session using SSO profile."""
    return boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)


def get_bedrock_runtime():
    session = get_boto_session()
    return session.client("bedrock-runtime", config=BOTO_CONFIG, verify=False)


def get_sfn_client():
    session = get_boto_session()
    return session.client("stepfunctions", config=BOTO_CONFIG, verify=False)


def get_athena_client():
    session = get_boto_session()
    return session.client("athena", config=BOTO_CONFIG, verify=False)


def get_glue_client():
    session = get_boto_session()
    return session.client("glue", config=BOTO_CONFIG, verify=False)


def invoke_claude(prompt: str, system_prompt: str = "", max_tokens: int = 4096) -> str:
    """Invoke Claude via Bedrock. Returns text response."""
    client = get_bedrock_runtime()

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": 0.0,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system_prompt:
        body["system"] = system_prompt

    response = client.invoke_model(
        modelId=CLAUDE_MODEL_ID,
        body=json.dumps(body),
        contentType="application/json",
        accept="application/json",
    )
    result = json.loads(response["body"].read())
    return result["content"][0]["text"]


def parse_json_response(text: str) -> dict:
    """Extract JSON from Claude response (handles markdown code blocks)."""
    json_str = text
    if "```json" in json_str:
        json_str = json_str.split("```json")[1].split("```")[0]
    elif "```" in json_str:
        json_str = json_str.split("```")[1].split("```")[0]
    return json.loads(json_str.strip())


# ─── Athena Query Execution ────────────────────────────────────────────────────

def run_athena_query(sql: str, database: str = None) -> dict:
    """
    Execute SQL via Athena and return results.
    Waits for completion (polling).
    """
    client = get_athena_client()
    db = database or ATHENA_DATABASE

    # Start query
    response = client.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": db},
        WorkGroup=ATHENA_WORKGROUP,
        ResultConfiguration={
            "OutputLocation": f"s3://{ATHENA_OUTPUT_BUCKET}/query-results/"
        },
    )
    query_id = response["QueryExecutionId"]

    # Poll for completion (max 60s)
    for _ in range(60):
        status = client.get_query_execution(QueryExecutionId=query_id)
        state = status["QueryExecution"]["Status"]["State"]

        if state == "SUCCEEDED":
            break
        elif state in ("FAILED", "CANCELLED"):
            reason = status["QueryExecution"]["Status"].get("StateChangeReason", "Unknown error")
            return {"error": reason, "status": state, "query_id": query_id}

        time.sleep(1)
    else:
        return {"error": "Query timed out after 60s", "status": "TIMEOUT", "query_id": query_id}

    # Get results
    results = client.get_query_results(QueryExecutionId=query_id)
    rows = results["ResultSet"]["Rows"]

    if not rows:
        return {"columns": [], "rows": [], "query_id": query_id}

    # First row is header
    columns = [col.get("VarCharValue", "") for col in rows[0]["Data"]]
    data_rows = []
    for row in rows[1:]:
        data_rows.append({
            columns[i]: cell.get("VarCharValue")
            for i, cell in enumerate(row["Data"])
        })

    return {"columns": columns, "rows": data_rows, "query_id": query_id}


# ─── Step Functions Integration ────────────────────────────────────────────────

def describe_step_function(arn: str) -> dict:
    """Fetch Step Function definition from AWS."""
    client = get_sfn_client()
    response = client.describe_state_machine(stateMachineArn=arn)
    return {
        "name": response["name"],
        "definition": json.loads(response["definition"]),
        "role_arn": response["roleArn"],
        "creation_date": response["creationDate"].isoformat(),
    }


def _looks_like_mwaa_env(path: str) -> bool:
    """Check if input looks like an MWAA environment name (not Python code)."""
    # MWAA env names are short alphanumeric+hyphens
    return bool(path) and len(path) < 100 and not any(kw in path for kw in ["import ", "def ", "dag", "=", "("])


def get_mwaa_client():
    session = get_boto_session()
    return session.client("mwaa", config=BOTO_CONFIG, verify=False)


def fetch_mwaa_dag(path: str) -> str:
    """
    Fetch DAG source from MWAA.
    Accepts: MWAA ARN or environment name.
    Returns DAG source code if accessible, otherwise returns environment metadata.
    """
    client = get_mwaa_client()

    # Extract environment name from ARN if needed
    if path.startswith("arn:aws:airflow:"):
        # arn:aws:airflow:region:account:environment/env-name
        env_name = path.split("/")[-1]
    else:
        env_name = path.strip()

    try:
        # Get environment details
        env_response = client.get_environment(Name=env_name)
        env_info = env_response["Environment"]

        dag_s3_path = env_info.get("DagS3Path", "dags/")
        source_bucket = env_info.get("SourceBucketArn", "").split(":")[-1] if env_info.get("SourceBucketArn") else ""

        # Try to list DAG files from S3
        dag_content = f"MWAA Environment: {env_name}\n"
        dag_content += f"Airflow Version: {env_info.get('AirflowVersion', 'unknown')}\n"
        dag_content += f"DAG S3 Path: s3://{source_bucket}/{dag_s3_path}\n"
        dag_content += f"Execution Role: {env_info.get('ExecutionRoleArn', 'unknown')}\n"

        # Attempt to read DAG files from S3
        if source_bucket:
            s3 = get_boto_session().client("s3", verify=False)
            try:
                objects = s3.list_objects_v2(
                    Bucket=source_bucket,
                    Prefix=dag_s3_path,
                    MaxKeys=10,
                )
                dag_files = [obj["Key"] for obj in objects.get("Contents", []) if obj["Key"].endswith(".py")]

                if dag_files:
                    # Read first DAG file
                    first_dag = dag_files[0]
                    obj = s3.get_object(Bucket=source_bucket, Key=first_dag)
                    dag_source = obj["Body"].read().decode("utf-8")
                    dag_content += f"\n--- DAG Source ({first_dag}) ---\n{dag_source}"

                    if len(dag_files) > 1:
                        dag_content += f"\n\n(+{len(dag_files)-1} more DAG files: {', '.join(dag_files[1:])})"
            except Exception:
                dag_content += "\n(Could not read DAG files from S3 — check permissions)"

        return dag_content

    except Exception as e:
        return f"Could not fetch MWAA environment '{env_name}': {e}\nInput treated as description."


# ─── FastAPI App ───────────────────────────────────────────────────────────────

app = FastAPI(title="AetherTest Data Flow API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Models ────────────────────────────────────────────────────────────────────

class JobConfig(BaseModel):
    type: str
    path: str
    name: str | None = None


class AnalyzeJobRequest(BaseModel):
    type: str
    path: str
    file_content: str | None = None  # Optional: uploaded file content


class GenerateTestsRequest(BaseModel):
    job_config: JobConfig
    dependencies: list[dict[str, Any]]
    force_regenerate: bool = False


class RunTestsRequest(BaseModel):
    job_config: JobConfig
    dependencies: list[dict[str, Any]]
    test_cases: list[dict[str, Any]]


class QueryRequest(BaseModel):
    input: str
    mode: str  # nlp | sql
    connection_id: str | None = None


class AnalyzeFailuresRequest(BaseModel):
    execution_id: str
    failed_tests: list[dict[str, Any]]
    recent_changes: list[str] = []


# ─── Storage ──────────────────────────────────────────────────────────────────

execution_history: list[dict[str, Any]] = []


# ─── Agent Prompts ─────────────────────────────────────────────────────────────

ANALYZE_JOB_SYSTEM = (
    "You are a data engineering expert. Given ANY pipeline definition "
    "— Step Function (ASL JSON), Airflow DAG (Python), metadata description, "
    "YAML config, or free-text — analyze it and extract:\n"
    "1. All source data paths (S3 buckets, Glue tables, DynamoDB tables, databases, APIs, files)\n"
    "2. All target/destination paths (S3, Redshift, Snowflake, Glue tables, data warehouses)\n"
    "3. Required connection strings, credentials references, or service endpoints\n"
    "4. The overall pipeline purpose and what transformations it performs\n\n"
    "Respond ONLY in valid JSON:\n"
    '{\n'
    '  "job_name": "descriptive name of what this pipeline does",\n'
    '  "dependencies": [\n'
    '    {"id": "unique-id", "label": "Human readable label", "type": "source|target|connection", "value": "actual path/ARN/table name", "editable": true}\n'
    '  ]\n'
    '}\n\n'
    "Be thorough. If analyzing:\n"
    "- Step Functions: Look at Lambda params, Glue job args, S3 paths, task inputs/outputs\n"
    "- Airflow DAGs: Look at operators (S3, GCS, BigQuery, Redshift, Postgres, etc.), connections, variables, XCom\n"
    "- Metadata/descriptions: Infer all data sources and sinks from the description\n"
    "- If the input is ambiguous, make reasonable assumptions and note them in labels"
)

GENERATE_TESTS_SYSTEM = (
    "You are a data quality testing expert for AWS data warehouses (Athena/Glue/S3/Iceberg).\n"
    "Given a pipeline's dependencies (sources, targets, connections), generate test cases as Athena-compatible SQL.\n\n"
    "Categories:\n"
    "- row_count: Compare source vs target row counts\n"
    "- schema: Verify column existence and types via information_schema or Glue catalog\n"
    "- null_check: Critical columns have no unexpected NULLs\n"
    "- transform: Business logic / aggregation validation\n"
    "- referential_integrity: FK relationships hold\n"
    "- freshness: Partition dates are recent\n"
    "- iceberg_integrity: Iceberg-specific checks (snapshots, compaction, time travel)\n\n"
    "CRITICAL RULES:\n"
    "- ONLY use table names and column names that appear in the ACTUAL GLUE CATALOG section below.\n"
    "- DO NOT invent or guess table names or column names that are not listed.\n"
    "- If a table or column is not in the catalog, DO NOT reference it.\n"
    "- Reference tables as database.table_name (e.g. icebergtarget.brand_sms_performance_kpi)\n"
    "- For Iceberg metadata queries, use: \"database\".\"table$snapshots\", \"database\".\"table$history\"\n"
    "- Use Athena/Trino syntax (NOT Spark or Hive syntax)\n"
    "- For freshness checks, query actual date columns in the data, not $snapshots metadata\n"
    "- Use CAST and TRY_CAST for safe type conversions\n"
    "- IMPORTANT: In Iceberg tables, most columns are VARCHAR/STRING. Always CAST date columns before comparing:\n"
    "  WRONG: WHERE processing_date <= current_date\n"
    "  RIGHT: WHERE CAST(processing_date AS date) <= current_date\n"
    "- IMPORTANT: For JOIN conditions across tables, CAST both sides to the same type:\n"
    "  WRONG: WHERE a.subscriber_no = b.subscriber_id\n"
    "  RIGHT: WHERE CAST(a.subscriber_no AS varchar) = CAST(b.subscriber_id AS varchar)\n"
    "- When comparing numeric values, CAST varchar columns: CAST(column AS BIGINT) or CAST(column AS DOUBLE)\n\n"
    "Respond ONLY in valid JSON:\n"
    '{\n'
    '  "test_cases": [\n'
    '    {\n'
    '      "id": "TC-XXXXXX",\n'
    '      "name": "Short name",\n'
    '      "user_story": "As a data engineer, I want to verify X so that Y",\n'
    '      "category": "row_count|schema|null_check|transform|referential_integrity|freshness|iceberg_integrity",\n'
    '      "description": "What this validates in plain English",\n'
    '      "sql": "Athena-compatible SQL using ONLY tables/columns from the catalog",\n'
    '      "expected": "What passing looks like",\n'
    '      "priority": "high|medium|low"\n'
    '    }\n'
    '  ]\n'
    '}\n\n'
    "Generate 8-12 test cases. ONLY use table and column names from the ACTUAL GLUE CATALOG provided.\n"
    "IMPORTANT: Each test MUST include a user_story field in the format: "
    "'As a [role], I want to verify [what] so that [why]'"
)

NLP_TO_SQL_SYSTEM = (
    "You are a SQL expert for AWS Athena (Presto/Trino syntax).\n"
    "Convert the user's natural language question into executable Athena SQL.\n\n"
    "Rules:\n"
    "- Use Presto/Trino syntax (ANSI SQL with Athena extensions)\n"
    "- Reference Glue catalog tables as database.table_name\n"
    "- Use appropriate date functions (date_diff, current_date, date_parse)\n"
    "- Add LIMIT 100 by default for safety\n\n"
    "Respond ONLY in valid JSON:\n"
    '{\n'
    '  "generated_sql": "SELECT ... FROM ...",\n'
    '  "explanation": "Brief explanation"\n'
    '}'
)


# ─── Endpoints ─────────────────────────────────────────────────────────────────


@app.get("/api/health")
async def health_check():
    """Verify AWS SSO session + Bedrock access."""
    try:
        session = get_boto_session()
        sts = session.client("sts", verify=False)
        identity = sts.get_caller_identity()
        return {
            "status": "connected",
            "account": identity["Account"],
            "arn": identity["Arn"],
            "region": AWS_REGION,
            "profile": AWS_PROFILE,
            "model": CLAUDE_MODEL_ID,
            "athena_database": ATHENA_DATABASE,
        }
    except Exception as e:
        error_msg = str(e)
        hint = f"Run: aws sso login --profile {AWS_PROFILE}"
        if "expired" in error_msg.lower() or "token" in error_msg.lower():
            hint = f"SSO token expired. Run: aws sso login --profile {AWS_PROFILE}"
        return {"status": "error", "error": error_msg, "hint": hint}


@app.post("/api/analyze-job")
async def analyze_job(req: AnalyzeJobRequest):
    """
    Analyze a job definition. Handles:
    - Step Functions: ARN → fetches real definition from AWS
    - Airflow: MWAA ARN → fetches DAG source, OR raw Python code
    - Metadata: free text, JSON, YAML, or any file content

    Enriches analysis with actual Glue catalog metadata when available.
    """
    try:
        job_context = ""
        glue_context = ""

        if req.type == "step_function":
            # Detect if it's an ARN or pasted code
            if req.path.startswith("arn:aws:states:"):
                sfn_data = describe_step_function(req.path)
                job_definition = json.dumps(sfn_data["definition"], indent=2)
                job_context = f"Step Function Name: {sfn_data['name']}\nRole: {sfn_data['role_arn']}\nASL Definition:\n{job_definition}"

                # Enrich with Glue catalog metadata — discover actual tables
                try:
                    glue = get_glue_client()
                    db_response = glue.get_databases()
                    catalog_info = []
                    for db in db_response.get("DatabaseList", []):
                        db_name = db["Name"]
                        tables_resp = glue.get_tables(DatabaseName=db_name, MaxResults=50)
                        table_names = [t["Name"] for t in tables_resp.get("TableList", [])]
                        if table_names:
                            # Get column details for each table
                            table_details = []
                            for tbl in tables_resp.get("TableList", []):
                                params = tbl.get("Parameters", {})
                                cols = [f"{c['Name']} ({c['Type']})" for c in tbl.get("StorageDescriptor", {}).get("Columns", [])]
                                is_iceberg = params.get("table_type", "").lower() == "iceberg"
                                loc = tbl.get("StorageDescriptor", {}).get("Location", "")
                                cols_str = ", ".join(cols[:10])
                                if len(cols) > 10:
                                    cols_str += "..."
                                iceberg_tag = " [ICEBERG]" if is_iceberg else ""
                                table_details.append(
                                    f"    - {tbl['Name']}{iceberg_tag}: "
                                    f"columns=[{cols_str}] "
                                    f"location={loc}"
                                )
                            catalog_info.append(f"  Database: {db_name}\n" + "\n".join(table_details))

                    if catalog_info:
                        glue_context = "\n\nAVAILABLE GLUE CATALOG (real tables in this AWS account):\n" + "\n".join(catalog_info)
                except Exception as glue_err:
                    glue_context = f"\n\n(Could not fetch Glue catalog: {glue_err})"

            else:
                # User pasted ASL JSON or description
                job_context = f"Step Function Definition (user-provided):\n{req.path}"
                if req.file_content:
                    job_context += f"\n\nAdditional file content:\n{req.file_content}"

        elif req.type == "airflow":
            # Detect if it's an MWAA ARN/environment or pasted code
            if req.path.startswith("arn:aws:airflow:") or _looks_like_mwaa_env(req.path):
                dag_source = fetch_mwaa_dag(req.path)
                job_context = f"Airflow DAG (fetched from MWAA):\n{dag_source}"
            else:
                # User pasted DAG Python code or description
                content = req.file_content or req.path
                job_context = f"Airflow DAG/Pipeline Definition:\n{content}"

        else:
            # Metadata: accept anything — text, JSON, YAML, file content
            content = req.file_content or req.path
            job_context = f"Pipeline Metadata/Description:\n{content}"

        prompt = f"""Analyze this data pipeline and extract ALL dependencies (sources, targets, connections):

Job Type: {req.type}
{job_context}
{glue_context}

Be thorough. Identify every data source, destination, and connection this pipeline uses.
If Glue catalog info is provided above, use actual table names and databases from it.
Mark Iceberg tables explicitly in the dependency labels."""

        response_text = invoke_claude(prompt, system_prompt=ANALYZE_JOB_SYSTEM)
        result = parse_json_response(response_text)
        return result

    except Exception as e:
        error_msg = str(e)
        if "StateMachineDoesNotExist" in error_msg or "does not exist" in error_msg.lower():
            raise HTTPException(status_code=404, detail=f"Resource not found: {req.path}")
        elif "AccessDenied" in error_msg or "not authorized" in error_msg.lower():
            raise HTTPException(status_code=403, detail=f"Access denied. Check IAM permissions.")
        elif "InvalidJson" in error_msg or "JSONDecodeError" in error_msg:
            raise HTTPException(status_code=500, detail=f"Agent returned invalid JSON. Retry or simplify input.")
        raise HTTPException(status_code=500, detail=f"Job analysis failed: {error_msg}")


@app.post("/api/generate-tests")
async def generate_tests(req: GenerateTestsRequest):
    """
    Generate test cases using Claude. Caches results in S3.
    Returns cached version unless force_regenerate=True or deps changed.
    """
    # Create cache key from job config type + path + selected dep values (captures what tests are FOR)
    import hashlib
    deps_values = sorted([d.get("value", "") for d in req.dependencies])
    cache_input = f"{req.job_config.type}:{req.job_config.path.strip()}:{','.join(deps_values)}"
    deps_key = hashlib.md5(cache_input.encode()).hexdigest()
    s3_key = f"test-scripts/{deps_key}.json"

    # Check if we have a cached version in S3
    force_regen = req.force_regenerate
    if not force_regen:
        try:
            session = get_boto_session()
            s3 = session.client("s3", verify=False)
            obj = s3.get_object(Bucket=ATHENA_OUTPUT_BUCKET, Key=s3_key)
            cached = json.loads(obj["Body"].read().decode("utf-8"))
            print(f"  ✅ Loaded cached tests from s3://{ATHENA_OUTPUT_BUCKET}/{s3_key}")
            return cached
        except Exception as e:
            print(f"  ℹ️ No cache ({type(e).__name__}), generating fresh...")

    deps_summary = "\n".join(
        f"- [{d.get('type', 'unknown')}] {d.get('label', 'Unknown')}: {d.get('value', '')}"
        for d in req.dependencies
    )

    # Enrich with actual Glue catalog metadata for accurate SQL
    # Only include databases/tables that are relevant to this pipeline's dependencies
    catalog_context = ""
    try:
        glue = get_glue_client()

        # Extract database and table hints from dependencies
        dep_values = [d.get("value", "").lower() for d in req.dependencies]
        dep_labels = [d.get("label", "").lower() for d in req.dependencies]
        all_dep_text = " ".join(dep_values + dep_labels)

        db_response = glue.get_databases()
        catalog_lines = []
        for db in db_response.get("DatabaseList", []):
            db_name = db["Name"]
            # Include this database if it's mentioned in dependencies OR if any dep table is in it
            tables_resp = glue.get_tables(DatabaseName=db_name, MaxResults=50)
            table_list = tables_resp.get("TableList", [])

            # Check if this database or any of its tables is referenced in dependencies
            db_relevant = db_name.lower() in all_dep_text
            relevant_tables = []
            for tbl in table_list:
                tbl_name = tbl["Name"].lower()
                if db_relevant or tbl_name in all_dep_text or any(tbl_name in dv for dv in dep_values):
                    relevant_tables.append(tbl)

            # If no specific match, but this is the only non-default DB, include it
            if not relevant_tables and db_relevant:
                relevant_tables = table_list

            for tbl in relevant_tables:
                params = tbl.get("Parameters", {})
                cols = [f"{c['Name']}:{c['Type']}" for c in tbl.get("StorageDescriptor", {}).get("Columns", [])]
                is_iceberg = params.get("table_type", "").lower() == "iceberg"
                iceberg_tag = " [ICEBERG]" if is_iceberg else ""
                catalog_lines.append(
                    f"  {db_name}.{tbl['Name']}{iceberg_tag} — {', '.join(cols)}"
                )

        if catalog_lines:
            catalog_context = (
                "\n\nACTUAL GLUE CATALOG (ONLY use these table and column names in SQL — "
                "do NOT invent any others. Note the types after colon — use CAST when comparing different types):\n"
                + "\n".join(catalog_lines)
            )
        else:
            # Fallback: include all databases if nothing matched
            catalog_lines_all = []
            for db in db_response.get("DatabaseList", []):
                db_name = db["Name"]
                tables_resp = glue.get_tables(DatabaseName=db_name, MaxResults=50)
                for tbl in tables_resp.get("TableList", []):
                    params = tbl.get("Parameters", {})
                    cols = [f"{c['Name']}:{c['Type']}" for c in tbl.get("StorageDescriptor", {}).get("Columns", [])]
                    is_iceberg = params.get("table_type", "").lower() == "iceberg"
                    iceberg_tag = " [ICEBERG]" if is_iceberg else ""
                    catalog_lines_all.append(
                        f"  {db_name}.{tbl['Name']}{iceberg_tag} — {', '.join(cols)}"
                    )
            if catalog_lines_all:
                catalog_context = (
                    "\n\nACTUAL GLUE CATALOG (ONLY use these table and column names in SQL — "
                    "do NOT invent any others. Note the types after colon — use CAST when comparing different types):\n"
                    + "\n".join(catalog_lines_all)
                )
    except Exception:
        pass  # If catalog fetch fails, proceed without — Claude will use dependency values

    prompt = f"""Generate Athena-compatible data flow test cases for this pipeline:

Job Type: {req.job_config.type}
Job Path: {req.job_config.path}

Dependencies:
{deps_summary}
{catalog_context}

RULES:
1. ONLY use table names and column names listed in the ACTUAL GLUE CATALOG above.
2. DO NOT invent or guess any table or column names.
3. Use format: database.table_name for table references.
4. For Iceberg metadata: SELECT * FROM "database"."table_name$snapshots" (with double quotes).
5. All SQL must be Athena V3/Trino compatible.
6. Each test MUST include a user_story.
7. Focus tests on tables and databases that are actually referenced in the Dependencies above. Do NOT test unrelated tables."""

    try:
        response_text = invoke_claude(prompt, system_prompt=GENERATE_TESTS_SYSTEM)
        result = parse_json_response(response_text)

        # Inject the target database into test metadata for run-time use
        target_db = ATHENA_DATABASE
        # Try to detect database from dependencies (database.table format)
        for d in req.dependencies:
            val = d.get("value", "")
            if "." in val and not val.startswith("s3://") and not val.startswith("arn:"):
                target_db = val.split(".")[0]
                break

        # Also try to detect from the generated SQL itself (first FROM clause)
        for tc in result.get("test_cases", []):
            sql = tc.get("sql", "")
            # Look for FROM database.table pattern in the SQL
            import re
            from_match = re.search(r'\bFROM\s+(\w+)\.(\w+)', sql, re.IGNORECASE)
            if from_match:
                detected_db = from_match.group(1)
                # Verify it's an actual Glue database (not a keyword)
                if detected_db.lower() not in ('select', 'where', 'and', 'or', 'information_schema'):
                    target_db = detected_db
                    break

        for tc in result.get("test_cases", []):
            tc["target_database"] = target_db

        # Cache in S3
        try:
            session = get_boto_session()
            s3 = session.client("s3", verify=False)
            s3.put_object(
                Bucket=ATHENA_OUTPUT_BUCKET,
                Key=s3_key,
                Body=json.dumps(result).encode("utf-8"),
                ContentType="application/json",
            )
            print(f"  ✅ Cached tests to s3://{ATHENA_OUTPUT_BUCKET}/{s3_key}")
        except Exception as cache_err:
            print(f"  ⚠️ Failed to cache tests in S3: {cache_err}")

        return result
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Agent returned invalid JSON: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Test generation failed: {e}")


@app.post("/api/run-tests")
async def run_tests(req: RunTestsRequest):
    """
    Execute test SQL queries via Athena against real data.
    Each test case's SQL is run and the result is compared to expected.
    """
    results = []

    for tc in req.test_cases:
        sql = tc.get("sql", "")
        test_id = tc.get("id", f"TC-{uuid.uuid4().hex[:6].upper()}")
        test_name = tc.get("name", "Unknown test")
        expected = tc.get("expected", "")
        description = tc.get("user_story") or tc.get("description", "")

        if not sql.strip():
            results.append({
                "test_id": test_id,
                "test_name": test_name,
                "description": description,
                "status": "skipped",
                "actual": "No SQL provided",
                "expected": expected,
                "duration_ms": 0,
                "error_message": "Empty SQL query",
            })
            continue

        start_time = time.time()

        try:
            # Use test-specific database if available, else default
            test_db = tc.get("target_database", ATHENA_DATABASE)
            query_result = run_athena_query(sql, database=test_db)
            duration_ms = int((time.time() - start_time) * 1000)

            if "error" in query_result:
                results.append({
                    "test_id": test_id,
                    "test_name": test_name,
                    "description": description,
                    "status": "error",
                    "actual": query_result["error"],
                    "expected": expected,
                    "duration_ms": duration_ms,
                    "error_message": query_result["error"],
                })
            else:
                rows = query_result.get("rows", [])
                row_count = len(rows)

                actual_summary = f"{row_count} rows returned"
                if row_count > 0 and query_result.get("columns"):
                    first_row_values = list(rows[0].values())
                    actual_summary = f"{row_count} rows: {first_row_values}"

                status = determine_test_status(expected, rows, row_count)

                results.append({
                    "test_id": test_id,
                    "test_name": test_name,
                    "description": description,
                    "status": status,
                    "actual": actual_summary,
                    "expected": expected,
                    "duration_ms": duration_ms,
                })

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            results.append({
                "test_id": test_id,
                "test_name": test_name,
                "description": description,
                "status": "error",
                "actual": str(e),
                "expected": expected,
                "duration_ms": duration_ms,
                "error_message": str(e),
            })

    execution = {
        "id": uuid.uuid4().hex[:8],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": len(results),
        "passed": sum(1 for r in results if r["status"] == "passed"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "errors": sum(1 for r in results if r["status"] == "error"),
        "skipped": sum(1 for r in results if r["status"] == "skipped"),
        "results": results,
    }

    execution_history.insert(0, execution)
    return {"execution": execution}


def determine_test_status(expected: str, rows: list, row_count: int) -> str:
    """
    Determine if test passed based on expected description and actual results.
    Heuristic rules:
    - "Empty result set" / "0 rows" → pass if row_count == 0
    - "count = 0" / "null_count = 0" → pass if first value is "0"
    - "counts match" → pass if row_count == 0 (mismatch query returns diffs)
    - Otherwise: pass if row_count > 0 (query expected to return data)
    """
    expected_lower = expected.lower()

    # Tests that expect empty results (no violations found)
    if any(phrase in expected_lower for phrase in [
        "empty result", "0 rows", "no rows", "counts match", "all columns present",
        "all fks valid", "loaded within", "sums match"
    ]):
        return "passed" if row_count == 0 else "failed"

    # Tests that check a specific value equals 0
    if any(phrase in expected_lower for phrase in ["= 0", "count = 0", "null_count = 0"]):
        if row_count > 0 and rows:
            first_val = str(list(rows[0].values())[0]) if rows[0] else ""
            return "passed" if first_val == "0" else "failed"
        return "passed"  # No rows = nothing to check = pass

    # Default: if query returns data, test passes (e.g., schema validation)
    return "passed" if row_count > 0 else "failed"


@app.post("/api/query")
async def execute_query(req: QueryRequest):
    """
    Execute NLP or SQL query via Athena.
    NLP mode: Claude converts to SQL first, then runs on Athena.
    SQL mode: runs directly on Athena.
    """
    if req.mode == "nlp":
        prompt = f"""Convert this to Athena SQL:

Question: {req.input}

Available database: {ATHENA_DATABASE}
Generate executable Athena SQL."""

        try:
            response_text = invoke_claude(prompt, system_prompt=NLP_TO_SQL_SYSTEM)
            parsed = parse_json_response(response_text)
            generated_sql = parsed.get("generated_sql", req.input)
        except Exception:
            generated_sql = f"-- Could not convert NLP query\n-- Original: {req.input}"
    else:
        generated_sql = req.input

    # Execute via Athena
    start_time = time.time()
    try:
        result = run_athena_query(generated_sql)
        execution_time_ms = int((time.time() - start_time) * 1000)

        if "error" in result:
            return {
                "generated_sql": generated_sql,
                "columns": [],
                "rows": [],
                "row_count": 0,
                "execution_time_ms": execution_time_ms,
                "error": result["error"],
            }

        return {
            "generated_sql": generated_sql,
            "columns": result.get("columns", []),
            "rows": result.get("rows", []),
            "row_count": len(result.get("rows", [])),
            "execution_time_ms": execution_time_ms,
        }
    except Exception as e:
        return {
            "generated_sql": generated_sql,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "execution_time_ms": 0,
            "error": str(e),
        }


@app.get("/api/results")
async def get_results():
    return execution_history


@app.get("/api/results/{run_id}")
async def get_result_detail(run_id: str):
    for run in execution_history:
        if run["id"] == run_id:
            return run
    raise HTTPException(status_code=404, detail="Run not found")


@app.get("/api/discover-databases")
async def discover_databases():
    """
    List available Glue databases and their tables.
    Useful to discover Iceberg targets for KPI pipelines.
    """
    try:
        glue = get_glue_client()

        # List databases
        db_response = glue.get_databases()
        databases = []

        for db in db_response.get("DatabaseList", []):
            db_name = db["Name"]
            # Get tables for each database
            tables_response = glue.get_tables(DatabaseName=db_name, MaxResults=50)
            tables = []
            for tbl in tables_response.get("TableList", []):
                table_info = {
                    "name": tbl["Name"],
                    "location": tbl.get("StorageDescriptor", {}).get("Location", ""),
                    "table_type": tbl.get("Parameters", {}).get("table_type", tbl.get("TableType", "unknown")),
                    "columns": [
                        {"name": col["Name"], "type": col["Type"]}
                        for col in tbl.get("StorageDescriptor", {}).get("Columns", [])
                    ],
                }
                # Detect Iceberg tables
                params = tbl.get("Parameters", {})
                if params.get("table_type", "").lower() == "iceberg" or "iceberg" in tbl.get("StorageDescriptor", {}).get("Location", "").lower():
                    table_info["is_iceberg"] = True
                tables.append(table_info)

            databases.append({
                "name": db_name,
                "description": db.get("Description", ""),
                "location": db.get("LocationUri", ""),
                "tables": tables,
            })

        return {"databases": databases}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to discover databases: {e}")


@app.get("/api/discover-databases/{db_name}")
async def discover_database_tables(db_name: str):
    """Get detailed table info for a specific database."""
    try:
        glue = get_glue_client()
        tables_response = glue.get_tables(DatabaseName=db_name, MaxResults=100)
        tables = []
        for tbl in tables_response.get("TableList", []):
            params = tbl.get("Parameters", {})
            storage = tbl.get("StorageDescriptor", {})
            tables.append({
                "name": tbl["Name"],
                "location": storage.get("Location", ""),
                "table_type": params.get("table_type", tbl.get("TableType", "unknown")),
                "is_iceberg": params.get("table_type", "").lower() == "iceberg",
                "columns": [
                    {"name": col["Name"], "type": col["Type"]}
                    for col in storage.get("Columns", [])
                ],
                "partition_keys": [
                    {"name": pk["Name"], "type": pk["Type"]}
                    for pk in tbl.get("PartitionKeys", [])
                ],
                "record_count": params.get("recordCount", "unknown"),
            })

        return {"database": db_name, "tables": tables}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list tables for {db_name}: {e}")


@app.post("/api/analyze-failures")
async def analyze_failures(req: AnalyzeFailuresRequest):
    """
    Analyze test failures using the test_analyst_agent.
    Calls the existing lambda handler directly for root-cause classification.
    """
    if not req.failed_tests:
        return {"analyses": [], "summary": {"total_failures": 0, "false_positives": 0, "real_defects": 0}}

    try:
        # Transform frontend TestResult format → agent expected format
        agent_failures = []
        for ft in req.failed_tests:
            agent_failures.append({
                "test_id": ft.get("test_id", ""),
                "test_name": ft.get("test_name", ""),
                "component": ft.get("description", "data-pipeline"),
                "failure_reason": ft.get("error_message") or ft.get("actual", "Unknown failure"),
                "failure_type": "unknown",
                "evidence": {
                    "actual_result": ft.get("actual", ""),
                    "expected_result": ft.get("expected", ""),
                    "duration_ms": ft.get("duration_ms", 0),
                },
            })

        result = test_analyst_handler({
            "tenant_id": "frontend-user",
            "execution_id": req.execution_id,
            "failed_tests": agent_failures,
            "recent_changes": req.recent_changes,
            "run_history": [],
        }, None)

        return {
            "analyses": result.get("analyses", []),
            "summary": result.get("summary", {}),
            "requires_immediate_attention": result.get("requires_immediate_attention", []),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failure analysis failed: {e}")


# ─── Startup ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("  AetherTest Data Flow Testing — API Server")
    print("=" * 60)
    print(f"  AWS Profile:    {AWS_PROFILE}")
    print(f"  Region:         {AWS_REGION}")
    print(f"  Model:          {CLAUDE_MODEL_ID}")
    print(f"  Athena DB:      {ATHENA_DATABASE}")
    print(f"  Athena Output:  s3://{ATHENA_OUTPUT_BUCKET}/")
    print()
    print("  If SSO expired, run:")
    print(f"    aws sso login --profile {AWS_PROFILE}")
    print()
    print("  Endpoints:")
    print("    GET  /api/health          → Check AWS connection")
    print("    POST /api/analyze-job     → Analyze pipeline job (real SFN)")
    print("    POST /api/generate-tests  → Generate test cases (Claude)")
    print("    POST /api/run-tests       → Execute via Athena")
    print("    POST /api/query           → NLP/SQL via Athena")
    print("    GET  /api/results         → Execution history")
    print("    GET  /api/discover-databases → List Glue databases & tables")
    print("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=8001)
