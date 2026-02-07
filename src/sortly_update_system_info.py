#!/usr/bin/env python3
"""
Fetch a Sortly record by name and update it with system hardware information.

Usage: python3 sortly_update_system_info.py <item_name>
"""

import sys

from sortly import (
    get_api_key,
    search_item_by_name,
    create_item,
    update_item,
    get_system_info,
    SEARCH_FOLDER_IDS,
    TEST_FOLDER_IDS,
)


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <item_name>")
        sys.exit(1)

    item_name = sys.argv[1]

    # Get API key from environment
    try:
        api_key = get_api_key()
    except EnvironmentError as e:
        print(f"Error: {e}")
        sys.exit(1)

    print(f"Searching for item '{item_name}'...")
    results = search_item_by_name(api_key, SEARCH_FOLDER_IDS, item_name)

    if not results:
        print(f"No item found with name '{item_name}'")
        create_confirm = input("Create a new record? (y/n): ").strip().lower()
        if create_confirm != "y":
            print("Cancelled.")
            sys.exit(0)
        item = create_item(api_key, TEST_FOLDER_IDS[0], item_name)
        if not item:
            print("Failed to create item.")
            sys.exit(1)
        item_id = item["id"]
    else:
        if len(results) > 1:
            print(
                f"Warning: Found {len(results)} items with name '{item_name}', using first match"
            )
        item = results[0]
        item_id = item["id"]
        print(f"Found item: {item['name']} (ID: {item_id})")

    # Get system hardware info
    print("\nGathering system information...")
    system_info = get_system_info()

    print("\nSystem information to update:")
    for key, value in system_info.items():
        if key in ("RAM", "Storage"):
            print(f"  {key}: {value} GB")
        else:
            print(f"  {key}: {value}")

    # Confirm with user
    confirm = input("\nProceed with update? (y/n): ").strip().lower()
    if confirm != "y":
        print("Update cancelled.")
        sys.exit(0)

    # Update the Sortly record
    print(f"\nUpdating Sortly record...")
    success = update_item(api_key, item_id, system_info)

    if success:
        print("\nDone!")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
