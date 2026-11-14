# SRS — GitHub + Render PostgreSQL: complete deployment walkthrough

**Use these exact files; the code already contains the full Cork UI and six offline JPG product samples.** These directions are for an initial demonstration using invented student details, not a security-approved production university rollout.

## STEP 0 — Save the latest package and choose a fresh cloud database

- Extract the ZIP; open the inner `SRS_Web_Application` folder. It contains `app.py`, `requirements.txt`, `templates/`, `static/`, and `tests/`.
- This package does not include any personal local SQLite data or your previous Windows operator credentials. The hosted operator will be created separately.
- Keep a local backup of your existing project for offline demonstration. New Render database will start with 22 assets and no students.
- Never share actual passwords, secret tokens, or DB URLs in GitHub or publicly.

## STEP 1 — Create GitHub private repository

1. Go to https://github.com and sign in / sign up.
2. Click **+ > New repository**. Name it `srs-smart-rental-system` and select **Private**; leave *Initialize README* unchecked.
3. Click **Create repository**.
4. Upload the **contents** of inner `SRS_Web_Application` folder to the repo root, not the ZIP and not a parent wrapper folder. Use GitHub **Add file > Upload files** for a small upload; use GitHub Desktop if directory upload behaves unexpectedly.
5. The repo root must visibly contain `app.py`, `requirements.txt`, `templates`, `static`, and `.python-version`.
6. Verify there are **no** `.srs_secret`, `.srs_station_token`, `srs.db`, `.venv`, or `.env` files; don't manually override `.gitignore`.
7. Commit the files to default branch **main**.

**Alternative Git commands**, from inside the inner project directory (after `git` is installed):

```
git init
git add .
git commit -m "Deploy-ready SRS Cork application"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/srs-smart-rental-system.git
git push -u origin main
```

Use your own GitHub username and browser authentication, never paste GitHub credentials into source code.

## STEP 2 — Create Render PostgreSQL

1. Sign in at https://dashboard.render.com (you can use GitHub login).
2. Choose **New > Postgres**.
3. Database name example: `srs-db`; choose a region, and for one-time demo choose Free if currently offered.
4. Wait until the database is **Available**.
5. Open **Connect** and copy **Internal Database URL** securely. Do **not** commit it to GitHub.
6. Set your web service to the *same region* as the database. Render free PostgreSQL expires after 30 days and has no managed backups, so use fake data and keep an offline demo backup.

## STEP 3 — Create Render Web Service

1. Select **New > Web Service > Git Provider > GitHub**, grant repository access and choose `srs-smart-rental-system`.
2. Select **Python** runtime and the `main` branch.
3. Name the service, e.g. `srs-campus-unique-name` (Render determines whether name is available).
4. Region: same as the database.
5. **Root Directory:** blank if `app.py` is at repository root; otherwise set to `SRS_Web_Application` when that is the nested directory containing `app.py`.
6. **Build Command**: `pip install -r requirements.txt`
7. **Start Command**: `uvicorn app:app --host 0.0.0.0 --port $PORT --proxy-headers`
8. Choose the desired instance plan (Free if offered). No separate static site is needed; FastAPI serves the UI and images.

## STEP 4 — Set Render environment variables BEFORE first deployment

In **Web Service > Environment**, add each item (the literal key is exact):

| Key | Value |
|---|---|
| `DATABASE_URL` | Your Render Postgres **Internal Database URL** |
| `SRS_DEPLOYMENT_MODE` | `production` |
| `SRS_SECRET_KEY` | First secure random string, 32+ characters |
| `SRS_STATION_TOKEN` | Second **different** secure random string, 32+ characters |
| `SRS_HTTPS` | `1` |
| `SRS_PUBLIC_URL` | Your actual `https://YOUR-SERVICE.onrender.com` URL |
| `SRS_INITIAL_OPERATOR_USER` | Desired admin username, e.g. `srsadmin` |
| `SRS_INITIAL_OPERATOR_PASSWORD` | Your own unique password, 12+ characters |

Generate two random strings locally in PowerShell / CMD by running twice (copy results privately):

