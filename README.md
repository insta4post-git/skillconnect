# SkillConnect

A location-based service marketplace. **Providers** (electricians, tutors, plumbers, beauticians...) list their skills; **customers** search by skill and location, send a request, chat, and review the provider after the job.

**Live demo:** _add your Render link here after deployment_ (first load may take about a minute, free hosting sleeps)
**Source:** _add your GitHub link here_

## Features
- Sign-up and login for customers, providers and an admin; JWT login, strong-password rules, login rate limit
- Profiles with city and photo; provider skills, weekly availability and pricing
- Search by skill, category, city, minimum rating and "near me"
- Requests: one-time and regular (long-term); accept, reject, complete, cancel
- Chat per request; phone and email are shared only after the provider accepts
- Ratings and reviews after a completed job, shown on the provider's public profile
- Separate dashboards for customer, provider and admin; admin panel for users, providers, requests and skills

## Technology stack
| Part | Technology |
|---|---|
| Frontend | HTML, CSS, vanilla JavaScript |
| Backend | Python, FastAPI, Pydantic |
| Database | MySQL, SQLAlchemy ORM, PyMySQL |
| Security | bcrypt password hashing, JWT (PyJWT), role-based access |
| Docs and testing | Swagger (`/docs`), `scripts/audit_project.py`, `scripts/smoke_test.py` |
| Hosting | Render (app) + Aiven (MySQL), GitHub |

## Project structure
```
SkillConnect/
├── frontend/      HTML pages, css/, js/
├── backend/       FastAPI app (app/), create_*.py, seed_*.py, scripts/
├── database/      schema.sql (reference copy of the tables)
├── docs/          architecture, ER diagram, database, API, deployment, screenshots
├── render.yaml    deployment settings
├── .env.example   settings template (the real .env is never committed)
└── README.md
```

## Documentation
- [Architecture](docs/ARCHITECTURE.md)
- [ER diagram and request flow](docs/ER_DIAGRAM.md)
- [Database schema](docs/DATABASE.md) and [schema.sql](database/schema.sql)
- [API documentation](docs/API.md) (live: `/docs`)
- [Deployment guide](docs/DEPLOYMENT.md)
- [Screenshot list](docs/SCREENSHOTS.md)

## Screenshots
| | |
|---|---|
| ![Home](docs/screenshots/01-home.png) | ![Search](docs/screenshots/02-search.png) |
| ![Provider](docs/screenshots/03-provider-profile.png) | ![Chat](docs/screenshots/06-chat.png) |
| ![Customer dashboard](docs/screenshots/07-customer-dashboard.png) | ![Admin](docs/screenshots/09-admin.png) |

## Installation (Windows, PowerShell)
Needs Python 3.11+ and MySQL 8.
```powershell
git clone https://github.com/YOUR-NAME/SkillConnect.git
cd SkillConnect\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item ..\.env.example .env      # open backend\.env and fill in your values
python create_database.py
python create_tables.py
python seed_skills.py
python create_admin.py              # creates the admin account
python seed_demo.py                 # optional demo providers, customers and reviews
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000 (API docs: http://127.0.0.1:8000/docs).

Generate the `SECRET_KEY` with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

## Testing
```powershell
python scripts\audit_project.py   # security audit (no server needed)
python scripts\smoke_test.py      # end-to-end test (server must be running)
```

## Security
bcrypt password hashing, JWT with expiry and fixed algorithm, role checks on the server for every request, users can only open their own requests and chats, input validation with Pydantic, SQL only through the ORM (bound parameters), user text shown with `textContent` (no XSS), CORS and security headers, login/register rate limit, secrets only in `.env`.

## Demo flow (5 minutes)
1. Search "electrician", open a provider (rating, reviews, no phone/email).
2. Register a customer, send a one-time request.
3. Log in as the provider: accept it, chat.
4. After the job time: mark completed, then the customer reviews; the rating appears on the profile.
5. Log in as admin: dashboard numbers, users, requests, skills.

## Future scope
Real-time chat (WebSockets), online payments, email/SMS notifications, map-based search, provider verification, edit/delete reviews, account deactivation, cloud storage for photos, a mobile app.
