# Deployment (free tier)

**Plan:** one **Render** web service (runs FastAPI and serves the frontend) + one free **Aiven for MySQL** database.
Free plans change, so check the current limits on [render.com/pricing](https://render.com/pricing) and [Aiven's free MySQL page](https://aiven.io/free-mysql-database) before you start.

Known catches of free tiers (verified Sep 2026): Render's free service **sleeps after 15 minutes** without visits and needs about a minute to wake up, so open the site a few minutes before a demo. Free disks are **temporary**, so uploaded profile photos can disappear after a restart (the initial-letter avatar is shown instead). Aiven free MySQL has 1 GB storage and no credit card.

## 1. Database (Aiven)
1. Sign up at aiven.io, create a free **MySQL** service, wait until it is *Running*.
2. On the service page copy **Host, Port, User, Password, Database name** (`defaultdb`). Aiven requires SSL, and the backend must connect with it (see "SSL" below).
3. Keep these values private. They go only into Render's environment settings, never into GitHub.

## 2. Backend + frontend (Render)
1. Push the project to GitHub (see README, "GitHub").
2. On render.com: **New > Blueprint** (uses `render.yaml`) or **New > Web Service**, pick your repo.
   - Root directory: `backend`
   - Build command: `pip install -r requirements.txt`
   - Start command: `python create_tables.py && python seed_skills.py && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Under **Environment** add: `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE` (from Aiven), `SECRET_KEY` (a NEW random 48-char string, not your laptop's), `CORS_ORIGINS` (`https://YOUR-SERVICE.onrender.com`).
4. Deploy. When the log says "Application startup complete", open `https://YOUR-SERVICE.onrender.com/api/health`: it must show the database connected.

## 3. Create the admin account (once)
Render free plans have no shell, so run the script from your laptop, pointed at the production database:
1. Temporarily put the Aiven values into your local `backend/.env`.
2. `python create_admin.py` (type the admin password yourself).
3. Restore your local `.env` to the local MySQL values.

## SSL
Aiven needs an encrypted connection. If the backend cannot connect ("SSL connection error" / "Access denied ... insecure"), `app/database.py` must pass `connect_args={"ssl": {"ca": ...}}` (or `{"ssl_disabled": False}` style option for PyMySQL) to `create_engine`. Controlled by an optional `.env` setting so local MySQL still works unchanged.

## After deployment
Open the live link, register, search, send a request: same checks as `python scripts/smoke_test.py` (set `SC_BASE=https://YOUR-SERVICE.onrender.com`). Add demo data with `python seed_demo.py` pointed at the same database if you want a populated demo.
