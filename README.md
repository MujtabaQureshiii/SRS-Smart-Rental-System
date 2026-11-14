> **For GitHub/Render cloud deployment, open `DEPLOY_STEP_BY_STEP.md` first.** Keep source functionality and Cork styling unchanged.

# Smart Rental System — Cork-inspired University Demonstration Web App

**Borrow Smart. Study Better.**

This is a working, responsive FastAPI + SQLAlchemy application using SQLite for local backup/demo and **PostgreSQL in Render cloud deployment**. The design takes **layout inspiration from Cork**; no commercial Cork theme source files are included. Styling is original. Your university SRS business-plan categories, costs, durations, operator-controlled payment and return process are retained.

## Quick start (Windows)

1. Install Python 3.11+ from https://python.org/ and check "Add Python to PATH".
2. Extract the ZIP and open `SRS_Web_Application`.
3. Run `setup_windows.bat` once to create a virtual environment and install requirements.
4. Run `create_operator_windows.bat` to create an account (password at least 12 characters; not displayed while typed).
5. Run `download_photos_windows.bat` while online to save actual photo samples from Wikimedia Commons, if desired.
6. Run `start_windows.bat`; browse http://127.0.0.1:8000/operator/login.
7. Sign in and select **Station QR Code** in the navigation. Print or display its QR code.
8. To scan the QR on a separate smartphone, stop the ordinary local server and run `start_lan_windows.bat`. Find your PC's IPv4 address (such as `192.168.1.20`) from the shown `ipconfig` output, and open the operator panel from `http://192.168.1.20:8000/operator/login` on the PC. On **Station QR Code**, enter `http://192.168.1.20:8000` as the base URL and regenerate the QR. The phone and laptop must share Wi-Fi, and Windows Firewall must permit the private-network connection.
9. Student scans QR with the **normal phone camera**. The QR opens a special station URL and enables the registration page.
10. Student registers; the operator checks the physical ID in **Students → Verify physical ID**. Student refreshes the **Verification** screen, then selects an item and duration.
11. Student selects payment method, makes payment externally (cash/JazzCash/EasyPaisa), and operator confirms receipt and issues a tagged item in **Rentals / Returns**.
12. Student sees the exact due time after actual item issuance. Operator records return condition and deposit release when complete.

For existing data/accounts, READ `UPDATE_EXISTING_INSTALLATION.md` BEFORE installing.

## Business scope

Six types, five main categories (22 initial assets): basic and scientific calculators (5 combined), USB drives (3), power banks (4), chargers/cables (5), and umbrellas (5). Business-plan rates remain in the database.

The system includes registration, unique asset IDs, operator ID verification, inventory, payment confirmation, tracked issue/due times, overdue controls, returns/inspection, held/released deposits, disputes/extensions, expenses, daily checks, operator access audit, and restricted actions. No automatic dispenser, student password account, or online payment gateway was added.

## QR versus wallet payment

**Station QR = access to the SRS student web registration process.** It's generated from a station token and is rendered as a real printable PNG. Students scan using a smartphone camera; no in-browser camera scanner is required. The secure route sets their station-entry session. Guessing direct `/register` won't bypass station entry.

**Payment = cash/JazzCash/EasyPaisa**, recorded as pending and approved by an operator before issuance. A QR is not, by itself, a live JazzCash or EasyPaisa merchant payment integration. No live payment gateway has been connected or simulated as though actual funds were transferred.

## Product photographs

The item cards use real sample photographs from Wikimedia Commons (authors and Creative Commons licenses in `PHOTO_CREDITS.md`). Download while online via `download_photos_windows.bat` (or `python download_product_photos.py`), to store them under `static/photos/` for offline use. If local photos are missing, the browser tries the same hosted photos; an icon placeholder appears if that also fails. Photos are generic examples, not a guarantee of a specific brand/model.

## Database & security

- SQLite `srs.db` automatically created/updated on first launch; retains students, operators, payments, rentals, deposits and asset records. Never delete your existing database.
- **NEW:** `student_verifications` table (non-destructive create-if-not-exists) tracks the required ID approval. The original tables are not dropped.
- `.srs_secret` signs user sessions; `.srs_station_token` gives station QR continuity. Keep these private and copy them with your database during upgrades.
- Passwords are PBKDF2-SHA256 hashed. Operator accounts require passwords of 12+ characters.
- Student password login and university single sign-on are not provided; physical university ID checking happens at the supervised station. For internet exposure, university approval, security assessment, HTTPS, backups, and stronger student session authentication are needed.
- An optional PostgreSQL deployment can be configured with `DATABASE_URL` + `psycopg[binary]`, but has not been tested here. Switching databases does not migrate existing SQLite data.
- External SMS delivery requires separate optional provider configuration. WhatsApp delivery is not implemented. The included operator reminder queue works locally.
- Daily cap, deposit amounts and umbrella session length are not fully defined in the source documents. Current sample assumes a provisional umbrella 3-hour session and 2 basic / 3 scientific calculators, both documented assumptions.

## Test

Install `pytest` and `httpx` if required, then run `python -m pytest -q tests/test_app.py`. See `docs/TEST_REPORT.md` for coverage and limitations.
