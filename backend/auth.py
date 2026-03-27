import os
from google.oauth2 import id_token
from google.auth.transport import requests
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .database import get_db_connection

security = HTTPBearer()

def verify_admin_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    
    if os.environ.get("SKIP_AUTH") == "true":
        return {"email": "local-admin@example.com", "role": "superadmin"}
        
    if not client_id:
        raise HTTPException(status_code=500, detail="Server misconfiguration: GOOGLE_CLIENT_ID missing")
        
    try:
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), client_id)
        user_email = idinfo.get("email")
        
        # Check against the Postgres admins table to establish role
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            try:
                cur.execute("SELECT role FROM admins WHERE email = %s", (user_email,))
                result = cur.fetchone()
                if not result:
                    raise HTTPException(status_code=403, detail="Email not authorized.")
                
                idinfo["role"] = result[0]
            finally:
                cur.close()
        finally:
            conn.close()
            
        return idinfo
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Auth error: {e}")
