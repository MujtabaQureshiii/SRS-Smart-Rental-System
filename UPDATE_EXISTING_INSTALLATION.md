# Updating an existing SRS installation — preserve your data

This version applies the approved Cork-inspired interface and adds the **actual station QR code entry and an operator ID-verification gate**. Your existing rentals, inventory, payment and return endpoints remain. The previous user records and accounts can remain in the same database.

1. **Stop** the old `start_windows.bat` server (Ctrl+C).
2. **Back up the entire old SRS folder**, especially its `srs.db` and `.srs_secret` files.
3. Extract this ZIP into a NEW folder; do not merge over the old running installation.
4. Copy `srs.db` and `.srs_secret` **from your old folder** into the new `SRS_Web_Application` folder. If you previously generated and distributed a station QR, copy `.srs_station_token` too; otherwise the QR will be regenerated with a new code.
5. Run `setup_windows.bat` (it installs updated requirements including `qrcode[pil]`).
6. Run `download_photos_windows.bat` while online to save the sample photos for offline use.
7. Run `start_windows.bat`, then log in using **the same operator username and password**.
8. From the operator dashboard, open **Station QR Code**. If scanning with a phone, instead use `start_lan_windows.bat` and enter your computer's LAN IP as the QR base URL (both devices on same Wi-Fi).
9. Students must now scan that QR and register, **then an operator must approve their physical ID in the Students screen BEFORE they can select an item**. Payment confirmation still happens before issuance.

On first run the SQLAlchemy application automatically creates the new `student_verifications` table in the existing database without deleting old tables. Old students are not silently marked verified: they must complete the station QR and physical-ID check.

**Important:** A station QR is NOT a payment gateway. The business plan uses the QR to open registration and track rentals; cash, JazzCash and EasyPaisa are still manually verified by the operator. No live external provider keys are included.

**Product photos:** Real sample photographs from Wikimedia Commons are downloaded by the optional photo script with attribution in `PHOTO_CREDITS.md`. If you have no internet and haven't downloaded the photos, a neutral icon fallback is shown. The physical rental stock is unchanged.
