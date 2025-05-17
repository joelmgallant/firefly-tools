# Firefly III Tools

Scripts for interacting with Firefly III, an open-source personal finance manager.

## Setup

1. Clone this repository
2. Copy `.env.example` to `.env` and fill in your API details:
   ```
   cp .env.example .env
   ```
3. Install required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Available Tools

### money.py

Interacts with Firefly III API to perform various transaction operations.

#### Usage

```bash
python money.py [action]
```

#### Available actions:

- **payback** (default): Queries transactions tagged with "payback" and exports them to CSV in the data folder.

## Data Storage

All exported CSV files and analysis data are stored in the `data/` directory, which is git-ignored.