```
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

The `SRS_PUBLIC_URL` can be added once Render shows its exact assigned `.onrender.com` hostname; the initial deployment does not strictly require this variable, but set it **before generating the station QR**.

**Warning**: Never upload a filled `.env` or display private variables in class. Keep the `SRS_SECRET_KEY` and `SRS_STATION_TOKEN` unchanged across future deploys, or sessions/old QR will be invalidated.

## STEP 5 — Deploy

1. Click **Create Web Service / Deploy**. Render installs dependencies, starts FastAPI, creates PostgreSQL tables, seeds 22 initial assets, and creates the first operator if none exists.
2. In Render > **Logs**, ensure the service reports **Live** / no errors. If an environment variable is missing, production startup fails deliberately instead of creating a temporary SQLite database.
3. Open `https://YOUR-SERVICE.onrender.com/health`. For a fresh database the result should be `{"status":"ok","categories":6,"assets":22}`.
4. Open `https://YOUR-SERVICE.onrender.com/operator/login`, sign in using `SRS_INITIAL_OPERATOR_USER` and `SRS_INITIAL_OPERATOR_PASSWORD`.
5. Once you confirm successful login and database retention, **remove only** `SRS_INITIAL_OPERATOR_USER` and `SRS_INITIAL_OPERATOR_PASSWORD` from Render > Environment, and save/redeploy; this removes plain bootstrap credentials from deployment settings. The operator account persists as a password hash in PostgreSQL.
6. Login again with the same credentials; do not rotate the session or QR secrets.

## STEP 6 — Generate a permanent public QR

1. Log in to **Operator Panel > Station QR Code**.
2. Verify the Base URL is the **real HTTPS Render URL**, not `localhost` or `192.168...`; if needed enter it manually.
3. Click to generate / display QR. Student scans with the normal phone camera using a different network or mobile data.
4. QR opens the station registration route on the hosted site. After student registration, the operator checks physical university ID. The student then selects item/rental duration. Operator manually verifies cash/JazzCash/EasyPaisa payment and issues item, then records return.
5. Do not mistake station-entrance QR for actual JazzCash/EasyPaisa merchant QR payment integration: no live payment processor is connected.

## STEP 7 — Presentation rehearsal / retention check

1. Log in on laptop and create a **fictional student** through QR on phone.
2. Verify in operator **Students**, approve physical ID, refresh phone, choose product, request rental, verify payment on laptop, issue then return item.
3. Confirm sample JPG photos display, status and due time update, finance/return records update.
4. Wait 20+ minutes, reopen the sleeping site (it may take a minute to start) and ensure previously saved student/operator/rental records are still present.
5. Repeat the next day from different phone/network. Prior to presentation, open the website 15–30 minutes early to wake the free host.
6. Keep a local offline version on friend's laptop and a tested hotspot as backup, because Render free service and university internet can fail independently.

## STEP 8 — Troubleshooting

- **Deployment rejects SQLite / DATABASE_URL missing**: ensure `DATABASE_URL` is the correct PostgreSQL internal URL from Render and not `sqlite:///...`.
- **Session or QR token missing**: create `SRS_SECRET_KEY` / `SRS_STATION_TOKEN` as 32+ char random values and set `SRS_HTTPS=1`.
- **`ModuleNotFoundError: psycopg`**: confirm `requirements.txt` includes `psycopg[binary]` and is committed; retry deploy.
- **Bad SQL / connection refused**: check database status, network region, and exact Internal Database URL.
- **No operator**: check bootstrap credentials existed before first successful startup and inspect Render logs; bootstrap runs only if no operators already exist.
- **Bad QR URL**: set `SRS_PUBLIC_URL` to actual HTTPS hostname; regenerate QR via Admin > Station QR Code.
- **Cannot access on phone**: use public `https://` hostname and internet connection, not laptop IP.
- **Photos absent**: verify six `.jpg` files are present under `static/photos/` in the repository; this ZIP already bundles them.
- **Free sleep**: on inactivity, first request wakes the service; the database should retain records as long as PostgreSQL remains available.
- **Existing local SQLite student/account data**: it is not automatically migrated; this release is intentionally a fresh deployment, not a database conversion/migration tool.
- **Safety**: avoid real student data without university permission and security review; the current QR/student identification model assumes supervised physical verification.

## Free-plan limits (verify before demo)

As of Nov 2026, Render documentation lists free PostgreSQL as 1 GB storage, 30-day expiration, no managed backups; free web service normally sleeps after 15 minutes idle. Always check the Render dashboard for current limits/availability. Official docs:
- https://render.com/docs/free
- https://render.com/docs/deploy-fastapi
- https://render.com/docs/configure-environment-variables
