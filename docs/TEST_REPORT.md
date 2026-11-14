# SRS Cork QR Upgrade — Validation Report

- 10 FastAPI/SQLAlchemy pytest integration/regression tests passed using disposable SQLite.
- Tests cover QR-gated registration, invalid station codes, physical-ID verification gate before item selection, operator payment check before issuance, return/inspection/deposit release, CSRF, operator access, dual approval, overdue status, login audit, rental dashboard data, UI assets and routes.
- Station QR PNG endpoint validated, and its encoded URL was actually decoded with OpenCV QRCodeDetector in a separate check. Actual smartphone camera and private LAN access were not testable here.
- The UI is an original Cork-inspired interpretation, not the commercial Cork theme or a pixel-perfect licensed copy.
- Browser navigation to the local HTTP development server is blocked by environment restrictions. HTTP routes and forms were exercised with the FastAPI TestClient. Do not confuse automated API testing with physical device/browser acceptance testing.
- Actual Wikimedia photo download blocked by environment network access. User can run `download_photos_windows.bat` when online; otherwise remote browser image or placeholder may show. Attribution is in PHOTO_CREDITS.md.
- Real JazzCash/EasyPaisa transfers, WhatsApp/SMS delivery, HOD escalation authority, and PostgreSQL deployment remain untested/unintegrated external requirements.

- CSS-only visual previews of actual Jinja pages rendered at 1440px and 390px using headless Chromium `set_content` (local server browsing blocked); no horizontal overflow observed. Offline product fallback shown in these previews.
