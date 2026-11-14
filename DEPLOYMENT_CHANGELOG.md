# SRS Render & PostgreSQL final packaging

All student/operator HTML templates, frontend styles, JavaScript, business workflow route handlers, pricing, item records, and dashboard logic remain unchanged from the preceding Cork QR-verified package.

Deployment-only adjustments:
- Render cloud detection and explicit PostgreSQL-only requirement in cloud mode (prevents silent fallback to ephemeral SQLite).
- Require strong persisted session secret, station QR token, and HTTPS cookie setting on Render.
- QR generator defaults to `SRS_PUBLIC_URL` when provided, to encode correct HTTPS hostname regardless of proxy-forwarded headers.
- Included generated six sample JPGs locally, original Cork UI assets, `.gitignore`, `.env.example`, `python-version`, and deployment instructions.
- Local development/offline backup still defaults to SQLite when not in production; cloud database holds all new deployed records.
- Initial operator can be bootstrapped through Render environment variables only if operators table empty; remove them after verified first login.

Scope notes:
- No automatic gateway payments, WhatsApp messages, email verification, or new rental features were added.
- Local SQLite records are *not* automatically transferred to PostgreSQL; start with a fresh hosted database for demonstration.
- Manual phone-to-public-server and hosted PostgreSQL integration testing must be completed by the user after deployment.
