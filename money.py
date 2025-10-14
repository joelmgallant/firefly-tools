"""
Interacts with Firefly III API to perform various transaction operations.

Available actions:
- payback: Queries transactions with tag "payback" OR category "vix-events", outputs to CSV.
- search: Search transactions by amount.
- category: Search transactions by category name.
- list-rules: List all automation rules.
- untagged: Query uncategorized transactions from past 3 months, suggest categories, export to CSV.
  Exports two files:
  - data/untagged.csv: Full transaction details with suggested categories
  - data/untagged_updates.csv: Transaction IDs and categories for bulk updates
  Use apply_categories.py to apply the suggested categories to Firefly III.
"""

import json
import requests
import pandas as pd
import argparse
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# Firefly III API connection settings
API_BASE_URL = os.getenv('FIREFLY_API_BASE_URL')
API_TOKEN = os.getenv('FIREFLY_API_TOKEN')

# Validate required environment variables
if not API_BASE_URL or not API_TOKEN:
    print("Error: Missing required environment variables.")
    print("Make sure you've created a .env file based on .env.example")
    exit(1)

def get_headers():
    """Return headers for API requests"""
    return {
        "accept": "application/vnd.api+json",
        "authorization": f"Bearer {API_TOKEN}",
        "content-type": "application/json",
        "user-agent": "vscode-restclient",
    }

# Internal function to fetch transactions based on a generic query string
def _fetch_transactions(query_string, limit=500):
    """Fetch transactions based on a query string from Firefly III API."""
    url = f"{API_BASE_URL}/search/transactions"
    headers = get_headers()
    params = {"query": query_string, "limit": str(limit)}
    
    full_request_url = requests.Request('GET', url, params=params).prepare().url
    print(f"Constructed API Request URL: {full_request_url}")
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()  # Raise exception for 4XX/5XX responses
        
        data = response.json()
        records = data.get("data", [])
        
        if not records:
            print("API returned no records (empty 'data' array).")
            print(f"Raw API response data: {json.dumps(data, indent=2)}") # Print raw data if no records
            
        transactions_details = []
        
        for record in records:
            if "attributes" in record and "transactions" in record["attributes"]:
                transaction_list = record["attributes"]["transactions"]
                if transaction_list: 
                    transactions_details.append(transaction_list[0])
                else:
                    print(f"Warning: Empty 'transactions' list for record ID: {record.get('id')}")
            else:
                print(f"Warning: Missing 'attributes' or 'transactions' key for record ID: {record.get('id')}")
        
        return transactions_details
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to Firefly III API: {e}")
        print(f"URL: {url}")
        exit(1)

# Modified fetch_transactions_by_tag to use the internal _fetch_transactions
def fetch_transactions_by_tag(tag, limit=500):
    """Fetch transactions with a specific tag."""
    query_string = f"tag:{tag}"
    return _fetch_transactions(query_string, limit)

def action_payback():
    """
    Default action: Query transactions tagged with 'payback' OR in category 'Vix-Events', output to CSV.
    """
    print(f"Querying transactions with: tag=payback OR category=vix-events...")

    # Fetch both queries separately since Firefly's OR doesn't work as expected
    print(f" - Fetching tag:payback...")
    payback_transactions = _fetch_transactions("tag:payback")

    print(f" - Fetching category:vix-events...")
    vix_transactions = _fetch_transactions("category:vix-events")

    # Merge and deduplicate by transaction_journal_id
    seen_ids = set()
    transactions = []

    for tx in payback_transactions + vix_transactions:
        tx_id = tx.get('transaction_journal_id')
        if tx_id not in seen_ids:
            seen_ids.add(tx_id)
            transactions.append(tx)

    print(f" - Combined: {len(transactions)} unique transactions\n")

    df = pd.DataFrame(transactions)
    
    columns = [
        "date",
        "amount",
        "description",
        "category_name",
        "source_name",
        "currency_code",
        "tags",
    ]
    
    # Ensure data directory exists
    data_dir = Path(__file__).parent / 'data'
    data_dir.mkdir(exist_ok=True)
    
    # Export to data directory
    output_path = data_dir / "payback.csv"
    filtered_df = df[columns].copy()

    # Sort by date (most recent first)
    filtered_df['date'] = pd.to_datetime(filtered_df['date'], utc=True)
    filtered_df = filtered_df.sort_values('date', ascending=False)

    filtered_df.to_csv(output_path, index=False)
    print(f"Exported {len(filtered_df)} payback transactions to {output_path}")

