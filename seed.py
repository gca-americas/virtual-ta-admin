import os
import sys

# Map standard PROJECT_ID to python GOOGLE_CLOUD_PROJECT string naturally if available
if os.environ.get("PROJECT_ID") and not os.environ.get("GOOGLE_CLOUD_PROJECT"):
    os.environ["GOOGLE_CLOUD_PROJECT"] = os.environ["PROJECT_ID"]

# Ensure backend module is available
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.database import get_db_connection


def seed_database():
    print("Initiating direct Python Cloud SQL tunnel...")

    try:
        # 1. Connect using our secure IAM tunnel natively
        conn = get_db_connection()
        conn.autocommit = True
        cur = conn.cursor()

        # 2. Read the schema file natively
        schema_path = os.path.join(os.path.dirname(__file__), "backend", "schema.sql")
        with open(schema_path, "r") as f:
            schema_sql = f.read()

        print("Executing schema natively...")

        # 3. Execute the SQL blocks linearly
        cur.execute(schema_sql)

        cur.close()
        conn.close()
        print("✅ Database cleanly initialized bypassing gcloud auth proxy!")

    except Exception as e:
        print(f"❌ Python Injection failed: {str(e)}")


if __name__ == "__main__":
    seed_database()
