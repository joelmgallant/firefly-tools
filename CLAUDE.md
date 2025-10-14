# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains Python scripts for interacting with Firefly III, an open-source personal finance manager. The main script (`money.py`) queries transaction data from a local Firefly III instance and performs various operations like filtering, searching, and exporting to CSV.

## Environment Setup

1. **Python Virtual Environment**: Use `venv/` for dependencies
   ```bash
   # Activate virtual environment
   source venv/bin/activate

   # Install dependencies
   pip install -r requirements.txt
   ```

2. **Environment Variables**: Create `.env` from `.env.example`
   ```
   FIREFLY_API_BASE_URL=http://example.com/api/v1
   FIREFLY_API_TOKEN=your_api_token_here
   ```

## Running the Scripts

The `money.py` script uses subcommands:

```bash
# Query transactions tagged with "payback" OR category "vix-events"
python money.py payback

# Search transactions by amount
python money.py search --amount 123.45

# Search by category
python money.py category "vix-events"

# List all automation rules
python money.py list-rules

# Query uncategorized transactions and suggest categories (NEW)
python money.py untagged
```

The `apply_categories.py` script applies suggested categories:

```bash
# Interactive mode
python apply_categories.py

# Non-interactive mode
python apply_categories.py --yes
```

## Architecture

### Core Components

- **money.py**: Main transaction query and analysis tool
  - **API Configuration**: Environment-based configuration for Firefly III API connection
  - **Generic Query Function** (`_fetch_transactions`): Internal function that handles all API requests using query strings
  - **Category Suggestion System** (`suggest_category`): AI pattern matching to suggest categories based on transaction descriptions
    - Supports 13+ category types (Debt, Transfer, Restaurant, Grocery, Medical, Household, etc.)
    - Uses keyword matching on transaction descriptions
    - Returns `(Uncategorized)` for unknown patterns
  - **Action Functions**: Command handlers for different operations
    - `action_payback()`: Query transactions with tag "payback" OR category "vix-events", export to CSV
    - `action_search_transactions()`: Search by exact amount
    - `action_category()`: Search by category name
    - `action_list_rules()`: List all automation rules from Firefly III
    - `action_untagged()`: **NEW** - Query uncategorized transactions from past 3 months, suggest categories, export to CSV
  - **CLI Entry Point** (`main()`): Argument parsing using subparsers

- **apply_categories.py**: Bulk category update tool
  - **Transaction Update Function** (`update_transaction_category`): Updates a single transaction's category via PUT request
  - **Main Workflow**:
    1. Reads `data/untagged_updates.csv`
    2. Shows summary of categories to apply
    3. Asks for confirmation (unless `--yes` flag)
    4. Updates each transaction via API with rate limiting (0.1s delay)
    5. Shows progress and final summary
  - **CLI Entry Point** (`main()`): Argument parsing with `--yes` flag for non-interactive mode

- **update_vix_rules.py**: Updates all vix-events rules to add "payback" tag
- **trigger_vix_rules.py**: Triggers execution of all vix-events rules on existing transactions

### API Integration

- **Firefly III API**: Documented at https://api-docs.firefly-iii.org/
- **Search API**: Documented at https://docs.firefly-iii.org/references/firefly-iii/search/
- **Authentication**: Bearer token via environment variable
- **Query Format**: Uses Firefly III's search syntax (e.g., `tag:payback`, `amount:123.45`)
- **Response Structure**: Nested JSON with `data[].attributes.transactions[]` hierarchy

### Data Output

- **CSV Exports**: Stored in `data/` directory (git-ignored)
- **Standard Columns**: date, amount, description, category_name, source_name, currency_code, tags
- **File Naming**: Action-specific
  - `data/payback.csv`: Transactions with tag "payback" OR category "vix-events" (sorted by date)
  - `data/untagged.csv`: **NEW** - All uncategorized transactions with suggested categories (sorted by date)
  - `data/untagged_updates.csv`: **NEW** - Transaction IDs and suggested categories for bulk updates (sorted by category, then date)

