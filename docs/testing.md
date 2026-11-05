# Testing and CI

## Application tests

Use a disposable Frappe v15 site with the app installed, MariaDB, and Redis available. From the bench directory:

```bash
bench --site test.localhost set-config allow_tests true
bench --site test.localhost run-tests --app warehouse_management
```

Tests create master data and stock entries, delete test ledger rows, and sometimes commit fixtures to make them visible to independent connections. Never run them on a production site.

Coverage includes receipt/consumption/transfer validation, Moving Average/FIFO/LIFO valuation, layer allocations, LIFO transfers after prior outgoing movements, exact cancellation reversals, restored layers, cancellation order, posting chronology, mixed-item method snapshots, method-change rejection, report filters, ledger immutability, and concurrent withdrawal attempts.

The concurrent test uses two independent database connections. Both establish a snapshot before submitting withdrawals against the same item; exactly one withdrawal can succeed when their combined demand exceeds available stock.

## Lint and formatting

From the application checkout, with pre-commit installed:

```bash
pre-commit run --all-files
```

Hook versions are recorded in `.pre-commit-config.yaml`. The GitHub Linters workflow also runs Semgrep and dependency auditing. These security tools may report new upstream findings independently of an application change; investigate failures rather than disabling the check.

## GitHub Actions

`.github/workflows/ci.yml` explicitly selects Frappe v15.126.0 rather than following Frappe's default branch. It uses Python 3.11, Node.js 22.14.0, Yarn 1.22.22, Bench 5.27.0, MariaDB 10.6, Redis 7.2, and Ubuntu 22.04. It installs the app on a clean site, builds assets, migrates, and runs the application tests.

A separate disposable `upgrade.localhost` site simulates legacy text balance fields and missing method snapshots, then migrates and verifies numeric preservation and read-only ledger permissions. A second migration verifies that rerunning the upgrade is safe. The fixture is restricted to that site name and is not an operator upgrade command.

The pre-migration validation tests cover invalid legacy numeric values. Actual legacy cancellation repair is deliberately not automated or claimed by the smoke test.

CI pins the framework and principal tool versions, but it does not lock every transitive Python dependency or container patch version. Update the workflow and documentation together when changing the supported baseline, and require a passing integration run for that baseline.
