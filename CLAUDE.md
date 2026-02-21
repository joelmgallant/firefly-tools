# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python scripts for automating personal finance management via [Firefly III](https://www.firefly-iii.org/) API. The tools handle transaction categorization, budget assignment, and automation rule synchronization.

## Environment Setup

```bash
source venv/bin/activate
pip install -r requirements.txt
# Copy .env.example to .env and fill in FIREFLY_API_BASE_URL and FIREFLY_API_TOKEN
```

## Commands

### Main CLI (`money.py`)

All subcommands accept `--date YYYY-MM-DD` where applicable (default: `2025-03-01`).

```bash
python money.py payback                        # Export payback/vix-events transactions to CSV
python money.py search --amount 123.45         # Search by exact amount
python money.py category "vix-events"          # Search by category name
python money.py list-rules                     # List all automation rules
python money.py untagged --date 2025-03-01     # Find uncategorized transactions, suggest categories
python money.py assign-budget --date 2025-03-01  # Assign budgets to unbudgeted withdrawals
python money.py refine-budgets --date 2025-03-01 # Move mis-budgeted transactions to correct budgets
python money.py categorize --date 2025-03-01   # Full pipeline: fetch, suggest, confirm, apply categories
```

### Standalone Scripts

```bash
python apply_categories.py [--yes]    # Apply suggested categories from data/untagged_updates.csv
python sync_rules.py [--dry-run]      # Sync local category patterns to Firefly III automation rules
python audit_rules.py                 # Export all Firefly rules to data/firefly_rules.json
python trigger_all_rules.py           # Trigger all active rules on existing transactions
python assign_transfer_budget.py      # Assign all Transfer-category transactions to Transfers budget
python compare_rules_patterns.py      # Compare Firefly rules vs local patterns, output gaps
python parse_category_patterns.py     # Export category_patterns dict to data/category_patterns.json
```

## Architecture

### Data Flow: Two Main Pipelines

**Categorization Pipeline:**
1. `money.py untagged` -- queries uncategorized transactions, runs `suggest_category()` keyword matching, exports `data/untagged.csv` + `data/untagged_updates.csv`
2. (Optional) Manual review/edit of `data/untagged_updates.csv`
3. `apply_categories.py --yes` -- reads CSV, PUTs category updates to Firefly API

**Rule Synchronization Pipeline:**
1. `audit_rules.py` -- fetches all rules from Firefly, saves `data/firefly_rules.json`
2. `parse_category_patterns.py` -- exports `suggest_category()` patterns to `data/category_patterns.json`
3. `compare_rules_patterns.py` -- diffs rules vs patterns, outputs `data/rules_comparison.json`
4. `sync_rules.py --dry-run` -- previews rule updates/creates based on comparison
5. `sync_rules.py` -- applies changes to Firefly III
6. `trigger_all_rules.py` -- runs all active rules on existing transactions

### Core Patterns

- **`_fetch_transactions(query_string, limit, paginate)`** in `money.py` is the central API query function. All transaction searches use Firefly III search syntax (e.g., `tag:payback`, `has_no_category:true`, `date_after:2025-01-01`).
- **`suggest_category(description)`** in `money.py` is the keyword-matching engine. It uses an ordered dict of `{category: [keywords]}` where earlier entries take precedence. Keywords are matched case-insensitively against `description.upper()`.
- **API response structure**: `data[].attributes.transactions[]` -- each record wraps a list of transaction splits; scripts always use `[0]` (first split).
- **Shared boilerplate**: Every script independently loads `.env`, creates headers with Bearer token. There is no shared module -- each script is self-contained.
- **Rate limiting**: All bulk-update scripts use `time.sleep(0.1)` between API calls.
- **CSV exports** go to `data/` (git-ignored). Standard columns: date, amount, description, category_name, source_name, currency_code, tags.

### Budget Assignment Logic (`money.py`)

- `assign-budget`: Routes unbudgeted withdrawals -- `vix-events` category to `Vix-Events` budget, `taweel` to `Taweel`, everything else to `Spending`
- `refine-budgets`: Re-routes `Spending` transactions -- checks for `vix-events`/`taweel`/`trip`/`travel` categories and moves to `Vix-Events`/`Taweel`/`Trips` budgets

### Adding New Actions to `money.py`

1. Create `action_<name>(date_after=...)` function
2. Use `_fetch_transactions(query_string)` with Firefly search syntax
3. Add subparser in `main()` with `--date` arg if needed
4. Follow existing DataFrame column selection pattern
5. Export to `data/<name>.csv` if needed

### Adding New Category Keywords

Edit the `category_patterns` dict in `suggest_category()` in `money.py`. Order matters -- more specific patterns before generic ones. After updating, run the rule sync pipeline to push changes to Firefly III automation rules.

## API References

- Firefly III API: https://api-docs.firefly-iii.org/
- Search syntax: https://docs.firefly-iii.org/references/firefly-iii/search/

## Related Context

The `.github/copilot-instructions.md` file documents a separate Google Calendar workflow (`finance-neo`) for tracking bills/payment status. Calendar ID: `1755c3b50e83da3aacb593d8bbc62937cad5d0e13fee28edc38e597c8e7d9f04@group.calendar.google.com`. Not currently integrated with the Firefly scripts.
