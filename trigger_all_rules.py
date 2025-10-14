"""
Triggers ALL automation rules in Firefly III to apply them to existing transactions.
"""

import requests
import os
import json
import time
from dotenv import load_dotenv
from pathlib import Path

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

def get_all_rules():
    """Fetch all rules from Firefly III"""
    url = f"{API_BASE_URL}/rules"
    headers = get_headers()

    all_rules = []
    page = 1

    while True:
        try:
            params = {"page": str(page)}
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()

            data = response.json()
            rules = data.get("data", [])

            if not rules:
                break

            all_rules.extend(rules)

            # Check pagination
            meta = data.get("meta", {})
            pagination = meta.get("pagination", {})
            total_pages = pagination.get("total_pages", 1)

            if page >= total_pages:
                break

            page += 1

        except requests.exceptions.RequestException as e:
            print(f"Error fetching rules: {e}")
            return []

    return all_rules

def trigger_rule(rule_id, rule_title):
    """Trigger a single rule"""
    url = f"{API_BASE_URL}/rules/{rule_id}/trigger"
    headers = get_headers()

    try:
        response = requests.post(url, headers=headers)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Error triggering rule {rule_id} ({rule_title}): {e}")
        return False

def main():
    """Trigger all automation rules"""

    print("=" * 80)
    print("TRIGGERING ALL FIREFLY III AUTOMATION RULES")
    print("=" * 80)

    print("\nFetching all rules...")
    rules = get_all_rules()

    if not rules:
        print("No rules found.")
        return

    # Filter to active rules only
    active_rules = [r for r in rules if r.get("attributes", {}).get("active", False)]

    print(f"Found {len(rules)} total rules ({len(active_rules)} active)")
    print(f"\nTriggering {len(active_rules)} active rules...\n")

    success_count = 0
    error_count = 0

    for i, rule in enumerate(active_rules, 1):
        rule_id = rule.get("id")
        attrs = rule.get("attributes", {})
        rule_title = attrs.get("title", "Unknown")

        # Get category from actions
        category = None
        actions = attrs.get("actions", [])
        for action in actions:
            if action.get("type") == "set_category":
                category = action.get("value")
                break

        category_str = f"→ {category}" if category else ""

        print(f"[{i}/{len(active_rules)}] Triggering: {rule_title} {category_str}")

        if trigger_rule(rule_id, rule_title):
            success_count += 1
            print(f"  ✓ Successfully triggered")
        else:
            error_count += 1

        # Rate limiting - be nice to the API
        time.sleep(0.5)

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"  ✓ Successfully triggered: {success_count}")
    if error_count > 0:
        print(f"  ✗ Errors: {error_count}")
    print(f"\nAll active rules have been triggered!")
    print("=" * 80)

if __name__ == "__main__":
    main()
