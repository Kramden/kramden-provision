#!/usr/bin/env python3
"""
Look up a Sortly record by item name.

Usage:
    python3 sortly_lookup_by_name.py <name>
    python3 sortly_lookup_by_name.py <name> --stage=spec
    python3 sortly_lookup_by_name.py <name> --stage=osload
"""

import argparse
import json
import sys

from sortly import (
    search_item_by_name,
    get_api_key,
    get_stage_folder_ids,
    list_subfolders,
    SEARCH_FOLDER_IDS,
)


def display_item(item):
    """Display item details in a readable format."""
    print(f"\n{'='*60}")
    print(f"Name: {item.get('name')}")
    print(f"ID: {item.get('id')}")
    print(f"SID: {item.get('sid')}")
    print(f"Parent ID: {item.get('parent_id')}")
    print(f"Type: {item.get('type')}")
    print(f"Created: {item.get('created_at')}")
    print(f"Updated: {item.get('updated_at')}")

    custom_attrs = item.get("custom_attribute_values", [])
    if custom_attrs:
        print(f"\nCustom Attributes:")
        for attr in custom_attrs:
            name = attr.get("custom_attribute_name") or attr.get("name")
            value = attr.get("value")
            if value is not None and value != "":
                print(f"  {name}: {value}")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="Look up a Sortly record by item name.")
    parser.add_argument("name", help="Item name to search for")
    parser.add_argument(
        "--stage",
        choices=["spec", "osload", "test"],
        help="Search stage-specific folders (spec or osload)",
    )
    args = parser.parse_args()

    try:
        api_key = get_api_key()
    except EnvironmentError as e:
        print(f"Error: {e}")
        sys.exit(1)

    if args.stage:
        root_folders = get_stage_folder_ids(args.stage)
        print(f"Discovering subfolders for stage '{args.stage}'...")
        folder_ids = []
        for fid in root_folders:
            folder_ids.extend(list_subfolders(api_key, fid))
        print(f"Searching {len(folder_ids)} folder(s)...")
    else:
        folder_ids = SEARCH_FOLDER_IDS

    print(f"Searching for '{args.name}' in folders: {', '.join(folder_ids)}...")
    results = search_item_by_name(api_key, folder_ids, args.name)
    if not results:
        print(f"\nNo items found with name '{args.name}'")
        sys.exit(1)

    print(f"\nFound {len(results)} matching item(s):")
    for item in results:
        display_item(item)

    # If exactly one match, offer to show full JSON
    if len(results) == 1:
        show_json = input("\nShow full JSON? (y/n): ").strip().lower()
        if show_json == "y":
            print(json.dumps(results[0], indent=4))


if __name__ == "__main__":
    main()
