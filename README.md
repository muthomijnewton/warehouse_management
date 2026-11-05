# Warehouse Management

A Frappe application for warehouse inventory, stock movements, valuation, and reporting.

## Features

- Items and units of measure (UOM).
- Hierarchical warehouses; movements use enabled, non-group warehouses.
- Stock receipts, consumption, and transfers.
- Moving Average, FIFO, and LIFO valuation.
- An append-only stock ledger with linked cancellation reversals.
- Stock Balance and Stock Ledger reports.

## Supported environment

The CI baseline is **Frappe v15.126.0**, Python **3.11**, Node.js **22.14.0**, Yarn **1.22.22**, MariaDB **10.6**, Redis **7.2**, and Frappe Bench **5.27.0** on Ubuntu **22.04**. The package accepts Python 3.10+, but CI currently exercises Python 3.11 only. Frappe v16 and PostgreSQL are not validated by this project.

CI pins the framework release and principal tools. Dependencies declared by Frappe and container patch releases can still change; this is not a complete dependency lockfile.

## Installation

Use a working Frappe v15 Bench environment with MariaDB and Redis. For a new development bench, install the system prerequisites described in the [Frappe installation guide](https://docs.frappe.io/framework/v15/user/en/installation), then initialize the supported release:

```bash
python3.11 -m pip install frappe-bench==5.27.0
bench init --frappe-branch v15.126.0 --python python3.11 frappe-bench
cd frappe-bench
bench get-app --branch develop warehouse_management https://github.com/muthomijnewton/warehouse_management.git
bench new-site warehouse.localhost
bench --site warehouse.localhost install-app warehouse_management
bench --site warehouse.localhost migrate
bench build --app warehouse_management
bench start
```

`bench new-site` prompts for database and site Administrator credentials. If the site already exists, skip that command. `bench start` is for development; use a production deployment configuration for a live service.

For a review branch, replace `develop` with that branch name in `bench get-app`.

**Existing installations:** back up the site and read the [upgrade guide](docs/upgrading.md) before pulling these changes. Numeric migration and legacy valuation auditing require attention before stock operations resume.

## Initial setup

Sign in as Administrator or a user with the System Manager role.

1. Create a UOM, such as Piece.
2. Create an Item with an item code, name, and UOM.
3. In Warehouse Settings, set the Default Valuation Method. An Item's Valuation Method overrides this setting when supplied.
4. Create warehouses. A group warehouse organizes child warehouses; it cannot receive or issue stock.

Choose each item's valuation method before recording stock. Once that item has ledger history, new submissions must use the same method, even when its current quantity is zero. Changing a setting does not revalue historical stock.

## Record stock movements

Create a Stock Entry, choose its purpose, set a posting date and time, and add items:

| Purpose | Source Warehouse | Target Warehouse | Receipt rate |
| --- | --- | --- | --- |
| Receipt | Empty | Required | Enter the purchase/unit receipt cost; zero is allowed |
| Consume | Required | Empty | Ignored; cost comes from stock valuation |
| Transfer | Required | Required, different from source | Ignored; value comes from source stock |

Quantities must be positive and finite. Rates must be non-negative and finite. Disabled items and disabled warehouses cannot be used.

Submit the entry to create ledger movements. An entry can contain items with different valuation methods: each item row records its own method, and the header shows `Mixed (see items)`.

### Posting and cancellation rules

- Posting date and time cannot be in the future or earlier than the latest ledger posting for any item in the entry, across all warehouses.
- Equal timestamps are allowed; creation time and ledger name break ties.
- New receipts, consumption, transfers, and cancellations for the same item are serialized using database locks held until commit or rollback.
- Stock cannot be consumed or transferred beyond the available quantity.
- Cancel transactions in reverse order for each item. If a later active entry uses an item, cancel that later entry first, including entries in other warehouses.
- Cancellation appends exact opposite quantities and values linked to the original ledger rows. It posts at cancellation time; the original posting date and ledger rows remain unchanged.
- After cancellation, refresh the posting time before submitting a new entry created earlier.

See [inventory rules and examples](docs/inventory.md) for the valuation model, cancellation behavior, and limitations.

## Reports

**Stock Balance** shows quantity, value, and average value per unit grouped by item and warehouse through an As of Date, inclusive. The server uses today's site date when the date is omitted. Item and Warehouse are optional filters; warehouse filtering selects the exact warehouse, not its descendants.

**Stock Ledger** requires an Item and Warehouse and shows opening balance, individual movements, and closing balance. From Date and To Date are inclusive. Without From Date, opening balance is zero and the report starts at the beginning of recorded history. A reversed transaction and its cancellation remain visible on their respective posting dates.

## Permissions and audit trail

System Manager can maintain master data and create, submit, cancel, and amend Stock Entries. Stock Ledger Entry is read-only through the application. Its controller rejects manual insertion, updates, deletion, and renaming, including ordinary permission bypasses. Stock Entries with ledger history cannot be deleted or renamed.

Server code, database administrators, and direct SQL remain trusted access paths; application controls do not make the database tamper-proof. Custom roles and site-specific permissions need a separate permissions review.

## Testing and contribution

From the bench directory, on a disposable test site:

```bash
bench --site test.localhost set-config allow_tests true
bench --site test.localhost run-tests --app warehouse_management
```

The tests modify and sometimes commit fixtures. Do not run them on a production site. See [testing and CI](docs/testing.md) for coverage, lint commands, and the migration smoke test.

Create a feature branch, run the applicable checks, and open a pull request that states the behavior change and validation performed. Passing CI is required before treating a change as validated.

## License

[MIT](license.txt).
