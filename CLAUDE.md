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

## Running the Script

The `money.py` script uses subcommands:

```bash
# Query transactions tagged with "payback" and export to CSV
python money.py payback

# Search transactions by amount
python money.py search --amount 123.45
```

## Architecture

### Core Components

- **money.py**: Single-file script organized into:
  - **API Configuration** (lines 23-40): Environment-based configuration for Firefly III API connection
  - **Generic Query Function** (`_fetch_transactions`, lines 43-79): Internal function that handles all API requests using query strings
  - **Tag-based Queries** (`fetch_transactions_by_tag`, lines 82-85): Wrapper that formats tag queries
  - **Action Functions** (lines 87-164): Command handlers for different operations
    - `action_payback()`: Default action for tagged transactions
    - `action_search_transactions()`: Search by amount
  - **CLI Entry Point** (`main()`, lines 166-201): Argument parsing using subparsers

### API Integration

- **Firefly III API**: Documented at https://api-docs.firefly-iii.org/
- **Search API**: Documented at https://docs.firefly-iii.org/references/firefly-iii/search/
- **Authentication**: Bearer token via environment variable
- **Query Format**: Uses Firefly III's search syntax (e.g., `tag:payback`, `amount:123.45`)
- **Response Structure**: Nested JSON with `data[].attributes.transactions[]` hierarchy

### Data Output

- **CSV Exports**: Stored in `data/` directory (git-ignored)
- **Standard Columns**: date, amount, description, category_name, source_name, currency_code, tags
- **File Naming**: Action-specific (e.g., `data/payback.csv`)

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