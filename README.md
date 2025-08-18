# About

Tool used by Kramden for OS Load and Final Test stages of the refurbishing process.

## Dependencies

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 python3-psutil python3-pyudev
```

## Running OS Load

```bash
cd src/
./osload.py
```

## Running Final Test

```bash
cd src/
./finaltest.py
```

## Run Unit Tests

```bash
python3 -m unittest discover tests
```

# Installation Instructions
## Build

### Dependances

- build-essential
- meson

### Build

```
rm -rf builddir
meson setup -Dprefix=$HOME/.local builddir
meson compile -C builddir --verbose
```

### Install

```
meson install -C builddir
```

### Run

```
$HOME/.local/bin/kramden-provision-osload
$HOME/.local/bin/kramden-provision-finaltest
```
