#!/usr/bin/env python3
"""
Fetch a Sortly record by name and update it with system hardware information.

Usage: python3 sortly_update_system_info.py <item_name>
"""

import requests
import json
import time
import sys
import os

from utils import Utils


def search_item_by_name(api_key, folder_id, item_name):
    """Search for an item by exact name in the specified folder."""
    url = "https://api.sortly.co/api/v1/items/search"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    query_params = {
        "page": 1,
        "per_page": 100,
        "include": "custom_attributes,photos,options,variants",
    }

    payload = {"folder_ids": [int(folder_id)], "name": item_name, "type": "item"}

    try:
        response = requests.post(
            url, params=query_params, json=payload, headers=headers
        )

        if response.status_code == 429:
            print("Rate limit hit, sleeping 60 seconds...")
            time.sleep(60)
            response = requests.post(
                url, params=query_params, json=payload, headers=headers
            )

        response.raise_for_status()
        data = response.json()
        items = data.get("data", [])

        # Filter for exact match
        exact_matches = [item for item in items if item.get("name") == item_name]
        return exact_matches

    except Exception as e:
        print(f"Error searching for item: {e}")
        return []


def create_item(api_key, folder_id, item_name):
    """Create a new item in the specified folder."""
    url = "https://api.sortly.co/api/v1/items"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    payload = {
        "name": item_name,
        "type": "item",
        "parent_id": folder_id,
    }

    print(f"Creating new item '{item_name}'...")
    try:
        response = requests.post(url, json=payload, headers=headers)
        if not response.ok:
            print(f"Failed to create item: {response.status_code}")
            print(f"Server response: {response.text}")
            return None
        data = response.json()
        item = data.get("data", data)
        print(f"Created item with ID: {item['id']}")
        return item
    except Exception as e:
        print(f"Error creating item: {e}")
        return None


def update_item(api_key, item_id, updates_dict):
    """Update custom attributes on a Sortly item."""
    base_url = f"https://api.sortly.co/api/v1/items/{item_id}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    print(f"Fetching item {item_id} to get attribute IDs...")
    try:
        response = requests.get(
            base_url, params={"include": "custom_attributes"}, headers=headers
        )
        response.raise_for_status()
        raw_json = response.json()
    except Exception as e:
        print(f"Error fetching item: {e}")
        return False

    item_data = raw_json.get("data", raw_json)
    current_attrs = item_data.get("custom_attribute_values", [])
    if not current_attrs:
        current_attrs = item_data.get("custom_attributes", [])

    # Build name to ID mapping
    name_to_id = {}
    for attr in current_attrs:
        name = attr.get("custom_attribute_name") or attr.get("name")
        c_id = attr.get("custom_attribute_id") or attr.get("id")
        if name and c_id:
            name_to_id[name] = c_id

    # Build payload
    payload_list = []
    print("Mapping updates...")
    for key, val in updates_dict.items():
        if key in name_to_id:
            attr_id = name_to_id[key]
            obj = {
                "custom_attribute_id": attr_id,
                "custom_attribute_name": key,
                "value": str(val),
            }
            payload_list.append(obj)
            print(f"  [OK] '{key}' -> {val}")
        else:
            print(f"  [!] '{key}' skipped (attribute not found on item)")

    if not payload_list:
        print("No valid updates to send.")
        return False

    final_body = {
        "custom_attribute_values": payload_list,
        "custom_attributes": [
            {"id": x["custom_attribute_id"], "value": x["value"]} for x in payload_list
        ],
    }

    print("Sending update...")
    try:
        put_resp = requests.put(base_url, json=final_body, headers=headers)
        if not put_resp.ok:
            print(f"Update failed: {put_resp.status_code}")
            print(f"Server response: {put_resp.text}")
            return False
        print("SUCCESS: Item updated.")
        return True
    except Exception as e:
        print(f"Update failed: {e}")
        return False


def get_system_info():
    """Retrieve system hardware information using Utils."""
    utils = Utils()

    brand = utils.get_vendor()
    model = utils.get_model()
    cpu = utils.get_cpu_info()
    ram = utils.get_mem()
    disks = utils.get_disks()
    gpu = utils.get_discrete_gpu()
    serial = utils.get_serial()
    batteries = utils.get_battery_capacities()
    device_type = utils.get_chassis_type()

    # Sum total storage in GB
    if disks:
        total_storage = sum(disks.values())
    else:
        total_storage = 0

    # Format battery capacity
    if batteries:
        capacities = list(batteries.values())
        if len(capacities) == 1:
            battery_health = f"{capacities[0]}%"
        else:
            # Multiple batteries - show all
            battery_health = ", ".join(f"{c}%" for c in capacities)
    else:
        battery_health = None

    info = {
        "Brand": brand,
        "Model": model,
        "CPU": cpu,
        "RAM": ram,  # Numeric value only
        "Storage": total_storage,  # Numeric value only
        "Serial# Scanner": serial,
    }

    # Only include Item Type if chassis type could be determined
    if device_type:
        info["Item Type"] = device_type

    # Only include Graphics if a discrete GPU is detected
    if gpu:
        info["Graphics"] = gpu

    # Only include Battery Health if batteries are detected
    if battery_health:
        info["Battery Health"] = battery_health

    return info


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <item_name>")
        sys.exit(1)

    item_name = sys.argv[1]

    # Get API key from environment
    api_key = os.environ.get("SORTLY_API_KEY")
    if not api_key:
        print("Error: SORTLY_API_KEY environment variable must be set")
        sys.exit(1)

    # Folder ID for items
    FOLDER_ID = 102298337

    print(f"Searching for item '{item_name}'...")
    results = search_item_by_name(api_key, FOLDER_ID, item_name)

    if not results:
        print(f"No item found with name '{item_name}'")
        create_confirm = input("Create a new record? (y/n): ").strip().lower()
        if create_confirm != "y":
            print("Cancelled.")
            sys.exit(0)
        item = create_item(api_key, FOLDER_ID, item_name)
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
