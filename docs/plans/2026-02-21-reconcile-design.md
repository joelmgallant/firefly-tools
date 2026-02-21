# Account Balance Reconciliation — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `money.py reconcile` subcommand that compares Firefly III account balances against actual bank balances and creates adjustment transactions for discrepancies.

**Architecture:** Three new functions in `money.py` — `_fetch_accounts()` for listing accounts via API, `_create_reconciliation_transaction()` for creating adjustment transactions, and `action_reconcile()` for the interactive CLI flow. One new subparser + dispatch entry in `main()`.

**Tech Stack:** Python 3.11, requests, argparse (all existing dependencies)

**API Endpoints Used:**
- `GET /api/v1/accounts?type=asset` — returns accounts with `current_balance`, `currency_code`, `name`
- `POST /api/v1/transactions` — creates transactions with `{"transactions": [{...}]}` payload

**Verified Account Data (from live API):**
- Accounts return: `data[].id`, `data[].attributes.name`, `.current_balance`, `.currency_code`
- Account types available: `asset`, `expense`, `revenue`, `reconciliation`

---

### Task 1: Add `_fetch_accounts()` helper function

**Files:**
- Modify: `money.py` (add after `_fetch_transactions()` function, around line 165)

**Step 1: Add the function**

Insert after the `_fetch_transactions()` function (line 165):

```python
def _fetch_accounts(account_type="asset"):
    """Fetch accounts from Firefly III API.

    Args:
        account_type: Account type filter (asset, expense, revenue, etc.)

    Returns:
        List of dicts with keys: id, name, current_balance, currency_code
    """
    url = f"{API_BASE_URL}/accounts"
    headers = get_headers()
    params = {"type": account_type, "limit": "50"}

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        accounts = []
        for record in data.get("data", []):
            attrs = record["attributes"]
            if not attrs.get("active", True):
                continue
            accounts.append({
                "id": record["id"],
                "name": attrs["name"],
                "current_balance": float(attrs["current_balance"]),
                "currency_code": attrs.get("currency_code", "CAD"),
            })

        return accounts

    except requests.exceptions.RequestException as e:
        print(f"Error fetching accounts: {e}")
        exit(1)
```

**Step 2: Verify it works**

Run: `source venv/bin/activate && python -c "from money import _fetch_accounts; import json; print(json.dumps(_fetch_accounts(), indent=2))"`

Expected: JSON list of accounts with id, name, current_balance, currency_code fields.

**Step 3: Commit**

```bash
git add money.py
git commit -m "Add _fetch_accounts() helper for Firefly III accounts API"
```

---

### Task 2: Add `_create_reconciliation_transaction()` helper function

**Files:**
- Modify: `money.py` (add after `_fetch_accounts()`)

**Step 1: Add the function**

Insert after `_fetch_accounts()`:

```python
def _create_reconciliation_transaction(account_id, account_name, amount, currency_code="CAD"):
    """Create a reconciliation adjustment transaction.

    If amount is positive, creates a deposit (Firefly balance is too low).
    If amount is negative, creates a withdrawal (Firefly balance is too high).

    Args:
        account_id: Firefly account ID
        account_name: Account name (for display)
        amount: Adjustment amount (positive = deposit, negative = withdrawal)
        currency_code: Currency code (default CAD)

    Returns:
        Tuple of (success: bool, message: str)
    """
    from datetime import date

    url = f"{API_BASE_URL}/transactions"
    headers = get_headers()

    abs_amount = abs(amount)

    if amount > 0:
        # Deposit: money coming IN to the account
        tx_type = "deposit"
        source_name = "(reconciliation)"
        destination_id = str(account_id)
        destination_name = None
        source_id = None
    else:
        # Withdrawal: money going OUT of the account
        tx_type = "withdrawal"
        source_id = str(account_id)
        source_name = None
        destination_name = "(reconciliation)"
        destination_id = None

    transaction = {
        "type": tx_type,
        "date": date.today().isoformat(),
        "amount": f"{abs_amount:.2f}",
        "description": f"Reconciliation adjustment — {account_name}",
        "currency_code": currency_code,
        "tags": ["reconciliation"],
    }

    if source_id:
        transaction["source_id"] = source_id
    if source_name:
        transaction["source_name"] = source_name
    if destination_id:
        transaction["destination_id"] = destination_id
    if destination_name:
        transaction["destination_name"] = destination_name

    payload = {
        "apply_rules": False,
        "fire_webhooks": False,
        "transactions": [transaction],
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return True, f"Created {tx_type} of ${abs_amount:.2f}"
    except requests.exceptions.RequestException as e:
        error_detail = ""
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json().get("message", e.response.text[:200])
            except Exception:
                error_detail = e.response.text[:200]
        return False, f"Failed to create transaction: {e} {error_detail}"
```

**Step 2: Verify it compiles**

Run: `source venv/bin/activate && python -c "from money import _create_reconciliation_transaction; print('OK')"`

Expected: `OK` (don't actually create a transaction yet — we'll test end-to-end in Task 3)

**Step 3: Commit**

```bash
git add money.py
git commit -m "Add _create_reconciliation_transaction() for balance adjustments"
```

---

### Task 3: Add `action_reconcile()` function

**Files:**
- Modify: `money.py` (add after `_create_reconciliation_transaction()`, before `main()`)

**Step 1: Add the action function**