# New function to search transactions by amount
def action_search_transactions(amount):
    """
    Search for transactions by a specific amount.
    Outputs results to console as JSON.
    """
    # Format amount as integer string if it's a whole number, else float string
    if amount == int(amount):
        amount_str = str(int(amount))
    else:
        amount_str = str(amount)
        
    query_string = f"amount:{amount_str}"
    
    search_description = f"amount exactly matching {amount_str}"
    
    print(f"Searching Firefly III for transactions with {search_description}...")
    print(f" - Query: '{query_string}'")

    transactions = _fetch_transactions(query_string)
            
    if transactions:
        print(f"Found {len(transactions)} transaction(s):")
        
        columns_to_display = [
            "date",
            "amount",
            "description",
            "category_name",
            "source_name",
            "currency_code",
            "tags",
        ]
        
        # Create a list of dictionaries, ensuring all keys are present
        # If a key is missing in a transaction, it will be filled with None (or NaN by pandas)
        display_data = []
        for t in transactions:
            display_data.append({col: t.get(col) for col in columns_to_display})
            
        summary_df = pd.DataFrame(display_data)
        
        # Ensure correct column order and that all desired columns are present
        summary_df = summary_df[columns_to_display]

        print(summary_df.to_string(index=False))
    else:
        print("No transactions found matching your criteria.")

def action_category(category_name):
    """
    Search for transactions by category name.
    Outputs results to console as a table.
    """
    query_string = f"category:{category_name}"

    print(f"Searching Firefly III for transactions with category '{category_name}'...")
    print(f" - Query: '{query_string}'")

    transactions = _fetch_transactions(query_string)

    if transactions:
        print(f"Found {len(transactions)} transaction(s):")

        columns_to_display = [
            "date",
            "amount",
            "description",
            "category_name",
            "source_name",
            "currency_code",
            "tags",
        ]

        display_data = []
        for t in transactions:
            display_data.append({col: t.get(col) for col in columns_to_display})

        summary_df = pd.DataFrame(display_data)
        summary_df = summary_df[columns_to_display]

        print(summary_df.to_string(index=False))
    else:
        print("No transactions found matching your criteria.")

