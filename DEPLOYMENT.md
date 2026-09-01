# Deployment Guide

This project is designed for **self-hosted personal use**. Each user should deploy their own copy and keep their own Trading 212, Telegram and optional AI credentials in their own secret store.

The application is read-only and advisory. V1 contains no Trading 212 order-submission implementation.

> [!IMPORTANT]
> Prove the configuration and live read-only data locally before deploying. A cloud deployment is not a substitute for validating symbol mappings, account totals, cash and Telegram delivery.

## 1. Pre-deployment checklist

From a clean checkout:

```bash
pip install -e ".[dev]"
portfolio-monitor validate-config
portfolio-monitor init-db
ruff check app tests
mypy app
pytest -q
```

Then, with your own read-only credentials in `.env`:

```bash
portfolio-monitor resolve-symbols
portfolio-monitor smoke-test
portfolio-monitor test-market-data --symbol YOUR_CONFIGURED_SYMBOL
portfolio-monitor test-notification
portfolio-monitor run-scan
```

If AI is enabled:

```bash
portfolio-monitor test-ai
```

Keep:

```text
DRY_RUN=true
```

Do not deploy if the live Trading 212 account data does not match what you expect in the Trading 212 app.

---

## 2. Docker test

Build:

```bash
docker build -t portfolio-transition-monitor .
```

Run:

```bash
docker run --rm --env-file .env -p 8000:8000 portfolio-transition-monitor
```

Check:

```text
GET http://localhost:8000/healthz
GET http://localhost:8000/readyz
```

The Dockerfile defines a non-root application user by default.

---

## 3. Recommended production architecture

For the current SQLite-based V1 use:

```text
one application service
one persistent volume
one scheduler replica
```

Do not run multiple scheduler replicas unless you intentionally redesign the locking/persistence model for distributed workers.

The application service provides:

- health/readiness HTTP endpoints
- protected manual scan endpoint
- built-in hourly scheduler
- Trading 212 read-only polling
- Yahoo primary market data
- optional Twelve Data fallback
- optional AI review
- Telegram notifications
- SQLite persistence

---

## 4. Environment variables

Required for live Trading 212 operation:

```text
APP_ENV=production
TZ=Europe/London
TRADING212_ENV=live
TRADING212_API_KEY=...
TRADING212_API_SECRET=...
DATABASE_URL=sqlite:////data/portfolio_monitor.db
ADMIN_TOKEN=...
DRY_RUN=true
SCHEDULER_ENABLED=true
SCHEDULER_MINUTE=5
SCHEDULER_TEST_INTERVAL_SECONDS=0
```

Telegram alerts:

```text
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

Optional Twelve Data fallback:

```text
TWELVE_DATA_API_KEY=...
```

Optional NVIDIA NIM:

```text
AI_PROVIDER=nvidia
NVIDIA_API_KEY=...
NVIDIA_MODEL=...
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
```

Optional OpenRouter:

```text
AI_PROVIDER=openrouter
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=...
```

If AI is not required:

```text
AI_PROVIDER=disabled
```

Never put secrets in source code, Docker images, committed `.env` files or public issue reports.

---

## 5. Persistent SQLite storage

Production SQLite must not live only in the container filesystem.

Recommended path:

```text
DATABASE_URL=sqlite:////data/portfolio_monitor.db
```

Mount persistent storage at:

```text
/data
```

The database contains:

- scan history
- portfolio snapshots
- position snapshots
- alert fingerprints/dedupe state
- market-history cache
- provider health
- scan lock state

Restart/redeploy testing must prove this data survives replacement of the application container.

---

## 6. Railway deployment

A simple Railway setup is:

1. Create a new Railway project.
2. Connect your own repository copy.
3. Deploy using the included Dockerfile.
4. Add the environment variables from the previous section in Railway Variables.
5. Add one persistent volume mounted at `/data`.
6. Keep one service replica.
7. Generate a public domain only if you want remote health/admin endpoints.

The monitoring process itself does not require a public website.

### Railway volume UID caveat

The Docker image normally runs as a non-root user.

Some Railway persistent-volume configurations mount storage with ownership that prevents the image user from writing SQLite files. If you confirm a permission error on `/data`, Railway may require a runtime UID override such as:

```text
RAILWAY_RUN_UID=0
```

Use that only when required by the platform's volume permissions. Prefer the non-root Docker user whenever the mounted volume can be written safely without an override.

---

## 7. Other hosting providers

The same Docker image can run on platforms such as Render, Fly.io or a VPS if the platform provides:

- persistent storage for SQLite
- environment/secret variables
- an always-on process for the built-in scheduler
- outbound HTTPS access to Trading 212, Yahoo, Telegram and optional providers

Adapt the persistent volume path to the host while keeping `DATABASE_URL` pointed at that persistent path.

Do not deploy SQLite on ephemeral storage.

---

## 8. Market-data behaviour in production

Current provider order:

```text
Yahoo (primary)
    |
    | provider failure
    v
