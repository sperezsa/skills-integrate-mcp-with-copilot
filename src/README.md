# Mergington High School Activities API

A simple FastAPI application for viewing and managing extracurricular activity registrations.

## Features

- View all available extracurricular activities
- Let teachers sign in and manage student registrations
- Let students view activities and participant lists without signing in

## Getting Started

1. Install the dependencies:

   ```
   pip install fastapi uvicorn
   ```

2. Run the application:

   ```
   cd src
   uvicorn app:app --reload
   ```

3. Open your browser and go to:
   - Activities: http://localhost:8000
   - API documentation: http://localhost:8000/docs
   - Alternative documentation: http://localhost:8000/redoc

## Teacher Accounts

Create a teacher account from the `src` directory. The command prompts for a
password and confirmation without echoing either value:

```
python create_teacher.py teacher-username
```

Passwords must be at least 12 characters. The command stores a salted
PBKDF2-HMAC-SHA256 hash in `src/teachers.json`; the credentials file is ignored
by Git. Run the command again with the same username to change that account's
password. If the account file is missing or invalid, teacher sign-in is
unavailable and the API reports a configuration error.

Teacher sessions use an HTTP-only, same-site cookie and expire after eight
hours. Sessions are held in memory and are cleared when the server restarts.
When serving the application over HTTPS, set `COOKIE_SECURE=true` so browsers
only send the session cookie over secure connections.

## API Endpoints

| Method | Endpoint                                                          | Description                                                         |
| ------ | ----------------------------------------------------------------- | ------------------------------------------------------------------- |
| GET    | `/activities`                                                     | Get all activities with their details and current participant count |
| POST   | `/auth/login`                                                      | Sign in as a teacher and establish a session                        |
| GET    | `/auth/session`                                                    | Get the current sign-in status                                      |
| POST   | `/auth/logout`                                                     | End the current teacher session                                     |
| POST   | `/activities/{activity_name}/signup?email=student@mergington.edu` | Register a student (teacher sign-in required)                       |
| DELETE | `/activities/{activity_name}/unregister?email=student@mergington.edu` | Unregister a student (teacher sign-in required)                  |

## Data Model

The application uses a simple data model with meaningful identifiers:

1. **Activities** - Uses activity name as identifier:

   - Description
   - Schedule
   - Maximum number of participants allowed
   - List of student emails who are signed up

2. **Students** - Uses email as identifier:
   - Name
   - Grade level

All data is stored in memory, which means data will be reset when the server restarts.
