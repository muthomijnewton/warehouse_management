# Upgrade existing installations

These changes tighten stock rules, make the application ledger immutable, and change two balance columns from text to numeric fields. Test the upgrade on a restored copy of the site before upgrading production.

## 1. Back up and pause stock activity

From the bench directory:

```bash
bench --site warehouse.localhost backup --with-files
bench --site warehouse.localhost set-maintenance-mode on
```

Pause scheduled jobs, integrations, and other writers as part of your normal deployment procedure. Maintenance mode alone does not stop trusted background code or direct SQL.

Record the installed app/framework revisions and reconcile item/warehouse quantities and values before changing code.

## 2. Update code and migrate

Update the application to the reviewed release/commit and use the supported Frappe v15 environment described in the README. Then run:

```bash
bench --site warehouse.localhost migrate
bench build --app warehouse_management
```

The pre-model-sync patch checks existing Qty After Transaction and Stock Value After Transaction values. It rejects empty, non-numeric, non-finite, out-of-range, or over-precision values rather than allowing silent coercion. A failure identifies the record and field to audit. Repair legacy data only through a reviewed maintenance procedure, then rerun migration.

Model sync converts Qty After Transaction to Float and Stock Value After Transaction to Currency. It adds valuation-method snapshots and unique reversal links. The post-model-sync patch resets the standard Stock Entry and Stock Ledger Entry permissions and adds lookup indexes. Review custom permissions afterward; the ledger controller still rejects ordinary manual writes.

Migration does not recalculate historical values, infer missing valuation methods, or guess which legacy movements were cancellation reversals. Frappe schema changes can commit independently of patch transactions; keep the backup until validation is complete.

## 3. Audit legacy item histories

Existing rows have no per-ledger valuation-method snapshot. New stock submissions and cancellations are blocked for an item while any of its ledger rows lack that snapshot.

Review the item's complete history, including all warehouses, receipt costs, allocations, consumed/transferred values, and canceled entries. Current Item or Warehouse Settings values do not prove which method was used historically. The old Stock Entry header also cannot prove each item's method in a mixed-item document.

If the complete history used one verified method and is consistent, attest it explicitly. For example:

```bash
bench --site warehouse.localhost execute warehouse_management.legacy_audit.confirm_valuation --kwargs '{"item":"ITEM-001","method":"FIFO"}'
```

The helper fills only blank method snapshots, rejects conflicts, locks the Item, and records an audit comment on the Item under the executing user. It is a maintenance command, not a Desk/API action. It does not set today's Item method, change quantities or values, or reconstruct missing reversal links. Keep the audit evidence with the deployment record.

If legacy canceled entries lack explicit reversal links, the helper rejects the attestation. Those records require a separate reviewed reconciliation/migration that identifies each reversal and verifies exact quantities and values. Histories that switched methods or contain valuation errors also require a separate correction plan; do not label them with today's method to bypass the check.

## 4. Verify before reopening

- Compare Stock Balance and Stock Ledger totals with the pre-upgrade reconciliation.
- Check warehouse-only and combined item/warehouse report filters.
- Confirm the active Item/settings method agrees with the audited history.
- Test receipt, consumption, transfer, and cancellation on a disposable copy.
- Confirm users can read the ledger but cannot manually create, edit, delete, or rename its records.
- Confirm operators understand chronological submission and reverse-order cancellation.

When verification is complete, restore your normal worker/integration configuration and disable maintenance mode:

```bash
bench --site warehouse.localhost set-maintenance-mode off
```

Do not roll back by deleting ledger entries or reversal rows. Restore the coordinated database/files backup and matching code revision if the upgrade must be abandoned.
