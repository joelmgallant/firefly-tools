# Categorize Transactions Skill — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `money.py categorize` subcommand that runs the full categorization pipeline (fetch untagged, suggest, summarize, confirm, apply) and a Claude Code skill file that orchestrates it.

**Architecture:** New `action_categorize()` function in `money.py` combines the fetch/suggest logic from `action_untagged()` with the API update logic from `apply_categories.py`. A `.claude/skills/categorize-transactions.md` skill file tells Claude when and how to use it.

**Tech Stack:** Python 3.11, requests, pandas, Firefly III API

---

### Task 1: Add `_update_transaction_category()` helper to `money.py`

Extract the API update logic from `apply_categories.py` into a reusable helper function in `money.py`.

**Files:**
- Modify: `money.py` (add after `get_headers()`, around line 53)

**Step 1: Add the helper function**

Add this function after `get_headers()` at line 53:

```python
import time

def _update_transaction_category(transaction_id, category_name):
    """Update a single transaction's category via Firefly III API.

    Args:
        transaction_id: The transaction journal ID
        category_name: The category to assign

    Returns:
        Tuple of (success: bool, message: str)
    """
    if category_name == '(Uncategorized)':
        return True, "Skipped - no category suggested"

    url = f"{API_BASE_URL}/transactions/{transaction_id}"
    headers = get_headers()

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        transaction_data = response.json()
    except requests.exceptions.RequestException as e:
        return False, f"Failed to fetch transaction: {e}"

    attrs = transaction_data['data']['attributes']
    if 'transactions' not in attrs or not attrs['transactions']:
        return False, "No transaction splits found"

    attrs['transactions'][0]['category_name'] = category_name

    try:
        response = requests.put(url, headers=headers, json={'transactions': attrs['transactions']})
        response.raise_for_status()
        return True, f"Updated to '{category_name}'"
    except requests.exceptions.RequestException as e:
        return False, f"Failed to update: {e}"
```

**Step 2: Add `import time` at the top if not already present**

Check if `time` is already imported. If not, add `import time` after the existing imports (around line 28).

**Step 3: Verify the file still parses**

Run: `python -c "import money; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add money.py
git commit -m "Extract _update_transaction_category helper for reuse"
```

---

### Task 2: Add `action_categorize()` function to `money.py`

This is the main function that chains fetch → suggest → export → summarize → confirm → apply.

**Files:**
- Modify: `money.py` (add after `action_untagged()`, around line 511)

**Step 1: Add the `action_categorize` function**

Insert after `action_untagged()` (after the line that prints the summary, around line 511):