Insert before `main()`:

```python
def action_reconcile():
    """Interactive account balance reconciliation.

    Fetches all asset accounts, lets user select which to reconcile,
    compares Firefly balances against actual balances entered by user,
    and offers to create adjustment transactions for discrepancies.
    """
    print("Fetching accounts...\n")
    accounts = _fetch_accounts(account_type="asset")

    if not accounts:
        print("No asset accounts found.")
        return

    # Display accounts for selection
    print("Select accounts to reconcile:")
    for i, acct in enumerate(accounts, 1):
        balance = acct['current_balance']
        sign = "" if balance >= 0 else ""
        print(f"  [{i}] {acct['name']:30} {sign}${abs(balance):>12,.2f} {acct['currency_code']}")

    print()
    selection = input("Enter account numbers (comma-separated, or 'all'): ").strip()

    if selection.lower() == 'all':
        selected = accounts
    else:
        try:
            indices = [int(s.strip()) - 1 for s in selection.split(',')]
            selected = [accounts[i] for i in indices if 0 <= i < len(accounts)]
        except (ValueError, IndexError):
            print("Invalid selection.")
            return

    if not selected:
        print("No accounts selected.")
        return

    # Reconcile each selected account
    results = []

    for acct in selected:
        print(f"\n{'─' * 50}")
        print(f"Reconciling: {acct['name']}")
        print(f"{'─' * 50}")
        print(f"  Firefly balance: ${acct['current_balance']:>12,.2f} {acct['currency_code']}")

        actual_input = input(f"  Actual balance:  $").strip()

        try:
            actual_balance = float(actual_input.replace(',', ''))
        except ValueError:
            print("  Invalid amount, skipping.")
            results.append({"account": acct['name'], "status": "skipped", "diff": 0})
            continue

        diff = actual_balance - acct['current_balance']

        if abs(diff) < 0.01:
            print("  ✓ Balances match!")
            results.append({"account": acct['name'], "status": "OK", "diff": 0})
            continue

        direction = "lower" if diff < 0 else "higher"
        print(f"  Difference: ${diff:>+,.2f} (actual is ${abs(diff):,.2f} {direction} than Firefly)")

        create = input("  Create adjustment transaction? [y/N]: ").strip().lower()

        if create in ['y', 'yes']:
            success, message = _create_reconciliation_transaction(
                acct['id'], acct['name'], diff, acct['currency_code']
            )
            if success:
                print(f"  ✓ {message}")
                results.append({"account": acct['name'], "status": "adjusted", "diff": diff})
            else:
                print(f"  ✗ {message}")
                results.append({"account": acct['name'], "status": "error", "diff": diff})
        else:
            print("  Skipped adjustment.")
            results.append({"account": acct['name'], "status": "skipped", "diff": diff})

    # Summary
    print(f"\n{'=' * 50}")
    print("RECONCILIATION SUMMARY")
    print(f"{'=' * 50}")
    for r in results:
        status_icon = {"OK": "✓", "adjusted": "⟳", "skipped": "⊘", "error": "✗"}.get(r['status'], "?")
        diff_str = f"  (${r['diff']:>+,.2f})" if r['diff'] != 0 else ""
        print(f"  {status_icon} {r['account']:30} {r['status']}{diff_str}")
    print(f"{'=' * 50}")
```

**Step 2: Verify it compiles**

Run: `source venv/bin/activate && python -c "from money import action_reconcile; print('OK')"`

Expected: `OK`

**Step 3: Commit**

```bash
git add money.py
git commit -m "Add action_reconcile() for interactive balance reconciliation"
```

---

### Task 4: Wire up the `reconcile` subcommand in `main()`

**Files:**
- Modify: `money.py:1153-1264` (the `main()` function)

**Step 1: Add the subparser**

Add after the `categorize_parser` block (around line 1241), before `args = parser.parse_args()`:

```python
    # Sub-parser for the "reconcile" action
    reconcile_parser = subparsers.add_parser("reconcile", help="Reconcile account balances against actual bank balances.")
```

**Step 2: Add the dispatch case**

Add to the `if/elif` chain (around line 1262), before the closing comment:

```python
    elif args.action == "reconcile":
        action_reconcile()
```

**Step 3: Update the module docstring**

Add to the docstring at top of file (around line 24):

```
- reconcile: Interactive account balance reconciliation.
  Fetches asset accounts, compares Firefly balances to actual bank balances,
  and creates adjustment transactions for discrepancies.
```

**Step 4: Verify the CLI help**

Run: `source venv/bin/activate && python money.py reconcile --help`

Expected: Help text showing "Reconcile account balances against actual bank balances."

**Step 5: Smoke test the full flow**

Run: `source venv/bin/activate && python money.py reconcile`

Expected: Shows list of accounts with balances, prompts for selection. Enter a number, verify it shows the account balance and asks for actual balance. Test with matching balance (should say "Balances match!") and with different balance (should offer adjustment).

**Step 6: Commit**

```bash
git add money.py
git commit -m "Wire up reconcile subcommand in CLI"
```

---

### Task 5: Update CLAUDE.md documentation

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Add reconcile to the CLI command list**

In the "Main CLI (`money.py`)" section, add:

```bash
python money.py reconcile                      # Reconcile account balances against actual bank balances
```

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "Document reconcile subcommand in CLAUDE.md"
```
