"""
High School Management System API

A FastAPI application that allows students to view extracurricular activities
and teachers to manage registrations at Mergington High School.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import logging
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pathlib import Path
import secrets

from fastapi import Cookie, Depends, FastAPI, HTTPException, Response, status
from pydantic import BaseModel

app = FastAPI(title="Mergington High School API",
              description="API for viewing activities and managing registrations")
logger = logging.getLogger(__name__)

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

TEACHERS_FILE = current_dir / "teachers.json"
SESSION_COOKIE = "teacher_session"
SESSION_DURATION = timedelta(hours=8)
PASSWORD_HASH_ITERATIONS = 600_000
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "").lower() in {"1", "true", "yes"}
teacher_sessions: dict[str, tuple[str, datetime]] = {}


class LoginRequest(BaseModel):
    username: str
    password: str


def load_teacher_accounts() -> dict:
    try:
        with TEACHERS_FILE.open(encoding="utf-8") as teacher_file:
            accounts = json.load(teacher_file)
    except FileNotFoundError as error:
        logger.error("Teacher account file is missing: %s", TEACHERS_FILE)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Teacher login is not configured",
        ) from error
    except (OSError, json.JSONDecodeError) as error:
        logger.exception("Unable to read teacher account file")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Teacher login is unavailable because account configuration is invalid",
        ) from error

    if not isinstance(accounts, dict):
        logger.error("Teacher account file must contain a JSON object")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Teacher login is unavailable because account configuration is invalid",
        )

    for username, account in accounts.items():
        if (
            not isinstance(username, str)
            or not isinstance(account, dict)
            or not isinstance(account.get("salt"), str)
            or not isinstance(account.get("password_hash"), str)
        ):
            logger.error("Invalid teacher account record for %r", username)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Teacher login is unavailable because account configuration is invalid",
            )
        try:
            salt = bytes.fromhex(account["salt"])
            password_hash = bytes.fromhex(account["password_hash"])
            if len(salt) < 16 or len(password_hash) != hashlib.sha256().digest_size:
                raise ValueError("Unexpected salt or password hash length")
        except ValueError as error:
            logger.error("Invalid password hash for teacher account %r", username)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Teacher login is unavailable because account configuration is invalid",
            ) from error

    return accounts


def get_session_teacher(session_id: str | None) -> str | None:
    if not session_id:
        return None

    session = teacher_sessions.get(session_id)
    if session is None:
        return None

    username, expires_at = session
    if expires_at <= datetime.now(timezone.utc):
        del teacher_sessions[session_id]
        return None
    return username


def require_teacher(session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> str:
    username = get_session_teacher(session_id)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Teacher login required",
        )
    return username


# In-memory activity database
activities = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]
    }
}


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    return activities


@app.post("/auth/login")
def login(login_request: LoginRequest, response: Response):
    accounts = load_teacher_accounts()
    account = accounts.get(login_request.username)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    provided_hash = hashlib.pbkdf2_hmac(
        "sha256",
        login_request.password.encode("utf-8"),
        bytes.fromhex(account["salt"]),
        PASSWORD_HASH_ITERATIONS,
    ).hex()
    if not hmac.compare_digest(provided_hash, account["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    session_id = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expired_sessions = [
        existing_id
        for existing_id, (_, expires_at) in teacher_sessions.items()
        if expires_at <= now
    ]
    for expired_id in expired_sessions:
        del teacher_sessions[expired_id]
    teacher_sessions[session_id] = (
        login_request.username,
        now + SESSION_DURATION,
    )
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_id,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="strict",
        max_age=int(SESSION_DURATION.total_seconds()),
        path="/",
    )
    return {"authenticated": True, "username": login_request.username}


@app.get("/auth/session")
def auth_session(session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE)):
    username = get_session_teacher(session_id)
    return {"authenticated": username is not None, "username": username}


@app.post("/auth/logout")
def logout(
    response: Response,
    session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE),
):
    if session_id:
        teacher_sessions.pop(session_id, None)
    response.delete_cookie(
        key=SESSION_COOKIE,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="strict",
        path="/",
    )
    return {"authenticated": False}


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(
    activity_name: str,
    email: str,
    _: str = Depends(require_teacher),
):
    """Sign a student up for an activity as a teacher."""

    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is not already signed up
    if email in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is already signed up"
        )

    # Add student
    activity["participants"].append(email)
    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(
    activity_name: str,
    email: str,
    _: str = Depends(require_teacher),
):
    """Unregister a student from an activity as a teacher."""

    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is signed up
    if email not in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is not signed up for this activity"
        )

    # Remove student
    activity["participants"].remove(email)
    return {"message": f"Unregistered {email} from {activity_name}"}
