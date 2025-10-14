"""
Compare Firefly III rules with local category patterns and identify gaps.
"""

import json
from pathlib import Path
from collections import defaultdict

def main():
    """Compare rules and patterns"""

    data_dir = Path(__file__).parent / 'data'

    # Load Firefly rules
    rules_path = data_dir / "firefly_rules.json"
    with open(rules_path, 'r') as f:
        firefly_rules = json.load(f)

    # Load category patterns
    patterns_path = data_dir / "category_patterns.json"
    with open(patterns_path, 'r') as f:
        category_patterns = json.load(f)

    print("=" * 80)
    print("COMPARING FIREFLY RULES VS LOCAL PATTERNS")
    print("=" * 80)

    # Extract category rules from Firefly
    firefly_categories = defaultdict(lambda: {"rules": [], "keywords": set()})

    for rule in firefly_rules:
        attrs = rule.get("attributes", {})
        actions = attrs.get("actions", [])

        # Find category setting action
        category_name = None
        for action in actions:
            if action.get("type") == "set_category":
                category_name = action.get("value")
                break

        if not category_name:
            continue

        # Extract keywords from triggers
        triggers = attrs.get("triggers", [])
        keywords = set()

        for trigger in triggers:
            trigger_type = trigger.get("type", "")
            trigger_value = trigger.get("value", "").upper()

            # Extract the actual keyword/pattern
            if trigger_type in ["description_contains", "description_starts", "description_is"]:
                keywords.add(trigger_value)

        firefly_categories[category_name]["rules"].append({
            "id": rule.get("id"),
            "title": attrs.get("title"),
            "active": attrs.get("active"),
            "triggers": triggers,
        })
        firefly_categories[category_name]["keywords"].update(keywords)

    # Compare categories
    print(f"\nLocal patterns: {len(category_patterns)} categories")
    print(f"Firefly rules: {len(firefly_categories)} categories\n")

    # Find missing categories (in patterns but not in Firefly)
    missing_categories = set(category_patterns.keys()) - set(firefly_categories.keys())

    # Find extra categories (in Firefly but not in patterns)
    extra_categories = set(firefly_categories.keys()) - set(category_patterns.keys())

    # Find common categories
    common_categories = set(category_patterns.keys()) & set(firefly_categories.keys())

    print("=" * 80)
    print("MISSING CATEGORIES (in patterns but not in Firefly)")
    print("=" * 80)

    if missing_categories:
        for category in sorted(missing_categories):
            keywords = category_patterns[category]
            print(f"\n{category}: {len(keywords)} keywords")
            print(f"  Keywords: {', '.join(keywords[:5])}")
            if len(keywords) > 5:
                print(f"  ... and {len(keywords) - 5} more")
    else:
        print("None - all pattern categories exist in Firefly")

    print("\n" + "=" * 80)
    print("EXTRA CATEGORIES (in Firefly but not in patterns)")
    print("=" * 80)

    if extra_categories:
        for category in sorted(extra_categories):
            rules = firefly_categories[category]["rules"]
            print(f"\n{category}: {len(rules)} rule(s)")
            for rule in rules:
                print(f"  [{rule['id']}] {rule['title']}")
    else:
        print("None - all Firefly categories match patterns")

    print("\n" + "=" * 80)
    print("CATEGORY KEYWORD COMPARISON")
    print("=" * 80)

    # Save detailed comparison
    comparison_data = {
        "missing_categories": {},
        "extra_categories": {},
        "keyword_gaps": {},
        "summary": {
            "total_pattern_categories": len(category_patterns),
            "total_firefly_categories": len(firefly_categories),
            "missing_count": len(missing_categories),
            "extra_count": len(extra_categories),
        }
    }

    # Add missing categories to comparison
    for category in missing_categories:
        comparison_data["missing_categories"][category] = {
            "keywords": category_patterns[category],
            "keyword_count": len(category_patterns[category])
        }

    # Add extra categories to comparison
    for category in extra_categories:
        comparison_data["extra_categories"][category] = {
            "rules": [{"id": r["id"], "title": r["title"]} for r in firefly_categories[category]["rules"]]
        }

    # Compare keywords for common categories
    for category in sorted(common_categories):
        pattern_keywords = set(k.upper() for k in category_patterns[category])
        firefly_keywords = firefly_categories[category]["keywords"]

        # Find keywords in patterns but not in Firefly
        missing_keywords = pattern_keywords - firefly_keywords

        # Find keywords in Firefly but not in patterns
        extra_keywords = firefly_keywords - pattern_keywords

        if missing_keywords or extra_keywords:
            print(f"\n{category}:")
            print(f"  Pattern keywords: {len(pattern_keywords)}")
            print(f"  Firefly keywords: {len(firefly_keywords)}")

            if missing_keywords:
                print(f"  Missing in Firefly: {len(missing_keywords)} keywords")
                sample = list(missing_keywords)[:3]
                print(f"    Sample: {', '.join(sample)}")
                if len(missing_keywords) > 3:
                    print(f"    ... and {len(missing_keywords) - 3} more")

            if extra_keywords:
                print(f"  Extra in Firefly: {len(extra_keywords)} keywords")
                sample = list(extra_keywords)[:3]
                print(f"    Sample: {', '.join(sample)}")
                if len(extra_keywords) > 3:
                    print(f"    ... and {len(extra_keywords) - 3} more")

            comparison_data["keyword_gaps"][category] = {
                "pattern_count": len(pattern_keywords),
                "firefly_count": len(firefly_keywords),
                "missing_in_firefly": list(missing_keywords),
                "extra_in_firefly": list(extra_keywords),
            }

    # Save comparison to JSON
    output_path = data_dir / "rules_comparison.json"
    with open(output_path, 'w') as f:
        json.dump(comparison_data, f, indent=2)

    print(f"\n\n{'=' * 80}")
    print("SUMMARY")
    print("=" * 80)
    print(f"Missing categories (need new rules): {len(missing_categories)}")
    print(f"Extra categories (in Firefly only): {len(extra_categories)}")
    print(f"Categories with keyword gaps: {len(comparison_data['keyword_gaps'])}")
    print(f"\nDetailed comparison saved to {output_path}")

if __name__ == "__main__":
    main()