```python
def action_categorize(date_after='2025-03-01', auto_confirm=False):
    """
    Full categorization pipeline: fetch uncategorized transactions, suggest categories,
    show summary, confirm, and apply updates via API.

    Args:
        date_after: Only fetch transactions after this date (YYYY-MM-DD format)
        auto_confirm: If True, skip confirmation prompt
    """
    query_string = f"has_no_category:true date_after:{date_after}"
    print(f"Fetching uncategorized transactions since {date_after}...")

    transactions = _fetch_transactions(query_string, limit=500, paginate=True)

    if not transactions:
        print(f"No uncategorized transactions found since {date_after}.")
        return

    print(f"\nFound {len(transactions)} uncategorized transactions\n")

    # Suggest categories
    for tx in transactions:
        tx['suggested_category'] = suggest_category(tx.get('description', ''))

    df = pd.DataFrame(transactions)

    # Export CSVs (audit trail)
    data_dir = Path(__file__).parent / 'data'
    data_dir.mkdir(exist_ok=True)

    export_columns = ["date", "amount", "description", "suggested_category", "source_name", "currency_code"]
    export_df = df[export_columns].copy()
    export_df['amount'] = pd.to_numeric(export_df['amount'])
    export_df['date'] = pd.to_datetime(export_df['date'], utc=True)
    export_df = export_df.sort_values('date', ascending=False)
    export_df.to_csv(data_dir / "untagged.csv", index=False)

    update_columns = ["transaction_journal_id", "date", "amount", "description", "suggested_category"]
    update_df = df[update_columns].copy()
    update_df['date'] = pd.to_datetime(update_df['date'], utc=True)
    update_df = update_df.sort_values(['suggested_category', 'date'], ascending=[True, False])
    update_df.to_csv(data_dir / "untagged_updates.csv", index=False)

    # Summary table
    print("=" * 70)
    print("CATEGORY SUMMARY")
    print("=" * 70)
    summary = export_df.groupby('suggested_category').agg(
        count=('amount', 'size'),
        total=('amount', 'sum')
    ).sort_values('total', ascending=False)

    for category, row in summary.iterrows():
        print(f"  {category:25} {int(row['count']):4} txns  ${row['total']:>10.2f}")

    to_update = df[df['suggested_category'] != '(Uncategorized)']
    to_skip = df[df['suggested_category'] == '(Uncategorized)']
    print(f"\n  To apply:  {len(to_update)} transactions")
    print(f"  To skip:   {len(to_skip)} transactions (uncategorized)")
    print("=" * 70)

    if to_update.empty:
        print("\nNo categories to apply.")
        return

    # Confirm
    if not auto_confirm:
        response = input("\nProceed with applying categories? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Cancelled.")
            return

    # Apply
    print("\nApplying categories...\n")
    success_count = 0
    skip_count = 0
    error_count = 0

    for idx, row in df.iterrows():
        tx_id = row['transaction_journal_id']
        category = row['suggested_category']
        description = row.get('description', '')

        success, message = _update_transaction_category(tx_id, category)

        if category == '(Uncategorized)':
            skip_count += 1
        elif success:
            success_count += 1
            print(f"  ✓ {description[:50]:50} → {category}")
        else:
            error_count += 1
            print(f"  ✗ {description[:50]:50} → {message}")

        time.sleep(0.1)

    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"  ✓ Applied:  {success_count}")
    if skip_count > 0:
        print(f"  ⊘ Skipped:  {skip_count} (uncategorized)")
    if error_count > 0:
        print(f"  ✗ Errors:   {error_count}")
    print("=" * 70)
```

**Step 2: Verify parse**

Run: `python -c "import money; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add money.py
git commit -m "Add action_categorize for full categorization pipeline"
```

---

### Task 3: Wire up `categorize` subparser in `main()`

**Files:**
- Modify: `money.py` (in `main()`, around line 885)

**Step 1: Add the subparser**

Add after the `refine-budgets` subparser block (around line 886), before `args = parser.parse_args()`:

```python
    # Sub-parser for the "categorize" action
    categorize_parser = subparsers.add_parser("categorize", help="Full categorization pipeline: fetch, suggest, confirm, apply.")
    categorize_parser.add_argument(
        "--date",
        type=str,
        default="2025-03-01",
        help="Only fetch transactions after this date (YYYY-MM-DD). Default: 2025-03-01"
    )
    categorize_parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompt and apply immediately"
    )
```

**Step 2: Add the action dispatch**

Add after the `refine-budgets` dispatch (around line 904), before the `if __name__` block:

```python
    elif args.action == "categorize":
        action_categorize(date_after=args.date, auto_confirm=args.yes)
```

**Step 3: Verify the subcommand is registered**

Run: `python money.py categorize --help`
Expected: Shows help text with `--date` and `--yes` options.

**Step 4: Commit**

```bash
git add money.py
git commit -m "Wire up categorize subcommand in CLI"
```

---

### Task 4: Update module docstring in `money.py`

**Files:**
- Modify: `money.py` (lines 1-21, the module docstring)

**Step 1: Add `categorize` to the docstring**

Add to the docstring's action list:

```
- categorize: Full categorization pipeline: fetch uncategorized, suggest categories, confirm, apply.
  Accepts --date parameter (default: 2025-03-01) and --yes flag to skip confirmation.
  Exports data/untagged.csv and data/untagged_updates.csv as audit trail.
```

**Step 2: Commit**

```bash
git add money.py
git commit -m "Document categorize subcommand in module docstring"
```

---

### Task 5: Create the skill file

**Files:**
- Create: `.claude/skills/categorize-transactions.md`

**Step 1: Write the skill file**

