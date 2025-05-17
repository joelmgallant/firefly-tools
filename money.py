"""
Interacts with Firefly III API to perform various transaction operations.

Available actions:
- payback: Queries transactions tagged with "payback" and outputs them to a CSV file.
- [Additional actions can be added here]

Default action: payback
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

def fetch_transactions_by_tag(tag, limit=500):
    """Fetch transactions with a specific tag"""
    url = f"{API_BASE_URL}/search/transactions"
    headers = get_headers()
    params = {"query": f"tag:{tag}", "limit": str(limit)}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()  # Raise exception for 4XX/5XX responses
        
        data = response.json()
        records = data.get("data", [])
        transactions = []
        
        # filter this data structure down
        for record in records:
            transactions.append(record["attributes"]["transactions"][0])
        
        return transactions
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to Firefly III API: {e}")
        print(f"URL: {url}")
        exit(1)

def action_payback():
    """
    Default action: Query transactions tagged with 'payback' and output to CSV.
    """
    transactions = fetch_transactions_by_tag("payback")
    
    print(json.dumps(transactions, indent=4))
    
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
    filtered_df = df[columns]
    filtered_df.to_csv(output_path, index=False)
    print(f"Exported {len(filtered_df)} payback transactions to {output_path}")

def main():
    """Parse arguments and execute the appropriate action"""
    parser = argparse.ArgumentParser(description="Firefly III Transaction Tool")
    parser.add_argument(
        "action", 
        nargs="?", 
        default="payback",
        choices=["payback"], 
        help="Action to perform (default: payback)"
    )
    args = parser.parse_args()
    
    # Execute the selected action
    if args.action == "payback":
        action_payback()
    # Additional actions can be added here with elif statements

if __name__ == "__main__":
    main()
