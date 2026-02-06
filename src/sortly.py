"""
Reusable Sortly API module.

Provides functions for searching, creating, and updating items in Sortly,
plus local system information gathering.
"""

import requests
import time
import os

from utils import Utils

SORTLY_API_BASE_URL = "https://api.sortly.co/api/v1"
DEFAULT_FOLDER_ID = 102298337
API_KEY_ENV_VAR = "SORTLY_API_KEY"


def get_api_key():
    """Read API key from SORTLY_API_KEY env var, raise EnvironmentError if missing."""
    api_key = os.environ.get(API_KEY_ENV_VAR)
    if not api_key:
        raise EnvironmentError(
            f"{API_KEY_ENV_VAR} environment variable must be set"
        )
    return api_key


def search_by_serial(api_key, folder_id, serial_number):
    """Search for items by serial number in the Serial# Scanner field."""
    url = f"{SORTLY_API_BASE_URL}/items/search"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    page = 1
    all_items = []
    more_pages = True

    while more_pages:
        query_params = {
            "page": page,
            "per_page": 100,
            "include": "custom_attributes,photos,options,variants",
        }

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


def search_item_by_name(api_key, folder_id, item_name):
    """Search for an item by exact name in the specified folder."""
    url = f"{SORTLY_API_BASE_URL}/items/search"
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
        max_retries = 3
        backoff_seconds = 60
        response = None

        for attempt in range(max_retries):
            response = requests.post(
                url, params=query_params, json=payload, headers=headers
            )

            if response.status_code != 429:
                break

            if attempt < max_retries - 1:
                print(
                    f"Rate limit hit (429). Sleeping {backoff_seconds} seconds before retry "
                    f"{attempt + 2} of {max_retries}..."
                )
                time.sleep(backoff_seconds)
                backoff_seconds *= 2
            else:
                print(
                    "Rate limit hit (429) and maximum retries reached. "
                    "Unable to complete search."
                )
                return []
        response.raise_for_status()
        data = response.json()
        items = data.get("data", [])

        # Filter for exact match
        exact_matches = [item for item in items if item.get("name") == item_name]
        return exact_matches

    except (requests.RequestException, ValueError) as e:
        print(f"Error searching for item: {e}")
        return []


def create_item(api_key, folder_id, item_name):
    """Create a new item in the specified folder."""
    url = f"{SORTLY_API_BASE_URL}/items"
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
    except (requests.RequestException, ValueError) as e:
        print(f"Error creating item: {e}")
        return None
    except KeyError:
        print("Error creating item: Response missing expected 'id' field")
        return None


def update_item(api_key, item_id, updates_dict):
    """Update custom attributes on a Sortly item."""
    base_url = f"{SORTLY_API_BASE_URL}/items/{item_id}"
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
    except (requests.RequestException, ValueError) as e:
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
    except (requests.RequestException, ValueError) as e:
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
            battery_health = ", ".join(f"{c}%" for c in capacities)
    else:
        battery_health = None

    info = {
        "Brand": brand,
        "Model": model,
        "CPU": cpu,
        "RAM": ram,
        "Storage": total_storage,
        "Serial# Scanner": serial,
    }

    if device_type:
        info["Item Type"] = device_type

    if gpu:
        info["Graphics"] = gpu

    if battery_health:
        info["Battery Health"] = battery_health

    return info
