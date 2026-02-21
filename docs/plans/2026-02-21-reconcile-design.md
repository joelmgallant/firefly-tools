# Design: Account Balance Reconciliation

## Problem

No way to compare Firefly III account balances against actual bank balances. Currently requires manually checking the bank app and eyeballing Firefly.

## Solution

New `money.py reconcile` subcommand that interactively walks through account balance comparison and creates adjustment transactions for discrepancies.

## User Flow

1. Fetch all asset accounts from Firefly API
2. Display accounts with current balances, prompt user to select which to reconcile
3. For each selected account:
   - Show Firefly balance
   - Prompt for actual balance from bank
   - If mismatch: show difference, offer to create adjustment transaction
   - If match: confirm and move on
4. Print summary table of all reconciled accounts

## New Functions in `money.py`

### `_fetch_accounts(account_type="asset")`

- Calls `GET /api/v1/accounts?type={account_type}`
- Returns list of `{id, name, current_balance, currency_code}`
- Handles pagination if needed

### `_create_reconciliation_transaction(account_id, account_name, amount, currency_code)`

- Creates a withdrawal (Firefly > actual) or deposit (Firefly < actual)
- Transaction details:
  - **Description**: `"Reconciliation adjustment"`
  - **Tag**: `reconciliation`
  - **Source**: the account (for withdrawals) or `"(reconciliation)"` (for deposits)
  - **Destination**: `"(reconciliation)"` (for withdrawals) or the account (for deposits)
  - **Date**: today
  - **Category**: none
  - **Budget**: none

### `action_reconcile()`

- Orchestrates the interactive flow
- No `--date` argument needed (always uses current balances)
- Outputs summary to console (no CSV export needed)

## CLI Interface

```
python money.py reconcile
```

No additional arguments. Fully interactive.

## Adjustment Transaction Rationale

Using tagged transactions (rather than Firefly's built-in reconciliation feature) keeps the adjustment visible in normal transaction lists and searchable via existing tools. The `reconciliation` tag makes it easy to find and audit these adjustments later.

## Dependencies

No new dependencies. Uses existing `requests` and standard library `input()`.
