import os
from dotenv import load_dotenv

load_dotenv()

import pg8000
from google.cloud.sql.connector import Connector, IPTypes
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from .auth import verify_admin_token
from .database import get_db_connection

app = FastAPI(title="Workshop TA Admin Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class EventRequest(BaseModel):
    event_name: str
    start_date: str
    end_date: str
    language: str
    country: str
    courses: list[str]


class AdminRequest(BaseModel):
    email: str
    role: str

class CourseRequest(BaseModel):
    id: str
    name: str
    repo_url: str
    directory_root: str = '/'
    is_published: bool = True


@app.on_event("startup")
def startup_event():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            root_emails = [
                e.strip()
                for e in os.environ.get("ROOT_ADMIN_EMAILS", "").split(",")
                if e.strip()
            ]
            for email in root_emails:
                cur.execute(
                    """
                    INSERT INTO admins (email, role) VALUES (%s, %s)
                    ON CONFLICT (email) DO UPDATE SET role = EXCLUDED.role
                """,
                    (email, "superadmin"),
                )
            conn.commit()
            print(f"Bootstrapped {len(root_emails)} total superadmins based on .env")
        except Exception as e:
            conn.rollback()
            print(f"Skipping bootstrap (schema likely not applied yet): {e}")
        finally:
            cur.close()
            conn.close()
    except Exception as e:
        print(f"Startup logic bypassed: {e}")


@app.get("/api/config")
def get_config():
    return {"google_client_id": os.environ.get("GOOGLE_CLIENT_ID", "")}


@app.get("/api/admin/verify")
async def verify_auth(admin_info: dict = Depends(verify_admin_token)):
    return {"status": "success", "role": admin_info.get("role")}


@app.post("/api/admin/events")
async def create_event(
    request: EventRequest, admin_info: dict = Depends(verify_admin_token)
):
    user_email = admin_info.get("email", "unknown")
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        try:
            import secrets, string

            event_id = "".join(
                secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8)
            )

            # Insert into events metadata
            cur.execute(
                """
                INSERT INTO events (id, event_name, start_date, end_date, language, country, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
                (
                    event_id,
                    request.event_name,
                    request.start_date,
                    request.end_date,
                    request.language,
                    request.country,
                    user_email,
                ),
            )

            # Inject new mapping
            for course_id in request.courses:
                cur.execute(
                    "INSERT INTO event_courses (event_id, course_id) VALUES (%s, %s)",
                    (event_id, course_id),
                )

            conn.commit()
        finally:
            cur.close()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database insert failed: {str(e)}")
    finally:
        conn.close()

    return {
        "status": "success",
        "message": f"Event {request.event_name} successfully saved to Cloud SQL!",
    }


@app.get("/api/admin/events")
async def list_events(admin_info: dict = Depends(verify_admin_token)):
    user_email = admin_info.get("email", "unknown")
    is_root = admin_info.get("role") == "superadmin"

    conn = get_db_connection()
    events = []
    try:
        cur = conn.cursor()
        try:
            if is_root:
                cur.execute(
                    "SELECT e.id, e.event_name, e.start_date, e.end_date, e.language, e.country, e.created_by, COALESCE(rl.status, 'SCHEDULED') AS status FROM events e LEFT JOIN running_logs rl ON e.id = rl.event_id ORDER BY e.start_date DESC"
                )
            else:
                cur.execute(
                    "SELECT e.id, e.event_name, e.start_date, e.end_date, e.language, e.country, e.created_by, COALESCE(rl.status, 'SCHEDULED') AS status FROM events e LEFT JOIN running_logs rl ON e.id = rl.event_id WHERE e.created_by = %s ORDER BY e.start_date DESC",
                    (user_email,),
                )

            columns = [desc[0] for desc in cur.description]
            db_events = [dict(zip(columns, row)) for row in cur.fetchall()]

            for row in db_events:
                cur.execute(
                    "SELECT course_id FROM event_courses WHERE event_id = %s",
                    (row["id"],),
                )
                courses = [c[0] for c in cur.fetchall()]

                events.append(
                    {
                        "id": row["id"],
                        "event_name": row["event_name"],
                        "start_date": row["start_date"].strftime("%Y-%m-%d")
                        if getattr(row.get("start_date"), "strftime", None)
                        else str(row.get("start_date", "")),
                        "end_date": row["end_date"].strftime("%Y-%m-%d")
                        if getattr(row.get("end_date"), "strftime", None)
                        else str(row.get("end_date", "")),
                        "language": row["language"],
                        "country": row["country"],
                        "createdBy": row["created_by"],
                        "status": row["status"],
                        "courses": courses,
                    }
                )
        finally:
            cur.close()
    finally:
        conn.close()

    return events


@app.delete("/api/admin/events/{event_id}")
async def delete_event(event_id: str, admin_info: dict = Depends(verify_admin_token)):
    user_email = admin_info.get("email", "unknown")
    is_root = admin_info.get("role") == "superadmin"

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        try:
            if is_root:
                cur.execute("DELETE FROM events WHERE id = %s", (event_id,))
            else:
                cur.execute(
                    "DELETE FROM events WHERE id = %s AND created_by = %s",
                    (event_id, user_email),
                )

            if cur.rowcount == 0:
                raise HTTPException(
                    status_code=404, detail="Event not found or permission denied."
                )

            conn.commit()
        finally:
            cur.close()
    except Exception as e:
        conn.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

    return {"status": "success", "message": f"Event {event_id} successfully deleted!"}


@app.get("/api/workshops")
async def list_workshops(q: str = None, admin_info: dict = Depends(verify_admin_token)):
    conn = get_db_connection()
    workshops = []
    try:
        cur = conn.cursor()
        try:
            if not q or q == "*":
                cur.execute("SELECT id, name FROM courses WHERE is_published = TRUE ORDER BY id ASC")
            else:
                wildcard_q = f"%%{q}%%"
                cur.execute("SELECT id, name FROM courses WHERE is_published = TRUE AND (name ILIKE %s OR id ILIKE %s) ORDER BY id ASC LIMIT 50", (wildcard_q, wildcard_q))
                
            for row in cur.fetchall():
                workshops.append({"id": row[0], "name": row[1]})
        finally:
            cur.close()
    except Exception as e:
        print(f"Failed to fetch workshops: {e}")
        raise HTTPException(status_code=500, detail=f"Database fetch failed: {str(e)}")
    finally:
        conn.close()
    return workshops


@app.get("/api/admin/users")
async def list_users(admin_info: dict = Depends(verify_admin_token)):
    if admin_info.get("role") != "superadmin":
        raise HTTPException(
            status_code=403, detail="SuperAdmin clearance strictly required."
        )

    conn = get_db_connection()
    users = []
    try:
        cur = conn.cursor()
        try:
            cur.execute("SELECT email, role FROM admins ORDER BY role DESC, email ASC")
            for row in cur.fetchall():
                users.append({"email": row[0], "role": row[1]})
        finally:
            cur.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    return users


@app.post("/api/admin/users")
async def add_user(
    request: AdminRequest, admin_info: dict = Depends(verify_admin_token)
):
    if admin_info.get("role") != "superadmin":
        raise HTTPException(
            status_code=403, detail="SuperAdmin clearance strictly required."
        )

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO admins (email, role) VALUES (%s, %s)
                ON CONFLICT (email) DO UPDATE SET role = EXCLUDED.role
            """,
                (request.email, request.role),
            )
            conn.commit()
        finally:
            cur.close()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    return {"status": "success", "message": f"{request.email} added as {request.role}!"}


