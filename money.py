"""
Interacts with Firefly III API to perform various transaction operations.

Available actions:
- payback: Queries transactions with tag "payback" OR category "vix-events", outputs to CSV.
- search: Search transactions by amount.
- category: Search transactions by category name.
- list-rules: List all automation rules.
- untagged: Query uncategorized transactions, suggest categories, export to CSV.
  Accepts --date parameter (default: 2025-03-01)
  Exports two files:
  - data/untagged.csv: Full transaction details with suggested categories
  - data/untagged_updates.csv: Transaction IDs and categories for bulk updates
  Use apply_categories.py to apply the suggested categories to Firefly III.
- assign-budget: Assign all unbudgeted withdrawal transactions to appropriate budgets.
  Accepts --date parameter (default: 2025-03-01)
  Categories 'vix-events' → Vix-Events, 'taweel' → Taweel, others → Spending.
- refine-budgets: Refine budget assignments by moving transactions from 'Spending' to specialized budgets.
  Accepts --date parameter (default: 2025-03-01)
  Checks categories and moves: vix-events → Vix-Events, taweel → Taweel, trip/travel → Trips.
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
def _fetch_transactions(query_string, limit=500, paginate=False):
    """
    Fetch transactions based on a query string from Firefly III API.

    Args:
        query_string: The search query
        limit: Number of results per page (max 500)
        paginate: If True, fetch all results across multiple pages. If False, only fetch first page.

    Returns:
        List of transaction dictionaries
    """
    url = f"{API_BASE_URL}/search/transactions"
    headers = get_headers()

    all_transactions = []
    page = 1
    per_page = min(limit, 500)  # API max is 500

    while True:
        params = {"query": query_string, "limit": str(per_page), "page": str(page)}

        if page == 1:
            full_request_url = requests.Request('GET', url, params=params).prepare().url
            print(f"Constructed API Request URL: {full_request_url}")

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()

            data = response.json()
            records = data.get("data", [])

            if not records:
                if page == 1:
                    print("API returned no records (empty 'data' array).")
                    print(f"Raw API response data: {json.dumps(data, indent=2)}")
                break

            # Extract transaction details
            for record in records:
                if "attributes" in record and "transactions" in record["attributes"]:
                    transaction_list = record["attributes"]["transactions"]
                    if transaction_list:
                        all_transactions.append(transaction_list[0])
                    else:
                        print(f"Warning: Empty 'transactions' list for record ID: {record.get('id')}")
                else:
                    print(f"Warning: Missing 'attributes' or 'transactions' key for record ID: {record.get('id')}")

            # Check if we should continue paginating
            if not paginate:
                break  # Only fetch first page

            if len(records) < per_page:
                break  # Last page (fewer results than limit)

            page += 1
            print(f"  Fetching page {page}...")

        except requests.exceptions.RequestException as e:
            print(f"Error connecting to Firefly III API: {e}")
            print(f"URL: {url}")
            exit(1)

    if paginate and page > 1:
        print(f"  Total pages fetched: {page}")

    return all_transactions

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
    # Order matters - more specific patterns should come before generic ones
    category_patterns = {
        # Special cases - check first
        'Returns': ['ITEM RETURNED NSF', 'NSF', 'CREDIT ADJUSTMENT'],
        'Income': ['CANADA'],  # Government deposits (tax refunds, carbon rebates)
        'Trip-Iceland': ['ISK @'],

        # Banking & Transfers
        'Transfer': ['TRANSFER', 'TFR', 'WWW TRF DDA', 'PAYMENT - THANK YOU', 'PAIEMENT - MERCI',
                    'ROYAL BANK OF CANADA', 'PYMT', 'CURRENCY CLOUD', 'WWW CASH ADV',
                    'AVANCE DE FONDS', '@ $'],  # Generic payment patterns like "1 @ $45.00"
        'Banking Fee': ['MONTHLY FEE', 'ANNUAL FEE', 'BANK FEE', 'RBC - SERVICE CHARGE',
                       'SERVICE CHARGE', 'WWW OD HDLG FEE', 'OD HDLG', 'CASH - SERVICE CHARGE',
                       'RBC ROYAL BANK'],
        'Debt': ['LOAN PMT', 'BILL PMT', 'WWW PMT', 'AFFIRM'],

        # Shopping
        'Electronics': ['FLOLAB', 'BLUEAIR'],  # Screen protectors, air purifiers
        'Clothing': ['SIMONS', 'H&M', 'ZARA', 'GAP', 'NIKE', 'ADIDAS', 'WORK AUTHORITY',
                    'VIVOBAREFOOT', 'LULULEMON', 'NOREASTER APPAREL', 'HEAT WAVE VISUAL',
                    'SHADES WORLD', 'CHERRYKITTEN', 'IYKYK'],
        'Jewelry': ['BISUTERIA', 'VENUS ENVY'],
        'Amazon': ['AMZN', 'AMAZON'],
        'Household': ['CANADIAN TIRE', 'IKEA', 'STAPLES', 'LONG & MCQUADE', 'FREAK LUNCHBOX',
                     'HOME DEPOT', 'KENT', 'TIDEWATER MERCHAN', 'MOUNTAIN EQUIPMENT COMPAN',
                     'MEC', "CLEVE'S SPORTING GOODS", 'WAL-MART', 'WALMART'],

        # Food & Drink
        'Alcohol': ['NSLC', 'GARRISON BREWING', 'GOOD ROBOT', 'PROPELLER BREWING', 'BULWARK CIDER',
                   '2 CROWS BREWING', 'BISHOPS CELLAR', 'OAK TREE LIQUOR', 'LIQUOR STORE',
                   'TOOTHY MOOSE', 'WEST ROYALTY LIQUOR', 'HARVEST BEER WINE', 'HARVEST DOWNTOWN',
                   'MERCATOR VINEYARDS'],
        'Food Delivery': ['DOORDASH', 'SKIPTHEDISHES', 'DD/DOORDASH'],
        'Restaurant': ['RESTAURANT', 'CAFE', 'COFFEE', 'PIZZA', 'BURGER', 'SUSHI', 'DINING',
                      'TIM HORTON', 'STARBUCKS', 'SUBWAY', 'MCDONALD', 'WENDY', 'A&W',
                      'CHATIME', 'ANTOJO TACO', 'MASHAWEE', 'MASHASWEE', 'A TASTE OF INDIA', 'CAFFE LUCCA',
                      'AU LIBAN', 'BONEHEADS BBQ', 'DURTY NELLYS', 'STUBBORN GOAT', 'THE PINT',
                      'DAVE\'S LOBSTER', 'SALT & ASH', 'JACK ASTOR', 'KFC', 'DAIRY QUEEN',
                      'RISTORANTE', 'BOOSTER JUICE', 'WEIRD HARBOUR', 'STEVE-O-RENO',
                      'THE MIDDLE SPOON', 'MERCANTILE SOCIAL', 'STARDUST BAR',
                      'BICYCLE THIEF', 'SEAHORSE TAVERN', 'BAR STILLWELL', 'TORIDORI',
                      'SQ *THE BAO JOURNEY', 'THE NARROWS', 'QUESADA', 'CABLE WHARF',
                      'ECONOMY SHOE SHOP', 'SQ *FRABJOUS DELIGHTS', 'PINATA CANTINA',
                      'CHURRERIA', 'PANADERIA FIKA', 'LA CHAPELLE', 'LUCCIANOS',
                      'ANITA LA MAMMA DEL GELATO', 'HIGH SOCIETY', 'PRETZELMAKER',
                      'MRS. FIELD', 'KAI BRADYS', 'FERVOR PALMA', 'EWR C3 GLOBAL BAZAAR',
                      'SQ *UNCOMMON GROUNDS', 'SQ *WORLD TEA HOUSE', 'TAQUILLA'],
        'Dessert': ['COWS', 'DAIRY BAR', 'BLACK BEAR ICE CREAM', 'ICE CREAM', 'GELATO'],
        'Grocery': ['SOBEYS', 'SUPERSTORE', 'WHOLEFDS', 'WALMART', 'COSTCO', 'LOBLAWS', 'METRO',
                   'MASSTOWN MARKET', 'ARTHUR\'S URBAN MARKET', 'PRICE MART', 'NEEDS', 'CO-OP',
                   'HIGHMART', 'NOVA GROCERY', 'E-JOY FOOD MART', 'MISHOO\'S VARIETY',
                   'L.A.SMITH CONVENIENCE', 'HYDROSTONE GROCETERIA', 'POINT PLEASANT GROCERY',
                   'DOLLARAMA', 'EMPIRE', 'SUPERMAX'],

        # Transportation & Travel
        'Hotels': ['HOTEL AXEL', 'HOTEL RUMBAO', 'RUMBAO TRIBUTE', 'MOXY HALIFAX', 'HOTEL'],
        'Transportation': ['STRAIT CROSSING BRIDGE', 'HALIFAX HARBOUR BRIDGE', 'FREENOW',
                          'PREMIER CAR SERVICE', 'MASABI', 'UNITED      0', 'UNITED AIRLINES'],
        'Travel Booking': ['EXPEDIA'],
        'Travel': ['AIR CAN', 'AIRCANADA', 'FORA TRAVEL', 'GETNOMAD'],
        'Taxi': ['UBER', 'LYFT', 'TAXI', 'REVEL', 'BIRD'],
        'Gas': ['PETRO', 'IRVING', 'SHELL', 'ESSO', 'MOBIL', 'CIRCLE K'],

        # Utilities & Services
        'Utilities': ['EASTLINK', 'TELUS', 'BELL', 'ROGERS', 'NSPI', 'ELECTRIC', 'VOIP.MS'],
        'Software': ['ADOBE', 'MICROSOFT', 'APPLE', 'GOOGLE', 'OPENAI', 'CHATGPT',
                    'KAGI.COM', 'SERIF', 'OCULUS', 'TRANSUNION', 'CLAUDE.AI', 'PADDLE.NET',
                    'MIMESTREAM', 'FLEXIBITS', 'FANTASTICAL', 'TOUCHNOTE', 'BIKEMAP',
                    'PAYPAL *MYNOISE'],
        'Shipping': ['UPS'],

        # Entertainment
        'Entertainment': ['NETFLIX', 'SPOTIFY', 'DISNEY', 'PRIME VIDEO', 'PRIMEVIDEO',
                         'Ad free for PrimeVideo', 'YOUTUBE', 'PSN', 'STEAM',
                         'CRUNCHYROLL', 'PATREON', 'SONY INTERACTIVE', 'FUTURE FLASH ARCADE',
                         'EVENTBRITE', 'SPIRIT HALLOWEEN', 'NAUTICUS', 'MARITIME FUN GROUP',
                         'AMBASSATOURS', 'HARBOUR QUEEN', 'CULTURE LINK', 'PLAYSTATION NETWORK',
                         'STEAMGAMES', 'CINEPLEX', 'HALIMAC AXE THROWING', 'SEVEN BAYS BOULDERING',
                         'ACTIVATE HALIFAX', 'SQ *FUTURE FLASH ARCAD', 'SANDSPIT', 'TILT-A-WHI',
                         'NBX*LIVE ART DANCE', 'HFX FEST', 'HALIFAXMUSIC', 'SHOWPASS'],

        # Health & Personal
        'Medical': ['PHARMACY', 'DRUG', 'DENTAL', 'DOCTOR', 'CLINIC', 'HOSPITAL',
                   'BAYSHORE HEALTHCARE', 'LAWTONS', 'SUNLIFE', 'QEII FOUNDATION',
                   'SUPPLEMENT KING', 'NOVA GP', 'FARMACIA', 'WALGREENS', "MURPHY'S QUEEN STREET PHA"],
        'Personal Care': ['BARBERSHOP', 'BARBER', 'SEPHORA', 'DANIELS TAILORS', 'UVAPESHOP'],
        'Vaping': ['VAPE', 'TWENTY-FOUR ELEVEN VAP'],

        # Other
        'Vehicle': ['PARKING', 'CAR WASH', 'AUTO', 'ACCESS NOVA SCOTIA-RMV'],  # RMV = Registry of Motor Vehicles
        'Donations': ['DONOR DRIVE', 'CCS DONOR', 'HALIFAX PRIDE'],
        'Vending': ['SH VENDING', 'VENDING', 'AMFM VENDING'],
    }

    # Check each pattern
    for category, keywords in category_patterns.items():
        for keyword in keywords:
            if keyword in desc_upper:
                # Special handling for "CANADA" - exclude company names
                if keyword == 'CANADA' and 'INC' in desc_upper:
                    continue
                return category

    # Default to uncategorized
    return '(Uncategorized)'

def action_untagged(date_after='2025-03-01'):
    """
    Query uncategorized transactions and suggest categories.
    Uses pagination to fetch all results.

    Args:
        date_after: Only fetch transactions after this date (YYYY-MM-DD format)
    """
    query_string = f"has_no_category:true date_after:{date_after}"
    print(f"Querying uncategorized transactions since {date_after}...")
    print(f" - Query: '{query_string}'")
    print(f" - Fetching page 1...")

    transactions = _fetch_transactions(query_string, limit=500, paginate=True)

    if not transactions:
        print(f"No uncategorized transactions found since {date_after}.")
        return

    print(f"\n - Found {len(transactions)} total uncategorized transactions\n")

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

def action_assign_budget(date_after='2025-03-01'):
    """
    Assign all unbudgeted transactions to appropriate budgets.

    Args:
        date_after: Only fetch transactions after this date (YYYY-MM-DD format)
    """
    query_string = f"has_no_budget:true date_after:{date_after}"
    print(f"Querying unbudgeted transactions since {date_after}...")
    print(f" - Query: '{query_string}'")

    # Fetch all unbudgeted transactions
    url = f"{API_BASE_URL}/search/transactions"
    headers = get_headers()
    params = {"query": query_string, "limit": "500"}

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()

        data = response.json()
        records = data.get("data", [])

        if not records:
            print("No unbudgeted transactions found.")
            return

        print(f" - Found {len(records)} unbudgeted transactions\n")

        # Extract transaction journal IDs
        transaction_ids = []
        transaction_details = []

        for record in records:
            if "attributes" in record and "transactions" in record["attributes"]:
                tx_list = record["attributes"]["transactions"]
                if tx_list:
                    tx = tx_list[0]
                    # Only process withdrawals (expenses), skip deposits/transfers
                    if tx.get('type') == 'withdrawal':
                        transaction_ids.append(record["id"])
                        transaction_details.append({
                            'id': record["id"],
                            'date': tx.get('date'),
                            'description': tx.get('description'),
                            'amount': tx.get('amount'),
                            'category': tx.get('category_name', '')
                        })

        if not transaction_ids:
            print("No withdrawal transactions found to budget.")
            return

        print(f"Found {len(transaction_ids)} withdrawal transactions to assign to 'Spending' budget")
        print(f"\nAssigning budget to {len(transaction_ids)} transactions...")

        # Update each transaction with appropriate budget based on category
        success_count = 0
        error_count = 0
        budget_counts = {}

        for i, tx_id in enumerate(transaction_ids, 1):
            tx_info = transaction_details[i-1]
            category = (tx_info.get('category') or '').lower()

            # Determine budget based on category
            if 'vix-events' in category:
                budget_name = "Vix-Events"
            elif 'taweel' in category:
                budget_name = "Taweel"
            else:
                budget_name = "Spending"

            # Track budget assignments
            budget_counts[budget_name] = budget_counts.get(budget_name, 0) + 1

            try:
                update_response = requests.put(
                    f"{API_BASE_URL}/transactions/{tx_id}",
                    headers=headers,
                    json={
                        "transactions": [{
                            "budget_name": budget_name
                        }]
                    }
                )

                if update_response.status_code in [200, 204]:
                    success_count += 1
                    print(f"[{i}/{len(transaction_ids)}] ✓ {budget_name:12} | {tx_info['description'][:40]}")
                else:
                    error_count += 1
                    print(f"[{i}/{len(transaction_ids)}] ✗ Error {update_response.status_code} | {tx_info['description'][:40]}")

                # Rate limiting - small delay between requests
                import time
                time.sleep(0.1)

            except requests.exceptions.RequestException as e:
                error_count += 1
                print(f"[{i}/{len(transaction_ids)}] ✗ Error: {tx_info['description'][:40]} - {e}")

        print("\n" + "=" * 80)
        print("Summary:")
        print(f"  ✓ Successfully updated: {success_count}")
        if error_count > 0:
            print(f"  ✗ Errors: {error_count}")
        print("\nBudget assignments:")
        for budget, count in sorted(budget_counts.items()):
            print(f"  {budget}: {count} transaction(s)")
        print("=" * 80)

    except requests.exceptions.RequestException as e:
        print(f"Error connecting to Firefly III API: {e}")
        exit(1)

def action_refine_budgets(date_after='2025-03-01'):
    """
    Refine budget assignments for transactions in 'Spending' budget.
    Checks if transactions should be in Taweel, Vix-Events, or Trips budgets based on category.

    Args:
        date_after: Only fetch transactions after this date (YYYY-MM-DD format)
    """
    query_string = f"budget:Spending date_after:{date_after}"
    print(f"Querying 'Spending' budget transactions since {date_after}...")
    print(f" - Query: '{query_string}'")

    # Fetch all Spending budget transactions
    url = f"{API_BASE_URL}/search/transactions"
    headers = get_headers()
    params = {"query": query_string, "limit": "500"}

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()

        data = response.json()
        records = data.get("data", [])

        if not records:
            print("No transactions found in 'Spending' budget.")
            return

        print(f" - Found {len(records)} transactions in 'Spending' budget\n")

        # Extract transaction details
        transaction_ids = []
        transaction_details = []

        for record in records:
            if "attributes" in record and "transactions" in record["attributes"]:
                tx_list = record["attributes"]["transactions"]
                if tx_list:
                    tx = tx_list[0]
                    # Only process withdrawals (expenses)
                    if tx.get('type') == 'withdrawal':
                        transaction_ids.append(record["id"])
                        transaction_details.append({
                            'id': record["id"],
                            'date': tx.get('date'),
                            'description': tx.get('description'),
                            'amount': tx.get('amount'),
                            'category': tx.get('category_name', '')
                        })

        if not transaction_ids:
            print("No withdrawal transactions found to refine.")
            return

        # Determine which transactions need budget changes
        changes_needed = []
        for i, tx_info in enumerate(transaction_details):
            category = (tx_info.get('category') or '').lower()

            # Determine correct budget based on category
            new_budget = None
            if 'vix-events' in category:
                new_budget = "Vix-Events"
            elif 'taweel' in category:
                new_budget = "Taweel"
            elif any(trip_cat in category for trip_cat in ['trip', 'travel']):
                # Matches: Trip-Iceland, Travel, Travel Booking
                new_budget = "Trips"

            # Only add if budget needs to change
            if new_budget:
                changes_needed.append({
                    'tx_id': transaction_ids[i],
                    'tx_info': tx_info,
                    'new_budget': new_budget
                })

        if not changes_needed:
            print("No budget refinements needed. All transactions are correctly budgeted!")
            return

        print(f"Found {len(changes_needed)} transactions that need budget refinement:")
        print(f"  - Spending → Vix-Events: {sum(1 for c in changes_needed if c['new_budget'] == 'Vix-Events')}")
        print(f"  - Spending → Taweel: {sum(1 for c in changes_needed if c['new_budget'] == 'Taweel')}")
        print(f"  - Spending → Trips: {sum(1 for c in changes_needed if c['new_budget'] == 'Trips')}")
        print(f"\nRefining budget assignments...\n")

        # Update transactions
        success_count = 0
        error_count = 0
        budget_counts = {}

        for i, change in enumerate(changes_needed, 1):
            tx_id = change['tx_id']
            tx_info = change['tx_info']
            new_budget = change['new_budget']

            budget_counts[new_budget] = budget_counts.get(new_budget, 0) + 1

            try:
                update_response = requests.put(
                    f"{API_BASE_URL}/transactions/{tx_id}",
                    headers=headers,
                    json={
                        "transactions": [{
                            "budget_name": new_budget
                        }]
                    }
                )

                if update_response.status_code in [200, 204]:
                    success_count += 1
                    category_display = tx_info.get('category', '')[:15]
                    print(f"[{i}/{len(changes_needed)}] ✓ {new_budget:12} | {category_display:15} | {tx_info['description'][:30]}")
                else:
                    error_count += 1
                    print(f"[{i}/{len(changes_needed)}] ✗ Error {update_response.status_code} | {tx_info['description'][:30]}")

                # Rate limiting
                import time
                time.sleep(0.1)

            except requests.exceptions.RequestException as e:
                error_count += 1
                print(f"[{i}/{len(changes_needed)}] ✗ Error: {tx_info['description'][:30]} - {e}")

        print("\n" + "=" * 80)
        print("Summary:")
        print(f"  ✓ Successfully refined: {success_count}")
        if error_count > 0:
            print(f"  ✗ Errors: {error_count}")
        print(f"\nTransactions moved from Spending to:")
        for budget, count in sorted(budget_counts.items()):
            print(f"  {budget}: {count} transaction(s)")
        print("=" * 80)

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
    untagged_parser = subparsers.add_parser("untagged", help="Query uncategorized transactions and suggest categories.")
    untagged_parser.add_argument(
        "--date",
        type=str,
        default="2025-03-01",
        help="Only fetch transactions after this date (YYYY-MM-DD). Default: 2025-03-01"
    )

    # Sub-parser for the "assign-budget" action
    assign_budget_parser = subparsers.add_parser("assign-budget", help="Assign all unbudgeted transactions to appropriate budgets.")
    assign_budget_parser.add_argument(
        "--date",
        type=str,
        default="2025-03-01",
        help="Only fetch transactions after this date (YYYY-MM-DD). Default: 2025-03-01"
    )

    # Sub-parser for the "refine-budgets" action
    refine_budgets_parser = subparsers.add_parser("refine-budgets", help="Refine budget assignments by moving transactions from 'Spending' to specialized budgets.")
    refine_budgets_parser.add_argument(
        "--date",
        type=str,
        default="2025-03-01",
        help="Only fetch transactions after this date (YYYY-MM-DD). Default: 2025-03-01"
    )

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
        action_untagged(date_after=args.date)
    elif args.action == "assign-budget":
        action_assign_budget(date_after=args.date)
    elif args.action == "refine-budgets":
        action_refine_budgets(date_after=args.date)
    # No need for an else here, as `required=True` in `add_subparsers` handles missing/invalid actions.

if __name__ == "__main__":
    main()
