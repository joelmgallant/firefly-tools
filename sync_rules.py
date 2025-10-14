"""
Synchronize Firefly III rules with local category patterns.

This script will:
1. Update existing category rules to include all keywords from patterns
2. Create new rules for categories that don't exist in Firefly

Usage:
    python sync_rules.py --dry-run  # Preview changes without applying
    python sync_rules.py            # Apply changes to Firefly III
"""

import requests
import os
import json
import argparse
from dotenv import load_dotenv
from pathlib import Path
from collections import defaultdict

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

def load_data():
    """Load Firefly rules and category patterns"""
    data_dir = Path(__file__).parent / 'data'

    # Load Firefly rules
    rules_path = data_dir / "firefly_rules.json"
    with open(rules_path, 'r') as f:
        firefly_rules = json.load(f)

    # Load category patterns
    patterns_path = data_dir / "category_patterns.json"
    with open(patterns_path, 'r') as f:
        category_patterns = json.load(f)

    # Load comparison data
    comparison_path = data_dir / "rules_comparison.json"
    with open(comparison_path, 'r') as f:
        comparison_data = json.load(f)

    return firefly_rules, category_patterns, comparison_data

def find_primary_rule_for_category(firefly_rules, category):
    """Find the primary (most general) rule for a category"""
    category_rules = []

    for rule in firefly_rules:
        attrs = rule.get("attributes", {})
        actions = attrs.get("actions", [])

        # Check if rule sets this category
        for action in actions:
            if action.get("type") == "set_category" and action.get("value") == category:
                category_rules.append({
                    "id": rule.get("id"),
                    "title": attrs.get("title"),
                    "rule": rule
                })
                break

    if not category_rules:
        return None

    # If there's only one rule, use it
    if len(category_rules) == 1:
        return category_rules[0]

    # Find the most general rule (one with the category name as title)
    for r in category_rules:
        if r["title"].lower() == category.lower():
            return r

    # Otherwise, return the first one
    return category_rules[0]

def update_rule(rule_id, triggers, actions, title, dry_run=False):
    """Update a rule via API"""
    if dry_run:
        return True

    url = f"{API_BASE_URL}/rules/{rule_id}"
    headers = get_headers()

    payload = {
        "title": title,
        "trigger": "store-journal",
        "active": True,
        "strict": False,
        "triggers": triggers,
        "actions": actions,
    }

    try:
        response = requests.put(url, headers=headers, json=payload)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Error updating rule {rule_id}: {e}")
        return False

def create_rule(category, keywords, rule_group_id="1", dry_run=False):
    """Create a new rule via API"""
    if dry_run:
        return True

    url = f"{API_BASE_URL}/rules"
    headers = get_headers()

    # Create triggers for all keywords
    triggers = []
    for keyword in keywords:
        triggers.append({
            "type": "description_contains",
            "value": keyword,
            "stop_processing": False
        })

    # Create action to set category
    actions = [{
        "type": "set_category",
        "value": category,
        "stop_processing": False
    }]

    payload = {
        "rule_group_id": rule_group_id,
        "title": category,
        "trigger": "store-journal",
        "active": True,
        "strict": False,
        "stop_processing": False,
        "triggers": triggers,
        "actions": actions,
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Error creating rule for {category}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Sync Firefly III rules with local patterns")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    args = parser.parse_args()

    print("=" * 80)
    print("FIREFLY III RULE SYNCHRONIZATION")
    print("=" * 80)

    if args.dry_run:
        print("\n⚠️  DRY RUN MODE - No changes will be applied\n")

    # Load data
    firefly_rules, category_patterns, comparison_data = load_data()

    # Get categories with keyword gaps
    keyword_gaps = comparison_data.get("keyword_gaps", {})

    print(f"\nCategories to update: {len(keyword_gaps)}")
    print(f"Categories to create: {len(comparison_data['missing_categories'])}")

    # Update existing rules
    if keyword_gaps:
        print("\n" + "=" * 80)
        print("UPDATING EXISTING RULES")
        print("=" * 80)

        update_count = 0
        for category, gap_info in sorted(keyword_gaps.items()):
            missing_keywords = gap_info.get("missing_in_firefly", [])

            if not missing_keywords:
                continue

            # Find the primary rule for this category
            primary_rule = find_primary_rule_for_category(firefly_rules, category)

            if not primary_rule:
                print(f"\n{category}: No primary rule found, skipping")
                continue

            print(f"\n{category}:")
            print(f"  Primary rule: [{primary_rule['id']}] {primary_rule['title']}")
            print(f"  Adding {len(missing_keywords)} keywords")

            # Get current triggers and actions
            attrs = primary_rule["rule"].get("attributes", {})
            current_triggers = attrs.get("triggers", [])
            current_actions = attrs.get("actions", [])

            # Add new triggers for missing keywords
            new_triggers = current_triggers.copy()
            for keyword in missing_keywords:
                new_triggers.append({
                    "type": "description_contains",
                    "value": keyword,
                    "stop_processing": False
                })

            # Update rule
            if update_rule(primary_rule['id'], new_triggers, current_actions, primary_rule['title'], dry_run=args.dry_run):
                update_count += 1
                print(f"  ✓ Updated rule with {len(new_triggers)} total triggers")
            else:
                print(f"  ✗ Failed to update rule")

        print(f"\n{update_count}/{len(keyword_gaps)} rules updated")

    # Create new rules
    missing_categories = comparison_data.get("missing_categories", {})
    if missing_categories:
        print("\n" + "=" * 80)
        print("CREATING NEW RULES")
        print("=" * 80)

        create_count = 0
        for category, cat_info in sorted(missing_categories.items()):
            keywords = cat_info.get("keywords", [])

            print(f"\n{category}:")
            print(f"  Creating rule with {len(keywords)} keywords")

            if create_rule(category, keywords, dry_run=args.dry_run):
                create_count += 1
                print(f"  ✓ Created rule")
            else:
                print(f"  ✗ Failed to create rule")

        print(f"\n{create_count}/{len(missing_categories)} rules created")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    if args.dry_run:
        print("\n⚠️  This was a DRY RUN - no changes were applied")
        print("Run without --dry-run to apply changes")
    else:
        print("\n✓ Synchronization complete!")

if __name__ == "__main__":
    main()
