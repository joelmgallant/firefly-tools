"""
Apply suggested categories to uncategorized transactions in Firefly III.
Reads from data/untagged_updates.csv and updates transactions via API.
"""

import os
import pandas as pd
import requests
from dotenv import load_dotenv
from pathlib import Path
import time
import argparse

# Load environment variables
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

API_BASE_URL = os.getenv('FIREFLY_API_BASE_URL')
API_TOKEN = os.getenv('FIREFLY_API_TOKEN')

def get_headers():
    return {
        'accept': 'application/vnd.api+json',
        'authorization': f'Bearer {API_TOKEN}',
        'content-type': 'application/json',
    }

def update_transaction_category(transaction_id, category_name):
    """Update a transaction's category via Firefly III API"""

    # Skip if category is (Uncategorized)
    if category_name == '(Uncategorized)':
        return True, "Skipped - no category suggested"

    url = f'{API_BASE_URL}/transactions/{transaction_id}'

    # First, get the current transaction data
    try:
        response = requests.get(url, headers=get_headers())
        response.raise_for_status()
        transaction_data = response.json()
    except requests.exceptions.RequestException as e:
        return False, f"Failed to fetch transaction: {e}"

    # Extract the transaction attributes
    attrs = transaction_data['data']['attributes']

    # Update the category in the first transaction split
    if 'transactions' in attrs and len(attrs['transactions']) > 0:
        attrs['transactions'][0]['category_name'] = category_name
    else:
        return False, "No transaction splits found"

    # Prepare the update payload
    update_payload = {
        'transactions': attrs['transactions']
    }

    # Update the transaction
    try:
        response = requests.put(url, headers=get_headers(), json=update_payload)
        response.raise_for_status()
        return True, f"Updated to '{category_name}'"
    except requests.exceptions.RequestException as e:
        return False, f"Failed to update: {e}"

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Apply suggested categories to Firefly III transactions')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompt')
    args = parser.parse_args()

    # Load the updates CSV
    updates_file = Path(__file__).parent / 'data' / 'untagged_updates.csv'

    if not updates_file.exists():
        print(f"Error: {updates_file} not found.")
        print("Please run 'python money.py untagged' first to generate the file.")
        return

    df = pd.read_csv(updates_file)

    print(f"Found {len(df)} transactions to process\n")

    # Group by suggested category for summary
    category_counts = df['suggested_category'].value_counts()
    print("Categories to apply:")
    for category, count in category_counts.items():
        if category != '(Uncategorized)':
            print(f"  {category}: {count} transaction(s)")

    uncategorized_count = category_counts.get('(Uncategorized)', 0)
    if uncategorized_count > 0:
        print(f"  (Uncategorized): {uncategorized_count} transaction(s) - will be skipped")

    print(f"\nTotal to update: {len(df[df['suggested_category'] != '(Uncategorized)'])} transactions")

    # Ask for confirmation unless --yes flag is provided
    if not args.yes:
        response = input("\nProceed with updates? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Cancelled.")
            return

    print("\nUpdating transactions...\n")

    success_count = 0
    skip_count = 0
    error_count = 0

    for idx, row in df.iterrows():
        transaction_id = row['transaction_journal_id']
        category = row['suggested_category']
        description = row['description']

        print(f"[{idx+1}/{len(df)}] {description[:50]:50} -> {category:15}", end=" ")

        success, message = update_transaction_category(transaction_id, category)

        if category == '(Uncategorized)':
            skip_count += 1
        elif success:
            success_count += 1
        else:
            error_count += 1

        print(f"[{message}]")

        # Rate limiting - be nice to the API
        time.sleep(0.1)

    print("\n" + "=" * 80)
    print(f"Summary:")
    print(f"  ✓ Successfully updated: {success_count}")
    if skip_count > 0:
        print(f"  ⊘ Skipped (uncategorized): {skip_count}")
    if error_count > 0:
        print(f"  ✗ Errors: {error_count}")
    print("=" * 80)

if __name__ == '__main__':
    main()
