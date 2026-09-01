# Portfolio Transition Monitor

A self-hosted, read-only portfolio transition monitor for Trading 212.

It reads your current portfolio, compares it with a target allocation that **you define**, watches market pullbacks and strength, and can send Telegram alerts when a gradual portfolio transition may be worth reviewing.

**This is not an automatic trading bot. It does not place orders.**

> [!IMPORTANT]
> This project is software, not investment advice. The included portfolio and threshold files are examples only. Replace them with your own strategy before using live data.

## What it does

- Reads Trading 212 account summary, positions and open orders with read-only credentials.
- Uses Trading 212 as the source of truth for live portfolio holdings and cash.
- Uses Yahoo market data first and Twelve Data as an optional fallback.
- Computes simple, explainable pullback/strength/volatility metrics.
- Scores BUILD, TRIM and ROTATE candidates.
- Applies deterministic sizing, cash-reserve and abnormal-drop safety rules.
- Optionally sends strong candidates to NVIDIA NIM or OpenRouter for a second-pass review.
- Sends Telegram alerts only when a candidate survives the rules and dedupe checks.
- Stores scan history, market-history cache, alert fingerprints and provider health in SQLite.
- Runs manually, locally on a schedule, in Docker, or on a host such as Railway.

Most scans should produce:

```text
NO ACTION
```

Silence is a feature. The goal is to avoid unnecessary trading.

## What it never does

The V1 application deliberately contains no order-submission implementation.

The Trading 212 client is allowlisted to read operations only. The project must not be modified to grant write/order permissions unless you intentionally redesign and re-audit the entire safety model.

## Current scope

This release is designed for self-hosted personal use. Each user runs their **own copy** and stores their own credentials locally or in their own deployment provider.

No central service receives or stores users' brokerage credentials.

Current V1 account-value and alert labels assume a **GBP Trading 212 account**. Configuration validation rejects other account currencies until the internal money model is generalized.

## Quick start

Requirements:

- Python 3.12+
- Git
- a Trading 212 account with read-only API access
- optional Telegram bot
- optional Twelve Data API key
- optional NVIDIA NIM or OpenRouter API key

Clone the repository:

```bash
git clone YOUR_PUBLIC_REPOSITORY_URL
cd portfolio-transition-monitor
```

Create a virtual environment.

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Copy the environment template:

```bash
cp .env.example .env
```

PowerShell:

```powershell
Copy-Item .env.example .env
```

Before adding real credentials, run:

```bash
portfolio-monitor validate-config
pytest -q
```

The repository ships with an **illustrative** AAPL/MSFT/GOOGL/AMZN configuration purely so the software can be validated out of the box. It is not a recommended portfolio.

Read [`SETUP.md`](SETUP.md) before connecting live data.

## Configure your desired portfolio shift

The three main files are:

```text
config/portfolio.yaml
config/thresholds.yaml
config/symbols.yaml
```

### `config/portfolio.yaml`

Define the portfolio you are gradually moving toward.

Example only:

```yaml
targets:
  AAPL: 0.25
  MSFT: 0.25
  GOOGL: 0.20
  AMZN: 0.20
  CASH: 0.10
```

Targets must sum to exactly `1.0`.

The same file controls:

- hard cash reserve
- desired cash percentage
- maximum single transition percentage
- alert cooldown
- optional groups/sleeves
- optional soft component targets
- strategic priority values

Strategic priorities are decimal values from `0.0` to `1.0`. They influence ranking but do not bypass safety controls.

### `config/thresholds.yaml`

A symbol appears under `pullback` if you want the system to consider adding it on weakness.

Example:

```yaml
pullback:
  GOOGL:
    watch: 0.05
    review: 0.08
    strong: 0.12
    abnormal_day: 0.12
```

A symbol appears under `trim` if you want the system to consider reducing it when it is above target and showing strength.

```yaml
trim:
  AAPL:
    watch: 0.06
    review: 0.10
    strong: 0.15
```

For each threshold set:

```text
watch < review < strong
```

Values are decimals, so `0.08` means `8%`.