def suggest_category(description):
    """Suggest a category based on transaction description patterns"""
    desc_upper = description.upper()

    # Mapping of keywords to categories
    category_patterns = {
        'Trip-Iceland': ['ISK @'],
        'Debt': ['LOAN PMT', 'BILL PMT', 'WWW PMT', 'AFFIRM'],
        'Transfer': ['TRANSFER', 'TFR', 'WWW TRF DDA', 'PAYMENT - THANK YOU', 'PAIEMENT - MERCI', 'ROYAL BANK OF CANADA'],
        'Banking Fee': ['MONTHLY FEE', 'ANNUAL FEE', 'BANK FEE'],
        'Alcohol': ['NSLC', 'GARRISON BREWING', 'GOOD ROBOT', 'PROPELLER BREWING', 'BULWARK CIDER',
                   '2 CROWS BREWING', 'BISHOPS CELLAR', 'OAK TREE LIQUOR', 'LIQUOR STORE',
                   'TOOTHY MOOSE', 'WEST ROYALTY LIQUOR'],
        'Food Delivery': ['DOORDASH', 'SKIPTHEDISHES', 'DD/DOORDASH'],
        'Restaurant': ['RESTAURANT', 'CAFE', 'COFFEE', 'PIZZA', 'BURGER', 'SUSHI', 'DINING',
                      'TIM HORTON', 'STARBUCKS', 'SUBWAY', 'MCDONALD', 'WENDY', 'A&W',
                      'CHATIME', 'ANTOJO TACO', 'MASHAWEE', 'A TASTE OF INDIA', 'CAFFE LUCCA',
                      'AU LIBAN', 'BONEHEADS BBQ', 'DURTY NELLYS', 'STUBBORN GOAT', 'THE PINT',
                      'DAVE\'S LOBSTER', 'SALT & ASH', 'JACK ASTOR', 'KFC', 'DAIRY QUEEN',
                      'RISTORANTE', 'BOOSTER JUICE', 'WEIRD HARBOUR', 'STEVE-O-RENO',
                      'THE MIDDLE SPOON', 'MERCANTILE SOCIAL', 'STARDUST BAR'],
        'Dessert': ['COWS', 'DAIRY BAR', 'BLACK BEAR ICE CREAM', 'ICE CREAM'],
        'Grocery': ['SOBEYS', 'SUPERSTORE', 'WHOLEFDS', 'WALMART', 'COSTCO', 'LOBLAWS', 'METRO',
                   'MASSTOWN MARKET', 'ARTHUR\'S URBAN MARKET', 'PRICE MART', 'NEEDS', 'CO-OP',
                   'HIGHMART', 'NOVA GROCERY', 'E-JOY FOOD MART', 'MISHOO\'S VARIETY',
                   'L.A.SMITH CONVENIENCE'],
        'Gas': ['PETRO', 'IRVING', 'SHELL', 'ESSO', 'MOBIL', 'CIRCLE K'],
        'Amazon': ['AMZN', 'AMAZON'],
        'Utilities': ['EASTLINK', 'TELUS', 'BELL', 'ROGERS', 'NSPI', 'ELECTRIC', 'VOIP.MS'],
        'Entertainment': ['NETFLIX', 'SPOTIFY', 'DISNEY', 'PRIME VIDEO', 'YOUTUBE', 'PSN', 'STEAM',
                         'CRUNCHYROLL', 'PATREON', 'SONY INTERACTIVE', 'FUTURE FLASH ARCADE',
                         'EVENTBRITE', 'SPIRIT HALLOWEEN', 'NAUTICUS', 'MARITIME FUN GROUP',
                         'AMBASSATOURS', 'HARBOUR QUEEN', 'CULTURE LINK'],
        'Taxi': ['UBER', 'LYFT', 'TAXI', 'REVEL', 'BIRD'],
        'Medical': ['PHARMACY', 'DRUG', 'DENTAL', 'DOCTOR', 'CLINIC', 'HOSPITAL',
                   'BAYSHORE HEALTHCARE', 'LAWTONS', 'SUNLIFE', 'QEII FOUNDATION',
                   'SUPPLEMENT KING', 'NOVA GP'],
        'Clothing': ['SIMONS', 'H&M', 'ZARA', 'GAP', 'NIKE', 'ADIDAS', 'WORK AUTHORITY'],
        'Software': ['ADOBE', 'MICROSOFT', 'APPLE', 'GOOGLE', 'OPENAI', 'CHATGPT',
                    'KAGI.COM', 'SERIF', 'OCULUS', 'TRANSUNION'],
        'Household': ['CANADIAN TIRE', 'IKEA', 'STAPLES', 'LONG & MCQUADE', 'FREAK LUNCHBOX'],
        'Vehicle': ['PARKING', 'CAR WASH', 'AUTO'],
        'Travel': ['AIR CAN', 'AIRCANADA', 'FORA TRAVEL', 'MOXY HALIFAX', 'GETNOMAD'],
        'Personal Care': ['BARBERSHOP', 'BARBER', 'SEPHORA', 'DANIELS TAILORS', 'UVAPESHOP'],
        'Vaping': ['VAPE', 'TWENTY-FOUR ELEVEN VAP'],
        'Shipping': ['UPS'],
    }

    # Check each pattern
    for category, keywords in category_patterns.items():
        for keyword in keywords:
            if keyword in desc_upper:
                return category

    # Default to uncategorized
    return '(Uncategorized)'

def action_untagged():
    """
    Query uncategorized transactions from past 3 months and suggest categories.
    """
    from datetime import datetime, timedelta

    # Calculate 3 months ago
    three_months_ago = datetime.now() - timedelta(days=90)
    date_str = three_months_ago.strftime('%Y-%m-%d')

    query_string = f"has_no_category:true date_after:{date_str}"
    print(f"Querying uncategorized transactions since {date_str}...")
    print(f" - Query: '{query_string}'")

    transactions = _fetch_transactions(query_string, limit=500)

    if not transactions:
        print("No uncategorized transactions found in the past 3 months.")
        return

    print(f" - Found {len(transactions)} uncategorized transactions\n")

    # Add suggested categories
    for tx in transactions:
        tx['suggested_category'] = suggest_category(tx.get('description', ''))

    # Create DataFrame
    df = pd.DataFrame(transactions)

    columns = [
        "date",
        "amount",
        "description",
        "suggested_category",
        "source_name",
        "currency_code",
    ]

    # Ensure data directory exists
    data_dir = Path(__file__).parent / 'data'
    data_dir.mkdir(exist_ok=True)

    # Export to data directory
    output_path = data_dir / "untagged.csv"
    filtered_df = df[columns].copy()

    # Convert amount to numeric and sort by date (most recent first)
    filtered_df['amount'] = pd.to_numeric(filtered_df['amount'])
    filtered_df['date'] = pd.to_datetime(filtered_df['date'], utc=True)
    filtered_df = filtered_df.sort_values('date', ascending=False)

    filtered_df.to_csv(output_path, index=False)
    print(f"Exported {len(filtered_df)} uncategorized transactions to {output_path}\n")

    # Export update file with transaction IDs and suggested categories
    update_columns = [
        "transaction_journal_id",
        "date",
        "amount",
        "description",
        "suggested_category",
    ]

    update_output_path = data_dir / "untagged_updates.csv"
    update_df = df[update_columns].copy()
    update_df['date'] = pd.to_datetime(update_df['date'], utc=True)
    update_df = update_df.sort_values(['suggested_category', 'date'], ascending=[True, False])
    update_df.to_csv(update_output_path, index=False)
    print(f"Exported update file to {update_output_path}")

    # Display summary grouped by suggested category
    print("=" * 80)
    print("SUGGESTED CATEGORIES")
    print("=" * 80)

    grouped = filtered_df.groupby('suggested_category')

    for category, group in sorted(grouped, key=lambda x: str(x[0])):
        print(f"\n{category}:")
        for _, row in group.iterrows():
            amount_str = f"${float(row['amount']):>10.2f}"
            date_str = row['date'].strftime('%Y-%m-%d')
            print(f"  {date_str} | {amount_str} | {row['description'][:60]}")
        print(f"  → {len(group)} transaction(s), Total: ${float(group['amount'].sum()):.2f}")