@app.delete("/api/admin/users/{user_email}")
async def delete_user(user_email: str, admin_info: dict = Depends(verify_admin_token)):
    if admin_info.get("role") != "superadmin":
        raise HTTPException(
            status_code=403, detail="SuperAdmin clearance strictly required."
        )

    if user_email == admin_info.get("email"):
        raise HTTPException(
            status_code=400, detail="SuperAdmins cannot delete themselves!"
        )

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM admins WHERE email = %s", (user_email,))
            conn.commit()
        finally:
            cur.close()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    return {"status": "success", "message": f"Revoked access for {user_email}."}


@app.get("/api/admin/courses")
async def list_admin_courses(q: str = None, admin_info: dict = Depends(verify_admin_token)):
    if admin_info.get("role") != "superadmin":
        raise HTTPException(status_code=403, detail="SuperAdmin clearance strictly required.")
    conn = get_db_connection()
    courses = []
    try:
        cur = conn.cursor()
        try:
            if not q or q == "*":
                cur.execute("SELECT id, name, repo_url, directory_root, is_published FROM courses ORDER BY name ASC")
            else:
                wildcard_q = f"%%{q}%%"
                cur.execute("SELECT id, name, repo_url, directory_root, is_published FROM courses WHERE name ILIKE %s OR id ILIKE %s ORDER BY name ASC LIMIT 50", (wildcard_q, wildcard_q))
                
            for row in cur.fetchall():
                courses.append({
                    "id": row[0], "name": row[1], "repo_url": row[2], 
                    "directory_root": row[3], "is_published": row[4]
                })
        finally:
            cur.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    return courses

