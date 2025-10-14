"""
Audit all automation rules from Firefly III and save to JSON for analysis.
"""

import requests
import os
import json
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

def main():
    """Fetch all rules and save to JSON"""

    url = f"{API_BASE_URL}/rules"
    headers = get_headers()

    print("Fetching all automation rules from Firefly III...")

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
            print(f"  Fetching page {page}...")

        except requests.exceptions.RequestException as e:
            print(f"Error connecting to Firefly III API: {e}")
            return

    print(f"\nFound {len(all_rules)} automation rules")

    # Save to JSON file
    data_dir = Path(__file__).parent / 'data'
    data_dir.mkdir(exist_ok=True)

    output_path = data_dir / "firefly_rules.json"

    with open(output_path, 'w') as f:
        json.dump(all_rules, f, indent=2)

    print(f"Saved rules to {output_path}")

    # Print summary
    print("\n" + "=" * 80)
    print("RULES SUMMARY")
    print("=" * 80)

    active_count = 0
    category_rules = []

    for rule in all_rules:
        attrs = rule.get("attributes", {})

        if attrs.get("active"):
            active_count += 1

        # Check if rule sets a category
        actions = attrs.get("actions", [])
        for action in actions:
            if action.get("type") == "set_category":
                category_rules.append({
                    "id": rule.get("id"),
                    "title": attrs.get("title"),
                    "category": action.get("value"),
                    "active": attrs.get("active"),
                    "triggers": attrs.get("triggers", []),
                })

    print(f"\nTotal rules: {len(all_rules)}")
    print(f"Active rules: {active_count}")
    print(f"Inactive rules: {len(all_rules) - active_count}")
    print(f"Rules that set categories: {len(category_rules)}")

    print("\n" + "=" * 80)
    print("CATEGORY RULES")
    print("=" * 80)

    # Group by category
    by_category = {}
    for rule in category_rules:
        category = rule["category"]
        if category not in by_category:
            by_category[category] = []
        by_category[category].append(rule)

    for category in sorted(by_category.keys()):
        rules_in_cat = by_category[category]
        print(f"\n{category} ({len(rules_in_cat)} rules):")

        for rule in rules_in_cat:
            status = "✓" if rule["active"] else "✗"

            # Show first 2 triggers
            trigger_summary = []
            for trigger in rule["triggers"][:2]:
                trigger_type = trigger.get("type", "")
                trigger_value = trigger.get("value", "")
                trigger_summary.append(f"{trigger_type}={trigger_value}")

            trigger_str = ", ".join(trigger_summary)
            if len(rule["triggers"]) > 2:
                trigger_str += f" (+{len(rule['triggers'])-2} more)"

            print(f"  {status} [{rule['id']}] {rule['title']}")
            print(f"      Triggers: {trigger_str}")

if __name__ == "__main__":
    main()
