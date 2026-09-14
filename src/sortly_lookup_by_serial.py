#!/usr/bin/env python3
"""
Look up a Sortly record by the device's serial number.

Usage:
    python3 sortly_lookup_by_serial.py                       # Use local machine's serial
    python3 sortly_lookup_by_serial.py <serial>              # Use specified serial number
    python3 sortly_lookup_by_serial.py <serial> --stage=spec
    python3 sortly_lookup_by_serial.py <serial> --stage=osload
"""

import argparse
import json
import sys

from utils import Utils
from sortly import (
    search_by_serial,
    get_api_key,
    get_stage_folder_ids,
    resolve_folder_ids,
    SEARCH_FOLDER_IDS,
)


def display_item(item):
    """Display item details in a readable format."""
    print(f"\n{'='*60}")
    print(f"Name: {item.get('name')}")
    print(f"ID: {item.get('id')}")
    print(f"SID: {item.get('sid')}")
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
    parser = argparse.ArgumentParser(description="Look up a Sortly record by serial number.")
    parser.add_argument("serial", nargs="?", help="Serial number (reads from local machine if omitted)")
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

    # Get serial number - from argument or local machine
    if args.serial:
        serial_number = args.serial
        print(f"Using provided serial: {serial_number}")
    else:
        print("Reading serial number from local machine...")
        utils = Utils()
        serial_number = utils.get_serial()
        if not serial_number:
            print("Error: Could not determine local machine serial number")
            sys.exit(1)
        print(f"Local serial: {serial_number}")

    if args.stage:
        root_folders = get_stage_folder_ids(args.stage)
        print(f"Looking up folders for stage '{args.stage}'...")
        folder_ids = resolve_folder_ids(root_folders)
    else:
        folder_ids = SEARCH_FOLDER_IDS

    print(f"Searching for serial '{serial_number}'...")
    results = search_by_serial(api_key, folder_ids, serial_number)
    if not results:
        print(f"\nNo items found with serial '{serial_number}'")
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
