"""
Update all rules in the vix-events group to add the 'payback' tag.
"""

import os
import requests
from dotenv import load_dotenv
from pathlib import Path

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

def get_all_rules():
    """Fetch all rules with pagination"""
    all_rules = []
    page = 1

    while True:
        url = f'{API_BASE_URL}/rules'
        params = {'page': page}
        response = requests.get(url, headers=get_headers(), params=params)
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

def update_rule_with_payback_tag(rule_id):
    """Add payback tag to a specific rule"""
    # First, get the full rule details
    url = f'{API_BASE_URL}/rules/{rule_id}'
    response = requests.get(url, headers=get_headers())

    if response.status_code != 200:
        print(f"  ERROR: Could not fetch rule {rule_id}: {response.status_code}")
        return False

    rule_data = response.json()
    attrs = rule_data['data']['attributes']

    # Check if payback tag already exists
    actions = attrs.get('actions', [])
    has_payback = any(
        a.get('type') == 'add_tag' and a.get('value') == 'payback'
        for a in actions
    )

    if has_payback:
        print(f"  ✓ Rule {rule_id} already has payback tag")
        return True

    # Add the payback tag action
    new_action = {
        'type': 'add_tag',
        'value': 'payback',
        'stop_processing': False
    }
    actions.append(new_action)

    # Prepare the update payload
    update_payload = {
        'title': attrs['title'],
        'trigger': attrs['trigger'],
        'active': attrs['active'],
        'strict': attrs['strict'],
        'stop_processing': attrs['stop_processing'],
        'triggers': attrs['triggers'],
        'actions': actions
    }

    # Update the rule
    response = requests.put(url, headers=get_headers(), json=update_payload)

    if response.status_code == 200:
        print(f"  ✓ Rule {rule_id} updated successfully")
        return True
    else:
        print(f"  ERROR: Failed to update rule {rule_id}: {response.status_code}")
        print(f"    Response: {response.text}")
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

    print(f"Found {len(vix_rules)} rules in vix-events group:\n")
    for rule in vix_rules:
        print(f"  - Rule {rule['id']}: {rule['title']}")

    print(f"\nUpdating {len(vix_rules)} rules to add 'payback' tag...\n")

    success_count = 0
    for rule in vix_rules:
        if update_rule_with_payback_tag(rule['id']):
            success_count += 1

    print(f"\n{'='*60}")
    print(f"Summary: {success_count}/{len(vix_rules)} rules updated successfully")
    print(f"{'='*60}")

if __name__ == '__main__':
    main()
