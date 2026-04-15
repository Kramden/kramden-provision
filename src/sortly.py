"""
Reusable Sortly API module.

Provides functions for searching, creating, and updating items in Sortly,
plus local system information gathering.
"""

import os
import reprlib
import time

import requests

from utils import Utils

SORTLY_API_BASE_URL = "https://api.sortly.co/api/v1"
OSLOAD_FOLDER_IDS = [
    "106345033",
    "106345034",
    "106345035",
    "106345038",
    "106345039",
    "106345040",
    "106345043",
    "106345044",
    "106345045",
]
SPEC_FOLDER_IDS = [
    "102396716",
    "102312621",
    "102312726",
    "102312732",
    "102312850",
]
TEST_FOLDER_IDS = ["102298337"]
EXPANDED_FOLDER_IDS = (
    TEST_FOLDER_IDS
    + OSLOAD_FOLDER_IDS
    + SPEC_FOLDER_IDS
    + [
        "102396723",
        "102312726",
        "102312732",
        "102312850",
        "102312733",
    ]
)

# RFT All-In-Ones: 102396716
# RFT Desktop: 102396723
# RFT Laptops: 102312621
# RFT Temporary Projects: 102312733
# RFT Problem Machines: # ALL OF THESE ARE EXPANDED SEARCH
### RFT Defective Laptop Shelf: 102312726
### RFT BIOS Locked Shelf: 102312732
### RFT Digital Asset Tag Bin: 102312850
### RFT Temporary Projects: 102312733

# RTA Programs (Linux) Desktop: 106345030
### RTA Programs (Linux) Desktop Stage 1: 106345033
### RTA Programs (Linux) Desktop Stage 2: 106345034
### RTA Programs (Linux) Desktop Stage 3: 106345035
# RTA Programs (Linux) Laptops: 106345031
### RTA Programs (Linux) Laptops Stage 1: 106345038
### RTA Programs (Linux) Laptops Stage 2: 106345039
### RTA Programs (Linux) Laptops Stage 3: 106345040
# RTA Programs (Linux) All-In-Ones: 106345032
### RTA Programs (Linux) All-In-Ones Stage 1: 106345043
### RTA Programs (Linux) All-In-Ones Stage 2: 106345044
### RTA Programs (Linux) All-In-Ones Stage 3: 106345045

# SPEC: Search all RFT folders
# OSLOAD/FINALTEST: All RTA + RTF Desktops + RTF All-In-Ones

#####################OLD###############################
# RTA All-In-Ones: 102396645
# RTA Laptops: 102312875
# RTA Desktop: 102396658
# TRIAGE TEST 102298337
# Allocated: 102309828
#####################OLD###############################

SEARCH_FOLDER_IDS = ["102309375", "102312621", "102298337"]
INCOMING_FOLDER_ID = "106628131"  # Spec-Not-Found - Leadership Only
API_KEY_ENV_VAR = "SORTLY_API_KEY"
SORTLY_API_CALL_COUNT = 0
_DEBUG_REPR = reprlib.Repr()
_DEBUG_REPR.maxdict = 8
_DEBUG_REPR.maxlist = 8
_DEBUG_REPR.maxstring = 120


def _format_request_debug(params=None, json_body=None):
    """Return a compact debug string for Sortly API request details."""
    details = []
    if params is not None:
        details.append(f"params={_DEBUG_REPR.repr(params)}")
    if json_body is not None:
        details.append(f"json={_DEBUG_REPR.repr(json_body)}")
    return " ".join(details)


def get_api_call_count():
    """Return the number of Sortly API calls made in this process."""
    return SORTLY_API_CALL_COUNT


def reset_api_call_count():
    """Reset the Sortly API call counter."""
    global SORTLY_API_CALL_COUNT
    SORTLY_API_CALL_COUNT = 0


def _sortly_request(method, url, **kwargs):
    """Send a Sortly API request with debug output and a running call counter."""
    global SORTLY_API_CALL_COUNT

    SORTLY_API_CALL_COUNT += 1
    call_number = SORTLY_API_CALL_COUNT
    debug_details = _format_request_debug(
        params=kwargs.get("params"), json_body=kwargs.get("json")
    )
    if debug_details:
        print(f"[Sortly API #{call_number}] {method.upper()} {url} {debug_details}")
    else:
        print(f"[Sortly API #{call_number}] {method.upper()} {url}")

    try:
        response = requests.request(method, url, **kwargs)
    except requests.RequestException as exc:
        print(f"[Sortly API #{call_number}] Request failed: {exc}")
        raise

    print(f"[Sortly API #{call_number}] Response {response.status_code}")
    return response


