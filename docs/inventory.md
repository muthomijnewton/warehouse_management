# Inventory rules

## Valuation methods

The effective method is the Item's Valuation Method, falling back to Warehouse Settings. A supported method must be configured before submission. Every submitted item row and ledger movement records the method used. The Stock Entry header is a summary, not the source of valuation for mixed-item entries.

**Moving Average:** a receipt adds quantity multiplied by receipt rate to the warehouse value. Consumption uses current warehouse value divided by quantity. A transfer removes that value from the source and adds the identical value to the target.

**FIFO:** consumption and transfers use the oldest remaining receipt layers first.

**LIFO:** consumption and transfers use the newest remaining receipt layers first. Historical outgoing movements are also replayed in LIFO order. Reversing FIFO layers only at the point of transfer would produce incorrect results after earlier consumption.

FIFO and LIFO transfers create separate movements for each transferred cost layer. The target retains those rates as new layers in the order posted by the transfer. This defines the target's subsequent FIFO/LIFO order; the system does not retain the original receipt's age across warehouses. Allocation rows identify the source Stock Entries, quantities, rates, and values used.

For example, receive 10 units at 20 and 10 at 30, then consume 4 using LIFO. The remaining stock is 10 at 20 and 6 at 30. Transferring 8 moves 6 at 30 plus 2 at 20: value 220. The source retains 8 units valued at 160.

The method cannot change for an item with ledger history, including canceled history or a zero balance. Changing a method on Item or Warehouse Settings does not rewrite old entries; submission rejects a mismatch. Migration of valuation methods is not implemented.

## Time and ordering

Dates and times use the Frappe site's timezone. New submissions must be at or after the latest ledger posting for each affected item across all warehouses, and at or before current site time. Drafts may contain earlier dates; the chronology check runs at submission under the item locks.

Entries with equal posting timestamps are ordered by creation time and ledger name. Backdated recalculation and future stock postings are not supported. There is no automatic reposting of subsequent valuations.

## Concurrency and transaction boundaries

Submission and cancellation lock the existing Item rows in sorted item-name order. This deliberately serializes all warehouses for the same item, including warehouses with no ledger rows yet. Different items can proceed independently.

Ledger reads use locking reads so a transaction that waited for an item lock sees the winner's committed balance rather than an earlier repeatable-read snapshot. A competing withdrawal rechecks availability before posting.

The controller does not commit. Frappe's request or job transaction commits a successful operation and rolls back a failed operation. Custom callers must also roll back after an exception; catching an exception and committing a partially executed transaction is unsupported.

## Cancellation

Cancellation is restricted to the latest active Stock Entry for every item it contains. Cancel later active entries first, even if they affect another warehouse. This conservative rule avoids recalculating dependent transactions.

For each original ledger row, cancellation appends a new row with:

- The opposite actual quantity.
- The opposite stock value.
- The original valuation rate and method.
- A unique Reversal Of link to that original row.
- The cancellation date and time, with a newly calculated running balance.

Original ledger entries and allocation rows remain for audit. Layer reconstruction excludes both a reversed original and its reversal, restoring the original layers rather than treating a reversal as a new receipt. Reports include both movements, so balances before the cancellation date continue to reflect the original transaction.

Example: receive 10 at 20, then 10 at 30. Cancel the latest receipt. The reversal removes exactly 10 units and value 300, leaving 10 units valued at 200. It does not remove stock at the current average of 25.

## Scope and limitations

- No historical valuation recalculation, valuation-method conversion, or automatic repair of legacy cancellations.
- No lot, batch, serial-number, reservation, accounting journal, or currency-conversion model.
- Ledger quantities and monetary fields use Frappe's numeric database fields, with nine decimal places in the supported MariaDB schema. Floating-point calculations may have small rounding differences; reconciliation should use the configured precision.
- Balances and layers are reconstructed from ledger history. The migration adds lookup indexes, but a persistent balance/layer cache for large ledgers is not implemented.
- Database administrators and trusted server code can bypass application protections. Use database access controls and backups as well.
