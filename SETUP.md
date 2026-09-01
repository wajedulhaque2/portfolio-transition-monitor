# Portfolio Transition Monitor — Setup Guide

This guide is for people running their **own self-hosted copy** of Portfolio Transition Monitor.

The application is read-only and advisory. It reads Trading 212 account data, compares the live portfolio with a target allocation you define, checks market pullbacks/strength, and can send Telegram alerts when a transition may be worth reviewing.

**It does not place trades and V1 contains no Trading 212 order-submission implementation.**

> [!IMPORTANT]
> This project is software, not investment advice. The example portfolio and thresholds shipped with the repository are illustrative only. Replace them with your own strategy before connecting live account data.

> [!NOTE]
> V1 currently assumes a GBP Trading 212 account for portfolio-value calculations, sizing and alert labels. Configuration validation rejects other account currencies until the money model is generalized.

## Recommended order

1. Install the project without credentials.
2. Replace the example portfolio configuration with your own targets and thresholds.
3. Run configuration validation and automated tests.
4. Create Trading 212 **read-only** API credentials.
5. Resolve and review Trading 212 symbol mappings.
6. Compare the live smoke-test output with the Trading 212 app.
7. Test market data.
8. Add Telegram and test delivery.
9. Run manual scans with `DRY_RUN=true`.
10. Optionally configure AI review.
11. Enable the scheduler only after all previous checks pass.
12. Optionally deploy your own instance to Railway or another host.

---

## 1. Prerequisites

Install:

- Python 3.12 or newer
- Git
- optional: Docker Desktop
- optional: Railway CLI if you plan to deploy to Railway

Check Python:

```bash
python --version
```

On Windows:

```powershell
py --version
```

---

## 2. Clone the repository

Once the public repository exists, clone it:

```bash
git clone YOUR_PUBLIC_REPOSITORY_URL
cd portfolio-transition-monitor
```

If you downloaded a ZIP instead, extract it and open a terminal in the extracted project directory.

---

## 3. Create a virtual environment

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation for the current session:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

## 4. Install the project

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Confirm the command-line interface is available:

```bash
portfolio-monitor --help
```

---

## 5. Create `.env`

### Windows PowerShell

```powershell
Copy-Item .env.example .env
```

### macOS / Linux

```bash
cp .env.example .env
```

Keep the initial development settings conservative:

```text
APP_ENV=development
TZ=Europe/London
TRADING212_ENV=demo
AI_PROVIDER=disabled
DATABASE_URL=sqlite:///./portfolio_monitor.db
DRY_RUN=true
SCHEDULER_ENABLED=false
SCHEDULER_MINUTE=5
SCHEDULER_TEST_INTERVAL_SECONDS=0
```

Generate an admin token:

```bash
portfolio-monitor generate-admin-token
```

Put the generated value in:

```text
ADMIN_TOKEN=...
```

Never commit `.env` and never paste API keys, Telegram tokens, account identifiers or admin tokens into issues or public logs.

---

## 6. Configure your portfolio transition

The strategy is controlled by:

```text
config/portfolio.yaml
config/thresholds.yaml
config/symbols.yaml
```

The repository includes an example using AAPL, MSFT, GOOGL and AMZN so the project validates and tests out of the box. These are **examples only**, not recommendations.

### `config/portfolio.yaml`

Define the portfolio you want to move toward gradually.

Example:

```yaml
account_currency: GBP
hard_min_cash_gbp: 100
desired_cash_pct: 0.10
max_single_transition_pct: 0.015
alert_cooldown_hours: 12
alert_validity_hours: 4

targets:
  AAPL: 0.25
  MSFT: 0.25
  GOOGL: 0.20
  AMZN: 0.20
  CASH: 0.10

groups: {}
soft_component_targets: {}
quality_rank: {}

biases:
  AAPL: TRIM
  MSFT: TRIM
  GOOGL: BUILD
  AMZN: BUILD

strategic_priority:
  AAPL: 0.80
  MSFT: 0.80
  GOOGL: 1.00
  AMZN: 0.95
```

Important rules:

- target values are decimals
- `0.25` means 25%
- all values under `targets` must total exactly `1.0`
- `targets.CASH` must equal `desired_cash_pct`
- `strategic_priority` values must be between `0.0` and `1.0`
- `max_single_transition_pct` is a hard deterministic ceiling before sensible tranche rounding

### `config/thresholds.yaml`

Put symbols you may want to add under `pullback`:

