# About

Tool used by Kramden for OS Load and Final Test stages of the refurbishing process.

## Dependencies

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 python3-psutil
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