`abnormal_day` is a fail-safe for large one-day declines. A qualifying build candidate with an unusually large one-day drop becomes `MANUAL_REVIEW` instead of an automatic-looking BUY recommendation.

### `config/symbols.yaml`

Map each internal symbol to market-data and Trading 212 identifiers.

Example:

```yaml
GOOGL:
  trading212: null
  twelve_data: GOOGL
  yahoo: GOOGL
  exchange: NASDAQ
  currency: USD
```

Leave `trading212: null` initially if you do not know the broker ticker.

After adding read-only Trading 212 credentials:

```bash
portfolio-monitor resolve-symbols
```

Review the output. Only then, if it is correct:

```bash
portfolio-monitor resolve-symbols --write
```

Run validation after every strategy change:

```bash
portfolio-monitor validate-config
pytest -q
```

More configuration examples are in [`config/README.md`](config/README.md).

## Trading 212 credentials

Use the official Trading 212 Public API and create a credential with **read-only permissions only**.

The application needs to read:

- account summary
- positions
- open orders
- instrument metadata

Never grant order-placement permissions to a credential used by this project.

Add credentials only to `.env` or your deployment provider's secret store:

```text
TRADING212_ENV=live
TRADING212_API_KEY=...
TRADING212_API_SECRET=...
```

Never commit `.env`.

Verify the live account mapping:

```bash
portfolio-monitor smoke-test
```

Compare the output with Trading 212 before trusting any recommendation.

## Market data

Current routing order:

```text
Yahoo (primary)
    |
    | on provider failure
    v
Twelve Data (optional fallback)
```

Yahoo does not require an API key.

Optional Twelve Data configuration:

```text
TWELVE_DATA_API_KEY=...
```

Test a configured symbol:

```bash
portfolio-monitor test-market-data --symbol GOOGL
```

The scanner rejects stale or unusable quotes instead of inventing prices.

Historical daily data is cached in SQLite so it does not need to be downloaded on every hourly scan.

## How the deterministic engine works

### BUILD

A symbol must normally:

- be listed in `thresholds.yaml` under `pullback`
- have fresh market data
- be below its direct target
- have no pending Trading 212 buy order
- clear its configured pullback threshold

The build score combines:

- how underweight the symbol is
- pullback from its 20-day high
- ATR-normalized pullback significance
- your configured strategic priority

Conceptually:

```text
BUILD_SCORE = 100 * (
    0.30 * underweight
  + 0.30 * raw_pullback
  + 0.20 * atr_significance
  + 0.20 * strategic_priority
)
```

### TRIM

A symbol must normally:

- be listed under `trim`
- have fresh market data
- be above its direct or soft target
- clear its configured strength threshold

Strength uses the strongest of:

- rebound from 20-day low
- positive 10-day return
- positive 20-day return

The score combines overweight size, measured strength, strategic priority and a small positive-P/L bonus.

```text
TRIM_SCORE = 100 * (
    0.40 * overweight
  + 0.30 * strength
  + 0.20 * strategic_priority
  + 0.10 * pnl_bonus
)
```

There are **no hard-coded ticker-specific trim rules** in the public template. Symbol preferences belong in configuration.

### ROTATE

The engine pairs a qualifying trim source with a qualifying build destination.

```text
ROTATION_SCORE =
    0.45 * BUILD_SCORE
  + 0.40 * TRIM_SCORE
  + diversification_bonus
```

When otherwise comparable, a rotation can be preferred because it shifts capital from something above target/strong into something below target/weak without consuming as much cash.

### Signal tiers

```text
STRONG  >= 85
REVIEW  >= 75
WATCH   >= 65
IGNORE  < 65
```

Only REVIEW/STRONG candidates normally progress to recommendation generation.

## Position sizing and cash safety

Normal build:

```text
min(0.75% of portfolio, 25% of target gap, configured max transition)
```

Strong build:

```text
min(1.25% of portfolio, 35% of target gap, configured max transition)
```

Normal trim:

```text
min(0.75% of portfolio, 25% of excess position value, configured max transition)
```

Strong trim:

```text
min(1.25% of portfolio, 40% of excess position value, configured max transition)
```

A standalone buy is rejected if it would take cash below `hard_min_cash_gbp`.