def action_list_rules():
    """
    List all automation rules from Firefly III.
    Outputs results to console as a table.
    """
    url = f"{API_BASE_URL}/rules"
    headers = get_headers()

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        data = response.json()
        rules = data.get("data", [])

        if not rules:
            print("No automation rules found.")
            return

        print(f"Found {len(rules)} automation rule(s):\n")

        rule_data = []
        for rule in rules:
            attrs = rule.get("attributes", {})

            # Build trigger summary
            triggers = attrs.get("triggers", [])
            trigger_summary = ", ".join([
                f"{t['type']}={t['value']}" for t in triggers[:2]
            ])
            if len(triggers) > 2:
                trigger_summary += f" (+{len(triggers)-2} more)"

            # Build action summary
            actions = attrs.get("actions", [])
            action_summary = ", ".join([
                f"{a['type']}={a['value']}" for a in actions[:2]
            ])
            if len(actions) > 2:
                action_summary += f" (+{len(actions)-2} more)"

            rule_data.append({
                "id": rule.get("id"),
                "active": "✓" if attrs.get("active") else "✗",
                "title": attrs.get("title"),
                "group": attrs.get("rule_group_title"),
                "triggers": trigger_summary,
                "actions": action_summary,
            })

        df = pd.DataFrame(rule_data)
        print(df.to_string(index=False))

    except requests.exceptions.RequestException as e:
        print(f"Error connecting to Firefly III API: {e}")
        exit(1)

def main():
    """Parse arguments and execute the appropriate action"""
    parser = argparse.ArgumentParser(description="Firefly III Transaction Tool")
    
    # Using subparsers to handle different actions (payback, search, etc.)
    # Making the action argument itself required.
    subparsers = parser.add_subparsers(dest="action", title="Available actions",
                                       help="Action to perform. Example: python money.py search --amount 100.50",
                                       required=True)

    # Sub-parser for the "payback" action
    # Assigning to payback_parser is conventional, even if not used for further arg additions here.
    payback_parser = subparsers.add_parser("payback", help="Query transactions with tag 'payback' OR category 'vix-events', output to CSV.")
    # payback_parser requires no additional arguments for action_payback()

    # Sub-parser for the "search" action
    search_parser = subparsers.add_parser("search", help="Search transactions by a specific amount.")
    search_parser.add_argument(
        "--amount",
        required=True,
        type=float,
        help="The exact amount to search for (e.g., 123.45 or -50.00)."
    )
    # Removed --date and --currency arguments for this basic version

    # Sub-parser for the "category" action
    category_parser = subparsers.add_parser("category", help="Search transactions by category name.")
    category_parser.add_argument(
        "category_name",
        type=str,
        help="The category name to search for (e.g., vix-events)."
    )

    # Sub-parser for the "list-rules" action
    list_rules_parser = subparsers.add_parser("list-rules", help="List all automation rules.")

    # Sub-parser for the "untagged" action
    untagged_parser = subparsers.add_parser("untagged", help="Query uncategorized transactions from past 3 months and suggest categories.")

    args = parser.parse_args()

    # Execute the selected action
    if args.action == "payback":
        action_payback()
    elif args.action == "search":
        action_search_transactions(args.amount)
    elif args.action == "category":
        action_category(args.category_name)
    elif args.action == "list-rules":
        action_list_rules()
    elif args.action == "untagged":
        action_untagged()
    # No need for an else here, as `required=True` in `add_subparsers` handles missing/invalid actions.

if __name__ == "__main__":
    main()
