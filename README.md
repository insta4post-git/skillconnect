# SkillConnect

Location-based service marketplace. Connects people who **have** a skill with people who **need** that skill.

This is the SkillConnect MVP. Step 2 adds the MySQL table structure.

## Stack

- Frontend: HTML, CSS, vanilla JavaScript
- Backend: Python, FastAPI
- Database: MySQL (SQLAlchemy + PyMySQL)
- Auth (later): JWT

## Project structure

```
skillconnect/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── crud.py
│   │   ├── security.py
│   │   └── routers/
│   ├── create_database.py
│   ├── create_tables.py
│   ├── .env.example
│   ├── .env
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── search.html
│   ├── provider.html
│   ├── dashboard.html
│   ├── css/style.css
│   └── js/app.js
├── .gitignore
└── README.md
```

## Setup (Windows PowerShell)

### 1. Fill secrets

Open `backend/.env` and replace:

- `MYSQL_PASSWORD=your_mysql_password_here` with your MySQL `root` password
- optionally `SECRET_KEY` with any random string (used later for JWT)

Do not commit `.env`. Use `.env.example` as the template for GitHub.

### 2. Python virtual environment

```powershell
cd "C:\Users\Shweta Sah\skillconnect\backend"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If Activate is blocked, run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then activate again.

### 3. Create the MySQL database

MySQL Server 8.0 should already be running (`MySQL80`). After the password is in `.env`:

```powershell
python create_database.py
```

Expected: `Database 'skillconnect' is ready.`

Then create tables:

```powershell
python create_tables.py
```

Expected: a list of tables (`users`, `provider_profiles`, `skills`, `categories`, `locations`, `service_requests`, `availability`, `messages`, `reviews`, and junction table `provider_skills`).

### 4. Start the app

From the `backend` folder, with the venv active:

```powershell
uvicorn app.main:app --reload
```

Then open:

- Frontend: http://127.0.0.1:8000/
- Swagger: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/api/health
- Register: http://127.0.0.1:8000/register.html
- Login: http://127.0.0.1:8000/login.html

Auth endpoints (Swagger):

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me` (Bearer token)
- `POST /api/auth/logout` (Bearer token)

Public signup roles are **CUSTOMER** and **PROVIDER** only. Admin accounts are created with:

```powershell
python create_admin.py
```

after setting `ADMIN_EMAIL` and `ADMIN_PASSWORD` in `backend/.env`. Then run `python create_tables.py` once so MySQL accepts the `ADMIN` role.

## Git / GitHub

This repo includes `.gitignore`, `.env.example`, and this README.

Git was not found on PATH on this machine. Install [Git for Windows](https://git-scm.com/download/win), then:

```powershell
cd "C:\Users\Shweta Sah\skillconnect"
git init
git add .
git commit -m "Step 1: SkillConnect project foundation"
```

Create a GitHub repository later and push. Never add `.env` (it is already ignored).

## Step 1 expected results

- FastAPI starts without crashing
- Home page loads
- `/api/health` returns `"status": "ok"`
- After `.env` password + `create_database.py`, health shows `"database_connected": true`