```yaml
pullback:
  GOOGL:
    watch: 0.05
    review: 0.08
    strong: 0.12
    abnormal_day: 0.12
```

Put symbols you may want to reduce under `trim`:

```yaml
trim:
  AAPL:
    watch: 0.06
    review: 0.10
    strong: 0.15
```

For every threshold set:

```text
watch < review < strong
```

Values are decimal percentages. For example `0.08` means 8%.

`abnormal_day` is a build-side safety rule. If a large one-day drop is detected, a qualifying add opportunity becomes `MANUAL_REVIEW` instead of a normal BUY recommendation.

### `config/symbols.yaml`

Every monitored symbol needs market-data metadata.

Example:

```yaml
GOOGL:
  trading212: null
  twelve_data: GOOGL
  yahoo: GOOGL
  exchange: NASDAQ
  currency: USD
```

Supported exchange names in the current freshness layer include:

```text
NYSE
NASDAQ
LSE
```

Leave `trading212: null` until you verify the broker ticker for your account.

See [`config/README.md`](config/README.md) for a detailed configuration reference.

---

## 7. Validate configuration before using credentials

Run:

```bash
portfolio-monitor validate-config
```

Expected result:

```text
Configuration valid. Targets total 100.00%
```

Then run the automated tests:

```bash
pytest -q
```

Recommended quality checks:

```bash
ruff check app tests
mypy app
pytest --cov=app --cov-report=term-missing
python -m pip_audit
```

Do not continue if configuration validation or the core test suite fails.

---

## 8. Initialize the local database

```bash
portfolio-monitor init-db
```

Default local database:

```text
sqlite:///./portfolio_monitor.db
```

The database stores scan history, portfolio snapshots, market-history cache, alert fingerprints, provider health and scan locking state.

---

## 9. Create Trading 212 read-only API credentials

Use the official Trading 212 Public API settings available in your Trading 212 account. The exact menu labels can change, so follow Trading 212's current documentation if the UI differs.

Create a key specifically for this monitor and grant only the read permissions needed to retrieve:

- account summary
- positions
- open orders
- instrument metadata

**Do not grant order-placement/write permissions.**

Add the credentials to `.env`:

```text
TRADING212_ENV=live
TRADING212_API_KEY=your_key_here
TRADING212_API_SECRET=your_secret_here
```

The application Trading 212 client explicitly allowlists GET operations only and does not contain order methods.

---

## 10. Resolve Trading 212 symbol mappings

Trading 212 broker ticker identifiers may differ from normal exchange symbols.

Preview mappings:

```bash
portfolio-monitor resolve-symbols
```

Review the entire output. Check every symbol in your own `config/symbols.yaml`.

If the suggestions are correct:

```bash
portfolio-monitor resolve-symbols --write
```

Then open `config/symbols.yaml` and inspect it manually.

Do not trust live recommendations until all relevant held positions map to the expected internal symbols.

If automatic resolution cannot find a symbol, enter the exact Trading 212 broker ticker manually after verifying it from the API/instrument metadata.

---

## 11. Verify the live Trading 212 account

Run:

```bash
portfolio-monitor smoke-test
```

Compare the output with the Trading 212 app.

Verify:

- account total is plausible
- cash is plausible
- all relevant holdings appear
- quantities match
- fractional quantities match
- values are plausible
- pending BUY orders are detected when applicable

The smoke test also reports:

```text
order_placement_implemented: false
```

If holdings, cash, values or symbol mappings are wrong, stop and fix the mapping/configuration before enabling scans.

---

## 12. Test market data

Current provider order is:

```text
Yahoo (primary)
    |
    | provider failure
    v
Twelve Data (optional fallback)
```

Yahoo requires no API key.

Test one of your configured symbols, for example:

```bash
portfolio-monitor test-market-data --symbol GOOGL
```

A successful result should show:

- source
- symbol
- plausible recent price
- currency
- provider timestamp
- number of daily bars
- latest historical bar date

The monitor rejects unusable/stale quotes rather than inventing a price.

### Optional Twelve Data fallback

Create a Twelve Data account and add:

```text
TWELVE_DATA_API_KEY=your_key_here
```

Make sure the symbol has a `twelve_data` mapping in `config/symbols.yaml`.

Yahoo remains the primary provider in the current router. Twelve Data is attempted when Yahoo fails.

---

## 13. Configure Telegram

Telegram is the normal notification interface for the self-hosted monitor.

Create a Telegram bot using Telegram's official `@BotFather` account.

