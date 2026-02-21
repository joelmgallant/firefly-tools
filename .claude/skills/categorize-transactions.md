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
