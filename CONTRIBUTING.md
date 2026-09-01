# Contributing

Contributions are welcome, especially improvements to reliability, provider handling, documentation, test coverage and configuration ergonomics.

This project has a deliberately conservative safety boundary: it is a **read-only advisory monitor**, not an execution engine.

## Safety invariants

Contributions must not casually weaken these properties:

- no Trading 212 order-submission implementation
- Trading 212 client remains read-only/GET-only
- stale/unavailable market data fails closed
- deterministic cash/sizing controls remain authoritative
- AI cannot increase deterministic limits
- abnormal-drop safety cannot be bypassed by AI
- secrets must not appear in logs/tests/example files
- `DRY_RUN=true` remains the intended V1 mode

A proposal that intentionally changes the product into a trading/execution system should be treated as a separate architecture/security project rather than a small pull request.

## Development setup

```bash
python -m venv .venv
```

Activate the environment, then:

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Run:

```bash
portfolio-monitor validate-config
ruff check app tests
mypy app
pytest -q
```

Coverage:

```bash
pytest --cov=app --cov-report=term-missing
```

Dependency audit:

```bash
python -m pip_audit
```

## Tests

Add or update tests for behavior changes.

High-value areas include:

- portfolio weights and groups
- BUILD/TRIM/ROTATE scoring
- tranche sizing
- cash-floor behavior
- stale quote rejection
- abnormal one-day drop safety
- provider fallback
- bounded retries/rate limits
- AI schema/fail-closed behavior
- dedupe persistence
- scheduler locking
- API admin authentication
- secret redaction

External API tests should normally use mocks/fakes rather than real credentials.

Never add real brokerage/API credentials to test fixtures.

## Configuration changes

The public repository's AAPL/MSFT/GOOGL/AMZN configuration is illustrative only.

Avoid adding a contributor's personal investment strategy as a default. Examples should remain obviously generic and should validate out of the box.

If you add a new configuration field, update:

- `config/README.md`
- `README.md` where relevant
- `SETUP.md` where relevant
- configuration validation
- tests

## Code style

The project uses:

- Ruff
- mypy
- pytest

Before opening a pull request:

```bash
ruff check app tests
mypy app
pytest -q
```

Keep provider retries bounded and errors fail-closed.

## Security

Read [`SECURITY.md`](SECURITY.md) before reporting a vulnerability.

Do not put secrets, account responses or private identifiers in public issues or pull requests.

## Pull requests

A useful pull request should explain:

- what behavior changes
- why the change is needed
- what tests cover it
- whether any configuration migration is required
- whether the safety/read-only boundary is affected

If a change affects external providers or deployment behavior, include a safe reproduction/verification method that does not require publishing credentials.