For rotations, the amount is limited to the smaller of the allowed build size and allowed trim size.

## Optional AI review

AI sits **after** the deterministic rules engine.

Supported providers:

- NVIDIA NIM
- OpenRouter
- disabled

Default:

```text
AI_PROVIDER=disabled
```

NVIDIA example:

```text
AI_PROVIDER=nvidia
NVIDIA_API_KEY=...
NVIDIA_MODEL=...
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
```

Test:

```bash
portfolio-monitor test-ai
```

AI may approve, downsize, reject or request manual review. It cannot increase the deterministic maximum amount and it cannot place a trade.

Malformed structured AI output is retried once and then fails closed.

## Telegram

Create a Telegram bot, then set:

```text
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

Test end-to-end delivery:

```bash
portfolio-monitor test-notification
```

A normal advisory alert looks like:

```text
PORTFOLIO TRANSITION ALERT

ROTATE: £100 AAPL → GOOGL
GOOGL: 000.00, pullback 10.0% from 20d high
AAPL: rebound 12.0% from 20d low
Score: 86.0 (STRONG)
Cash: ~£000
Reason: Strong overweight funding source paired with underweight pullback

Advisory only — no automatic trade has been placed.
```

## Run a scan

Keep:

```text
DRY_RUN=true
```

Then:

```bash
portfolio-monitor run-scan
```

A healthy scan can simply return:

```text
NO ACTION
```

## Scheduler

Enable automatic hourly scanning with:

```text
SCHEDULER_ENABLED=true
SCHEDULER_MINUTE=5
TZ=Europe/London
```

The built-in scheduler runs around minute 5 of each hour. Exchange-session freshness rules prevent old closed-market quotes from being blindly treated as fresh actionable data.

Use one scheduler replica with the current SQLite lock design.

## API service

Run locally:

```bash
uvicorn app.api:app --host 127.0.0.1 --port 8000
```

Endpoints:

```text
GET  /healthz
GET  /readyz
POST /admin/run-scan
```

Generate an admin token:

```bash
portfolio-monitor generate-admin-token
```

Set it as:

```text
ADMIN_TOKEN=...
```

The admin scan endpoint requires `X-Admin-Token`.

## Database and persistence

Default local database:

```text
sqlite:///./portfolio_monitor.db
```

Important persisted state includes:

- scan runs
- portfolio snapshots
- position snapshots
- alert fingerprints
- market-history cache
- provider health
- scan lock

If deploying, put SQLite on persistent storage.

## Docker

```bash
docker build -t portfolio-transition-monitor .
docker run --rm --env-file .env -p 8000:8000 portfolio-transition-monitor
```

Or:

```bash
docker compose up --build
```

See [`DEPLOYMENT.md`](DEPLOYMENT.md) for Railway and other hosting guidance.

## Development quality gates

```bash
ruff check app tests
mypy app
python -m pytest -q
python -m pytest -q -W error::ResourceWarning
python -m pytest --cov=app --cov-report=term-missing
python -m pip_audit
```

Recommended secret scan before publishing:

```bash
gitleaks git . --redact --no-banner
```

Verify the Trading 212 package has no accidental write requests:

```bash
git grep -nE "\.(post|put|patch|delete)\(" -- app/trading212
```

That command should return no Trading 212 write calls.

## Security rules for users

- Use read-only brokerage credentials.
- Keep `.env` out of Git.
- Do not paste secrets into issues, screenshots or logs.
- Use a long random `ADMIN_TOKEN` if exposing the service publicly.
- Prefer private deployment unless you need HTTP health/admin endpoints.
- Keep `DRY_RUN=true`.
- Rotate any credential immediately if it is accidentally exposed.

See [`SECURITY.md`](SECURITY.md).

## Contributing

Contributions are welcome. Read [`CONTRIBUTING.md`](CONTRIBUTING.md) before opening a pull request.

## License

MIT. See [`LICENSE`](LICENSE).

## Disclaimer

This software is provided for informational and educational use. It does not provide financial, investment, tax or legal advice. Market data can be delayed, incomplete or wrong. You are responsible for reviewing every alert and for any investment decision you make.
