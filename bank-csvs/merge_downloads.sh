#!/usr/bin/env bash
# Merge downloaded bank CSVs into the auto-import files, then archive originals.
#
# accountactivity*.csv  → td.csv   (TD Visa: no headers, 5 columns)
# csv*.csv              → rbc.csv  (RBC: header row, 8 columns)
#
# After merging, downloads are renamed with a date prefix (YYMMDD-bank-N.csv)
# and moved to the archive/ directory.
#
# Usage: ./merge_downloads.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DOWNLOAD_DIR="$SCRIPT_DIR/download"
ARCHIVE_DIR="$SCRIPT_DIR/archive"
DATE_PREFIX="$(date +%y%m%d)"

if [ ! -d "$DOWNLOAD_DIR" ]; then
  echo "No download directory found at $DOWNLOAD_DIR"
  exit 1
fi

mkdir -p "$ARCHIVE_DIR"

# --- TD (accountactivity files, no headers) ---
td_files=()
for f in "$DOWNLOAD_DIR"/accountactivity*.csv; do
  [ -e "$f" ] && td_files+=("$f")
done

if [ ${#td_files[@]} -gt 0 ]; then
  cat "${td_files[@]}" > "$SCRIPT_DIR/td.csv"
  echo "Merged ${#td_files[@]} TD file(s) → td.csv ($(wc -l < "$SCRIPT_DIR/td.csv") lines)"

  i=1
  for f in "${td_files[@]}"; do
    archive_name="${DATE_PREFIX}-td-${i}.csv"
    mv "$f" "$ARCHIVE_DIR/$archive_name"
    echo "  Archived $(basename "$f") → archive/$archive_name"
    ((i++))
  done
else
  echo "No accountactivity*.csv files found — td.csv unchanged"
fi

# --- RBC (csv* files, with header row) ---
rbc_files=()
for f in "$DOWNLOAD_DIR"/csv*.csv; do
  [ -e "$f" ] && rbc_files+=("$f")
done

if [ ${#rbc_files[@]} -gt 0 ]; then
  # Take header from the first file, then data rows from all files
  head -1 "${rbc_files[0]}" > "$SCRIPT_DIR/rbc.csv"
  for f in "${rbc_files[@]}"; do
    tail -n +2 "$f" >> "$SCRIPT_DIR/rbc.csv"
  done
  echo "Merged ${#rbc_files[@]} RBC file(s) → rbc.csv ($(wc -l < "$SCRIPT_DIR/rbc.csv") lines)"

  i=1
  for f in "${rbc_files[@]}"; do
    archive_name="${DATE_PREFIX}-rbc-${i}.csv"
    mv "$f" "$ARCHIVE_DIR/$archive_name"
    echo "  Archived $(basename "$f") → archive/$archive_name"
    ((i++))
  done
else
  echo "No csv*.csv files found — rbc.csv unchanged"
fi

# Clean up empty download dir
remaining=$(find "$DOWNLOAD_DIR" -maxdepth 1 -name '*.csv' | wc -l)
if [ "$remaining" -eq 0 ]; then
  echo "Download directory is clean"
fi
