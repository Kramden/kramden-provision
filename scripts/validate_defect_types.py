#!/usr/bin/env python3
"""Validates src/defect_types.json -- the editable defect-type buttons +
tracking-sheet datacodes for src/manualtest.py (see that file's
_merge_defect_types/_page_entries for how it's loaded).

Run directly (`python3 scripts/validate_defect_types.py`), imported from
tests/test_manualtest.py, and run in CI on every PR touching the config
file (.github/workflows/validate-defect-types.yaml) -- including PRs opened
by the defect-type-request workflow, so a bad automated edit never reaches
a mergeable PR either.
"""
import json
import os
import re
import sys

DEFECT_TYPES_PATH = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "..", "src", "defect_types.json"
)


def validate(defect_types):
    """Returns a list of human-readable error strings; empty if valid.
    `defect_types` is the parsed contents of defect_types.json."""
    errors = []
    for page_key, page in defect_types.items():
        if page_key.startswith("_"):
            continue
        prefix = page.get("code_prefix")
        if not prefix:
            errors.append(f'{page_key}: missing "code_prefix"')
            continue
        reserved = set(page.get("reserved_codes", []))
        code_pattern = re.compile(rf"^{re.escape(prefix)}[0-9A-Z]{{2}}$")

        labels_seen = set()
        codes_seen = set()
        orders_seen = set()
        for entry in page.get("types", []):
            label = entry.get("label")
            code = entry.get("code")
            order = entry.get("order")

            if not label:
                errors.append(f"{page_key}: entry with missing/empty label: {entry!r}")
                continue
            if label in labels_seen:
                errors.append(f'{page_key}: duplicate label "{label}"')
            labels_seen.add(label)

            if not code or not code_pattern.match(code):
                errors.append(
                    f'{page_key}: "{label}" has code {code!r}, which doesn\'t '
                    f'match this page\'s prefix "{prefix}" (expected format '
                    f'{prefix}NN)'
                )
            elif code in reserved:
                errors.append(
                    f'{page_key}: "{label}" uses code "{code}", which is '
                    f"reserved for a hardcoded special entry in "
                    f"manualtest.py -- pick a different code"
                )
            elif code in codes_seen:
                errors.append(f'{page_key}: duplicate code "{code}" (label "{label}")')
            else:
                codes_seen.add(code)

            if order is None or not isinstance(order, int):
                errors.append(f'{page_key}: "{label}" has a missing/invalid order')
            elif order in orders_seen:
                errors.append(f'{page_key}: duplicate order {order} (label "{label}")')
            else:
                orders_seen.add(order)

            # sub_buttons/no_sub_buttons (see manualtest.py's
            # _sub_buttons_override) supersede a page's own default
            # sub-picker for this entry, so they're mutually exclusive with
            # each other and with the older no_location/no_keys flags,
            # which only mean something to a page's own default dispatch.
            behavior_flags = [
                flag
                for flag in ("sub_buttons", "no_sub_buttons", "no_location", "no_keys")
                if flag in entry
            ]
            if len(behavior_flags) > 1:
                errors.append(
                    f'{page_key}: "{label}" sets more than one of '
                    f"sub_buttons/no_sub_buttons/no_location/no_keys "
                    f"({', '.join(behavior_flags)}) -- pick at most one"
                )

            if "sub_buttons" in entry:
                sub_buttons = entry["sub_buttons"]
                if (
                    not isinstance(sub_buttons, list)
                    or not sub_buttons
                    or not all(
                        isinstance(b, str) and b.strip() for b in sub_buttons
                    )
                ):
                    errors.append(
                        f'{page_key}: "{label}" has an invalid "sub_buttons" '
                        f"-- must be a non-empty list of non-empty strings"
                    )
                elif len(set(sub_buttons)) != len(sub_buttons):
                    errors.append(
                        f'{page_key}: "{label}" has duplicate entries in '
                        f'"sub_buttons"'
                    )

            if "no_sub_buttons" in entry and not isinstance(
                entry["no_sub_buttons"], bool
            ):
                errors.append(
                    f'{page_key}: "{label}" has a non-boolean "no_sub_buttons"'
                )

    return errors


def main():
    with open(DEFECT_TYPES_PATH) as f:
        defect_types = json.load(f)

    errors = validate(defect_types)
    if errors:
        print(f"{DEFECT_TYPES_PATH} is invalid:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(f"{DEFECT_TYPES_PATH} is valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
