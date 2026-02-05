#!/usr/bin/env python3
"""
Look up a Sortly record by the device's serial number.

Usage:
    python3 sortly_lookup_by_serial.py           # Use local machine's serial
    python3 sortly_lookup_by_serial.py <serial>  # Use specified serial number
"""

import requests
import json
import time
import sys
import os

from utils import Utils


def search_by_serial(api_key, folder_id, serial_number):
    """Search for items by serial number in the Serial# Scanner field."""
    url = "https://api.sortly.co/api/v1/items/search"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    page = 1
    all_items = []
    more_pages = True

    print(f"Searching for serial '{serial_number}'...")

    while more_pages:
        query_params = {
            "page": page,
            "per_page": 100,
            "include": "custom_attributes,photos,options,variants",
        }

        # Search using the serial number as a query term
        payload = {
            "folder_ids": [int(folder_id)],
            "type": "item",
            "query": serial_number,
        }

        try:
            response = requests.post(
                url, params=query_params, json=payload, headers=headers
            )

            if response.status_code == 429:
                print("Rate limit hit, sleeping 60 seconds...")
                time.sleep(60)
                continue

            response.raise_for_status()
            data = response.json()
            items = data.get("data", [])

            if not items:
                more_pages = False
            else:
                all_items.extend(items)
                page += 1
                if len(items) < 100:
                    more_pages = False

        except Exception as e:
            print(f"Error: {e}")
            break

    # Filter results to only include items where Serial# Scanner matches
    matching_items = []
    for item in all_items:
        custom_attrs = item.get("custom_attribute_values", [])
        for attr in custom_attrs:
            attr_name = attr.get("custom_attribute_name") or attr.get("name")
            if attr_name == "Serial# Scanner" and attr.get("value") == serial_number:
                matching_items.append(item)
                break

    return matching_items


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
    # Get API key from environment
    api_key = os.environ.get("SECRET_KEY")
    if not api_key:
        print("Error: SECRET_KEY environment variable must be set")
        sys.exit(1)

    # Get serial number - from argument or local machine
    if len(sys.argv) > 1:
        serial_number = sys.argv[1]
        print(f"Using provided serial: {serial_number}")
    else:
        print("Reading serial number from local machine...")
        utils = Utils()
        serial_number = utils.get_serial()
        if not serial_number:
            print("Error: Could not determine local machine serial number")
            sys.exit(1)
        print(f"Local serial: {serial_number}")

    # Folder ID for items
    FOLDER_ID = 102298337

    results = search_by_serial(api_key, FOLDER_ID, serial_number)

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
