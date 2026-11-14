# SRS Web Application — GitHub + Render deployment guide

This deployment-ready edition uses the same SRS rental features as the previous Cork-themed ZIP. Changes limited to deployment support: PostgreSQL driver/URL compatibility, persistent QR token through environment variable, initial operator creation through environment variables, and six bundled JPG rental product images.

## A. Prepare locally
1. Keep your existing installation backed up. This ZIP does **not** contain or migrate your local database (`srs.db`) or operator accounts.
2. Extract ZIP and locate the **inner** `SRS_Web_Application` directory that contains `app.py`, `requirements.txt`, `static/`, and `templates/`.
3. Never upload: `srs.db`, `.srs_secret`, `.srs_station_token`, `.env`, `.venv/`, or any real student personal data. The `.gitignore` excludes these.
4. Use a private GitHub repository where possible.

## B. GitHub upload using browser
1. Sign in at https://github.com and choose New repository.
2. Name `srs-smart-rental-system`, choose **Private**, do not initialize README/gitignore/license, then Create repository.
3. On the empty repository, choose `uploading an existing file` (or Add file → Upload files).
4. Drag the **contents of** `SRS_Web_Application` (not a single ZIP). Check `app.py`, `requirements.txt`, `templates/`, and `static/` appear at the repository root. GitHub's browser upload may have file/size restrictions; if it cannot upload folders, use GitHub Desktop or Git CLI.
5. Click Commit changes.

Alternative Git CLI from inside the `SRS_Web_Application` folder:
```
git init
git add .
git commit -m "Initial SRS cloud-ready application"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/srs-smart-rental-system.git
git push -u origin main
```
(Complete GitHub authentication through your browser / credential manager.)

## C. Create Render PostgreSQL
1. Visit https://dashboard.render.com; create an account or sign in.
2. New → Postgres; name `srs-db`; choose a region and plan; create database.
3. Copy the **Internal Database URL** (same region/workspace as the web service).
4. Free Postgres expires after 30 days and lacks managed backups; use a paid persistent database for real use.

## D. Create Render Web Service
1. Render Dashboard → New → Web Service → connect GitHub → choose `srs-smart-rental-system`.
2. Set environment to Python, branch `main`, and if files are nested set Root Directory to `SRS_Web_Application` (otherwise leave blank).
3. Build: `pip install -r requirements.txt`
4. Start: `uvicorn app:app --host 0.0.0.0 --port $PORT`
5. Choose a plan; Free is suitable only for demonstrations (may sleep after inactivity).
6. Set Environment variables **before first deployment**:
   - `DATABASE_URL` = Render PostgreSQL Internal Database URL
   - `SRS_SECRET_KEY` = long secure random token (generate locally using Python secrets.token_urlsafe(48))
   - `SRS_STATION_TOKEN` = a **different** long secure random token (>=32 characters)
   - `SRS_HTTPS` = `1`
   - `SRS_INITIAL_OPERATOR_USER` = new operator username
   - `SRS_INITIAL_OPERATOR_PASSWORD` = new strong password (>=12 chars)
7. Deploy and monitor build/runtime logs. On startup it creates the tables, seeds 22 items, and only creates the initial operator if there are zero operators.
8. Once the operator account is created, delete **only** `SRS_INITIAL_OPERATOR_USER` and `SRS_INITIAL_OPERATOR_PASSWORD` from Render environment, then save/deploy. Keep database URL, secret key, HTTPS, and QR token unchanged.
9. Health check: `https://YOUR-NAME.onrender.com/health` should show `status: ok`, `categories: 6`, `assets: 22` on a new database. These counts change only with inventory/category changes.
10. Operator: `https://YOUR-NAME.onrender.com/operator/login`.
11. Log in → Station QR Code → use the HTTPS Render website URL → generate QR → scan with a phone on mobile data. Student registers and waits for operator's physical ID check, then rents an item; operator verifies payments and returns.

## E. After launch — privacy and reliability
- The QR launches the student site; it does not collect a live JazzCash/EasyPaisa QR payment. The operator still manually verifies payment.
- Real student information requires university approval, HTTPS, backups, a retention policy, and a proper security review; use synthetic data for demonstration first.
- Current app's student flow uses a QR session and enrollment/department checks rather than university SSO. QR access does not prove a person's identity; the operator must physically verify ID.
- Free Render web services sleep after inactivity, so the first QR open may take extra time.
- Render free local filesystem is ephemeral; do not store a production database in SQLite on a free web service.
- On the Free plan, PostgreSQL expires after 30 days, and its data may be lost if not upgraded; plan accordingly.
- The app queues due reminders for operator action, but does not automatically deliver real WhatsApp messages.
- New code pushes to the connected main branch can automatically trigger redeployment.

## F. Troubleshooting
- `ModuleNotFoundError: psycopg`: ensure the updated `requirements.txt` containing `psycopg[binary]` is in your GitHub repository.
- `could not connect` to DB: verify `DATABASE_URL`, Postgres status, region, and correct environment variables.
- `No such table`: ensure the app completed startup and has database privileges.
- Can't log in: check that initial operator env variables were configured for the first successful startup and the database was attached; if account already exists, bootstrap does not recreate it.
- Old QR invalid: QR depends on `SRS_STATION_TOKEN` and hostname; never rotate the station token without regenerating and reprinting QR codes.
- Product images missing: confirm `static/photos/*.jpg` was committed to GitHub (the six files are bundled in this edition).
