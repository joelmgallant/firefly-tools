"""
Trigger execution of all vix-events rules to apply them to existing transactions.
"""

import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

API_BASE_URL = os.getenv('FIREFLY_API_BASE_URL')
API_TOKEN = os.getenv('FIREFLY_API_TOKEN')

def get_headers():
    return {
        'accept': 'application/json',
        'authorization': f'Bearer {API_TOKEN}',
        'content-type': 'application/json',
    }

def get_all_rules():
    """Fetch all rules with pagination"""
    headers = {
        'accept': 'application/vnd.api+json',
        'authorization': f'Bearer {API_TOKEN}',
    }

    all_rules = []
    page = 1

    while True:
        url = f'{API_BASE_URL}/rules'
        params = {'page': page}
        response = requests.get(url, headers=headers, params=params)
        data = response.json()

        rules = data.get('data', [])
        if not rules:
            break

        all_rules.extend(rules)

        links = data.get('links', {})
        if not links.get('next'):
            break

        page += 1

    return all_rules

def trigger_rule(rule_id, start_date, end_date):
    """Trigger a rule to execute on transactions within date range"""
    url = f'{API_BASE_URL}/rules/{rule_id}/trigger'

    payload = {
        'start': start_date.strftime('%Y-%m-%d'),
        'end': end_date.strftime('%Y-%m-%d')
    }

    response = requests.post(url, headers=get_headers(), json=payload)

    if response.status_code == 204:
        return True
    else:
        print(f"    ERROR: Status {response.status_code} - {response.text}")
        return False

def main():
    print("Fetching all rules...")
    all_rules = get_all_rules()
    print(f"Found {len(all_rules)} total rules\n")

    # Find vix-events rules
    vix_rules = []
    for rule in all_rules:
        attrs = rule.get('attributes', {})
        group = attrs.get('rule_group_title', '')

        if 'vix' in group.lower():
            vix_rules.append({
                'id': rule.get('id'),
                'title': attrs.get('title')
            })

    print(f"Found {len(vix_rules)} rules in vix-events group\n")

    # Calculate date range - last 2 years to cover all transactions
    end_date = datetime.now()
    start_date = end_date - timedelta(days=730)

    print(f"Triggering rules for date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}\n")

    success_count = 0
    for rule in vix_rules:
        print(f"  Triggering rule {rule['id']:>3}: {rule['title'][:60]}")
        if trigger_rule(rule['id'], start_date, end_date):
            print(f"    ✓ Success")
            success_count += 1
        print()

    print(f"{'='*60}")
    print(f"Summary: {success_count}/{len(vix_rules)} rules triggered successfully")
    print(f"{'='*60}")

if __name__ == '__main__':
    main()
