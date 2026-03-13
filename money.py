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
- recategorize: Re-run suggest_category() on all transactions in a category and reclassify mismatches.
  Usage: python money.py recategorize "Taxi"
- categorize: Full categorization pipeline: fetch uncategorized, suggest categories, confirm, apply.
  Accepts --date parameter (default: 2025-03-01) and --yes flag to skip confirmation.
  Exports data/untagged.csv and data/untagged_updates.csv as audit trail.
- reconcile: Interactive account balance reconciliation.
  Fetches asset accounts, compares Firefly balances to actual bank balances,
  and creates adjustment transactions for discrepancies.
- backup: Back up Firefly III Docker volumes (database + uploads) to ~/backups/firefly/.
  Creates timestamped tar.gz archives of both MariaDB data and uploads volumes.
"""

import json
import time
import requests
import pandas as pd
import argparse
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
env_dir = Path(__file__).parent
load_dotenv(dotenv_path=env_dir / '.env')

# Firefly III API connection settings
API_BASE_URL = os.getenv('FIREFLY_API_BASE_URL')
API_TOKEN = os.getenv('FIREFLY_API_TOKEN')

# Validate required environment variables
if not API_BASE_URL or not API_TOKEN:
    print("Error: Missing required environment variables.")
    print("Make sure you've created a .env file based on .env.example")
    exit(1)

# Try primary URL; fall back to .env.localhost if unreachable
def _check_api_connectivity(url):
    try:
        requests.get(f"{url}/about", headers={"accept": "application/vnd.api+json"}, timeout=3)
        return True
    except requests.exceptions.RequestException:
        return False

if not _check_api_connectivity(API_BASE_URL):
    fallback_env = env_dir / '.env.localhost'
    if fallback_env.exists():
        from dotenv import dotenv_values
        fallback = dotenv_values(fallback_env)
        fallback_url = fallback.get('FIREFLY_API_BASE_URL')
        if fallback_url and _check_api_connectivity(fallback_url):
            print(f"Primary API unreachable, using fallback: {fallback_url}")
            API_BASE_URL = fallback_url
            API_TOKEN = fallback.get('FIREFLY_API_TOKEN', API_TOKEN)

def get_headers():
    """Return headers for API requests"""
    return {
        "accept": "application/vnd.api+json",
        "authorization": f"Bearer {API_TOKEN}",
        "content-type": "application/json",
        "user-agent": "vscode-restclient",
    }

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

    # Tag reconciliation adjustment transactions with their own category
    if 'RECONCILIATION ADJUSTMENT' in desc_upper:
        return 'Reconciliation'

    # Mapping of keywords to categories
    # Order matters - more specific patterns should come before generic ones
    category_patterns = {
        # Special cases - check first
        'Returns': ['ITEM RETURNED NSF', 'NSF', 'CREDIT ADJUSTMENT'],
        'Income': ['UBIQUE NETWORKS', 'NET PAY', 'INITIAL CARRYOVER'],  # Salary and deposits
        'Trip-Iceland': ['ISK @'],

        # Banking & Transfers
        'Transfer': ['TRANSFER', 'TFR', 'WWW TRF DDA', 'PAYMENT - THANK YOU', 'PAIEMENT - MERCI',
                    'ROYAL BANK OF CANADA', 'PYMT', 'CURRENCY CLOUD', 'WWW CASH ADV',
                    'AVANCE DE FONDS', '@ $', 'USD @', 'EUR @', 'INTERAC NTWK/RESEAU'],  # Currency conversions & e-transfers
        'Banking Fee': ['MONTHLY FEE', 'ANNUAL FEE', 'BANK FEE', 'RBC - SERVICE CHARGE',
                       'SERVICE CHARGE', 'WWW OD HDLG FEE', 'OD HDLG', 'CASH - SERVICE CHARGE',
                       'RBC ROYAL BANK', 'CASH ADVANCE FEE', 'DEC 2024 FEES',
                       'TD PAYMENT PLAN'],
        'Debt': ['LOAN PMT', 'BILL PMT', 'WWW PMT', 'AFFIRM', 'WWW PAYMENT', 'AMEX REGULAR',
                'CAPITAL ONE M', 'PAYBRIGHT'],

        # Shopping
        'Electronics': ['FLOLAB', 'BLUEAIR', 'BEST BUY', 'BLACKMAGIC CLOUD'],
        'Clothing': ['SIMONS', 'H&M', 'ZARA', 'GAP', 'NIKE', 'ADIDAS', 'WORK AUTHORITY',
                    'VIVOBAREFOOT', 'LULULEMON', 'NOREASTER APPAREL', 'HEAT WAVE VISUAL',
                    'SHADES WORLD', 'CHERRYKITTEN', 'IYKYK', 'AVIATOR NATION', 'LEATHER MAN INC',
                    "LEVI'S", 'LACOSTE', 'NOTHERN WATTERS', 'MANHATTAN WARDROBE', 'ANDAR 1015'],
        'Jewelry': ['BISUTERIA', 'VENUS ENVY', 'JAMES AND SON'],
        'Household': ['CANADIAN TIRE', 'IKEA', 'STAPLES', 'LONG & MCQUADE', 'FREAK LUNCHBOX',
                     'HOME DEPOT', 'KENT', 'TIDEWATER MERCHAN', 'MOUNTAIN EQUIPMENT COMPAN',
                     'MEC', "CLEVE'S SPORTING GOODS", 'WAL-MART', 'WALMART', 'ATLANTIC GARDENS',
                     'WINNERS', 'HOMESENSE', 'MICHAELS', 'GIANT TIGER',
                     'CRATE AND BARREL', 'WILLIAMS-SONOMA', 'CDN TIRE STORE', 'TARGET',
                     'FLOWER SHOP', 'TOSH CO', 'HOW BAZAAR', 'MASTERMIND TOYS',
                     'CANADA COMPUTERS', 'CHICORY BLUE'],

        # Food & Drink
        'Alcohol': ['NSLC', 'GARRISON BREWING', 'GOOD ROBOT', 'PROPELLER BREWING', 'BULWARK CIDER',
                   '2 CROWS BREWING', 'BISHOPS CELLAR', 'OAK TREE LIQUOR', 'LIQUOR STORE',
                   'TOOTHY MOOSE', 'WEST ROYALTY LIQUOR', 'HARVEST BEER WINE', 'HARVEST DOWNTOWN',
                   'MERCATOR VINEYARDS', 'CHAIN YARD CIDER', 'SQ *PROPELLER B', 'BRASSERIE MCAUSLAN',
                   'ALCOOL NB LIQUOR'],
        'Mealkit': ['CHEFCOOKIT', 'COOK IT', 'FRESH PREP'],
        'Food Delivery': ['DOORDASH', 'SKIPTHEDISHES', 'DD/DOORDASH', 'UBEREATS', 'UBER   EATS',
                         'UBER* EATS', 'UBER   *EATS'],
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
                      'SQ *UNCOMMON GROUNDS', 'SQ *WORLD TEA HOUSE', 'TAQUILLA',
                      'PASQUIER', 'NEW GLASGOW LOBSTER', 'PITA PIT', 'CANTON SAIGON', 'PUR & SIMPLE',
                      'INDOCHINE BANH MI', 'MEZZA LEBANESE', 'PUMP HOUSE', 'TWO DOORS DOWN',
                      'HELIUM COMEDY', 'GONG CHA', 'CHUNGCHUN HOTDOG', "WILLY'S FRESH CUT",
                      'TSUJIRI', "JOHNNY", 'CARNEGIE DINER', 'DENNY', 'CORNER BAKERY',
                      'WESTSIDE MARKET', 'CROSSOVER', 'SHAKE SHACK', 'FRESHLY SQUEEZED',
                      "LULU'S PASTA BAR", 'KRAVE SPRING', "DAVE'S FRUIT", 'BAR LE CAMPUS',
                      'LE PETIT', 'MANCHU WOK', 'TACO BOYZ', 'AFRITE KITCHEN', 'FIVE GUYS',
                      'BAKERY', 'TURBO CHICKEN', 'TRIDENT BOOKSELLERS', 'SAPORI ITALIAN',
                      'MELTWICH', 'CANTON', 'PUMP HOUSE BREWPUB', 'DRIFT SALON & BAR',
                      'SMOKEY HOUSE', 'LIONS HEAD TAVERN', 'WATER STREET WILSON', 'CRAFT BEER',
                      'UNCOMMON GROUNDS', 'PORT PUB', 'MAXWELLS PLUM', 'PROXI DUTCH',
                      'NOOK AND CRANNY', 'BOTROW', 'NOGGINS CORNER', 'GREIG POTTERY',
                      '540 NORTH', 'TRAIN STATION BIKE', 'ESCONDITE', 'BAR RENARD', 'NINE LOCKS',
                      'THE CANTEEN', 'DOGS ON WHEELS', 'DRIFT SALON', 'BOATHOUSE BITES',
                      "HARRY'S DAIRY", 'FIDDLING FISHERMA', 'YUKYUKS', 'HIMALAYAN CURRY',
                      'AUCTION HOUSE', 'THORNBLOOM', 'ELI AND TRIX', 'GOBONG', 'HOUSE FRIENDS',
                      'FINN FOLK', 'LFBAKERY', 'EAST COAST BAKERY', 'ONROUTE', 'HUDSON ST',
                      'DUNKIN', 'MILANO', 'CAVICCHI', 'FOG COMPANY', 'LANE FARMS',
                      'BEIRUT WAY', 'TST-', 'TST*', 'SUDA TABLE', 'SEBASTIANS NEWS',
                      'AMC ONLINE', 'BOWL', 'CHESS PIECE', 'SNOOTY FOX',
                      'BROWN HOUND', 'BREAD N WINE', 'PARTYBOY', 'OWLS HOLLOW', 'DA ZERO',
                      'BROADWAY', 'PRE ROLL WORLD', 'STILLWELL BREWING',
                      'AWASH', 'CHINATOWN DELI', 'DILLY DALLY', 'SIMS STEAKHOUSE',
                      'RATINAUD', "FINBAR", 'PAPA JOE', 'TIDE & TALES', 'BREAD LOUNGE',
                      'FISH TALES', 'FIN FOLK', 'GRECO', "RUDY", 'WIRED MONK',
                      'BAGEL MONTREAL', 'EAST ROYALTY', 'FOURTH PULL', 'BROCHETTERIE',
                      'BK #', 'DD/BR', 'MIKE & CO', 'FLYNNS', 'ALEXANDRAS',
                      'SICILIAN', 'TONY\'S DONAIR', 'KAJIKI', 'BOSTON PIZZA',
                      'JONG\'S FOOD', "BIRD'S NEST CAFE", 'BAR GEORGE',
                      'EASTERN TEA BAR', 'RAMBLERS', 'SHIPWRIGHT BREWING'],
        'Dessert': ['COWS', 'DAIRY BAR', 'BLACK BEAR ICE CREAM', 'ICE CREAM', 'GELATO',
                   'PANADERIA', 'AMORINO', 'GELATERIA', 'LA MAMMA DEL GELATO',
                   'CHOCOLAT', 'ROUSSEAU CHOCOLAT', 'MAGNOLIA BAKERY',
                   'SEES CANDIES', 'SUGAH', 'LEONIDAS', 'FROZEN CUSTARD', 'BOMBONIERA',
                   'BEAVERTAILS'],
        'Grocery': ['SOBEYS', 'SUPERSTORE', 'WHOLEFDS', 'WALMART', 'COSTCO', 'LOBLAWS', 'METRO',
                   'MASSTOWN MARKET', 'ARTHUR\'S URBAN MARKET', 'PRICE MART', 'NEEDS', 'CO-OP',
                   'HIGHMART', 'NOVA GROCERY', 'E-JOY FOOD MART', 'MISHOO\'S VARIETY',
                   'L.A.SMITH CONVENIENCE', 'HYDROSTONE GROCETERIA', 'POINT PLEASANT GROCERY',
                   'DOLLARAMA', 'EMPIRE', 'SUPERMAX', 'GETAWAY BUTCHER', 'MR SEAFOOD',
                   'WINSLOE CONVENIENCE', 'LOCAL SOURCE', 'JEAN COUTU', 'VALUE VILLAGE',
                   'COUCHE-TARD', 'MARKET', 'DEPANNEUR', 'FARGI', 'RAFI SUPERMARKET',
                   'PROXIM SUPERMERCATS', 'STUYTOWN MARKETPLACE', 'SEAFOOD', 'LOBSTER',
                   'SALLY BEAUTY', 'HANDPIE COMPANY', 'CAVENDISH TOURIST', 'DESERRES',
                   'CLOVERFARM', 'RIVERVIEW COUNTRY', 'FRESC I VERD',
                   "DUTCHMAN'S CHEES", 'ACIDLEAGUE', "ARTHUR'S URBAN"],

        # Transportation & Travel
        'Hotels': ['HOTEL AXEL', 'HOTEL RUMBAO', 'RUMBAO TRIBUTE', 'MOXY HALIFAX', 'HOTEL',
                  'FOUR POINTS BY SHERATO', 'ESME MIAMI'],
        'Transportation': ['STRAIT CROSSING BRIDGE', 'HALIFAX HARBOUR BRIDGE', 'FREENOW',
                          'PREMIER CAR SERVICE', 'MASABI', 'UNITED      0', 'UNITED AIRLINES',
                          'MTA*NYCT PAYGO', 'STM ', 'A30 EXPRESS'],
        'Travel Booking': ['EXPEDIA', 'FLIGHTCONNECTIONS'],
        'Travel': ['AIR CAN', 'AIRCANADA', 'FORA TRAVEL', 'GETNOMAD', 'VIRGIN VOYAGES',
                  'VIRGIN CRUISE', 'WESTJET', 'DELTA AIR'],
        'Taxi': ['UBERTRIP', 'UBER   TRIP', 'UBER* TRIP', 'UBER   *TRIP',
                'LYFT', 'TAXI', 'REVEL', 'BIRD', 'MOVE SCOOTER', 'HFXESCOOTERS'],
        'Gas': ['PETRO', 'IRVING', 'SHELL', 'ESSO', 'MOBIL', 'CIRCLE K', 'ULTRAMAR',
               'CDN TIRE GASBAR', 'FAST FUEL'],

        # Utilities & Services
        'Utilities': ['EASTLINK', 'TELUS', 'BELL', 'ROGERS', 'NSPI', 'ELECTRIC', 'VOIP.MS'],
        'Software': ['AMAZON WEB SERVICES', 'AWS', 'ADOBE', 'MICROSOFT', 'APPLE', 'GOOGLE', 'OPENAI', 'CHATGPT',
                    'KAGI.COM', 'SERIF', 'OCULUS', 'TRANSUNION', 'CLAUDE.AI', 'PADDLE.NET',
                    'MIMESTREAM', 'FLEXIBITS', 'FANTASTICAL', 'TOUCHNOTE', 'BIKEMAP',
                    'PAYPAL *MYNOISE', 'OTTER.AI', 'COURSRA', 'SIMPLETAX', 'BITWARDEN',
                    'RUNPOD.IO', 'VAGON INC', 'DRI*NVIDIA', 'TWITCH', 'SMIGHT-TIP',
                    'ITCH.IO', 'VPN*', 'NINTENDO', 'GODADDY',
                    'UBERONE', 'UBERPASS', 'UBERDIRECTCA', 'UBER* ONE', 'UBER*ONE',
                    'ELEVENLABS', 'SQSP*', 'ECOBEE', 'CANVA*', 'FACEBK',
                    'SEATGEEK', 'PAYPAL *ITCH'],
        'Amazon': ['AMZN', 'AMAZON'],
        'Shipping': ['UPS'],

        # Entertainment
        'Entertainment': ['NETFLIX', 'SPOTIFY', 'DISNEY', 'PRIME VIDEO', 'PRIMEVIDEO',
                         'Ad free for PrimeVideo', 'YOUTUBE', 'PSN', 'STEAM',
                         'CRUNCHYROLL', 'PATREON', 'SONY INTERACTIVE', 'FUTURE FLASH ARCADE',
                         'EVENTBRITE', 'SPIRIT HALLOWEEN', 'NAUTICUS', 'MARITIME FUN GROUP',
                         'AMBASSATOURS', 'HARBOUR QUEEN', 'CULTURE LINK', 'PLAYSTATION NETWORK',
                         'STEAMGAMES', 'CINEPLEX', 'HALIMAC AXE THROWING', 'SEVEN BAYS BOULDERING',
                         'ACTIVATE HALIFAX', 'SQ *FUTURE FLASH ARCAD', 'SANDSPIT', 'TILT-A-WHI',
                         'NBX*LIVE ART DANCE', 'HFX FEST', 'HALIFAXMUSIC', 'SHOWPASS',
                         'PEACOCK', 'SOHO HOUSE', 'SHINDIG', 'GALLERY', 'ZWICKER',
                         'DROPOUT', 'FEVER*', 'BEAR BALL', 'SCIENCE & HUMANS', 'WET  N WILD',
                         'MARITIME BUS', 'AMBASSATOURS', 'BOOK OF MORMON', 'GLOW THE EVENT',
                         'AXE MANAGEMENT', 'PIE OH MY', 'PEI CMC', 'QUEEN\'S MARQUE',
                         'MONCTON CHORAL', 'WB STUDIO', 'PLAYSTATIONNETWORK', 'FROGDUST',
                         'WILD THINGS', 'MARTIN HOUSE', 'DUNES STUDIO', 'EAST POINT LIGHTHOUSE',
                         'JARDI BOTANIC', 'LAWRENCETOWN SURF', 'RUSTICO-SURF', 'SKI WENTWORTH',
                         'LEGO '],

        # Health & Personal
        'Taweel': ['BAYSHORE HEALTHCARE', 'STARLINK INTERNET'],
        'Medical': ['PHARMACY', 'DRUG', 'DENTAL', 'DOCTOR', 'CLINIC', 'HOSPITAL',
                   'LAWTONS', 'SUNLIFE', 'QEII FOUNDATION',
                   'SUPPLEMENT KING', 'NOVA GP', 'FARMACIA', 'WALGREENS', "MURPHY'S QUEEN STREET PHA",
                   'MEDICINE SHOPPE', 'SIGNATURE HEALTH', 'KEYSTONE HEALTH', 'PERIODONTICS',
                   'SLEEP THERAPUTICS', 'BEDFORD PERIODONTICS', 'QEII PARKING',
                   'LANDING SURGICAL'],
        'Personal Care': ['BARBERSHOP', 'BARBER', 'SEPHORA', 'DANIELS TAILORS', 'UVAPESHOP',
                         'ONE BLOCK BABERSHOP', 'DOLLAR SHAVE CLUB', 'SPA', 'VITALITY MEDI',
                         'HIGHLANDER SPA', 'PURE VISION', 'ALCONE COMPANY', 'FITTED CLOSET',
                         'DULY NOTED', 'MOONSNAIL SOAPWORKS',
                         'LUSH HALIFAX', 'CHARLOTTE TILBURY', 'AESOP', 'SAJE WELLNESS',
                         'SPRIG APOTHECARY'],
        'Vaping': ['VAPE', 'TWENTY-FOUR ELEVEN VAP', 'KVD PLEASANT'],

        # Other
        'Vehicle': ['PARKING', 'CAR WASH', 'AUTO', 'ACCESS NOVA SCOTIA-RMV',
                   'QEII PARKING', 'POWNALL PARKADE', 'PARK INDIGO', 'HRM ON-LINE PARKING',
                   'WASH WORLD', 'GREEN MACHINE'],
        'Donations': ['DONOR DRIVE', 'CCS DONOR', 'HALIFAX PRIDE', 'WIKIMEDIA', 'BIDEAWHILE'],
        'Vending': ['SH VENDING', 'VENDING', 'AMFM VENDING'],
        'Legal': ['NS JUSTICE', 'JUSTICE ONLINE PAYMENT'],
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

    # Step 2: Assign budgets to unbudgeted transactions
    print("\n--- Assigning budgets ---\n")
    action_assign_budget(date_after=date_after)

    # Step 3: Refine budget assignments
    print("\n--- Refining budgets ---\n")
    action_refine_budgets(date_after=date_after)

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

def _get_budget_for_category(category_name):
    """Determine the correct budget for a given category name.

    Returns:
        Budget name string, or None if no budget should be assigned.
    """
    cat_lower = (category_name or '').lower()
    if cat_lower == '(uncategorized)':
        return None
    if 'vix-events' in cat_lower:
        return "Vix-Events"
    if 'taweel' in cat_lower:
        return "Taweel"
    if any(t in cat_lower for t in ['trip', 'travel']):
        return "Trips"
    return "Spending"


def action_recategorize(category_name, auto_confirm=False):
    """Re-run suggest_category() on all transactions in a given category and reclassify mismatches.

    Fetches all transactions with the specified category, runs each description through
    suggest_category(), shows a summary of proposed changes grouped by new category,
    prompts for confirmation, then updates both category and budget via API.

    Args:
        category_name: The category to audit (e.g. "Taxi")
        auto_confirm: If True, skip confirmation prompt
    """
    query_string = f"category_is:{category_name}"
    print(f"Fetching all '{category_name}' transactions...")

    transactions = _fetch_transactions(query_string, limit=500, paginate=True)

    if not transactions:
        print(f"No transactions found with category '{category_name}'.")
        return

    print(f"\nFound {len(transactions)} transactions in '{category_name}'\n")

    # Run suggest_category on each and find mismatches
    matches = []
    mismatches = []

    for tx in transactions:
        description = tx.get('description', '')
        suggested = suggest_category(description)
        tx['suggested_category'] = suggested

        if suggested.lower() == category_name.lower():
            matches.append(tx)
        else:
            mismatches.append(tx)

    print(f"  Correctly categorized: {len(matches)}")
    print(f"  Need reclassification: {len(mismatches)}")

    if not mismatches:
        print(f"\nAll '{category_name}' transactions are correctly categorized. GG EZ.")
        return

    # Group mismatches by new suggested category
    from collections import defaultdict
    by_new_category = defaultdict(list)
    for tx in mismatches:
        by_new_category[tx['suggested_category']].append(tx)

    print(f"\n{'=' * 70}")
    print(f"PROPOSED RECLASSIFICATIONS")
    print(f"{'=' * 70}")

    for new_cat, txs in sorted(by_new_category.items(), key=lambda x: -len(x[1])):
        budget = _get_budget_for_category(new_cat)
        budget_display = f" (budget: {budget})" if budget else ""
        print(f"\n  {category_name} → {new_cat}{budget_display}: {len(txs)} transactions")
        # Show first 5 examples
        for tx in txs[:5]:
            amount = float(tx.get('amount', 0))
            desc = tx.get('description', '')[:55]
            print(f"    ${amount:>9.2f}  {desc}")
        if len(txs) > 5:
            print(f"    ... and {len(txs) - 5} more")

    print(f"\n{'=' * 70}")
    print(f"  Total to reclassify: {len(mismatches)}")
    print(f"{'=' * 70}")

    if not auto_confirm:
        response = input("\nProceed with reclassification? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Cancelled.")
            return

    # Apply changes
    print("\nApplying reclassifications...\n")
    success_count = 0
    error_count = 0
    skip_count = 0

    for tx in mismatches:
        tx_id = tx.get('transaction_journal_id')
        new_category = tx['suggested_category']
        description = tx.get('description', '')

        if new_category == '(Uncategorized)':
            # Clear category by setting to empty string
            update_payload = {'category_name': ''}
        else:
            update_payload = {'category_name': new_category}

        # Also set budget
        budget = _get_budget_for_category(new_category)
        if budget:
            update_payload['budget_name'] = budget

        url = f"{API_BASE_URL}/transactions/{tx_id}"
        headers = get_headers()

        try:
            resp = requests.put(url, headers=headers, json={'transactions': [update_payload]})
            if resp.status_code in [200, 204]:
                success_count += 1
                print(f"  ✓ {description[:45]:45} → {new_category}")
            else:
                error_count += 1
                print(f"  ✗ {description[:45]:45} → Error {resp.status_code}")
        except requests.exceptions.RequestException as e:
            error_count += 1
            print(f"  ✗ {description[:45]:45} → {e}")

        time.sleep(0.1)

    print(f"\n{'=' * 70}")
    print("RESULTS")
    print(f"{'=' * 70}")
    print(f"  ✓ Reclassified: {success_count}")
    if error_count > 0:
        print(f"  ✗ Errors:       {error_count}")
    print(f"{'=' * 70}")


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
        sign = "" if balance >= 0 else "-"
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


def action_backup():
    """Back up Firefly III Docker volumes (database + uploads).

    Creates timestamped tar.gz archives of both the MariaDB data volume
    and the uploads volume to ~/backups/firefly/.
    """
    import subprocess
    from datetime import date

    backup_dir = Path.home() / "backups" / "firefly"
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = date.today().isoformat()

    volumes = [
        ("firefly-iii_firefly_iii_db", f"firefly_db_{timestamp}.tar.gz", "database"),
        ("firefly-iii_firefly_iii_upload", f"firefly_upload_{timestamp}.tar.gz", "uploads"),
    ]

    results = []

    for volume_name, filename, label in volumes:
        filepath = backup_dir / filename
        print(f"Backing up {label} ({volume_name})...")

        cmd = [
            "docker", "run", "--rm",
            "-v", f"{volume_name}:/source:ro",
            "-v", f"{backup_dir}:/backup",
            "ubuntu",
            "tar", "-czf", f"/backup/{filename}", "-C", "/source", ".",
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0 and filepath.exists():
                size_mb = filepath.stat().st_size / (1024 * 1024)
                print(f"  ✓ {filename} ({size_mb:.1f} MB)")
                results.append((label, "OK", size_mb))
            else:
                stderr = result.stderr.strip()[:200] if result.stderr else "Unknown error"
                print(f"  ✗ Failed: {stderr}")
                results.append((label, "FAILED", 0))
        except subprocess.TimeoutExpired:
            print(f"  ✗ Timed out after 5 minutes")
            results.append((label, "TIMEOUT", 0))
        except FileNotFoundError:
            print(f"  ✗ Docker not found. Is Docker/OrbStack running?")
            results.append((label, "FAILED", 0))
            break

    print(f"\n{'=' * 50}")
    print("BACKUP SUMMARY")
    print(f"{'=' * 50}")
    for label, status, size_mb in results:
        icon = "✓" if status == "OK" else "✗"
        size_str = f"  ({size_mb:.1f} MB)" if size_mb > 0 else ""
        print(f"  {icon} {label:12} {status}{size_str}")
    print(f"  Location: {backup_dir}")
    print(f"{'=' * 50}")


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

    # Sub-parser for the "categorize" action
    # Sub-parser for the "recategorize" action
    recategorize_parser = subparsers.add_parser("recategorize", help="Re-run suggest_category() on a category and reclassify mismatches.")
    recategorize_parser.add_argument(
        "category_name",
        type=str,
        help="The category to audit and reclassify (e.g., Taxi)."
    )
    recategorize_parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompt and apply immediately"
    )

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

    # Sub-parser for the "reconcile" action
    reconcile_parser = subparsers.add_parser("reconcile", help="Reconcile account balances against actual bank balances.")

    # Sub-parser for the "backup" action
    backup_parser = subparsers.add_parser("backup", help="Back up Firefly III Docker volumes (database + uploads).")

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
    elif args.action == "recategorize":
        action_recategorize(args.category_name, auto_confirm=args.yes)
    elif args.action == "categorize":
        action_categorize(date_after=args.date, auto_confirm=args.yes)
    elif args.action == "reconcile":
        action_reconcile()
    elif args.action == "backup":
        action_backup()
    # No need for an else here, as `required=True` in `add_subparsers` handles missing/invalid actions.

if __name__ == "__main__":
    main()
