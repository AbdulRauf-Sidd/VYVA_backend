"""
DRY RUN of update_db_from_json.py: does everything, prints the summary, then rolls
back so nothing is saved.

Usage:
    .venv/bin/python scripts/dry_run_update.py
"""

from update_db_from_json import main

if __name__ == "__main__":
    main(dry_run=True)
