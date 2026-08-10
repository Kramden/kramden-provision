# About

Tools used by Kramden for the computer refurbishing process. Each tool is a GTK4/Adwaita application that guides the technician through the workflow.

- **Spec** — Registers/updates the device in Sortly inventory, runs hardware checks, and generates a tracking sheet PDF.
- **OS Load** — Identifies the device (K-number), registers with Landscape, and collects system information.
- **Final Test** — Performs final hardware validation, walking through defect-type checks page by page, before the device ships.
- **Secure Erase** — Detects non-removable SATA/NVMe drives and securely wipes them.
- **Device** — End-user application that displays the Kramden guide and device information (hardware specs). Creates a `~/.config/kramden-intro-done` marker on close to track first launch.

## Sortly Integration

The OS Load and Spec workflows integrate with the [Sortly](https://www.sortly.com/) inventory API to look up, create, and update device records.

On startup each workflow looks up the device by its serial number. If a matching Sortly record is found the K-number is pre-populated and the record is updated with the latest system information (brand, model, CPU, RAM, storage, serial, GPU, battery health, etc.).

### Configuration

| Environment Variable | Description |
|---|---|
| `SORTLY_API_KEY` | **Required.** API key for authenticating with the Sortly API. |
| `KRAMDEN_TEST` | Optional. When set, all workflows use `TEST_FOLDER_IDS` instead of their stage-specific folders. |

Each workflow searches its own set of top-level Sortly folders and recursively discovers all subfolders underneath them:

| Workflow | Folder IDs |
|---|---|
| Spec | `SPEC_FOLDER_IDS` |
| OS Load | `OSLOAD_FOLDER_IDS` |
| Test | `TEST_FOLDER_IDS` |

### CLI Scripts

Standalone scripts for working with Sortly outside the wizard workflows:

```bash
# Look up a device by serial number (auto-detects if no serial given)
SORTLY_API_KEY=... python3 src/sortly_lookup_by_serial.py [serial] [--stage=spec|osload|test]

# Look up a device by name
SORTLY_API_KEY=... python3 src/sortly_lookup_by_name.py <name> [--stage=spec|osload|test]

# Update a device record with system info
SORTLY_API_KEY=... python3 src/sortly_update_system_info.py <item_name>
```

## Defect Types

The defect-type buttons and tracking-sheet datacodes shown on each Final Test page (Physical Defects, Screen, Touchscreen, Webcam, Keyboard, USB-A, USB-C, WiFi, Touchpad, Browser, and Browser's "Audio" sub-picker) are config-driven from `src/defect_types.json`, rather than hardcoded in `src/manualtest.py`. Each entry has a `label`, a fixed `code` (order-independent -- never derive a new one from position), an `order`, and optionally `sub_buttons` (custom labels to pop up instead of the page's normal picker) or `no_sub_buttons` (report directly, no picker at all).

After hand-editing `src/defect_types.json`, validate it with:

```bash
python3 scripts/validate_defect_types.py
```

This also runs in CI on any PR touching that file (`.github/workflows/validate-defect-types.yaml`).

Some buttons have extra logic wired to them beyond a plain label + code (e.g. Physical Defects' "Cracks"/"Broken Part", Keyboard's "Physical damage") and stay hardcoded in `manualtest.py`; their codes are listed in each page's `reserved_codes` so the config can't collide with them.

### Requesting a defect-type change via GitHub Issue

Adding or removing a *plain* defect-type button doesn't require touching code. Open a new issue using the **"Defect type / datacode change"** template (`.github/ISSUE_TEMPLATE/defect-type-change.yml`) and fill in:

| Field | Notes |
|---|---|
| Action | `Add` or `Remove`. |
| Page | Which test page's button list to change. |
| Button label | Exact button text. For `Remove`, must match an existing button's label exactly. |
| Datacode | `Add` only. Format `<PREFIX><NN>` (e.g. `SC10`); leave blank to auto-assign the next free code for that page. |
| Sub-buttons | `Add` only (not for Sound). One label per line to pop up under the new button instead of the page's default picker. Leave blank for the page's normal behavior. |
| No sub-buttons | `Add` only. Check to have the button report directly with no popup at all. Mutually exclusive with Sub-buttons. |
| Why | Optional context for the reviewer. |

Submitting the issue triggers `.github/workflows/defect-type-request.yaml`, which:

1. Parses the issue body with `scripts/apply_defect_type_request.py` and applies the change to `src/defect_types.json`.
2. Re-validates the result with `scripts/validate_defect_types.py` as a safety net.
3. On success, opens a pull request with the change (closing the issue); on failure, comments the rejection reason back on the issue so it can be edited and reopened.

This workflow only runs once, on freshly opened issues, and is restricted to org members/collaborators since it pushes a branch and opens a PR with repo write access. A maintainer still has to review and merge the resulting PR before the change takes effect.

## Dependencies

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 python3-psutil python3-pyudev python3-reportlab python3-fonttools python3-requests python3-apt avahi-utils efivar git
```

## Running

```bash
cd src/
./osload.py
./spec.py
./finaltest.py
./deviceinfo.py
./secureerase.py
```

## Run Unit Tests

```bash
python3 -m unittest discover tests
```

# Installation

## Build Dependencies

- build-essential
- meson

## Build

```
rm -rf builddir
meson setup -Dprefix=$HOME/.local builddir
meson compile -C builddir --verbose
```

## Install

```
meson install -C builddir
```

## Run

```
$HOME/.local/bin/kramden-provision-osload
$HOME/.local/bin/kramden-spec
$HOME/.local/bin/kramden-provision-finaltest
$HOME/.local/bin/kramden-device
$HOME/.local/bin/kramden-secure-erase
```