@app.post("/api/admin/courses")
async def create_course(req: CourseRequest, admin_info: dict = Depends(verify_admin_token)):
    if admin_info.get("role") != "superadmin":
        raise HTTPException(status_code=403, detail="SuperAdmin clearance strictly required.")
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO courses (id, name, repo_url, directory_root, is_published) 
                VALUES (%s, %s, %s, %s, %s)
            """, (req.id, req.name, req.repo_url, req.directory_root, req.is_published))
            conn.commit()
        finally:
            cur.close()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create course. Does ID already exist? ({str(e)})")
    finally:
        conn.close()
    return {"status": "success", "message": f"Course {req.id} created!"}

@app.put("/api/admin/courses/{course_id}")
async def update_course(course_id: str, req: CourseRequest, admin_info: dict = Depends(verify_admin_token)):
    if admin_info.get("role") != "superadmin":
        raise HTTPException(status_code=403, detail="SuperAdmin clearance strictly required.")
    if req.id != course_id:
        raise HTTPException(status_code=400, detail="Cannot modify Course Primary Key IDs directly.")
        
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute("""
                UPDATE courses SET name = %s, repo_url = %s, directory_root = %s, is_published = %s
                WHERE id = %s
            """, (req.name, req.repo_url, req.directory_root, req.is_published, course_id))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Course not found.")
            conn.commit()
        finally:
            cur.close()
    except Exception as e:
        conn.rollback()
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    return {"status": "success", "message": f"Course {course_id} updated!"}

@app.delete("/api/admin/courses/{course_id}")
async def admin_delete_course(course_id: str, admin_info: dict = Depends(verify_admin_token)):
    if admin_info.get("role") != "superadmin":
        raise HTTPException(status_code=403, detail="SuperAdmin clearance strictly required.")
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM courses WHERE id = %s", (course_id,))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Course not found.")
            conn.commit()
        finally:
            cur.close()
    except Exception as e:
        conn.rollback()
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=f"Error deleting course (might be linked to active events?): {str(e)}")
    finally:
        conn.close()
    return {"status": "success", "message": f"Course {course_id} cleanly deleted!"}

@app.get("/api/admin/logs")
async def admin_get_logs(
    event_id: str = None, 
    event_name: str = None,
    status: str = None,
    sort_by: str = "scheduled_start_date",
    date_filter_type: str = "scheduled_start",
    date_min: str = None,
    date_max: str = None,
    admin_info: dict = Depends(verify_admin_token)
):
    if admin_info.get("role") not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Admin clearance strictly required.")
    
    conn = get_db_connection()
    logs = []
    try:
        cur = conn.cursor()
        try:
            query_base = "SELECT event_id, event_name, cloud_run_service_name, cloud_run_url, scheduled_start_date, scheduled_end_date, actual_datetime_started, actual_datetime_ended, status FROM running_logs WHERE 1=1"
            params = []
            
            if event_id:
                query_base += " AND event_id = %s"
                params.append(event_id)
                
            if event_name:
                query_base += " AND event_name ILIKE %s"
                params.append(f"%{event_name}%")
                
            if status:
                query_base += " AND status = %s"
                params.append(status)
                
            if date_min and date_max:
                if date_filter_type == "scheduled_start":
                    query_base += " AND scheduled_start_date >= %s AND scheduled_start_date <= %s"
                    params.extend([date_min, date_max])
                elif date_filter_type == "scheduled_end":
                    query_base += " AND scheduled_end_date >= %s AND scheduled_end_date <= %s"
                    params.extend([date_min, date_max])
                elif date_filter_type == "actual_start":
                    query_base += " AND DATE(actual_datetime_started) >= %s AND DATE(actual_datetime_started) <= %s"
                    params.extend([date_min, date_max])
                elif date_filter_type == "actual_end":
                    query_base += " AND DATE(actual_datetime_ended) >= %s AND DATE(actual_datetime_ended) <= %s"
                    params.extend([date_min, date_max])
                
            allowed_sort = ["event_id", "event_name", "scheduled_start_date", "scheduled_end_date", "actual_datetime_started", "actual_datetime_ended", "status"]
            if sort_by not in allowed_sort:
                sort_by = "scheduled_start_date"
                
            query_base += f" ORDER BY {sort_by} DESC"
            
            cur.execute(query_base, tuple(params))
            for row in cur.fetchall():
                logs.append({
                    "event_id": row[0],
                    "event_name": row[1],
                    "cloud_run_service_name": row[2],
                    "cloud_run_url": row[3],
                    "scheduled_start_date": row[4].strftime("%Y-%m-%d") if row[4] else None,
                    "scheduled_end_date": row[5].strftime("%Y-%m-%d") if row[5] else None,
                    "actual_datetime_started": row[6].isoformat() if row[6] else None,
                    "actual_datetime_ended": row[7].isoformat() if row[7] else None,
                    "status": row[8]
                })
        finally:
            cur.close()
    except Exception as e:
        print(f"Error fetching logs natively: {e}")
        raise HTTPException(status_code=500, detail="Database fetch execution aborted.")
    finally:
        conn.close()
        
    return logs

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
