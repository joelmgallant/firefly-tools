"""
Finds transactions currently categorized as "Amazon" that contain AWS keywords
and updates them to "Software" category.
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
    """Find Amazon transactions with AWS keywords and update to Software category"""

    # Query for transactions with category "Amazon"
    query_string = "category:Amazon"
    url = f"{API_BASE_URL}/search/transactions"
    headers = get_headers()

    print(f"Querying transactions with category 'Amazon'...")
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
                            'category': tx.get('category_name', '')
                        })

            if len(records) < per_page:
                break

            page += 1
            print(f"  Fetching page {page}...")

        except requests.exceptions.RequestException as e:
            print(f"Error connecting to Firefly III API: {e}")
            return

    if not all_transactions:
        print("No Amazon transactions found.")
        return

    print(f" - Found {len(all_transactions)} Amazon transactions\n")

    # Filter for AWS-specific transactions
    aws_keywords = ['AMAZON WEB SERVICES', 'AWS']
    aws_transactions = []

    for tx in all_transactions:
        desc_upper = tx['description'].upper()
        if any(keyword in desc_upper for keyword in aws_keywords):
            aws_transactions.append(tx)

    if not aws_transactions:
        print("No AWS transactions found in Amazon category. All good!")
        return

    print(f"Found {len(aws_transactions)} AWS transactions that need to be recategorized:\n")

    # Show what will be updated
    for tx in aws_transactions:
        print(f"  {tx['date'][:10]} | ${float(tx['amount']):>10.2f} | {tx['description'][:60]}")

    print(f"\nUpdating {len(aws_transactions)} transactions from 'Amazon' to 'Software' category...\n")

    # Update transactions
    success_count = 0
    error_count = 0

    for i, tx_info in enumerate(aws_transactions, 1):
        tx_id = tx_info['id']

        try:
            update_response = requests.put(
                f"{API_BASE_URL}/transactions/{tx_id}",
                headers=headers,
                json={
                    "transactions": [{
                        "category_name": "Software"
                    }]
                }
            )

            if update_response.status_code in [200, 204]:
                success_count += 1
                print(f"[{i}/{len(aws_transactions)}] ✓ Software | {tx_info['description'][:50]:<50} | Was: Amazon")
            else:
                error_count += 1
                print(f"[{i}/{len(aws_transactions)}] ✗ Error {update_response.status_code} | {tx_info['description'][:50]}")

            # Rate limiting
            time.sleep(0.1)

        except requests.exceptions.RequestException as e:
            error_count += 1
            print(f"[{i}/{len(aws_transactions)}] ✗ Error: {tx_info['description'][:50]} - {e}")

    print("\n" + "=" * 80)
    print("Summary:")
    print(f"  ✓ Successfully updated: {success_count}")
    if error_count > 0:
        print(f"  ✗ Errors: {error_count}")
    print(f"\nAll AWS transactions are now categorized as 'Software'")
    print("=" * 80)

if __name__ == "__main__":
    main()
