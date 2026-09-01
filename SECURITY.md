# Security Policy

Portfolio Transition Monitor handles sensitive brokerage, notification and optional AI credentials. Treat every deployment as a private financial-data system even though the application is read-only.

## Core security model

V1 is intentionally advisory only.

The project is designed around these invariants:

- Trading 212 credentials must be read-only.
- The application contains no Trading 212 order-submission implementation.
- Trading 212 API access is explicitly limited to allowlisted GET operations.
- `DRY_RUN=true` is the intended operating mode.
- Missing/stale market data fails closed.
- AI cannot increase deterministic sizing limits or place trades.
- Secrets are loaded from environment variables, not committed files.
- Secret-redaction filtering is enabled in application logging.
- The manual scan HTTP endpoint requires an admin token.
- Self-hosted users keep their credentials in their own environment/deployment account.

## Credentials

Never commit or publish:

- `.env`
- Trading 212 API key/secret
- Telegram bot token
- Telegram chat ID when treated as private
- NVIDIA/OpenRouter API keys
- `ADMIN_TOKEN`
- account identifiers
- production database files

Use a password manager or the deployment provider's secret store.

For Trading 212, grant only the read permissions needed for account summary, positions, open orders and instrument metadata.

Do not add trading/write permissions to solve a read-access problem.

## Before publishing a fork

Run:

```bash
git status --short
git check-ignore .env
ruff check app tests
mypy app
pytest -q
python -m pip_audit
```

If Gitleaks is installed:

```bash
gitleaks git . --redact --no-banner
```

Check the Trading 212 package for accidental HTTP write calls:

```bash
git grep -nE "\.(post|put|patch|delete)\(" -- app/trading212
```

The expected result is no order/write implementation.

## Logs and bug reports

Application logs may contain provider names, symbols and HTTP status information. Secret-redaction logic is intended to remove configured credential values, but users should still review logs before sharing them publicly.

Do not paste full production `.env` files, brokerage responses, database contents, account IDs or private URLs into public issues.

Use a minimal sanitized reproduction whenever possible.

## Reporting a vulnerability

Do not open a public issue containing exploit details, credentials or sensitive account data.

If GitHub Private Vulnerability Reporting is enabled for the public repository, use that channel.

Otherwise contact the repository maintainer privately through the maintainer's GitHub profile and share only the minimum information necessary to establish a secure reporting channel.

For ordinary non-security bugs that contain no sensitive information, use the normal GitHub issue tracker.

## Supported security scope

Security fixes are expected to target the latest public release/default branch.

Self-hosted users are responsible for:

- securing their host account
- protecting deployment-provider access
- protecting SSH keys
- controlling access to the SQLite database
- rotating exposed credentials
- keeping Python/dependencies updated
- reviewing configuration before acting on any alert

## If a secret is exposed

1. Revoke/rotate the affected credential immediately at the provider.
2. Remove it from local files/logs that may be shared.
3. If it was committed, remove it from Git history as appropriate.
4. Run a secret scan again.
5. Verify the replacement credential has only the minimum required permissions.

Do not rely on deleting a GitHub file alone after a credential has already entered commit history; rotate the secret.