```markdown
---
name: categorize-transactions
description: Use when categorizing uncategorized Firefly III transactions, running the categorization pipeline, doing monthly finance cleanup, or finding untagged transactions
---

# Categorize Transactions

## Overview

End-to-end pipeline for categorizing uncategorized transactions in Firefly III. Fetches untagged transactions, suggests categories via keyword matching, shows a summary, and applies updates after confirmation.

## When to Use

- User asks to categorize transactions or find untagged/uncategorized ones
- User mentions finance cleanup, monthly categorization, or transaction review
- User wants to apply suggested categories to Firefly III

## Quick Reference

| Component | Location |
|-----------|----------|
| Main command | `python money.py categorize --date YYYY-MM-DD [--yes]` |
| Keyword engine | `suggest_category()` in `money.py` |
| Audit CSVs | `data/untagged.csv`, `data/untagged_updates.csv` |
| Standalone apply | `python apply_categories.py --yes` (reads from CSV) |
| Category patterns | `category_patterns` dict inside `suggest_category()` |

## Workflow

### Step 1: Run the categorize command

```bash
cd /Users/joelmgallant/Desktop/firefly-tools
source venv/bin/activate
python money.py categorize --date 2025-03-01
```

This will:
1. Fetch all uncategorized transactions since the given date
2. Run keyword matching via `suggest_category()`
3. Export audit CSVs to `data/`
4. Print a summary table (category, count, total amount)
5. Ask for confirmation before applying

Use `--yes` to skip the confirmation prompt.

### Step 2: Review the summary

Check the summary table for:
- **(Uncategorized)** entries — these are transactions the keyword engine couldn't match
- Unexpected category assignments — keywords matching the wrong category

If there are many uncategorized transactions, consider adding new keywords (see below).

### Step 3: Apply or abort

- Type `yes` to apply all suggested categories
- Type `no` to abort and review `data/untagged_updates.csv` manually

## Adding New Keywords

When unrecognized merchants appear in the (Uncategorized) list:

1. Open `money.py` and find the `category_patterns` dict inside `suggest_category()` (around line 274)
2. Add the merchant keyword to the appropriate category list
3. Order matters — more specific patterns before generic ones
4. Keywords are matched case-insensitively against `description.upper()`
5. Re-run `python money.py categorize --date ...` to verify matches

### After adding keywords, sync rules to Firefly III:

```bash
python audit_rules.py
python parse_category_patterns.py
python compare_rules_patterns.py
python sync_rules.py --dry-run   # preview
python sync_rules.py             # apply
python trigger_all_rules.py      # run rules on existing transactions
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| No transactions found | Check `--date` is early enough, verify Firefly API is running |
| API errors during apply | Check `.env` for valid `FIREFLY_API_TOKEN`, verify Firefly is accessible |
| Wrong category suggested | Check keyword order in `category_patterns` — earlier entries take precedence |
| Stale default date | The default `--date` is `2025-03-01` — pass a more recent date if needed |
```

**Step 2: Commit**

```bash
git add .claude/skills/categorize-transactions.md
git commit -m "Add categorize-transactions skill for Claude Code"
```

---

### Task 6: Update CLAUDE.md with new subcommand

**Files:**
- Modify: `CLAUDE.md` (in the "Main CLI (`money.py`)" section)

**Step 1: Add `categorize` to the commands list**

Add to the commands block under `### Main CLI (`money.py`)`:

```bash
python money.py categorize --date 2025-03-01   # Full pipeline: fetch, suggest, confirm, apply categories
```

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "Document categorize subcommand in CLAUDE.md"
```

---

### Task 7: Smoke test the full pipeline

**Step 1: Verify CLI help**

Run: `python money.py categorize --help`
Expected: Shows usage with `--date` and `--yes/-y` flags.

**Step 2: Dry run (no `--yes`)**

Run: `python money.py categorize --date 2026-01-01`
Expected: Fetches transactions, shows summary table, prompts for confirmation. Type `no` to abort without applying.

**Step 3: Verify CSV exports**

Check that `data/untagged.csv` and `data/untagged_updates.csv` were created with the expected columns.

**Step 4: If all looks good, commit any final tweaks**

No commit needed if no changes — this is just verification.