Twelve Data (optional fallback)
```

Yahoo quotes/history are attempted first.

If Yahoo fails and Twelve Data is configured for the symbol, Twelve Data is attempted.

If neither source is usable, the symbol is excluded from actionable evaluation. The application does not invent a price.

Daily market history is cached in SQLite and refreshed only when a newer completed exchange session requires it.

---

## 9. Production health checks

After deployment verify:

```text
GET /healthz -> 200
GET /readyz  -> 200
```

`/readyz` should confirm the expected dry-run/AI state without exposing credentials.

Then execute one manual scan from a secure service shell:

```bash
portfolio-monitor run-scan
```

A healthy result may simply be:

```text
NO ACTION
```

---

## 10. Telegram production test

Run from the deployed service/container:

```bash
portfolio-monitor test-notification
```

Confirm the test appears in Telegram.

Testing from your laptop is not enough if production will run in the cloud; verify outbound Telegram access from the actual deployed container.

---

## 11. AI production test

Only if AI is enabled:

```bash
portfolio-monitor test-ai
```

The result should satisfy the application's structured response schema.

The deterministic recommendation size remains the maximum; AI cannot enlarge it or submit a trade.

If AI is unstable, set:

```text
AI_PROVIDER=disabled
```

The deterministic monitor can continue without it.

---

## 12. Scheduler verification

Production settings:

```text
SCHEDULER_ENABLED=true
SCHEDULER_MINUTE=5
SCHEDULER_TEST_INTERVAL_SECONDS=0
```

The built-in scheduler should create roughly one scan around minute 5 of each hour.

Do not infer scheduler failure merely because Telegram is silent. Inspect `scan_runs`.

Example:

```bash
python -c "from app.config import get_settings; from app.db.session import Database; from app.db.models import ScanRun; from sqlalchemy import select; db=Database(get_settings().database_url); s=db.Session(); rows=s.scalars(select(ScanRun).order_by(ScanRun.id.desc()).limit(10)).all(); [print((r.started_at,r.status,r.candidate_count,r.notification_sent)) for r in rows]; s.close(); db.close()"
```

At least two consecutive scheduled runs should appear before relying on unattended operation.

---

## 13. Persistence/restart test

Before restart:

1. Note the current number/latest IDs of `scan_runs`.
2. Confirm provider-health or history-cache records exist.

Restart or redeploy the service.

After restart:

1. Confirm `/healthz` and `/readyz` recover.
2. Confirm previous scan records still exist.
3. Confirm the scheduler creates a new scan.
4. Confirm alert/dedupe records remain.

A restart that loses SQLite history is a failed production deployment.

---

## 14. Protected admin endpoint

The manual HTTP scan endpoint requires:

```text
X-Admin-Token: <ADMIN_TOKEN>
```

Do not expose the token in frontend code, URLs or logs.

Requests with missing or incorrect tokens should be rejected.

The public health/readiness endpoints should not expose private portfolio contents.

---

## 15. Security acceptance checks

Before publishing/deploying a release, run:

```bash
ruff check app tests
mypy app
pytest -q
python -m pip_audit
```

If Gitleaks is installed:

```bash
gitleaks git . --redact --no-banner
```

Confirm `.env` is ignored:

```bash
git check-ignore .env
```

Confirm the Trading 212 package has no obvious HTTP write calls:

```bash
git grep -nE "\.(post|put|patch|delete)\(" -- app/trading212
```

The expected result is no matching Trading 212 write call.

See [`SECURITY.md`](SECURITY.md) for the project's security model and reporting guidance.

---

## 16. Production acceptance checklist

A deployment is ready for unattended advisory monitoring only when all of the following are true:

- configuration validates
- automated tests pass
- `DRY_RUN=true`
- Trading 212 credentials are read-only
- Trading 212 smoke-test values match the user's account
- symbol mappings are reviewed
- market data succeeds for configured symbols
- Yahoo failure fallback is tested when Twelve Data is configured
- Telegram test succeeds from the production container
- AI test succeeds if AI is enabled
- `/healthz` and `/readyz` return 200
- manual production scan succeeds
- scheduler creates hourly scan records
- no overlapping duplicate scans occur
- persistent SQLite data survives restart/redeploy
- no Trading 212 order-submission implementation exists

If any safety-critical input is unavailable or stale, the correct operational result is `NO ACTION` rather than an invented recommendation.
