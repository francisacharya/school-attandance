import sys
import os
from pathlib import Path

# Add project root to sys.path to import db and core
_root = Path(__file__).resolve().parent.parent
sys.path.append(str(_root))

from fastapi import FastAPI, Depends, HTTPException, status, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from jose import JWTError, jwt
from passlib.context import CryptContext

from db.database import get_connection, verify_password, init_database
from core.auth import authenticate, UserSession
from core import services

# Configuration
SECRET_KEY = "your-secret-key-change-this-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # 1 day

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    yield

app = FastAPI(title="Attendance System API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    full_name: str
    user_id: int

class TokenData(BaseModel):
    username: Optional[str] = None

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    
    conn = get_connection()
    try:
        user = conn.execute("SELECT * FROM users WHERE username = ?", (token_data.username,)).fetchone()
        if user is None:
            raise credentials_exception
        return dict(user)
    finally:
        conn.close()


@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    session = authenticate(form_data.username, form_data.password)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": session.username, "role": session.role}, expires_delta=access_token_expires
    )
    return {
        "access_token": access_token, 
        "token_type": "bearer", 
        "role": session.role, 
        "full_name": session.full_name,
        "user_id": session.user_id
    }

@app.get("/me")
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return current_user

# Admin Endpoints
@app.get("/admin/stats")
async def get_admin_stats(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    conn = get_connection()
    try:
        return services.admin_stats(conn)
    finally:
        conn.close()

# --- Admin & User Management ---

@app.get("/admin/users/all")
async def api_get_all_users(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    conn = get_connection()
    try:
        rows = conn.execute("SELECT id, username, role, full_name, email FROM users ORDER BY role, username").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@app.post("/admin/users")
async def api_add_user(data: dict, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    from db.database import hash_password_new
    ph, salt = hash_password_new(data["password"])
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, salt, role, full_name, email, phone) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (data["username"], ph, salt, data["role"], data["full_name"], data.get("email", ""), data.get("phone", ""))
        )
        uid = cur.lastrowid
        if data["role"] == "student":
            code = f"STU-{uid}"
            conn.execute("INSERT INTO students (user_id, student_code) VALUES (?, ?)", (uid, code))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(400, str(e))
    finally:
        conn.close()
    return {"status": "ok"}

@app.delete("/admin/users/{uid}")
async def api_delete_user(uid: int, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    conn = get_connection()
    try:
        conn.execute("DELETE FROM users WHERE id = ?", (uid,))
        conn.commit()
    finally:
        conn.close()
    return {"status": "ok"}

@app.put("/admin/users/{uid}")
async def api_update_user(uid: int, data: dict, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    conn = get_connection()
    try:
        # Check if user exists
        user = conn.execute("SELECT role FROM users WHERE id = ?", (uid,)).fetchone()
        if not user:
            raise HTTPException(404, "User not found")
        
        old_role = user["role"]
        
        # Build update query
        fields = ["username = ?", "full_name = ?", "role = ?", "email = ?", "phone = ?"]
        params = [data["username"], data["full_name"], data["role"], data.get("email", ""), data.get("phone", "")]
        
        if data.get("password"):
            from db.database import hash_password_new
            ph, salt = hash_password_new(data["password"])
            fields.extend(["password_hash = ?", "salt = ?"])
            params.extend([ph, salt])
            
        params.append(uid)
        conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", params)
        
        # Role change management: user -> student
        if data["role"] == "student" and old_role != "student":
            code = f"STU-{uid}"
            conn.execute("INSERT OR IGNORE INTO students (user_id, student_code) VALUES (?, ?)", (uid, code))
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(400, str(e))
    finally:
        conn.close()
    return {"status": "ok"}

@app.get("/students")
async def api_get_students(current_user: dict = Depends(get_current_user)):
    conn = get_connection()
    try:
        rows = conn.execute("""SELECT u.id, u.full_name, s.student_code 
                               FROM users u JOIN students s ON u.id = s.user_id 
                               WHERE u.role = 'student'""").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

# --- Timetable Management ---

@app.get("/admin/timetable/all")
async def api_get_all_timetable(
    session_id: int = None, course_id: int = None, semester_id: int = None, 
    teacher_id: int = None, is_archived: int = 0,
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    query = """SELECT t.id, 
                      t.session_id, sy.label AS session, 
                      t.course_id, c.name AS course, 
                      t.semester_id, sem.name AS semester, 
                      t.subject_id, sub.name AS subject, 
                      t.teacher_user_id, u.full_name AS teacher, 
                      t.room_id, r.name AS room, 
                      t.day_of_week, 
                      t.period_id, p.label AS period, p.start_time || ' - ' || p.end_time AS time,
                      t.is_archived
               FROM timetable t
               JOIN session_years sy ON sy.id = t.session_id
               JOIN courses c ON c.id = t.course_id
               JOIN semesters sem ON sem.id = t.semester_id
               JOIN subjects sub ON sub.id = t.subject_id
               JOIN users u ON u.id = t.teacher_user_id
               LEFT JOIN rooms r ON r.id = t.room_id
               JOIN periods p ON p.id = t.period_id
               WHERE (t.session_id = ? OR ? IS NULL)
                 AND (t.course_id = ? OR ? IS NULL)
                 AND (t.semester_id = ? OR ? IS NULL)
                 AND (t.teacher_user_id = ? OR ? IS NULL)
                 AND t.is_archived = ?
               ORDER BY t.day_of_week, p.sort_order"""
    conn = get_connection()
    try:
        rows = conn.execute(query, (session_id, session_id, course_id, course_id, semester_id, semester_id, teacher_id, teacher_id, is_archived)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@app.get("/admin/timetable/export/html")
async def api_export_timetable_html(session_id: int = None, course_id: int = None, semester_id: int = None, teacher_id: int = None, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    
    # Re-use the existing query logic but formatted for PDF
    query = """SELECT t.id, sy.label AS session, c.name AS course, sem.name AS semester, 
                      sub.name AS subject, u.full_name AS teacher, r.name AS room, 
                      t.day_of_week, p.label AS period, p.start_time || ' - ' || p.end_time AS time
               FROM timetable t
               JOIN session_years sy ON sy.id = t.session_id
               JOIN courses c ON c.id = t.course_id
               JOIN semesters sem ON sem.id = t.semester_id
               JOIN subjects sub ON sub.id = t.subject_id
               JOIN users u ON u.id = t.teacher_user_id
               LEFT JOIN rooms r ON r.id = t.room_id
               JOIN periods p ON p.id = t.period_id
               WHERE (t.session_id = ? OR ? IS NULL)
                 AND (t.course_id = ? OR ? IS NULL)
                 AND (t.semester_id = ? OR ? IS NULL)
                 AND (t.teacher_user_id = ? OR ? IS NULL)
               ORDER BY t.day_of_week, p.sort_order"""
    
    conn = get_connection()
    rows = conn.execute(query, (session_id, session_id, course_id, course_id, semester_id, semester_id, teacher_id, teacher_id)).fetchall()
    conn.close()

    days_map = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    html = """<html><head><style>
        body { font-family: 'Inter', sans-serif; padding: 40px; color: #1e293b; }
        h1 { color: #3b82f6; margin-bottom: 30px; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; }
        .day-section { margin-bottom: 40px; }
        .day-title { font-weight: bold; font-size: 18px; color: #64748b; margin-bottom: 15px; text-transform: uppercase; letter-spacing: 0.05em; }
        table { width: 100%; border-collapse: collapse; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        th { background: #f8fafc; color: #475569; text-align: left; padding: 12px 15px; border-bottom: 2px solid #e2e8f0; font-size: 12px; }
        td { padding: 12px 15px; border-bottom: 1px solid #f1f5f9; font-size: 13px; }
        tr:last-child td { border-bottom: none; }
        .time { font-family: monospace; color: #3b82f6; font-weight: 600; }
        .subject { font-weight: 700; color: #1e293b; }
    </style></head><body><h1>Academic Master Schedule</h1>"""

    for d_idx, day_name in enumerate(days_map):
        day_rows = [r for r in rows if r["day_of_week"] == d_idx]
        if not day_rows: continue
        
        html += f'<div class="day-section"><div class="day-title">{day_name}</div>'
        html += '<table><thead><tr><th>Time / Period</th><th>Subject</th><th>Teacher</th><th>Course / Sem</th><th>Room</th></tr></thead><tbody>'
        for r in day_rows:
            html += f'<tr><td class="time">{r["time"]}<br/><small style="color:#94a3b8">{r["period"]}</small></td>'
            html += f'<td class="subject">{r["subject"]}</td>'
            html += f'<td>{r["teacher"]}</td>'
            html += f'<td>{r["course"]}<br/><small style="color:#94a3b8">{r["semester"]}</small></td>'
            html += f'<td>{r["room"] or "N/A"}</td></tr>'
        html += '</tbody></table></div>'
    
    html += '</body></html>'
    return html

@app.post("/admin/timetable")
async def api_add_timetable_entry(data: dict, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    conn = get_connection()
    import sqlite3
    try:
        # Support both single day and multi-day inserts
        days = data.get("days", [data.get("day_of_week")])
        for dow in days:
            if dow is None: continue
            conn.execute("""INSERT INTO timetable (session_id, course_id, semester_id, subject_id, teacher_user_id, room_id, day_of_week, period_id)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                         (data["session_id"], data["course_id"], data["semester_id"], data["subject_id"], 
                          data["teacher_user_id"], data.get("room_id"), int(dow), data["period_id"]))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        raise HTTPException(400, "Conflict: This subject is already scheduled for one of the selected day/period slots.")
    except Exception as e:
        conn.rollback()
        raise HTTPException(400, str(e))
    finally:
        conn.close()
    return {"status": "ok"}

@app.put("/admin/timetable/{entry_id}")
async def api_update_timetable_entry(entry_id: int, data: dict, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    conn = get_connection()
    import sqlite3
    try:
        conn.execute("""UPDATE timetable SET session_id=?, course_id=?, semester_id=?, subject_id=?, teacher_user_id=?, room_id=?, day_of_week=?, period_id=?
                       WHERE id=?""",
                     (data["session_id"], data["course_id"], data["semester_id"], data["subject_id"], 
                      data["teacher_user_id"], data.get("room_id"), int(data["day_of_week"]), data["period_id"], entry_id))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        raise HTTPException(400, "Conflict: Slot occupied.")
    finally:
        conn.close()
    return {"status": "ok"}

@app.delete("/admin/timetable/{entry_id}")
async def api_delete_timetable_entry(entry_id: int, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    conn = get_connection()
    try:
        conn.execute("DELETE FROM timetable WHERE id=?", (entry_id,))
        conn.commit()
    finally:
        conn.close()
    return {"status": "ok"}

@app.put("/admin/timetable/{id}/archive")
async def api_archive_timetable(id: int, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    conn = get_connection()
    try:
        conn.execute("UPDATE timetable SET is_archived = 1 WHERE id = ?", (id,))
        conn.commit()
    finally:
        conn.close()
    return {"status": "ok"}

@app.put("/admin/timetable/{id}/unarchive")
async def api_unarchive_timetable(id: int, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    conn = get_connection()
    try:
        conn.execute("UPDATE timetable SET is_archived = 0 WHERE id = ?", (id,))
        conn.commit()
    finally:
        conn.close()
    return {"status": "ok"}

# --- Rules & Settings ---

@app.post("/admin/rules/geofence")
async def api_update_geofence(data: dict, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    conn = get_connection()
    try:
        conn.execute("INSERT OR REPLACE INTO geofence_settings (id, campus_lat, campus_lng, radius_meters, classroom_only) VALUES (1, ?, ?, ?, ?)",
                     (data["lat"], data["lng"], data["radius"], data["class_only"]))
        conn.commit()
    finally:
        conn.close()
    return {"status": "ok"}

@app.get("/admin/rules/sms")
async def api_get_sms_settings(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    from core.app_settings import KEY_TWILIO_ACCOUNT_SID, KEY_TWILIO_AUTH_TOKEN, KEY_TWILIO_FROM_NUMBER, KEY_TWILIO_ENABLED, get_setting
    return {
        "enabled": get_setting(KEY_TWILIO_ENABLED, "0") == "1",
        "sid": get_setting(KEY_TWILIO_ACCOUNT_SID, ""),
        "token": get_setting(KEY_TWILIO_AUTH_TOKEN, ""),
        "from_num": get_setting(KEY_TWILIO_FROM_NUMBER, "")
    }

@app.post("/admin/rules/sms")
async def api_update_sms_settings(data: dict, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    from core.app_settings import KEY_TWILIO_ACCOUNT_SID, KEY_TWILIO_AUTH_TOKEN, KEY_TWILIO_FROM_NUMBER, KEY_TWILIO_ENABLED, set_setting
    set_setting(KEY_TWILIO_ENABLED, "1" if data["enabled"] else "0")
    set_setting(KEY_TWILIO_ACCOUNT_SID, data["sid"])
    set_setting(KEY_TWILIO_AUTH_TOKEN, data["token"])
    set_setting(KEY_TWILIO_FROM_NUMBER, data["from_num"])
    return {"status": "ok"}

# --- Teacher & Student Portal ---

@app.get("/teacher/corrections")
async def api_get_corrections(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "teacher": raise HTTPException(403, "Teacher only")
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT c.id, ar.student_user_id AS student_id, ar.attendance_date AS date, c.reason, c.new_status AS status 
            FROM attendance_corrections c
            JOIN attendance_records ar ON ar.id = c.attendance_record_id
            WHERE c.corrected_by = ?
        """, (current_user["id"],)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@app.get("/student/leaves")
async def api_get_student_leaves(current_user: dict = Depends(get_current_user)):
    conn = get_connection()
    try:
        rows = conn.execute("SELECT id, start_date, end_date, reason, status, created_at FROM leave_requests WHERE student_user_id = ? ORDER BY created_at DESC",
                            (current_user["id"],)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@app.post("/student/leaves")
async def api_add_leave_request(data: dict, current_user: dict = Depends(get_current_user)):
    conn = get_connection()
    try:
        now = datetime.now().isoformat()
        conn.execute("""INSERT INTO leave_requests 
                        (student_user_id, start_date, end_date, reason, status, submitted_by_user_id, created_at) 
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
                     (current_user["id"], data["start_date"], data["end_date"], data["reason"], 'pending', current_user["id"], now))
        conn.commit()
    finally:
        conn.close()
    return {"status": "ok"}

@app.get("/admin/leaves")
async def api_get_admin_leaves(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    conn = get_connection()
    try:
        rows = conn.execute("""SELECT l.id, l.start_date, l.end_date, l.reason, l.status, l.created_at, u.full_name AS student_name
                               FROM leave_requests l
                               JOIN users u ON u.id = l.student_user_id
                               ORDER BY l.status = 'pending' DESC, l.created_at DESC""").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@app.post("/admin/leave/review")
async def api_review_leave(data: dict, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    conn = get_connection()
    try:
        now = datetime.now().isoformat()
        conn.execute("UPDATE leave_requests SET status = ?, reviewed_by = ?, reviewed_at = ? WHERE id = ?",
                     (data["status"], current_user["id"], now, data["id"]))
        
        if data["status"] == "approved":
            from core.services import apply_leave_to_attendance
            apply_leave_to_attendance(conn, data["id"])
        else:
            from core.services import clear_leave_attendance
            clear_leave_attendance(conn, data["id"])
            
        conn.commit()
    finally:
        conn.close()
    return {"status": "ok"}

@app.get("/teacher/subjects")
async def api_get_teacher_subjects(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "teacher": raise HTTPException(403, "Teacher only")
    conn = get_connection()
    try:
        rows = conn.execute("""SELECT s.id, s.code, s.name FROM subjects s
                               INNER JOIN teacher_subjects ts ON ts.subject_id = s.id
                               WHERE ts.teacher_user_id = ? ORDER BY s.code""",
                            (current_user["id"],)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@app.get("/teacher/schedule")
async def api_get_teacher_schedule(current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["teacher", "admin"]: raise HTTPException(403, "Forbidden")
    conn = get_connection()
    try:
        params = [current_user["id"]]
        where_clause = "WHERE t.teacher_user_id = ? AND t.is_archived = 0"
        if current_user["role"] == "admin":
            params = []
            where_clause = "WHERE t.is_archived = 0"

        rows = conn.execute(f"""SELECT t.id, t.day_of_week,
                                      t.subject_id, sub.code AS subject_code, sub.name AS subject_name,
                                      t.period_id, p.label AS period_label, p.start_time, p.end_time, p.sort_order,
                                      t.room_id, r.name AS room_name, r.building AS room_building,
                                      t.course_id, COALESCE(c.name, '') AS course_name,
                                      t.semester_id, COALESCE(sem.name, '') AS semester_name,
                                      t.session_id, COALESCE(sy.label, '') AS session_name
                               FROM timetable t
                               JOIN subjects sub ON sub.id = t.subject_id
                               JOIN periods p ON p.id = t.period_id
                               LEFT JOIN rooms r ON r.id = t.room_id
                               LEFT JOIN courses c ON c.id = t.course_id
                               LEFT JOIN semesters sem ON sem.id = t.semester_id
                               LEFT JOIN session_years sy ON sy.id = t.session_id
                               {where_clause}
                               ORDER BY t.day_of_week, p.sort_order""",
                            params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@app.get("/student/schedule")
async def api_get_student_schedule(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "student": raise HTTPException(403, "Student only")
    conn = get_connection()
    try:
        # Join enrollments with timetable to get the student's actual schedule
        rows = conn.execute("""SELECT t.id, t.day_of_week,
                                      t.subject_id, sub.code AS subject_code, sub.name AS subject_name,
                                      t.period_id, p.label AS period_label, p.start_time, p.end_time, p.sort_order,
                                      t.room_id, r.name AS room_name, r.building AS room_building
                               FROM timetable t
                               JOIN enrollments e ON e.subject_id = t.subject_id
                               JOIN subjects sub ON sub.id = t.subject_id
                               JOIN periods p ON p.id = t.period_id
                               LEFT JOIN rooms r ON r.id = t.room_id
                               WHERE e.student_user_id = ? AND t.is_archived = 0
                               ORDER BY t.day_of_week, p.sort_order""",
                            (current_user["id"],)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@app.get("/teacher/today-stats")
async def api_get_teacher_today_stats(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "teacher": raise HTTPException(403, "Teacher only")
    conn = get_connection()
    try:
        today = datetime.now().date().isoformat()
        total = conn.execute("SELECT COUNT(*) as c FROM attendance_records WHERE teacher_user_id = ? AND attendance_date = ?", (current_user["id"], today)).fetchone()["c"]
        present = conn.execute("SELECT COUNT(*) as c FROM attendance_records WHERE teacher_user_id = ? AND attendance_date = ? AND status = 'present'", (current_user["id"], today)).fetchone()["c"]
        absent = conn.execute("SELECT COUNT(*) as c FROM attendance_records WHERE teacher_user_id = ? AND attendance_date = ? AND status = 'absent'", (current_user["id"], today)).fetchone()["c"]
        subjects = conn.execute("SELECT COUNT(DISTINCT subject_id) as c FROM timetable WHERE teacher_user_id = ? AND is_archived = 0", (current_user["id"],)).fetchone()["c"]
        return {"today_records": total, "present": present, "absent": absent, "total_subjects": subjects}
    finally:
        conn.close()

@app.get("/teacher/roster/{subject_id}")
async def api_get_roster(subject_id: int, current_user: dict = Depends(get_current_user)):
    # In a real app, verify teacher teaches this subject
    conn = get_connection()
    try:
        rows = conn.execute("""SELECT u.id, u.full_name, s.student_code
                               FROM users u
                               INNER JOIN students s ON s.user_id = u.id
                               INNER JOIN enrollments e ON e.student_user_id = u.id
                               WHERE e.subject_id = ? ORDER BY u.full_name""",
                            (subject_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@app.post("/teacher/roster/{subject_id}/{student_id}")
async def api_add_roster(subject_id: int, student_id: int, current_user: dict = Depends(get_current_user)):
    conn = get_connection()
    try:
        # Check if teacher teaches this subject
        count = conn.execute("SELECT COUNT(DISTINCT subject_id) as c FROM timetable WHERE teacher_user_id = ? AND subject_id = ? AND is_archived = 0",
                             (current_user["id"], subject_id)).fetchone()["c"]
        if count == 0 and current_user["role"] != "admin":
            raise HTTPException(403, "You do not teach this subject")
            
        conn.execute("INSERT OR IGNORE INTO enrollments (student_user_id, subject_id) VALUES (?, ?)", (student_id, subject_id))
        conn.commit()
        return {"status": "success"}
    finally:
        conn.close()

@app.delete("/teacher/roster/{subject_id}/{student_id}")
async def api_remove_roster(subject_id: int, student_id: int, current_user: dict = Depends(get_current_user)):
    conn = get_connection()
    try:
        # Check if teacher teaches this subject
        count = conn.execute("SELECT COUNT(DISTINCT subject_id) as c FROM timetable WHERE teacher_user_id = ? AND subject_id = ? AND is_archived = 0",
                             (current_user["id"], subject_id)).fetchone()["c"]
        if count == 0 and current_user["role"] != "admin":
            raise HTTPException(403, "You do not teach this subject")
            
        conn.execute("DELETE FROM enrollments WHERE student_user_id = ? AND subject_id = ?", (student_id, subject_id))
        conn.commit()
        return {"status": "success"}
    finally:
        conn.close()

@app.get("/teacher/lessons")
async def api_get_lessons(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "teacher": raise HTTPException(403, "Teacher only")
    conn = get_connection()
    try:
        rows = conn.execute("SELECT id, title, content, created_at FROM lesson_plans WHERE teacher_id = ? ORDER BY created_at DESC",
                            (current_user["id"],)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@app.post("/teacher/lessons")
async def api_add_lesson(data: dict, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "teacher": raise HTTPException(403, "Teacher only")
    conn = get_connection()
    try:
        conn.execute("INSERT INTO lesson_plans (teacher_id, title, content, created_at) VALUES (?, ?, ?, ?)",
                     (current_user["id"], data["title"], data["content"], datetime.now().isoformat()))
        conn.commit()
    finally:
        conn.close()
    return {"status": "ok"}

# --- Academic CRUD ---

@app.get("/academic/sessions")
async def api_get_sessions():
    conn = get_connection()
    try:
        rows = conn.execute("SELECT id, label, start_date, end_date FROM session_years ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@app.post("/academic/sessions")
async def api_add_session(data: dict, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    conn = get_connection()
    try:
        conn.execute("INSERT INTO session_years (label, start_date, end_date) VALUES (?, ?, ?)", 
                     (data["label"], data["start_date"], data["end_date"]))
        conn.commit()
    finally:
        conn.close()
    return {"status": "ok"}

@app.put("/academic/sessions/{id}")
async def api_update_session(id: int, data: dict, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    conn = get_connection()
    try:
        conn.execute("UPDATE session_years SET label = ?, start_date = ?, end_date = ? WHERE id = ?", 
                     (data["label"], data["start_date"], data["end_date"], id))
        conn.commit()
    finally:
        conn.close()
    return {"status": "ok"}

@app.delete("/academic/sessions/{id}")
async def api_delete_session(id: int, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    conn = get_connection()
    try:
        conn.execute("DELETE FROM session_years WHERE id = ?", (id,))
        conn.commit()
    finally:
        conn.close()
    return {"status": "ok"}

@app.get("/academic/courses")
async def api_get_courses():
    conn = get_connection()
    try:
        rows = conn.execute("SELECT id, code, name FROM courses ORDER BY code").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@app.post("/academic/courses")
async def api_add_course(data: dict, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    conn = get_connection()
    try:
        conn.execute("INSERT INTO courses (code, name) VALUES (?, ?)", (data["code"], data["name"]))
        conn.commit()
    finally:
        conn.close()
    return {"status": "ok"}

@app.put("/academic/courses/{id}")
async def api_update_course(id: int, data: dict, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    conn = get_connection()
    try:
        conn.execute("UPDATE courses SET code = ?, name = ? WHERE id = ?", (data["code"], data["name"], id))
        conn.commit()
    finally:
        conn.close()
    return {"status": "ok"}

@app.delete("/academic/courses/{id}")
async def api_delete_course(id: int, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    conn = get_connection()
    try:
        conn.execute("DELETE FROM courses WHERE id = ?", (id,))
        conn.commit()
    finally:
        conn.close()
    return {"status": "ok"}

@app.get("/academic/semesters")
async def api_get_semesters():
    conn = get_connection()
    try:
        rows = conn.execute("SELECT id, name FROM semesters ORDER BY name").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@app.post("/academic/semesters")
async def api_add_semester(data: dict, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    conn = get_connection()
    try:
        conn.execute("INSERT INTO semesters (name) VALUES (?)", (data["name"],))
        conn.commit()
    finally:
        conn.close()
    return {"status": "ok"}

@app.put("/academic/semesters/{id}")
async def api_update_semester(id: int, data: dict, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    conn = get_connection()
    try:
        conn.execute("UPDATE semesters SET name = ? WHERE id = ?", (data["name"], id))
        conn.commit()
    finally:
        conn.close()
    return {"status": "ok"}

@app.delete("/academic/semesters/{id}")
async def api_delete_semester(id: int, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    conn = get_connection()
    try:
        conn.execute("DELETE FROM semesters WHERE id = ?", (id,))
        conn.commit()
    finally:
        conn.close()
    return {"status": "ok"}

@app.get("/academic/subjects")
async def api_get_subjects():
    conn = get_connection()
    try:
        rows = conn.execute("SELECT id, code, name FROM subjects ORDER BY code").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@app.post("/academic/subjects")
async def api_add_subject(data: dict, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    conn = get_connection()
    try:
        conn.execute("INSERT INTO subjects (code, name) VALUES (?, ?)", (data["code"], data["name"]))
        conn.commit()
    finally:
        conn.close()
    return {"status": "ok"}

@app.put("/academic/subjects/{id}")
async def api_update_subject(id: int, data: dict, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    conn = get_connection()
    try:
        conn.execute("UPDATE subjects SET code = ?, name = ? WHERE id = ?", (data["code"], data["name"], id))
        conn.commit()
    finally:
        conn.close()
    return {"status": "ok"}

@app.delete("/academic/subjects/{id}")
async def api_delete_subject(id: int, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    conn = get_connection()
    try:
        conn.execute("DELETE FROM subjects WHERE id = ?", (id,))
        conn.commit()
    finally:
        conn.close()
    return {"status": "ok"}

@app.get("/academic/rooms")
async def api_get_rooms():
    conn = get_connection()
    try:
        rows = conn.execute("SELECT id, name, building FROM rooms ORDER BY name").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@app.post("/academic/rooms")
async def api_add_room(data: dict, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    conn = get_connection()
    try:
        conn.execute("INSERT INTO rooms (name, building) VALUES (?, ?)", (data["name"], data["building"]))
        conn.commit()
    finally:
        conn.close()
    return {"status": "ok"}

@app.put("/academic/rooms/{id}")
async def api_update_room(id: int, data: dict, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    conn = get_connection()
    try:
        conn.execute("UPDATE rooms SET name = ?, building = ? WHERE id = ?", (data["name"], data["building"], id))
        conn.commit()
    finally:
        conn.close()
    return {"status": "ok"}

@app.delete("/academic/rooms/{id}")
async def api_delete_room(id: int, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    conn = get_connection()
    try:
        conn.execute("DELETE FROM rooms WHERE id = ?", (id,))
        conn.commit()
    finally:
        conn.close()
    return {"status": "ok"}

@app.get("/academic/periods")
async def api_get_periods():
    conn = get_connection()
    try:
        rows = conn.execute("SELECT id, label, start_time, end_time, sort_order FROM periods ORDER BY sort_order, id").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@app.post("/academic/periods")
async def api_add_period(data: dict, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    conn = get_connection()
    try:
        conn.execute("INSERT INTO periods (label, start_time, end_time, sort_order) VALUES (?, ?, ?, ?)", 
                     (data["label"], data["start_time"], data["end_time"], int(data["sort_order"])))
        conn.commit()
    finally:
        conn.close()
    return {"status": "ok"}

@app.put("/academic/periods/{id}")
async def api_update_period(id: int, data: dict, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    conn = get_connection()
    try:
        conn.execute("UPDATE periods SET label = ?, start_time = ?, end_time = ?, sort_order = ? WHERE id = ?", 
                     (data["label"], data["start_time"], data["end_time"], int(data["sort_order"]), id))
        conn.commit()
    finally:
        conn.close()
    return {"status": "ok"}

@app.delete("/academic/periods/{id}")
async def api_delete_period(id: int, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    conn = get_connection()
    try:
        conn.execute("DELETE FROM periods WHERE id = ?", (id,))
        conn.commit()
    finally:
        conn.close()
    return {"status": "ok"}

# --- Admin Attendance Management ---

@app.get("/admin/attendance")
async def api_admin_get_attendance(
    student_id: int = None, subject_id: int = None, 
    period_id: int = None, date_from: str = None, date_to: str = None,
    status: str = None,
    teacher_id: int = None, session_id: int = None, course_id: int = None,
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    conn = get_connection()
    try:
        query = """SELECT ar.id, ar.attendance_date, ar.status, ar.capture_method, ar.marked_at, ar.notes,
                          ar.subject_id, sub.code AS subject_code, sub.name AS subject_name,
                          ar.student_user_id, su.full_name AS student_name, st.student_code,
                          ar.teacher_user_id, tu.full_name AS teacher_name,
                          ar.period_id, p.label AS period_label, p.start_time, p.end_time
                   FROM attendance_records ar
                   JOIN subjects sub ON sub.id = ar.subject_id
                   JOIN users su ON su.id = ar.student_user_id
                   LEFT JOIN students st ON st.user_id = su.id
                   JOIN users tu ON tu.id = ar.teacher_user_id
                   JOIN periods p ON p.id = ar.period_id
                   WHERE 1=1"""
        params = []
        if student_id:
            query += " AND ar.student_user_id = ?"
            params.append(student_id)
        if subject_id:
            query += " AND ar.subject_id = ?"
            params.append(subject_id)
        if period_id:
            query += " AND ar.period_id = ?"
            params.append(period_id)
        if date_from:
            query += " AND ar.attendance_date >= ?"
            params.append(date_from)
        if date_to:
            query += " AND ar.attendance_date <= ?"
            params.append(date_to)
        if status:
            query += " AND ar.status = ?"
            params.append(status)
        if teacher_id:
            query += " AND ar.teacher_user_id = ?"
            params.append(teacher_id)
        if session_id:
            query += " AND sub.session_id = ?"
            params.append(session_id)
        if course_id:
            query += " AND sub.course_id = ?"
            params.append(course_id)
        query += " ORDER BY ar.attendance_date DESC, p.sort_order, su.full_name"
        rows = conn.execute(query, tuple(params)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@app.post("/admin/attendance")
async def api_admin_add_attendance(data: dict, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    conn = get_connection()
    try:
        rec_id, _ = services.get_or_create_attendance(
            conn,
            subject_id=data["subject_id"],
            teacher_id=data.get("teacher_user_id", current_user["id"]),
            student_id=data["student_user_id"],
            period_id=data["period_id"],
            attendance_date=data["attendance_date"],
            status=data["status"],
            lesson_plan_id=None,
            capture_method="admin_web"
        )
        conn.commit()
        return {"status": "ok", "id": rec_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(400, str(e))
    finally:
        conn.close()

@app.put("/admin/attendance/{record_id}")
async def api_admin_update_attendance(record_id: int, data: dict, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    conn = get_connection()
    try:
        row = conn.execute("SELECT id FROM attendance_records WHERE id = ?", (record_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Record not found")
        conn.execute(
            """UPDATE attendance_records SET status = ?, marked_at = ? WHERE id = ?""",
            (data["status"], datetime.now().isoformat(), record_id)
        )
        conn.commit()
        return {"status": "ok"}
    finally:
        conn.close()

@app.delete("/admin/attendance/{record_id}")
async def api_admin_delete_attendance(record_id: int, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    conn = get_connection()
    try:
        conn.execute("DELETE FROM attendance_records WHERE id = ?", (record_id,))
        conn.commit()
    finally:
        conn.close()
    return {"status": "ok"}

# --- Reports & Marking ---

@app.get("/attendance/summary")
async def api_get_attendance_summary(current_user: dict = Depends(get_current_user)):
    conn = get_connection()
    try:
        today = datetime.now().date().isoformat()
        if current_user["role"] == "student":
            records = conn.execute("SELECT status, COUNT(*) as count FROM attendance_records WHERE student_user_id = ? GROUP BY status", (current_user["id"],)).fetchall()
            return [dict(r) for r in records]
        elif current_user["role"] == "teacher":
            records = conn.execute("SELECT status, COUNT(*) as count FROM attendance_records WHERE teacher_user_id = ? AND attendance_date = ? GROUP BY status", (current_user["id"], today)).fetchall()
            return [dict(r) for r in records]
        return []
    finally:
        conn.close()

@app.post("/attendance/mark")
async def api_mark_attendance(data: dict, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["teacher", "admin"]: raise HTTPException(403, "Forbidden")
    conn = get_connection()
    try:
        services.get_or_create_attendance(conn, subject_id=data["subject_id"], teacher_id=current_user["id"], student_id=data["student_id"], period_id=data["period_id"], attendance_date=datetime.now().date().isoformat(), status=data["status"], lesson_plan_id=None, capture_method="web_manual")
        conn.commit()
    finally:
        conn.close()
    return {"status": "success"}

@app.post("/teacher/generate_qr")
async def api_generate_qr(data: dict, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["teacher", "admin"]: raise HTTPException(403, "Forbidden")
    conn = get_connection()
    try:
        # Verify subject is not archived
        active_count = conn.execute("SELECT COUNT(*) as c FROM timetable WHERE teacher_user_id = ? AND subject_id = ? AND period_id = ? AND is_archived = 0",
                                    (current_user["id"], data["subject_id"], data["period_id"])).fetchone()["c"]
        if active_count == 0 and current_user["role"] != "admin":
            raise HTTPException(400, "This class slot is archived or you are not the assigned teacher.")

        import uuid
        token = str(uuid.uuid4())
        today = datetime.now().date().isoformat()
        now_str = datetime.now().isoformat()
        # Expires in 1 hour
        expires = (datetime.now() + timedelta(hours=1)).isoformat()
        conn.execute(
            """INSERT INTO class_qr_sessions (token, subject_id, period_id, attendance_date, created_by, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (token, data["subject_id"], data["period_id"], today, current_user["id"], now_str, expires)
        )
        conn.commit()
        return {"status": "success", "token": token}
    finally:
        conn.close()

@app.post("/student/checkin")
async def api_student_checkin(data: dict, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "student": raise HTTPException(403, "Students only")
    conn = get_connection()
    try:
        token = data.get("token")
        if not token: raise HTTPException(400, "Token required")
        
        session = conn.execute("SELECT * FROM class_qr_sessions WHERE token = ?", (token,)).fetchone()
        if not session: raise HTTPException(404, "Invalid QR code")
        
        if datetime.fromisoformat(session["expires_at"]) < datetime.now():
            raise HTTPException(400, "QR code expired")
            
        # Verify enrollment
        enrolled = conn.execute("SELECT COUNT(*) as c FROM enrollments WHERE student_user_id = ? AND subject_id = ?",
                                (current_user["id"], session["subject_id"])).fetchone()["c"]
        if enrolled == 0:
            raise HTTPException(403, "You are not enrolled in this class")
            
        services.get_or_create_attendance(
            conn, 
            subject_id=session["subject_id"], 
            teacher_id=session["created_by"], 
            student_id=current_user["id"], 
            period_id=session["period_id"], 
            attendance_date=session["attendance_date"], 
            status="present", 
            lesson_plan_id=None, 
            capture_method="student_qr"
        )
        conn.commit()
        return {"status": "success"}
    finally:
        conn.close()

@app.get("/teacher/attendance/range")
async def api_get_teacher_attendance_range(subject_id: int, start_date: str, end_date: str, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["teacher", "admin"]: raise HTTPException(403, "Forbidden")
    conn = get_connection()
    try:
        # Fetch matching existing attendance records
        query = """SELECT student_user_id, attendance_date, status, period_id 
                   FROM attendance_records 
                   WHERE subject_id = ? AND attendance_date >= ? AND attendance_date <= ?"""
        rows = conn.execute(query, (subject_id, start_date, end_date)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@app.post("/attendance/bulk-mark")
async def api_bulk_mark_attendance(data: dict, current_user: dict = Depends(get_current_user)):
    """Expected data: { 'records': [{ 'student_id': 1, 'subject_id': 1, 'period_id': 1, 'date': '2026-01-01', 'status': 'present' }] }"""
    if current_user["role"] not in ["teacher", "admin"]: raise HTTPException(403, "Forbidden")
    conn = get_connection()
    try:
        results_ids = []
        for rec in data.get("records", []):
             services.get_or_create_attendance(
                 conn,
                 subject_id=rec["subject_id"],
                 teacher_id=current_user["id"],
                 student_id=rec["student_id"],
                 period_id=rec["period_id"],
                 attendance_date=rec["date"],
                 status=rec["status"],
                 lesson_plan_id=None,
                 capture_method="bulk_web"
             )
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(400, str(e))
    finally:
        conn.close()

@app.get("/attendance/student_stats_bs")
async def api_get_student_stats_bs(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "student":
        # Allow parent to see their child's stats
        if current_user["role"] == "parent":
            conn = get_connection()
            try:
                from core.services import parent_child_user_id
                child_id = parent_child_user_id(conn, current_user["id"])
                if not child_id: raise HTTPException(404, "No linked student")
                user_id = child_id
            finally: conn.close()
        else:
            raise HTTPException(403, "Student/Parent only")
    else:
        user_id = current_user["id"]

    conn = get_connection()
    try:
        import nepali_datetime
        from datetime import date
        rows = conn.execute("SELECT attendance_date, status FROM attendance_records WHERE student_user_id = ?", (user_id,)).fetchall()
        
        # Group by Nepali year and month
        monthly = {}
        for r in rows:
            ad_str = r["attendance_date"]
            status = r["status"]
            try:
                y, m, d = map(int, ad_str.split('-'))
                bs = nepali_datetime.date.from_datetime_date(date(y, m, d))
                key = f"{bs.year}-{bs.month:02d}"
                if key not in monthly:
                    monthly[key] = {"year": bs.year, "month": bs.month, "present": 0, "absent": 0, "late": 0, "excused": 0, "total": 0}
                monthly[key][status] += 1
                monthly[key]["total"] += 1
            except: continue
            
        res = sorted(monthly.values(), key=lambda x: (x["year"], x["month"]), reverse=True)
        return res
    finally:
        conn.close()

@app.get("/export/compliance")
async def api_export_compliance(start_date: str, end_date: str, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin": raise HTTPException(403, "Admin only")
    conn = get_connection()
    try:
        return services.compliance_report_csv(conn, start_date, end_date)
    finally:
        conn.close()

if __name__ == "__main__":
    import uvicorn
    init_database()
    uvicorn.run(app, host="0.0.0.0", port=8080)
