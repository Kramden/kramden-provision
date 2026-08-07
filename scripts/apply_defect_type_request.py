#!/usr/bin/env python3
"""Applies one "Add" or "Remove" request (from the
".github/ISSUE_TEMPLATE/defect-type-change.yml" Issue Form) to
src/defect_types.json.

Usage: pipe the issue body to stdin --
    gh issue view <number> --json body -q .body | python3 scripts/apply_defect_type_request.py

Prints a single JSON object describing the outcome to stdout and exits 0 if
src/defect_types.json was updated, or exits 1 (leaving the file untouched)
if the request was rejected -- see
.github/workflows/defect-type-request.yaml, which uses this to decide
whether to open a PR or comment the rejection reason back on the issue.
"""
import json
import os
import re
import sys

sys.path.insert(1, os.path.dirname(os.path.realpath(__file__)))
from validate_defect_types import validate  # noqa: E402

DEFECT_TYPES_PATH = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "..", "src", "defect_types.json"
)

# Must match the "Page" dropdown's option text in
# .github/ISSUE_TEMPLATE/defect-type-change.yml exactly.
PAGE_DISPLAY_TO_KEY = {
    "Physical Defects": "physical_defects",
    "Screen": "screen",
    "Touchscreen": "touchscreen",
    "Webcam": "webcam",
    "Keyboard": "keyboard",
    "USB-A": "usb_a",
    "USB-C": "usb_c",
    "WiFi": "wifi",
    "Touchpad": "touchpad",
    "Browser": "browser",
    'Sound (Browser\'s "Audio" sub-picker)': "sound",
}

# Issue Forms render each field as a "### <label>" heading followed by the
# response (or "_No response_" for an empty optional field).
_FIELD_PATTERN = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)


def parse_issue_body(body):
    """Returns {field label: response text} for every "### label" block in
    an Issue Form-rendered issue body."""
    fields = {}
    matches = list(_FIELD_PATTERN.finditer(body))
    for i, match in enumerate(matches):
        label = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        value = body[start:end].strip()
        if value == "_No response_":
            value = ""
        fields[label] = value
    return fields


def _next_free_code(page, prefix, used_codes):
    for n in range(1, 100):
        code = f"{prefix}{n:02d}"
        if code not in used_codes:
            return code
    return None  # pragma: no cover -- 99 codes exhausted


def apply_request(defect_types, fields):
    """Mutates `defect_types` in place for a valid request. Returns
    (ok, message, details) -- details is a dict of extra info for the
    caller (page_key, label, code, action) on success."""
    action = fields.get("Action", "").strip()
    page_display = fields.get("Page", "").strip()
    label = fields.get("Button label", "").strip()
    datacode = fields.get("Datacode", "").strip()

    if action not in ("Add", "Remove"):
        return False, f'Unrecognized action "{action}" (expected Add or Remove).', {}
    if not label:
        return False, "Button label is required.", {}

    page_key = PAGE_DISPLAY_TO_KEY.get(page_display)
    if page_key is None or page_key not in defect_types:
        return False, f'Unrecognized page "{page_display}".', {}
    page = defect_types[page_key]
    entries = page["types"]
    prefix = page["code_prefix"]
    reserved = set(page.get("reserved_codes", []))
    existing_labels = {e["label"]: e for e in entries}

    if action == "Remove":
        if label not in existing_labels:
            return False, (
                f'"{label}" isn\'t an editable entry on the {page_display} page '
                f"(it may not exist, or it may be one of that page's special "
                f"buttons that can only be changed by a developer)."
            ), {}
        entries.remove(existing_labels[label])
        return (
            True,
            f'Removed "{label}" from {page_display}.',
            {"page": page_key, "label": label, "action": "Remove"},
        )

    # Add
    if label in existing_labels:
        return False, f'"{label}" already exists on the {page_display} page.', {}

    used_codes = reserved | {e["code"] for e in entries}
    if datacode:
        if not re.match(rf"^{re.escape(prefix)}[0-9A-Z]{{2}}$", datacode):
            return False, (
                f'Datacode "{datacode}" doesn\'t match the {page_display} page\'s '
                f'"{prefix}NN" format.'
            ), {}
        if datacode in used_codes:
            return False, (
                f'Datacode "{datacode}" is already used on the {page_display} page '
                f"(either by another button or reserved for one of its special "
                f"buttons) -- pick a different code or leave it blank to "
                f"auto-assign one."
            ), {}
    else:
        datacode = _next_free_code(page, prefix, used_codes)
        if datacode is None:
            return False, f"No free codes left with prefix {prefix}.", {}  # pragma: no cover

    next_order = max((e["order"] for e in entries), default=0) + 1
    entries.append({"label": label, "code": datacode, "order": next_order})
    return (
        True,
        f'Added "{label}" ({datacode}) to {page_display}.',
        {"page": page_key, "label": label, "code": datacode, "action": "Add"},
    )


def main():
    body = sys.stdin.read()
    fields = parse_issue_body(body)

    with open(DEFECT_TYPES_PATH) as f:
        defect_types = json.load(f)

    ok, message, details = apply_request(defect_types, fields)
    if ok:
        errors = validate(defect_types)
        if errors:
            ok = False
            message = "Validation failed after applying the request: " + "; ".join(errors)

    if not ok:
        print(json.dumps({"status": "rejected", "message": message}))
        return 1

    with open(DEFECT_TYPES_PATH, "w") as f:
        json.dump(defect_types, f, indent=2)
        f.write("\n")

    print(json.dumps({"status": "applied", "message": message, **details}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