Send:

```text
/newbot
```

Follow Telegram's prompts and copy the bot token.

Open your new bot and send it a message such as `/start`.

Use Telegram Bot API `getUpdates`, or another trusted method, to find the numeric chat ID for the conversation where alerts should be sent.

Add both values to `.env`:

```text
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

Test from the machine/container that will actually run the monitor:

```bash
portfolio-monitor test-notification
```

Do not enable scheduled monitoring until you have received the test message successfully.

---

## 14. Run the first manual scan

Keep:

```text
AI_PROVIDER=disabled
DRY_RUN=true
SCHEDULER_ENABLED=false
```

Run:

```bash
portfolio-monitor run-scan
```

A healthy result can simply be:

```text
NO ACTION
```

That is expected. The system is deliberately designed to prefer silence to low-quality activity.

If a recommendation appears, inspect it manually. No trade is submitted.

Run manual scans over multiple market sessions before turning on the scheduler.

---

## 15. Optional AI review

AI is optional and sits after the deterministic engine.

Default:

```text
AI_PROVIDER=disabled
```

### NVIDIA NIM

Configure:

```text
AI_PROVIDER=nvidia
NVIDIA_API_KEY=your_key_here
NVIDIA_MODEL=your_model_identifier
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
```

Test:

```bash
portfolio-monitor test-ai
```

### OpenRouter

Configure:

```text
AI_PROVIDER=openrouter
OPENROUTER_API_KEY=your_key_here
OPENROUTER_MODEL=your_model_identifier
```

If both are configured and the application/provider mode supports fallback, NVIDIA can be primary with OpenRouter available as a secondary provider.

The deterministic amount remains a hard ceiling. AI may approve, downsize, reject or request manual review; it cannot increase the deterministic maximum or place an order.

Malformed structured output is retried once and then fails closed.

If you do not want an AI dependency, leave:

```text
AI_PROVIDER=disabled
```

The deterministic scanner still works.

---

## 16. Run the API service locally

```bash
uvicorn app.api:app --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/readyz
```

PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/healthz
Invoke-RestMethod http://127.0.0.1:8000/readyz
```

