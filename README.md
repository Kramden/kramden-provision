# About

Tool used by Kramden for OS Load, Spec, and Final Test stages of the refurbishing process. Each stage is a GTK4/Adwaita wizard that guides the technician through the workflow.

- **OS Load** — Identifies the device (K-number), registers with Landscape, and collects system information.
- **Spec** — Registers/updates the device in Sortly inventory, runs hardware checks, and generates a tracking sheet PDF.
- **Final Test** — Performs final hardware validation before the device ships.

## Sortly Integration

The OS Load and Spec workflows integrate with the [Sortly](https://www.sortly.com/) inventory API to look up, create, and update device records.

On startup each workflow looks up the device by its serial number. If a matching Sortly record is found the K-number is pre-populated and the record is updated with the latest system information (brand, model, CPU, RAM, storage, serial, GPU, battery health, etc.).

### Configuration

| Environment Variable | Description |
|---|---|
| `SORTLY_API_KEY` | **Required.** API key for authenticating with the Sortly API. |
| `SORTLY_FOLDER_ID` | Optional. Overrides the default Sortly folder ID for all workflows. |

Default folder IDs when `SORTLY_FOLDER_ID` is not set:

| Workflow | Default Folder ID |
|---|---|
| OS Load | `S8WM5R1510` |
| Spec | `S8WM5R1509` |
| CLI scripts | `102298337` |

### CLI Scripts

Two standalone scripts are provided for working with Sortly outside the wizard workflows:

```bash
# Look up a device by serial number
SORTLY_API_KEY=... python3 src/sortly_lookup_by_serial.py [serial] [folder_id]

# Update a device record with system info
SORTLY_API_KEY=... python3 src/sortly_update_system_info.py <item_name>
```

## Dependencies

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 python3-psutil python3-pyudev python3-reportlab python3-requests
```

## Running

```bash
cd src/
./osload.py
./spec.py
./finaltest.py
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
```
