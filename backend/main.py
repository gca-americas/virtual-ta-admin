from backend.database import get_db_connection
import os
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from .auth import verify_admin_token
import urllib.request
from urllib.error import HTTPError
from urllib.parse import urlparse

load_dotenv()
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
    directory_root: str = "/"
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
async def list_events(
    limit: int = 50,
    offset: int = 0,
    status: str = None,
    start_date: str = None,
    end_date: str = None,
    creator_email: str = None,
    admin_info: dict = Depends(verify_admin_token)
):
    user_email = admin_info.get("email", "unknown")
    is_root = admin_info.get("role") == "superadmin"

    conn = get_db_connection()
    events = []
    try:
        cur = conn.cursor()
        try:
            query = """
                SELECT e.id, e.event_name, e.start_date, e.end_date, e.language, e.country, e.created_by, 
                       COALESCE(rl.status, 'SCHEDULED') AS status,
                       STRING_AGG(ec.course_id, ',') AS courses
                FROM events e 
                LEFT JOIN running_logs rl ON e.id = rl.event_id 
                LEFT JOIN event_courses ec ON e.id = ec.event_id
            """

            conditions = []
            params = []

            if not is_root:
                conditions.append("e.created_by = %s")
                params.append(user_email)
            elif creator_email:
                conditions.append("e.created_by ILIKE %s")
                params.append(f"%{creator_email}%")

            if start_date:
                conditions.append("e.start_date >= %s")
                params.append(start_date)

            if end_date:
                conditions.append("e.end_date <= %s")
                params.append(end_date)

            if status:
                status_list = [s.strip() for s in status.split(',')]
                status_conds = []
                for s in status_list:
                    if s == "SCHEDULED":
                        status_conds.append("rl.status IS NULL")
                    else:
                        status_conds.append("rl.status = %s")
                        params.append(s)
                if status_conds:
                    conditions.append(f"({' OR '.join(status_conds)})")

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " GROUP BY e.id, rl.status ORDER BY e.start_date DESC LIMIT %s OFFSET %s"
            params.extend([limit, offset])

            cur.execute(query, params)
            columns = [desc[0] for desc in cur.description]
            db_events = [dict(zip(columns, row)) for row in cur.fetchall()]

            for row in db_events:
                courses_list = row["courses"].split(',') if row["courses"] else []
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
                        "courses": courses_list,
                    }
                )
        finally:
            cur.close()
    finally:
        conn.close()

    return events