def get_stage_folder_ids(stage):
    """Return folder IDs for the given stage, or TEST_FOLDER_IDS if KRAMDEN_TEST is set."""
    if os.environ.get("KRAMDEN_TEST"):
        return TEST_FOLDER_IDS
    stage_map = {
        "spec": SPEC_FOLDER_IDS,
        "osload": OSLOAD_FOLDER_IDS,
        "test": TEST_FOLDER_IDS,
    }
    return stage_map[stage]


def get_api_key():
    """Read API key from SORTLY_API_KEY env var, raise EnvironmentError if missing."""
    api_key = os.environ.get(API_KEY_ENV_VAR)
    if not api_key:
        raise EnvironmentError(f"{API_KEY_ENV_VAR} environment variable must be set")
    return api_key


def search_by_serial(api_key, folder_ids, serial_number):
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
            "type": "item",
            "query": serial_number,
            "folder_ids": folder_ids,
        }

        try:
            response = _sortly_request(
                "post", url, params=query_params, json=payload, headers=headers
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


def search_item_by_name(api_key, folder_ids, item_name):
    """Search for an item by exact name in the specified folders."""
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

    payload = {"name": item_name, "type": "item", "folder_ids": folder_ids}

    try:
        max_retries = 3
        backoff_seconds = 60
        response = None

        for attempt in range(max_retries):
            response = _sortly_request(
                "post", url, params=query_params, json=payload, headers=headers
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
        response = _sortly_request("post", url, json=payload, headers=headers)
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
        response = _sortly_request(
            "get", base_url, params={"include": "custom_attributes"}, headers=headers
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
        put_resp = _sortly_request("put", base_url, json=final_body, headers=headers)
        if not put_resp.ok:
            print(f"Update failed: {put_resp.status_code}")
            print(f"Server response: {put_resp.text}")
            return False
        print("SUCCESS: Item updated.")
        return True
    except (requests.RequestException, ValueError) as e:
        print(f"Update failed: {e}")
        return False


def list_subfolders(api_key, parent_id, depth=0):
    """Recursively find all subfolder IDs under a given parent folder."""
    indent = "  " * depth
    print(f"{indent}Checking folder {parent_id} for subfolders...")

    url = f"{SORTLY_API_BASE_URL}/items"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    child_ids = []
    child_names = {}
    max_retries = 3
    backoff_seconds = 60
    page = 1
    more_pages = True

    while more_pages:
        query_params = {"folder_id": parent_id, "page": page, "per_page": 100}

        for attempt in range(max_retries):
            try:
                response = _sortly_request(
                    "get", url, params=query_params, headers=headers
                )

                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        print(
                            f"{indent}Rate limit hit (429). Sleeping {backoff_seconds} seconds before retry "
                            f"{attempt + 2} of {max_retries}..."
                        )
                        time.sleep(backoff_seconds)
                        backoff_seconds *= 2
                        continue
                    else:
                        print(
                            f"{indent}Rate limit hit (429) and maximum retries reached."
                        )
                        more_pages = False
                        break

                response.raise_for_status()
                data = response.json()
                items = data.get("data", [])

                if not items:
                    more_pages = False
                    break

                for item in items:
                    if item.get("type") == "folder":
                        cid = str(item["id"])
                        child_ids.append(cid)
                        child_names[cid] = item.get("name", cid)

                if len(items) < 100:
                    more_pages = False
                else:
                    page += 1
                break

            except (requests.RequestException, ValueError) as e:
                print(f"{indent}Error listing subfolders: {e}")
                more_pages = False
                break

    if child_ids:
        names = ", ".join(f"{child_names[c]} ({c})" for c in child_ids)
        print(f"{indent}Found {len(child_ids)} subfolder(s): {names}")
    else:
        print(f"{indent}No subfolders")

    # Recurse into each child folder
    all_ids = [parent_id]
    for child_id in child_ids:
        all_ids.extend(list_subfolders(api_key, child_id, depth + 1))

    return all_ids


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
        total_storage = sum(d["size"] for d in disks.values())
    else:
        total_storage = 0

    # Format battery capacity
    if batteries:
        # Format as "BAT0: 87%" or "BAT0: 87%, BAT1: 78%"
        battery_parts = [f"{name}: {capacity}%" for name, capacity in batteries.items()]
        battery_health = ", ".join(battery_parts)
    else:
        battery_health = None

    info = {
        "Brand": brand,
        "Chassis Model": model,
        "CPU": cpu,
        "RAM": ram,
        "Storage": total_storage,
        "Serial# Scanner": serial,
        "Serial Number": serial,
    }

    if device_type:
        info["Item Type"] = device_type

    if gpu:
        info["Graphics"] = gpu
    else:
        igpu = utils.get_integrated_gpu()
        if igpu:
            info["Graphics"] = igpu

    if battery_health:
        info["Battery Health"] = battery_health

    return info