## Category Suggestion System

The `suggest_category()` function uses keyword matching to automatically categorize transactions:

### Supported Categories

| Category | Keywords |
|----------|----------|
| **Debt** | LOAN PMT, BILL PMT, WWW PMT |
| **Transfer** | TRANSFER, TFR |
| **Restaurant** | RESTAURANT, CAFE, COFFEE, PIZZA, BURGER, SUSHI, DINING, TIM HORTON, STARBUCKS, SUBWAY, MCDONALD, WENDY, A&W |
| **Grocery** | SOBEYS, SUPERSTORE, WHOLEFDS, WALMART, COSTCO, LOBLAWS, METRO |
| **Gas** | PETRO, IRVING, SHELL, ESSO, MOBIL, CIRCLE K |
| **Amazon** | AMZN, AMAZON |
| **Utilities** | EASTLINK, TELUS, BELL, ROGERS, NSPI, ELECTRIC |
| **Entertainment** | NETFLIX, SPOTIFY, DISNEY, PRIME VIDEO, YOUTUBE, PSN, STEAM |
| **Taxi** | UBER, LYFT, TAXI, REVEL |
| **Medical** | PHARMACY, DRUG, DENTAL, DOCTOR, CLINIC, HOSPITAL |
| **Clothing** | SIMONS, H&M, ZARA, GAP, NIKE, ADIDAS |
| **Software** | ADOBE, MICROSOFT, APPLE, GOOGLE |
| **Household** | CANADIAN TIRE, IKEA |
| **Vehicle** | PARKING, CAR WASH, AUTO |

### Adding New Categories

To add a new category or keywords:

1. Edit the `category_patterns` dictionary in `suggest_category()` function in `money.py`
2. Add your category name as a key and a list of keywords as the value
3. Keywords are matched case-insensitively against transaction descriptions
4. Earlier categories in the dictionary take precedence if multiple keywords match

## Workflow: Auto-Categorize Uncategorized Transactions

1. **Generate Suggestions**:
   ```bash
   python money.py untagged
   ```
   - Queries transactions with `has_no_category:true` from past 90 days
   - Applies pattern matching via `suggest_category()`
   - Exports `data/untagged.csv` (for review) and `data/untagged_updates.csv` (for bulk update)

2. **Review Suggestions** (Optional):
   - Open `data/untagged_updates.csv`
   - File is sorted by category, then date
   - Manually edit the `suggested_category` column if needed

3. **Apply Categories**:
   ```bash
   python apply_categories.py --yes
   ```
   - Reads `data/untagged_updates.csv`
   - Updates each transaction via PUT `/transactions/{id}`
   - Skips transactions with `(Uncategorized)` category
   - Shows progress and summary

## Adding New Actions

When adding new transaction query capabilities:

1. Create a new action function: `action_<name>()`
2. Use `_fetch_transactions(query_string)` with appropriate Firefly III query syntax
3. Add subparser in `main()` with required arguments
4. Follow the same DataFrame column selection pattern for consistency
5. Export to `data/<name>.csv` if CSV output is needed

## Dependencies

- **requests**: Firefly III API HTTP client
- **pandas**: DataFrame operations and CSV export
- **python-dotenv**: Environment variable management

## Google Calendar Integration (Related Context)

The `.github/copilot-instructions.md` file contains rules for a separate Google Calendar workflow (`finance-neo`) that tracks bills and payment status. This is related context but not currently integrated with `money.py`:

- Calendar ID: `1755c3b50e83da3aacb593d8bbc62937cad5d0e13fee28edc38e597c8e7d9f04@group.calendar.google.com`
- Paid events marked with ✅ prefix and green color (Color ID `10`)
- Monthly TSV exports with columns: Date, Name, Amount, Payment Status, Category
- Categories: Investment, Housing, Loan, Utilities, Entertainment, Personal Transfer, Insurance, Bank Fee, Credit Card, Medical
- swagger docs for firefly-iii are available at https://api-docs.firefly-iii.org/