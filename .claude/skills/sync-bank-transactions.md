---
name: sync-bank-transactions
description: Use when importing bank transaction CSVs into Firefly III, merging downloaded bank exports, or triggering the data importer autoimport endpoint
---

# Sync Bank Transactions

## Overview

End-to-end workflow for importing bank CSV exports into Firefly III via the data importer's autoimport endpoint. Downloads go into `bank-csvs/download/`, get merged by bank, then auto-imported.

## When to Use

- User downloaded new bank CSVs and wants to import them
- User asks to sync transactions, import CSVs, or update Firefly
- User mentions RBC or TD bank exports
- Troubleshooting the data importer connection or autoimport

## Quick Reference

| Component | Location |
|-----------|----------|
| Raw downloads | `bank-csvs/download/` |
| Archive | `bank-csvs/archive/` (YYMMDD-bank-N.csv) |
| Merge script | `bank-csvs/merge_downloads.sh` |
| RBC merged CSV | `bank-csvs/rbc.csv` (has header row) |
| TD merged CSV | `bank-csvs/td.csv` (no headers) |
| RBC importer config | `bank-csvs/rbc.json` |
| TD importer config | `bank-csvs/td.json` |
| Docker compose | `/Users/joelmgallant/git/firefly-iii/docker-compose.yml` |
| Importer env | `/Users/joelmgallant/git/firefly-iii/.env.dataimporter` |
| Autoimport secret | Stored in `.env.dataimporter` as `AUTO_IMPORT_SECRET` |

## Workflow

```
1. Download CSVs from bank websites into bank-csvs/download/
2. Run: ./bank-csvs/merge_downloads.sh
3. Run: curl -X POST "http://localhost:81/autoimport?secret=<SECRET>&directory=/import"
```

## Bank File Conventions

| Bank | Download pattern | Format | Merged into |
|------|-----------------|--------|-------------|
| TD Visa | `accountactivity*.csv` | No headers, 5 cols: date, description, debit, credit, balance | `td.csv` |
| RBC | `csv*.csv` | Header row, 8 cols: Account Type, Account Number, Transaction Date, Cheque Number, Description 1, Description 2, CAD$, USD$ | `rbc.csv` |

The merge script handles deduplication of RBC headers (keeps one) and concatenates all TD files directly. After merging, originals are renamed with a date prefix (`YYMMDD-bank-N.csv`) and moved to `archive/`.

## Docker Architecture

The data importer runs as a service in docker-compose alongside the Firefly III app:

- **app** (fireflyiii/core) — port 80, the main Firefly III instance
- **data_importer** (fireflyiii/data-importer) — port 81, with `bank-csvs/` mounted at `/import`
- **db** (mariadb) — database

All three share `firefly-network`. The importer reaches the app at `http://app:8080` (stable Docker hostname).

## Autoimport Endpoint

```bash
# Trigger import of all CSVs in /import
curl -X POST "http://localhost:81/autoimport?secret=<SECRET>&directory=/import"
```

- Pairs CSVs with JSON configs by filename (`rbc.csv` + `rbc.json`)
- Long-running — may return 504 timeout on large imports, but processing continues in the container
- Check progress: `docker logs -f firefly-iii-data_importer-1`
- Duplicate detection is enabled — safe to re-run

## Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| 401 Unauthenticated | PAT expired or invalidated (e.g., after app upgrade) | Generate new PAT at `http://localhost/profile` (OAuth tab), update `.env.dataimporter`, restart importer |
| Version mismatch error | Data importer newer than Firefly app | `docker compose pull app && docker compose up -d` |
| 504 Gateway Timeout | Import takes longer than nginx timeout | Not an error — import continues in background, check `docker logs` |
| Files not visible in container | Volume mount issue | Verify with `docker exec firefly-iii-data_importer-1 ls /import/` |
| Config not matched | JSON filename doesn't match CSV filename | Ensure `rbc.json` pairs with `rbc.csv`, `td.json` with `td.csv` |

## Key Environment Variables (.env.dataimporter)

| Variable | Purpose |
|----------|---------|
| `FIREFLY_III_ACCESS_TOKEN` | Personal Access Token for API auth |
| `CAN_POST_FILES` | Enables `/autoupload` endpoint |
| `CAN_POST_AUTOIMPORT` | Enables `/autoimport` endpoint |
| `IMPORT_DIR_ALLOWLIST` | Container path allowed for directory import (`/import`) |
| `FALLBACK_IN_DIR` | Use `_fallback.json` when no matching config exists |
| `AUTO_IMPORT_SECRET` | Secret for autoimport/autoupload endpoints (min 16 chars) |

Note: `FIREFLY_III_URL` is set inline in docker-compose.yml as `http://app:8080`, not in the env file.