Protected manual scan endpoint:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/admin/run-scan -Headers @{"X-Admin-Token"="YOUR_ADMIN_TOKEN"}
```

Do not expose `ADMIN_TOKEN` publicly.

---

## 17. Enable hourly monitoring locally

After all tests and smoke checks pass, change `.env`:

```text
SCHEDULER_ENABLED=true
SCHEDULER_MINUTE=5
SCHEDULER_TEST_INTERVAL_SECONDS=0
```

Restart the application process.

The built-in scheduler wakes around minute 5 of each hour using the configured timezone.

It may wake outside exchange opening hours. Market freshness/session logic prevents old closed-market quotes from being blindly treated as fresh actionable data.

Use one scheduler process/replica with the current SQLite lock design.

---

## 18. Docker

Build:

```bash
docker build -t portfolio-transition-monitor .
```

Run:

```bash
docker run --rm --env-file .env -p 8000:8000 portfolio-transition-monitor
```

Or:

```bash
docker compose up --build
```

Check `/healthz` and `/readyz` after startup.

The Docker image defines a non-root application user by default.

---

## 19. Deploy your own Railway instance

See [`DEPLOYMENT.md`](DEPLOYMENT.md) for the detailed production guide.

Recommended simple layout:

```text
one service
one persistent volume
one scheduler replica
```

Typical Railway variables:

```text
APP_ENV=production
TZ=Europe/London
TRADING212_ENV=live
TRADING212_API_KEY=...
TRADING212_API_SECRET=...
TWELVE_DATA_API_KEY=
AI_PROVIDER=disabled
NVIDIA_API_KEY=
NVIDIA_MODEL=
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
OPENROUTER_API_KEY=
OPENROUTER_MODEL=
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
DATABASE_URL=sqlite:////data/portfolio_monitor.db
ADMIN_TOKEN=...
DRY_RUN=true
SCHEDULER_ENABLED=true
SCHEDULER_MINUTE=5
SCHEDULER_TEST_INTERVAL_SECONDS=0
```

Attach a persistent volume mounted at:

```text
/data
```

Railway volume ownership may require a runtime UID adjustment for SQLite write access. Read `DEPLOYMENT.md` before changing the container user.

---

## 20. Production acceptance checklist

Do not consider a deployment complete until you have personally verified:

- `/healthz` returns HTTP 200
- `/readyz` returns HTTP 200
- `DRY_RUN=true`
- Trading 212 smoke test matches your account
- no order-placement method exists
- at least one market-data symbol succeeds
- Telegram test message arrives
- AI connectivity succeeds if you enabled AI
- a complete manual scan succeeds
- scheduled scans actually appear in `scan_runs`
- SQLite data survives a service restart/redeploy
- repeated identical alerts are deduplicated

A production monitor that sends no alert for hours or days may still be working correctly. Check scan history rather than judging health by notification frequency.

---

## 21. Inspect scan history

Local example:

```bash
python -c "from app.config import get_settings; from app.db.session import Database; from app.db.models import ScanRun; from sqlalchemy import select; db=Database(get_settings().database_url); s=db.Session(); rows=s.scalars(select(ScanRun).order_by(ScanRun.id.desc()).limit(10)).all(); [print((r.started_at,r.status,r.candidate_count,r.notification_sent,r.detail)) for r in rows]; s.close(); db.close()"
```

On a deployment provider, run the same Python command in the service/container shell.

Do not paste private portfolio values or identifiers into public bug reports.

---

## 22. Inspect provider health

```bash
python -c "from app.config import get_settings; from app.db.session import Database; from app.db.models import ProviderHealthRecord; from sqlalchemy import select; db=Database(get_settings().database_url); s=db.Session(); rows=s.scalars(select(ProviderHealthRecord).order_by(ProviderHealthRecord.provider)).all(); [print((r.provider,r.last_operation,r.consecutive_failures,r.total_successes,r.total_failures,r.last_error)) for r in rows]; s.close(); db.close()"
```

Provider health stores provider/operation counters and exception **types**, not raw secret-bearing exception messages.

---

## 23. Changing your strategy later

After changing any of:

```text
config/portfolio.yaml
config/thresholds.yaml
config/symbols.yaml
```

always run:

```bash
portfolio-monitor validate-config
ruff check app tests
mypy app
pytest -q
```

Do not alter target weights just because an asset moved for a few days. The application assumes your configuration represents a deliberate strategic plan.

---

## 24. Troubleshooting

### `portfolio-monitor: command not found`

Activate the virtual environment and reinstall:

```bash
pip install -e ".[dev]"
```

### `ModuleNotFoundError: app`

Install the project in editable mode:

```bash
pip install -e ".[dev]"
```

### `validate-config` fails

Read every error. Common causes:

- targets do not sum to `1.0`
- `targets.CASH` differs from `desired_cash_pct`
- a threshold symbol has no symbol mapping
- a pullback symbol has no direct target
- `watch`, `review`, `strong` are out of order
- unsupported account currency

### Trading 212 returns 401/403

Check:

- key/secret copied correctly
- correct live/demo environment
- required read permissions enabled
- any Trading 212 IP restriction allows the machine/server making requests

Do not enable trading permissions to solve a read error.

### Trading 212 positions show broker tickers instead of your internal symbols

Run:

```bash
portfolio-monitor resolve-symbols
```

Review the output carefully, then use `--write` only when correct.

### Account total/cash is wrong

Disable the scheduler and stop using recommendations until the mismatch is understood.

### Yahoo fails

Yahoo is the primary provider. If Twelve Data is configured and mapped, the router should attempt Twelve Data after a Yahoo failure.

If all providers fail, the asset is not actionable. The application does not invent a quote.

### Twelve Data returns 429

Retries are bounded. The application should fail closed rather than loop forever.

### Quote is stale

The symbol should not produce an actionable BUILD/TRIM/ROTATE alert.

### Telegram test fails

Check the bot token, chat ID and network access from the machine/container running the service. Never post either credential publicly.

### AI fails

Set:

```text
AI_PROVIDER=disabled
```

and continue using the deterministic scanner.

### Railway database disappears after redeploy

Confirm the database URL uses the mounted volume:

```text
DATABASE_URL=sqlite:////data/portfolio_monitor.db
```

and confirm a persistent volume is mounted at `/data`.

### No Telegram alerts arrive

First verify scan history. If scans are completing with `status='ok'` and zero candidates, the system is functioning normally and simply has no qualifying transition to report.

---

## Final operating rule

When data is missing, stale, unsafe or contradictory, the intended result is:

```text
NO ACTION
```

When a large one-day drop may require human context:

```text
MANUAL REVIEW
```

Every alert remains advisory and must be executed, ignored or modified manually by the user in Trading 212.
