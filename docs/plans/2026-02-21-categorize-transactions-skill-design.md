# Categorize Transactions Skill Design

## Overview

Codify the transaction categorization pipeline (Pipeline 1) into a `money.py categorize` subcommand and a Claude Code skill file that orchestrates it.

## Context

Currently, categorization is a multi-step manual process:
1. `python money.py untagged --date YYYY-MM-DD` (fetch + suggest)
2. Optional manual review of `data/untagged_updates.csv`
3. `python apply_categories.py --yes` (apply via API)

This design consolidates steps 1-3 into a single subcommand with an inline summary and confirmation prompt, plus a skill that tells Claude when and how to invoke it.

## Design

### New Subcommand: `money.py categorize`

```bash
python money.py categorize --date 2025-03-01        # interactive confirm
python money.py categorize --date 2025-03-01 --yes  # auto-apply
```

#### Flow

1. **Fetch** uncategorized transactions via `_fetch_transactions("has_no_category:true date_after:{date}")`
2. **Suggest** categories using `suggest_category()` for each transaction
3. **Export** results to `data/untagged.csv` and `data/untagged_updates.csv` (audit trail)
4. **Summarize** inline -- print category breakdown table (count + total amount per category)
5. **Confirm** -- prompt user unless `--yes` flag is passed
6. **Apply** -- PUT category updates to Firefly API with rate limiting (0.1s between calls)
7. **Report** -- print success/skip/error counts

#### Implementation: `action_categorize(date_after, auto_confirm)`

- Reuses `_fetch_transactions` and `suggest_category` from existing code
- Inlines the API update logic (simple PUT per transaction, same as `apply_categories.py`)
- Still exports CSVs so the standalone `apply_categories.py` path remains usable

### Skill File: `.claude/skills/categorize-transactions.md`

**Triggers:** User mentions categorizing transactions, untagged, finance cleanup, monthly review.

**Contents:**
- When to use (trigger phrases)
- Quick reference table (commands, key files, how suggest_category works)
- Full workflow steps
- Adding new keywords to `suggest_category()` when unrecognized merchants appear
- Post-categorization reminder to run rule sync pipeline if keywords were added
- Troubleshooting common issues (API errors, stale dates)

### Changes Summary

| Component | Change |
|-----------|--------|
| `money.py` | New `action_categorize()` function + `categorize` subparser with `--date` and `--yes` |
| `.claude/skills/categorize-transactions.md` | New skill file |
| `CLAUDE.md` | Update commands section to document `categorize` subcommand |
| `apply_categories.py` | No changes (remains as standalone alternative) |

## Decisions

- **Approach chosen:** `money.py` subcommand + skill (over pure instruction skill or wrapper script) -- keeps CLI as single entry point
- **Review step:** Inline summary + confirm (over manual CSV review or auto-apply)
- **CSV export preserved:** For audit trail and backward compatibility with `apply_categories.py`
