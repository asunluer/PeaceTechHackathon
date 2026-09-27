# GUARDIA

GUARDIA preserves publicly observable online abuse reports for NGO review. The two front ends have separate audiences: the **mobile app is only for victims**, who share a public post to GUARDIA from any social app; the **web app is only for NGO staff** (investigators and administrators), who review cases and contact victims by email. The API creates a case, queues a Playwright capture, encrypts original files, records SHA-256 hashes, and lets an assigned investigator review and export the case.

This is an MVP. Its output is a structured preservation record, not a forensic certification or a legal admissibility claim.

## Services

- `apps/mobile`: Flutter Android/iOS app for victims: self-registration, sign-in, a post-login "How to report" dialog, share target that submits immediately, and a receipt with capture status and an optional "What happened?" description. Uses Dio, Riverpod, GoRouter, `flutter_secure_storage`, and `share_handler`.
- `apps/web`: SvelteKit NGO/admin workspace. Victim accounts are refused at sign-in and any existing victim session is ended. Case pages show the victim's registered email so staff can make contact. The API token is kept server-side in an HTTP-only, SameSite Strict cookie; server routes proxy every authorized API call, evidence file download, and PDF export, so the browser never talks to the API directly. In deployment, set `API_INTERNAL_URL` (the FastAPI base URL) and `ORIGIN` (the public HTTPS origin).
- `apps/api`: FastAPI auth, case/evidence APIs, migrations, PDF export and capture worker. `app/application` holds use cases, `app/infrastructure` holds PostgreSQL and encrypted object storage, `app/worker/capture.py` runs the Playwright worker. Main endpoints: `/api/v1/auth/*`, `/api/v1/users`, `/api/v1/reports`, `/api/v1/cases` (including `?q=` search), `/api/v1/evidence/{id}`, `/api/v1/cases/{id}/report.pdf`. Configured through `GUARDIA_DB_*`, `GUARDIA_JWT_SECRET`, `GUARDIA_STORAGE_ENCRYPTION_KEY`, and `GUARDIA_STORAGE_ROOT` (Compose sets these from the root `.env`).
- `docker`: local deployment images for API, web and worker.
- `shared`: documents the API contract boundary. The API's OpenAPI document is the source of truth.

## Start locally

1. Copy `.env.example` to `.env`. Set separate, random `POSTGRES_PASSWORD`, `JWT_SECRET` (at least 32 bytes), and `STORAGE_ENCRYPTION_KEY` (exactly 32 UTF-8 bytes). Keep `.env` private.
2. Run `docker compose up --build -d` in this directory. The migration job must exit successfully; `docker compose ps -a` shows service health. The web app is at `http://localhost:3000`, and API health is at `http://localhost:8000/api/v1/health`.
3. Provision the first administrator: `docker compose exec api python -m app.cli.create_admin --email admin@example.org`. Enter a unique password at the prompt.
4. Sign in as the administrator on the web, then create NGO investigator accounts under **Users**. Victims create their own accounts in the mobile app (`POST /api/v1/auth/register`, which can only ever create a victim account). Assign a submitted case to an investigator from that case page.

Staff can change their password from the web account page, victims from the mobile app. Changing it revokes existing access tokens, so they must sign in again.

Set `WEB_ORIGIN` in `.env` when the web app is served from a different origin. It must match the browser-facing URL so SvelteKit can validate form requests.

PostgreSQL and encrypted evidence use named Docker volumes. The API and web ports bind to local loopback only.

## Mobile setup

From `apps/mobile`, run `flutter pub get` and `flutter analyze`. The default API URL, `http://10.0.2.2:8000/api/v1`, works for an Android emulator reaching this machine. For an iOS simulator use `flutter run --dart-define=GUARDIA_API_URL=http://127.0.0.1:8000/api/v1`. For a physical device, set an HTTPS URL reachable from that device. Development HTTP allowances may need platform configuration; production deployments require HTTPS.

Running with `flutter run -d chrome` (Flutter web) calls the API cross-origin from whatever `localhost` port the dev server picks. The API allows this via `CORS_ORIGINS` in `.env` (default `*`; the app authenticates with a Bearer token it attaches itself, never a cookie, so a permissive origin list here is not a CSRF risk). Narrow it to your app's real origin(s), comma-separated, before any shared or production deployment.

Android registers an `ACTION_SEND` text share target. iOS includes a Share Extension target, CocoaPods integration and shared App Group entitlements. To install on an iOS device, open the Xcode workspace, select a signing team for both Runner and ShareExtension, and register `group.org.guardia.guardia` for both targets. The bundle IDs and group ID can be changed together for your organization. Full Xcode is required to build and sign the iOS targets.

## Workflow

1. A victim installs the app, registers with an email address the NGO can contact, and sees a "How to report" dialog after signing in. In Instagram, Facebook, TikTok, X, Reddit or Threads she taps **Share → GUARDIA**; the link is submitted immediately with no form. If she is signed out, the link waits until she signs in. The receipt shows the capture status and lets her add an optional description. `POST /api/v1/reports` atomically creates a case, submitted-link record, queued evidence record, and audit event.
2. The worker resolves and screens public addresses, loads the page in Chromium, and captures HTML, a full-page screenshot, a viewport screenshot, visible text and available metadata. Each original file is encrypted with AES-256-GCM on a write-once volume. A SHA-256 manifest identifies the package. Failed captures retain a failure reason.
3. Administrators see all cases and assign investigators; investigators see only assigned cases. Case pages show the victim's contact email (`GET /api/v1/cases/{id}/contact`, staff only), capture status, hashes, downloadable files, an inline full-page and focused screenshot preview, a sandboxed HTML snapshot viewer (`sandbox=""` iframe, no scripts or cookies shared with the app), timelines, notes and audits. Case and evidence lists have page navigation. Cases can be searched (`?q=` on the case list) across case text and captured evidence.
4. Investigators and administrators can download a PDF with the case statement, timeline, evidence metadata, and file hashes.

Captured files, submitted links, notes and audit logs have database rules that reject updates and deletes. Case archival is a status change; it does not delete evidence. File downloads verify the SHA-256 digest after decryption.

## Checks

- API: from `apps/api`, install `requirements-dev.txt` in a virtual environment and run `python -m pytest -q`.
- Web: from `apps/web`, run `npm ci`, `npm run check`, and `npm run build`.
- Flutter: from `apps/mobile`, run `flutter pub get`, `flutter analyze`, `flutter test`, and `flutter build apk --debug`.
- Database: `docker compose run --rm migrate alembic check` after migration.
- An isolated Compose smoke test is in `apps/api/tests/smoke_integration.py`; it exercises report submission, access rules, capture, encrypted file downloads and PDF generation against a disposable database.
- GitHub Actions runs API tests, web checks/build, Android checks/build, and an iOS simulator build.

## Deployment boundary

The local Compose stack is for development. Before Internet exposure, add HTTPS, sign-in and sign-up rate limiting (victim registration is open, so also consider email verification to stop mass account creation), outbound network controls for the browser worker, backups and key rotation, monitoring, and a retention/deletion policy approved for the jurisdiction. In production mode the worker refuses to start without `CAPTURE_PROXY_URL`; that proxy must filter resolved destinations at connection time, and the worker network must prevent direct egress. DNS screening alone does not fully prevent DNS rebinding. The worker may not capture pages requiring authentication or blocking automation. API access tokens expire after 15 minutes by default; the mobile app asks the user to sign in again after expiry.
