import os
import pg8000
from google.cloud.sql.connector import Connector, IPTypes
from fastapi import HTTPException
from google.cloud import secretmanager

# Optional fallback: load from Secret Manager natively if not already passed via .env variables
if not os.environ.get("CLOUD_SQL_CONNECTION_NAME"):
    try:
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
        client = secretmanager.SecretManagerServiceClient()
        secret_name = (
            f"projects/{project_id}/secrets/events-db-credentials/versions/latest"
        )
        response = client.access_secret_version(request={"name": secret_name})
        secret_payload = response.payload.data.decode("utf-8")

        for line in secret_payload.strip().split("\n"):
            if line.startswith("export "):
                line = line[7:].strip()
                if "=" in line:
                    key, val = line.split("=", 1)
                    val = val.strip(" '\"")
                    os.environ[key] = val
        print("Loaded DB credentials from Secret Manager natively.")
    except Exception as e:
        print(f"Secret Manager auto-load skipped or failed: {e}")

connector = None


def get_db_connection():
    global connector
    if connector is None:
        connector = Connector()

    conn_name = os.environ.get("CLOUD_SQL_CONNECTION_NAME")
    if not conn_name:
        raise HTTPException(
            status_code=500,
            detail="Missing CLOUD_SQL_CONNECTION_NAME structurally locally in .env AND Secret Manager failed.",
        )

    try:
        conn = connector.connect(
            conn_name,
            "pg8000",
            user=os.environ.get("DB_USER", ""),
            password=os.environ.get("DB_PASS", ""),
            db=os.environ.get("DB_NAME", ""),
            ip_type=IPTypes.PUBLIC,
        )
        return conn
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Cloud SQL Tunnel failed: {str(e)}"
        )
