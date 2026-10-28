# Job Application Tracker

A full-stack web app to track job applications through the hiring pipeline: add applications, move them between stages on a board, attach the resume you used for each one, and see stats about your search.

**Stack:** FastAPI · PostgreSQL (async SQLAlchemy 2.0, asyncpg) · JWT auth · Vanilla HTML/CSS/JS · Docker · GitHub Actions

## Signup and Login Preview ##
![Job Application Tracker Signup and Login](docs/Signup.png) 

### Dashboard Preview ###
![Job Application Tracker Dashboard](docs/dashboard.png) 

## Features

- **Authentication** - sign up, email OTP verification, login with JWT bearer tokens
- **Applications CRUD** - company, position, location, salary range, applied date, job link, notes
- **Kanban board** - Applied / Interviewing / Offered / Rejected, change status from any card
- **Search & filter** - by company/position text and by status, with pagination on the API
- **Dashboard stats** - totals, active applications, offers, offer rate (SQL `GROUP BY` aggregation)
- **Resume storage** - upload/replace/download a PDF per application (stored as `bytea` in PostgreSQL, 5 MB limit, PDF signature check)
- **Per-user data isolation** - every query is scoped to the authenticated user
- **Tests + CI** - pytest suite (in-memory SQLite, no database setup needed) running on GitHub Actions
- **Docker** - one command to run the API, PostgreSQL and UI

## Security notes

- Passwords hashed with **bcrypt**
- OTPs generated with `secrets`, stored **hashed**, expire after 5 minutes, max 5 attempts, 30 s resend cooldown
- JWT access tokens (HS256) with expiry; all `/applications` routes require a valid token
- Ownership enforced on every read/update/delete, so one user cannot access another user's records or resumes
- User-provided text is HTML-escaped in the frontend (XSS protection)
- `DEV_MODE=true` returns the OTP in the API response when SMTP is not configured. **Use only for local demos; set `DEV_MODE=false` in production.**

## Quick start

### Option A - Docker (easiest)

```bash
git clone https://github.com/bokkavivek/job_application_tracker.git
cd job_application_tracker
docker compose up --build
```

Open http://localhost:8000 (UI) or http://localhost:8000/docs (interactive API docs).

### Option B - Local

Requires Python 3.11+ and PostgreSQL.

```bash
# 1. create the database (once)
psql -U postgres -c "CREATE DATABASE job_tracker;"

# 2. run the app
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env             # then set DATABASE_URL and JWT_SECRET
uvicorn main:app --reload
```

`DATABASE_URL` format: `postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/job_tracker`. Tables are created automatically on startup.

### Real OTP emails (optional)

Fill `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` in `.env` (for Gmail use an app password) and set `DEV_MODE=false`.

## API overview

| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/signup` | Create account |
| POST | `/auth/send-otp` | Send email verification code |
| POST | `/auth/verify-otp` | Verify email |
| POST | `/auth/login` | Returns JWT access token |
| GET | `/auth/me` | Current user |
| POST | `/applications` | Create application |
| GET | `/applications?status=&search=&skip=&limit=` | List with filters + pagination |
| GET | `/applications/stats` | Counts by status, offer rate |
| GET / PUT / DELETE | `/applications/{id}` | Read / update / delete |
| PATCH | `/applications/{id}/status` | Change status |
| POST / GET | `/applications/{id}/resume` | Upload / download PDF resume |

Full interactive docs at `/docs`.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

Tests run against in-memory SQLite, so no running PostgreSQL is needed. Resume upload/download should also be tried manually against a real PostgreSQL.

## Project structure

```
main.py            FastAPI app, routes, error handling, serves the frontend
crud.py            Business logic (auth, applications, resume storage)
schemas.py         Pydantic request models + validation
security.py        bcrypt, OTP hashing, JWT, get_current_user dependency
database.py        Async engine, session dependency, table creation
models.py          SQLAlchemy models (User, JobApplication)
email_service.py   SMTP OTP delivery (falls back to logs in dev)
config.py          Environment-based settings
frontend/          index.html, style.css, app.js (no build step)
tests/             pytest suite
Dockerfile, docker-compose.yml, .github/workflows/ci.yml
```

## Possible next steps

- Reminders / follow-up dates, interview timeline per application
- Drag-and-drop between board columns
- Alembic migrations, refresh tokens and password reset
- Deploy: Render/Railway (API) + a free hosted PostgreSQL (e.g. Neon, Supabase)
