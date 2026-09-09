#!/usr/bin/env python3
"""
Look up a Sortly folder's hierarchy (ancestors + descendants) via the
folder lookup endpoint and print every folder id it returns.

Usage:
    python3 sortly_folder_lookup.py <folder_id> [folder_id ...]
"""

import argparse
import sys

from sortly import get_folder_lookup_config
import requests


def main():
    parser = argparse.ArgumentParser(
        description="Print all folder ids returned by the Sortly folder lookup endpoint."
    )
    parser.add_argument("folder_id", nargs="+", type=int, help="One or more folder ids")
    args = parser.parse_args()

    try:
        url, api_key = get_folder_lookup_config()
    except EnvironmentError as e:
        print(f"Error: {e}")
        sys.exit(1)

    response = requests.post(
        url,
        json={"folderIds": args.folder_id},
        headers={"Content-Type": "application/json", "X-API-Key": api_key},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    for folder in data.get("folders", []):
        print(folder["id"])

    if data.get("notFound"):
        print(f"Not found: {data['notFound']}", file=sys.stderr)
    if data.get("errors"):
        print(f"Errors: {data['errors']}", file=sys.stderr)


if __name__ == "__main__":
    main()
