"""
Assigns all transactions with category "Transfer" to the "Transfers" budget.
"""

import requests
import os
from dotenv import load_dotenv
from pathlib import Path
import time

# Load environment variables
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

API_BASE_URL = os.getenv('FIREFLY_API_BASE_URL')
API_TOKEN = os.getenv('FIREFLY_API_TOKEN')

def get_headers():
    """Return headers for API requests"""
    return {
        "accept": "application/vnd.api+json",
        "authorization": f"Bearer {API_TOKEN}",
        "content-type": "application/json",
        "user-agent": "vscode-restclient",
    }

def main():
    """Assign all Transfer category transactions to Transfers budget"""

    # Query for transactions with category "Transfer"
    query_string = "category:Transfer"
    url = f"{API_BASE_URL}/search/transactions"
    headers = get_headers()

    print(f"Querying transactions with category 'Transfer'...")
    print(f" - Query: '{query_string}'")

    all_transactions = []
    page = 1
    per_page = 500

    while True:
        params = {"query": query_string, "limit": str(per_page), "page": str(page)}

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()

            data = response.json()
            records = data.get("data", [])

            if not records:
                break

            # Extract transaction details
            for record in records:
                if "attributes" in record and "transactions" in record["attributes"]:
                    tx_list = record["attributes"]["transactions"]
                    if tx_list:
                        tx = tx_list[0]
                        all_transactions.append({
                            'id': record["id"],
                            'date': tx.get('date'),
                            'description': tx.get('description'),
                            'amount': tx.get('amount'),
                            'category': tx.get('category_name', ''),
                            'budget': tx.get('budget_name', '')
                        })

            if len(records) < per_page:
                break

            page += 1
            print(f"  Fetching page {page}...")

        except requests.exceptions.RequestException as e:
            print(f"Error connecting to Firefly III API: {e}")
            return

    if not all_transactions:
        print("No Transfer transactions found.")
        return

    print(f" - Found {len(all_transactions)} Transfer transactions\n")

    # Show summary
    budgeted_count = sum(1 for tx in all_transactions if tx['budget'])
    unbudgeted_count = len(all_transactions) - budgeted_count

    print(f"Current budget status:")
    print(f"  - Already budgeted: {budgeted_count}")
    print(f"  - Unbudgeted: {unbudgeted_count}")
    print(f"\nAssigning all {len(all_transactions)} transactions to 'Transfers' budget...\n")

    # Update transactions
    success_count = 0
    error_count = 0

    for i, tx_info in enumerate(all_transactions, 1):
        tx_id = tx_info['id']

        try:
            update_response = requests.put(
                f"{API_BASE_URL}/transactions/{tx_id}",
                headers=headers,
                json={
                    "transactions": [{
                        "budget_name": "Transfers"
                    }]
                }
            )

            if update_response.status_code in [200, 204]:
                success_count += 1
                current_budget = tx_info['budget'] or '(none)'
                print(f"[{i}/{len(all_transactions)}] ✓ Transfers | {tx_info['description'][:50]:<50} | Was: {current_budget}")
            else:
                error_count += 1
                print(f"[{i}/{len(all_transactions)}] ✗ Error {update_response.status_code} | {tx_info['description'][:50]}")

            # Rate limiting
            time.sleep(0.1)

        except requests.exceptions.RequestException as e:
            error_count += 1
            print(f"[{i}/{len(all_transactions)}] ✗ Error: {tx_info['description'][:50]} - {e}")

    print("\n" + "=" * 80)
    print("Summary:")
    print(f"  ✓ Successfully updated: {success_count}")
    if error_count > 0:
        print(f"  ✗ Errors: {error_count}")
    print(f"\nAll Transfer transactions are now assigned to 'Transfers' budget")
    print("=" * 80)

if __name__ == "__main__":
    main()