@app.get("/api/admin/events/export")
async def export_events(
    status: str = None,
    start_date: str = None,
    end_date: str = None,
    creator_email: str = None,
    admin_info: dict = Depends(verify_admin_token)
):
    user_email = admin_info.get("email", "unknown")
    is_root = admin_info.get("role") == "superadmin"

    conn = get_db_connection()
    events = []
    try:
        cur = conn.cursor()
        try:
            query = """
                SELECT e.id, e.event_name, e.start_date, e.end_date, e.language, e.country, e.created_by, 
                       COALESCE(rl.status, 'SCHEDULED') AS status,
                       STRING_AGG(ec.course_id, ',') AS courses
                FROM events e 
                LEFT JOIN running_logs rl ON e.id = rl.event_id 
                LEFT JOIN event_courses ec ON e.id = ec.event_id
            """

            conditions = []
            params = []

            if not is_root:
                conditions.append("e.created_by = %s")
                params.append(user_email)
                
                # Natively restrict Non-SuperAdmins strictly to the last 6 months mathematically!
                import datetime
                six_months_ago = datetime.datetime.now() - datetime.timedelta(days=180)
                conditions.append("e.start_date >= %s")
                params.append(six_months_ago.strftime("%Y-%m-%d"))
            elif creator_email:
                conditions.append("e.created_by ILIKE %s")
                params.append(f"%{creator_email}%")

            if start_date:
                conditions.append("e.start_date >= %s")
                params.append(start_date)

            if end_date:
                conditions.append("e.end_date <= %s")
                params.append(end_date)

            if status:
                status_list = [s.strip() for s in status.split(',')]
                status_conds = []
                for s in status_list:
                    if s == "SCHEDULED":
                        status_conds.append("rl.status IS NULL")
                    else:
                        status_conds.append("rl.status = %s")
                        params.append(s)
                if status_conds:
                    conditions.append(f"({' OR '.join(status_conds)})")

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " GROUP BY e.id, rl.status ORDER BY e.start_date DESC"

            cur.execute(query, params)
            columns = [desc[0] for desc in cur.description]
            db_events = [dict(zip(columns, row)) for row in cur.fetchall()]

            for row in db_events:
                courses_list = row["courses"].split(',') if row["courses"] else []
                events.append(
                    {
                        "id": row["id"],
                        "event_name": row["event_name"],
                        "start_date": row["start_date"].strftime("%Y-%m-%d") if getattr(row.get("start_date"), "strftime", None) else str(row.get("start_date", "")),
                        "end_date": row["end_date"].strftime("%Y-%m-%d") if getattr(row.get("end_date"), "strftime", None) else str(row.get("end_date", "")),
                        "language": row["language"],
                        "country": row["country"],
                        "createdBy": row["created_by"],
                        "status": row["status"],
                        "courses": courses_list,
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
                cur.execute(
                    "SELECT id, name FROM courses WHERE is_published = TRUE ORDER BY id ASC"
                )
            else:
                wildcard_q = f"%%{q}%%"
                cur.execute(
                    "SELECT id, name FROM courses WHERE is_published = TRUE AND (name ILIKE %s OR id ILIKE %s) ORDER BY id ASC LIMIT 50",
                    (wildcard_q, wildcard_q),
                )

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
async def list_admin_courses(
    q: str = None, admin_info: dict = Depends(verify_admin_token)
):
    if admin_info.get("role") != "superadmin":
        raise HTTPException(
            status_code=403, detail="SuperAdmin clearance strictly required."
        )
    conn = get_db_connection()
    courses = []
    try:
        cur = conn.cursor()
        try:
            sql_base = """
                SELECT c.id, c.name, c.repo_url, c.directory_root, c.is_published, 
                       es.eval_date_time as last_eval_date, es.score as eval_score, 
                       c.last_update_date
                FROM courses c
                LEFT JOIN LATERAL (
                    SELECT score, eval_date_time 
                    FROM eval_suggestion 
                    WHERE course_id = c.id 
                    ORDER BY eval_date_time DESC 
                    LIMIT 1
                ) es ON true
            """

            if not q or q == "*":
                cur.execute(f"{sql_base} ORDER BY c.name ASC")
            else:
                wildcard_q = f"%%{q}%%"
                cur.execute(
                    f"{sql_base} WHERE c.name ILIKE %s OR c.id ILIKE %s ORDER BY c.name ASC LIMIT 50",
                    (wildcard_q, wildcard_q),
                )

            for row in cur.fetchall():
                courses.append(
                    {
                        "id": row[0],
                        "name": row[1],
                        "repo_url": row[2],
                        "directory_root": row[3],
                        "is_published": row[4],
                        "last_eval_date": row[5].strftime("%Y-%m-%d %H:%M:%S") if row[5] else None,
                        "eval_score": row[6],
                        "last_update_date": row[7].strftime("%Y-%m-%d %H:%M:%S") if row[7] else None,
                    }
                )
        finally:
            cur.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    return courses


def validate_github_repo_sync(repo_url: str, directory_root: str):
    repo_url = repo_url.strip()
    if repo_url.endswith(".git"):
        repo_url = repo_url[:-4]

    parsed = urlparse(repo_url)
    if parsed.netloc != "github.com":
        return False, "Repository URL must be a valid github.com HTTP URL."

    path_parts = [p for p in parsed.path.split("/") if p]
    if len(path_parts) < 2:
        return False, "Invalid GitHub repository URL format."

    owner, repo = path_parts[0], path_parts[1]

    clean_dir = directory_root.strip("/")
    raw_path = f"{clean_dir}/SKILL.md" if clean_dir else "SKILL.md"

    url_main = f"https://raw.githubusercontent.com/{owner}/{repo}/main/{raw_path}"
    url_master = f"https://raw.githubusercontent.com/{owner}/{repo}/master/{raw_path}"

    # 1. Verify repo actually exists & is Public
    repo_check_url = f"https://github.com/{owner}/{repo}"
    try:
        req = urllib.request.Request(repo_check_url, method="HEAD")
        urllib.request.urlopen(req, timeout=5)
    except HTTPError as e:
        if e.code == 404:
            return (
                False,
                f"Repository '{owner}/{repo}' does not exist or is currently Private.",
            )
        return False, f"Failed to verify repository: HTTP {e.code}"
    except Exception as e:
        return False, f"Network error evaluating repository: {str(e)}"

    # 2. Check if SKILL.md fundamentally exists inside the specified directory
    try:
        req_m = urllib.request.Request(url_main, method="HEAD")
        urllib.request.urlopen(req_m, timeout=5)
        return True, ""
    except Exception:
        pass

    try:
        req_ma = urllib.request.Request(url_master, method="HEAD")
        urllib.request.urlopen(req_ma, timeout=5)
        return True, ""
    except Exception:
        path_str = f"/{clean_dir}/" if clean_dir else "/"
        return (
            False,
            f"Repository is public, but 'SKILL.md' was mathematically NOT FOUND inside directory root '{path_str}' on 'main' or 'master' branches.",
        )


@app.post("/api/admin/courses")
async def create_course(
    req: CourseRequest, admin_info: dict = Depends(verify_admin_token)
):
    if admin_info.get("role") != "superadmin":
        raise HTTPException(
            status_code=403, detail="SuperAdmin clearance strictly required."
        )

    # Dynamic GitHub Validation logic explicitly injected
    is_valid, err_msg = validate_github_repo_sync(req.repo_url, req.directory_root)
    if not is_valid:
        raise HTTPException(status_code=400, detail=err_msg)

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO courses (id, name, repo_url, directory_root, is_published) 
                VALUES (%s, %s, %s, %s, %s)
            """,
                (req.id, req.name, req.repo_url, req.directory_root, req.is_published),
            )
            conn.commit()
        finally:
            cur.close()
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create course. Does ID already exist? ({str(e)})",
        )
    finally:
        conn.close()
    return {"status": "success", "message": f"Course {req.id} created!"}


@app.put("/api/admin/courses/{course_id}")
async def update_course(
    course_id: str, req: CourseRequest, admin_info: dict = Depends(verify_admin_token)
):
    if admin_info.get("role") != "superadmin":
        raise HTTPException(
            status_code=403, detail="SuperAdmin clearance strictly required."
        )
    if req.id != course_id:
        raise HTTPException(
            status_code=400, detail="Cannot modify Course Primary Key IDs directly."
        )

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                UPDATE courses SET name = %s, repo_url = %s, directory_root = %s, is_published = %s, last_update_date = CURRENT_TIMESTAMP
                WHERE id = %s
            """,
                (
                    req.name,
                    req.repo_url,
                    req.directory_root,
                    req.is_published,
                    course_id,
                ),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Course not found.")
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
    return {"status": "success", "message": f"Course {course_id} updated!"}


@app.delete("/api/admin/courses/{course_id}")
async def admin_delete_course(
    course_id: str, admin_info: dict = Depends(verify_admin_token)
):
    if admin_info.get("role") != "superadmin":
        raise HTTPException(
            status_code=403, detail="SuperAdmin clearance strictly required."
        )
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
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting course (might be linked to active events?): {str(e)}",
        )
    finally:
        conn.close()
    return {"status": "success", "message": f"Course {course_id} cleanly deleted!"}


@app.get("/api/admin/logs")
async def admin_get_logs(
    limit: int = 50,
    offset: int = 0,
    event_id: str = None,
    event_name: str = None,
    status: str = None,
    sort_by: str = "scheduled_start_date",
    date_filter_type: str = "scheduled_start",
    date_min: str = None,
    date_max: str = None,
    admin_info: dict = Depends(verify_admin_token),
):
    if admin_info.get("role") not in ["admin", "superadmin"]:
        raise HTTPException(
            status_code=403, detail="Admin clearance strictly required."
        )

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
                    query_base += (
                        " AND scheduled_start_date >= %s AND scheduled_start_date <= %s"
                    )
                    params.extend([date_min, date_max])
                elif date_filter_type == "scheduled_end":
                    query_base += (
                        " AND scheduled_end_date >= %s AND scheduled_end_date <= %s"
                    )
                    params.extend([date_min, date_max])
                elif date_filter_type == "actual_start":
                    query_base += " AND DATE(actual_datetime_started) >= %s AND DATE(actual_datetime_started) <= %s"
                    params.extend([date_min, date_max])
                elif date_filter_type == "actual_end":
                    query_base += " AND DATE(actual_datetime_ended) >= %s AND DATE(actual_datetime_ended) <= %s"
                    params.extend([date_min, date_max])

            allowed_sort = [
                "event_id",
                "event_name",
                "scheduled_start_date",
                "scheduled_end_date",
                "actual_datetime_started",
                "actual_datetime_ended",
                "status",
            ]
            if sort_by not in allowed_sort:
                sort_by = "scheduled_start_date"

            query_base += f" ORDER BY {sort_by} DESC LIMIT %s OFFSET %s"
            params.extend([limit, offset])

            cur.execute(query_base, tuple(params))
            for row in cur.fetchall():
                logs.append(
                    {
                        "event_id": row[0],
                        "event_name": row[1],
                        "cloud_run_service_name": row[2],
                        "cloud_run_url": row[3],
                        "scheduled_start_date": row[4].strftime("%Y-%m-%d")
                        if row[4]
                        else None,
                        "scheduled_end_date": row[5].strftime("%Y-%m-%d")
                        if row[5]
                        else None,
                        "actual_datetime_started": row[6].isoformat()
                        if row[6]
                        else None,
                        "actual_datetime_ended": row[7].isoformat() if row[7] else None,
                        "status": row[8],
                    }
                )
        finally:
            cur.close()
    except Exception as e:
        print(f"Error fetching logs natively: {e}")
        raise HTTPException(status_code=500, detail="Database fetch execution aborted.")
    finally:
        conn.close()

    return logs


@app.get("/api/admin/logs/export")
async def admin_export_logs(
    event_id: str = None,
    event_name: str = None,
    status: str = None,
    sort_by: str = "scheduled_start_date",
    date_filter_type: str = "scheduled_start",
    date_min: str = None,
    date_max: str = None,
    admin_info: dict = Depends(verify_admin_token),
):
    if admin_info.get("role") not in ["admin", "superadmin"]:
        raise HTTPException(
            status_code=403, detail="Admin clearance strictly required."
        )

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
                    query_base += (
                        " AND scheduled_start_date >= %s AND scheduled_start_date <= %s"
                    )
                    params.extend([date_min, date_max])
                elif date_filter_type == "scheduled_end":
                    query_base += (
                        " AND scheduled_end_date >= %s AND scheduled_end_date <= %s"
                    )
                    params.extend([date_min, date_max])
                elif date_filter_type == "actual_start":
                    query_base += " AND DATE(actual_datetime_started) >= %s AND DATE(actual_datetime_started) <= %s"
                    params.extend([date_min, date_max])
                elif date_filter_type == "actual_end":
                    query_base += " AND DATE(actual_datetime_ended) >= %s AND DATE(actual_datetime_ended) <= %s"
                    params.extend([date_min, date_max])

            allowed_sort = [
                "event_id",
                "event_name",
                "scheduled_start_date",
                "scheduled_end_date",
                "actual_datetime_started",
                "actual_datetime_ended",
                "status",
            ]
            if sort_by not in allowed_sort:
                sort_by = "scheduled_start_date"

            query_base += f" ORDER BY {sort_by} DESC"

            cur.execute(query_base, tuple(params))
            for row in cur.fetchall():
                logs.append(
                    {
                        "event_id": row[0],
                        "event_name": row[1],
                        "cloud_run_service_name": row[2],
                        "cloud_run_url": row[3],
                        "scheduled_start_date": row[4].strftime("%Y-%m-%d")
                        if row[4]
                        else None,
                        "scheduled_end_date": row[5].strftime("%Y-%m-%d")
                        if row[5]
                        else None,
                        "actual_datetime_started": row[6].isoformat()
                        if row[6]
                        else None,
                        "actual_datetime_ended": row[7].isoformat() if row[7] else None,
                        "status": row[8],
                    }
                )
        finally:
            cur.close()
    except Exception as e:
        print(f"Error fetching logs natively: {e}")
        raise HTTPException(status_code=500, detail="Database fetch execution aborted.")
    finally:
        conn.close()

    return logs


@app.get("/api/admin/eval_suggestions")
async def get_eval_suggestions(
    course_id: str,
    admin_info: dict = Depends(verify_admin_token)
):
    if admin_info.get("role") not in ["admin", "superadmin"]:
        raise HTTPException(
            status_code=403, detail="Admin clearance strictly required."
        )

    conn = get_db_connection()
    suggestions = []
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT id, course_id, eval_date_time, score, suggest_update
                FROM eval_suggestion
                WHERE course_id = %s
                ORDER BY eval_date_time DESC
                LIMIT 20
                """,
                (course_id,)
            )
            for row in cur.fetchall():
                suggestions.append({
                    "id": row[0],
                    "course_id": row[1],
                    "eval_date_time": row[2].isoformat() if row[2] else None,
                    "score": row[3],
                    "suggest_update": row[4]
                })
        finally:
            cur.close()
    except Exception as e:
        print(f"Failed to fetch eval suggestions: {e}")
        raise HTTPException(status_code=500, detail="Database fetch failed.")
    finally:
        conn.close()
        
    return suggestions


@app.get("/api/admin/eval_logs")
async def get_eval_logs(
    course_id: str,
    eval_date_time: str,
    admin_info: dict = Depends(verify_admin_token)
):
    if admin_info.get("role") not in ["admin", "superadmin"]:
        raise HTTPException(
            status_code=403, detail="Admin clearance strictly required."
        )

    conn = get_db_connection()
    logs = []
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT id, event_id, course_id, eval_date_time, level, question_number, question, prefer_answer, ta_answer
                FROM eval_log
                WHERE course_id = %s AND eval_date_time = %s
                ORDER BY question_number ASC
                """,
                (course_id, eval_date_time)
            )
            for row in cur.fetchall():
                logs.append({
                    "id": row[0],
                    "event_id": row[1],
                    "course_id": row[2],
                    "eval_date_time": row[3].isoformat() if row[3] else None,
                    "level": row[4],
                    "question_number": row[5],
                    "question": row[6],
                    "prefer_answer": row[7],
                    "ta_answer": row[8]
                })
        finally:
            cur.close()
    except Exception as e:
        print(f"Failed to fetch eval logs: {e}")
        raise HTTPException(status_code=500, detail="Database fetch failed.")
    finally:
        conn.close()

    return logs


app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
