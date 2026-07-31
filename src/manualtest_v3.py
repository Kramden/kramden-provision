import glob
import os
import subprocess
import sys
import threading

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Adw, Gdk, GdkPixbuf, GLib, GObject, Gtk
from utils import Utils

CUSTOM_OPTION = "Custom..."

# Placeholder option lists. Real content to be filled in later — these exist
# only so the dropdowns/checklists have something selectable to preview the
# layout with.
PLACEHOLDER_REASONS = ["Reason option 1", "Reason option 2", "Reason option 3"]

# Fixed Physical Defects defect-type list; a defect's tracking-sheet code
# (PD01, PD02, ...) is just its 1-based position here -- see
# CUSTOM_REASON_CODE_SUFFIX below.
PHYSICAL_DEFECT_TYPES = [
    "Dents",
    "Deep Scratches",
    "Peeling Paint",
    "Cracks",
    "Broken Part",
    "Feet Coming Off/Missing From Device",
]
# Fixed code overrides for defect types whose position in the list above
# doesn't match their tracking-sheet code (see
# PhysicalDefectsPage._defect_code) -- e.g. "Feet Coming Off/Missing From
# Device" is PD08 by convention rather than the PD06 its list position
# would otherwise imply, since PD06/PD07 are reserved.
PHYSICAL_DEFECT_CODES = {
    "Feet Coming Off/Missing From Device": "PD08",
}
# Hinge/feet issues are self-explanatory with no meaningful location to ask
# for.
PHYSICAL_NO_LOCATION_TYPES = {
    "Hinge Broken",
    "Loose Hinge",
    "Feet Coming Off/Missing From Device",
}
# Marked the same way as a screen/touchscreen defect (see SCREEN_SECTIONS).
PHYSICAL_SCREEN_SECTION_TYPES = {"Screen Cracked"}
# Ask which part is affected, then where on that part (same sextant grid as
# SCREEN_SECTIONS below -- see _build_section_picker).
PHYSICAL_PART_LOCATION_TYPES = {"Dents", "Deep Scratches", "Peeling Paint", "Cracks"}
PHYSICAL_AFFECTED_PARTS = [
    "Top of the lid",
    "The Bezel (Around the screen)",
    "Near the keyboard",
    "On the bottom",
    "On one of the sides of the laptop (including the back or front)",
    "One or multiple corners",
]
# Ask which port type, reusing the same location picker as the dedicated
# USB-A/USB-C pages (see UsbPortLocationMixin), plus its own optional
# per-location port-# field. Only USB-A/USB-C trigger the
# suppress-on-matching-page logic below since those are the only port types
# with their own dedicated test page; "Other" additionally asks for a
# free-text description of the port.
PHYSICAL_PORT_DAMAGE_TYPES = {"Port Damaged"}
PHYSICAL_PORT_TYPES = [
    "USB-A",
    "USB-C",
    "Ethernet",
    "HDMI",
    "DP",
    "Charging Port",
    "Other",
]

# "Broken Part" hands off Keys/Screen/USB-A/USB-C sub-reports to their own
# dedicated test page (its own datacode) instead of Physical Defects --
# see PhysicalDefectsPage._build_broken_part_picker/_delegate_broken_part.
# "Hinge" and "Other" have no dedicated page and stay Physical-Defects-coded.
PHYSICAL_BROKEN_PART_TYPES = {"Broken Part"}
BROKEN_PART_KEYS_TYPE = "Keys have physical damage"
BROKEN_PART_PORT_TYPE = "Port physically broken"
BROKEN_PART_HINGE_TYPE = "Hinge"
BROKEN_PART_SCREEN_TYPE = "Screen"
BROKEN_PART_OTHER_TYPE = "Other"
BROKEN_PART_SUB_TYPES = [
    BROKEN_PART_KEYS_TYPE,
    BROKEN_PART_PORT_TYPE,
    BROKEN_PART_HINGE_TYPE,
    BROKEN_PART_SCREEN_TYPE,
    BROKEN_PART_OTHER_TYPE,
]

PLACEHOLDER_INSTRUCTIONS = "(Instructions for this test will go here)"

USB_A_DEFECT_TYPES = [
    "USB Port is finicky, connection cuts in and out",
    "USB Port does not work",
    "USB Port is physically damage",
]
# Must match an entry in USB_A_DEFECT_TYPES exactly -- when Physical Defects'
# "Port Damaged" is reported against a USB-A port, that same reason is
# suppressed on UsbAPage's own dropdown so it isn't double reported (see
# PhysicalDefectsPage._on_port_damage_type_changed).
USB_A_PORT_DAMAGE_REASON = "USB Port is physically damage"
# Tracking-sheet codes for USB-A reasons -- "finicky" and "does not work"
# both just mean the port doesn't work right, so they share the default
# UA01 code; only "physically damage" gets its own (UA02). Same "several
# reasons, one code" pattern as KeyboardPage._reason_code.
USB_A_REASON_CODES = {
    "USB Port is finicky, connection cuts in and out": "UA01",
    "USB Port does not work": "UA01",
    "USB Port is physically damage": "UA02",
}

USB_C_DEFECT_TYPES = [
    "USB-C Port is finicky, connection cuts in and out",
    "USB-C Port does not work",
    "USB-C Port is physically damage",
    "USB-C Port works one way, but when flipping it upside-down, it doesn't work",
]
# Must match an entry in USB_C_DEFECT_TYPES exactly -- see
# USB_A_PORT_DAMAGE_REASON above, same suppression but for UsbCPage.
USB_C_PORT_DAMAGE_REASON = "USB-C Port is physically damage"
# See USB_A_REASON_CODES above -- "finicky"/"does not work" share UC01, and
# the upside-down failure (unique to USB-C) gets its own UC03.
USB_C_REASON_CODES = {
    "USB-C Port is finicky, connection cuts in and out": "UC01",
    "USB-C Port does not work": "UC01",
    "USB-C Port is physically damage": "UC02",
    "USB-C Port works one way, but when flipping it upside-down, it doesn't work": "UC03",
}

USB_PORT_LOCATIONS = ["Left Side", "Right Side", "Back"]

# "Audio" must be an exact defect-type option (not free text) so the tracking
# sheet can key off it directly to fill in the "Sound:" field -- see
# TogglePage.has_reason() and SpecCompleteV3._on_tracking_clicked.
BROWSER_DEFECT_TYPES = ["Video", "Audio"]

WIFI_DEFECT_TYPES = [
    "Wi-Fi doesn't work",
    "Wi-Fi is extremely slow",
    "No WiFi device detected",
]

TOUCHPAD_DEFECT_TYPES = [
    "Touchpad does not work at all",
    "A problem with left or right click",
    "Touchpad looks as if it is bulging out",
    "Something is wrong with how the cursor moves",
    "Part of the touchpad doesn't work",
]

# "Part of the touchpad doesn't work" pops up the same 6-section grid used
# for screen/touchscreen locations (see SCREEN_SECTIONS) so the tech can
# mark which part is dead -- see TouchpadPage.build_reason_locations. It
# gets a fixed TP09 code (see TOUCHPAD_REASON_CODES/TouchpadPage._reason_code)
# rather than the position-based TP05 its slot in the list above would
# otherwise imply, since TP05/TP06 are already taken by the cursor
# sub-reasons (see TOUCHPAD_CURSOR_CODES).
TOUCHPAD_PARTIAL_REASON = "Part of the touchpad doesn't work"
TOUCHPAD_REASON_CODES = {
    TOUCHPAD_PARTIAL_REASON: "TP09",
}

# "A problem with left or right click" expands into "Left click"/"Right
# click"/"Touchpad click" instead of the generic touchpad-location section
# picker -- see TouchpadPage._build_click_picker. "Left click"/"Right
# click" each get their own independent Top/Bottom location grid (a left-
# click issue on Top and a right-click issue on Bottom aren't the same
# report -- same "each gets its own grid" pattern as
# PhysicalDefectsPage._build_part_location_picker); "Touchpad click" (the
# physical push-to-click mechanism) has no location to narrow down. Unlike
# every other reason here, this reason itself carries no single code --
# each side reports under its own fixed code regardless of Top vs Bottom
# (see TOUCHPAD_CLICK_SIDE_CODES/TouchpadPage._touchpad_click_notes).
TOUCHPAD_CLICK_REASON = "A problem with left or right click"
TOUCHPAD_CLICK_LOCATION_OPTIONS = ["Top", "Bottom"]
TOUCHPAD_CLICK_SIDE_OPTIONS = ["Left click", "Right click", "Touchpad click"]
# "Touchpad click" has no Top/Bottom location popup -- see
# TouchpadPage._build_click_picker/_touchpad_click_notes.
TOUCHPAD_CLICK_SIDES_WITH_LOCATION = {"Left click", "Right click"}
TOUCHPAD_CLICK_SIDE_CODES = {
    "Left click": "TP07",
    "Right click": "TP08",
    "Touchpad click": "TP02",
}
TOUCHPAD_CLICK_CODE_LABELS = {
    "TP07": "Left click broken",
    "TP08": "Right click broken",
    "TP02": "Touchpad click broken",
}

# "Something is wrong with how the cursor moves" expands into this
# pick-list -- like the click reason above, it carries no single code of
# its own; each selected behavior reports under its own fixed code
# instead (see TOUCHPAD_CURSOR_CODES/TouchpadPage._touchpad_cursor_notes).
TOUCHPAD_CURSOR_REASON = "Something is wrong with how the cursor moves"
TOUCHPAD_CURSOR_CODES = {
    "Cursor drags slowly": "TP04",
    "Cursor moves on its own": "TP05",
    "Cursor is too sensitive, it moves too fast": "TP06",
}
TOUCHPAD_CURSOR_CODE_LABELS = {
    "TP04": "Cursor drags slowly",
    "TP05": "Cursor moves on its own",
    "TP06": "Touchpad too sensitive",
}
TOUCHPAD_CURSOR_OPTIONS = list(TOUCHPAD_CURSOR_CODES)

# Tracking-sheet note text for the touchpad reasons that don't expand into
# a sub-picker -- see TouchpadPage._touchpad_reason_notes. Edit the values
# here to change the wording that ends up on the tracking sheet (the code,
# e.g. "TP01", is prepended automatically from reason_options position --
# see CUSTOM_REASON_CODE_SUFFIX comment below).
TOUCHPAD_REASON_NOTES = {
    "Touchpad does not work at all": "Touchpad broken",
    "Touchpad looks as if it is bulging out": "Touchpad bulging",
    TOUCHPAD_PARTIAL_REASON: "Part of touchpad not working",
}

SCREEN_DEFECT_TYPES = [
    "Light Spots",
    "Bruises",
    "Deep Scratches",
    "Dead Pixels",
    "Keyboard imprints on the screen",
    "Screen glitches out",
    "Backlight failing",
    "Screen broken",
    "Screen cracked",
]
# Must match an entry in SCREEN_DEFECT_TYPES exactly -- Physical Defects'
# "Broken Part" -> "Screen" delegates to this same no-location reason
# instead of recording its own Physical-Defects note (see
# PhysicalDefectsPage._delegate_broken_part).
SCREEN_BROKEN_REASON = "Screen broken"

WEBCAM_DEFECT_TYPES = [
    "The webcam does not work at all",
    "The webcam reports a solid black screen",
    "There are lines going across or down the webcam output",
    "The Image is blurry",
    "The video is very choppy with a low frame rate",
    "Everything is monochrome and flashing",
    "No webcam device found",
]

# Tracking-sheet note text used when WebcamPage auto-detects no usable
# webcam is present -- see WebcamPage.__init__/get_notes_entries.
WEBCAM_NO_DEVICE_NOTE = "No webcam present"
WEBCAM_IR_ONLY_NOTE = "IR camera only, no webcam present"

TOUCHSCREEN_DEFECT_TYPES = [
    "Areas of the touchscreen aren't working",
    "Where I touch is not where it registers",
    "The touchscreen doesn't work at all",
    "The cursor freaks out when I touch the screen",
]

# The keyboard's top-level failure-reason buttons. "Physical damage" isn't
# one of the 9 fixed data codes below -- picking it expands into its own
# pick-list (PHYSICAL_DAMAGE_CATEGORIES) whose individual categories carry
# the real codes (KB03/KB04/KB05) -- see KeyboardPage.build_reason_locations,
# KEYBOARD_REASON_CODES, and PHYSICAL_DAMAGE_CATEGORY_CODES below.
KEYBOARD_DEFECT_TYPES = [
    "The whole keyboard does not work",
    "Certain keys do not work",
    "Physical damage",
    "Certain keys need extra pressure or massaging to work",
    "It is an international keyboard",
    "Certain keys stick",
    "Keys report the incorrect keys when typing",
    "Certain keys are scratched",
]

# Tracking-sheet/failure-summary data codes for every keyboard reason
# except "Physical damage" (see PHYSICAL_DAMAGE_CATEGORY_CODES for that
# one) -- fixed explicitly here, rather than derived from each reason's
# position in KEYBOARD_DEFECT_TYPES, since "Physical damage" occupies one
# button but represents 3 codes (KB03/KB04/KB05), which would throw off
# position-based numbering -- see KeyboardPage._reason_code.
KEYBOARD_REASON_CODES = {
    "The whole keyboard does not work": "KB01",
    "Certain keys do not work": "KB02",
    "Certain keys need extra pressure or massaging to work": "KB06",
    "It is an international keyboard": "KB07",
    "Certain keys stick": "KB08",
    "Keys report the incorrect keys when typing": "KB09",
}

# These two reasons apply to the whole keyboard with nothing to point at --
# see KeyboardPage.build_reason_locations -- so they get no keyboard popup
# at all, just added to the list like PhysicalDefectsPage/TouchpadPage's
# no-location reasons. Every other reason above (and every "Physical
# damage" category below) pops up the keyboard picker so the tech can mark
# which specific keys are affected.
KEYBOARD_NO_KEYS_REASONS = {
    "The whole keyboard does not work",
    "It is an international keyboard",
}

# "Physical damage" expands into this pick-list instead of a single
# keyboard popup -- see KeyboardPage.build_reason_locations. Each selected
# category gets its own "Select Keys" popup. "Keys are scratched" has no
# code of its own -- per user direction it's reported under the same KB04
# code as "Keys are cracked" (see KeyboardPage._physical_damage_notes,
# which merges their key sets together on the tracking sheet).
KEYBOARD_PHYSICAL_DAMAGE_REASON = "Physical damage"
PHYSICAL_DAMAGE_CATEGORIES = [
    "Keys are worn through",
    "Keys are cracked",
    "Keys are scratched",
    "Keys are missing",
]
PHYSICAL_DAMAGE_CATEGORY_CODES = {
    "Keys are worn through": "KB05",
    "Keys are cracked": "KB04",
    "Keys are scratched": "KB10",
    "Keys are missing": "KB03",
}
PHYSICAL_DAMAGE_CODE_LABELS = {
    "KB05": "Keys worn through",
    "KB04": "Keys cracked",
    "KB03": "Keys missing",
}

SOUND_DEFECT_TYPES = [
    "Sound does not work",
    "Sound is crunchy",
    "Sound is too quiet even with volume all the way up",
    "Dummy Output/No Audio Device Detected",
]

# Simplified keyboard layout used by the keyboard failure-location picker.
KEYBOARD_LAYOUT = [
    ["~", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "=", "Backspace"],
    ["Tab", "Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "[", "]", "\\"],
    ["CapsLock", "A", "S", "D", "F", "G", "H", "J", "K", "L", ";", "'", "Enter"],
    ["LeftShift", "Z", "X", "C", "V", "B", "N", "M", ",", ".", "/", "RightShift"],
    ["Fn", "LeftCtrl", "LeftAlt", "Space", "RightAlt", "RightCtrl"],
]

ALL_KEYBOARD_KEYS = [key for row in KEYBOARD_LAYOUT for key in row]
ENTIRE_KEYBOARD_MARKER = "__ENTIRE_KEYBOARD__"

# Tracking sheet "Notes & Cosmetics" entries report each failure reason as a
# short parseable code (e.g. "KB02: Key(s) Sticking (F, G)") instead of a full
# sentence. The number is just 1-based position of that reason string in the
# page's reason_options list (KEYBOARD_DEFECT_TYPES, TOUCHPAD_DEFECT_TYPES,
# etc.) or PHYSICAL_DEFECT_TYPES for Physical Defects -- so to add a new
# code, add a new entry to that list (it gets the next number for free); to
# change a code's wording, edit the string in place. A reason typed in via
# the "Custom..." free-text box has no fixed slot, so it falls back to
# "<PREFIX>O" instead of a number.
CUSTOM_REASON_CODE_SUFFIX = "OT"

# The 6 regions of a laptop screen (3 across the top half, 3 across the
# bottom half) used by the Screen/Touchscreen/Screen-Cracked defect-location
# picker: the tech clicks whichever zones the issue appears in instead of
# hand-drawing a mark, e.g. "Light Spots (Upper Right, Lower Middle)".
SCREEN_SECTIONS = [
    "Upper Left",
    "Upper Middle",
    "Upper Right",
    "Lower Left",
    "Lower Middle",
    "Lower Right",
]


def _toggle_button_css(button):
    if button.get_active():
        button.add_css_class("toggle-fail-active")
    else:
        button.remove_css_class("toggle-fail-active")


# Wording for the Yes/No question every page leads with (see TogglePage and
# PhysicalDefectsPage below). To reword the question for every page at
# once, edit the template here; to change what a single page calls itself
# in that question, pass topic= to TogglePage.__init__ (or edit the
# PhysicalDefectsPage topic below) instead of touching this template.
DEFECT_QUESTION_TEMPLATE = "Did the {topic} work as expected? (Select all that apply)"


def _scroll_to_bottom(scrolled_window):
    """Scroll `scrolled_window` all the way down once the layout settles, so
    content a button click just revealed (a panel, a newly-added entry row,
    ...) is visible without the user having to remember to scroll for it.
    Called twice: one idle pass catches instant layout changes (e.g. a
    ListBox row append), and a delayed pass catches revealer/expander
    animations, which take ~250ms to finish growing."""

    def _do_scroll():
        adjustment = scrolled_window.get_vadjustment()
        if adjustment is not None:
            adjustment.set_value(adjustment.get_upper() - adjustment.get_page_size())
        return GLib.SOURCE_REMOVE

    GLib.idle_add(_do_scroll)
    GLib.timeout_add(260, _do_scroll)


def _build_section_row(
    title, options, select_all_label=None, columns=3, on_change=None
):
    """Build a plain Gtk.ListBoxRow holding a title, an optional "select
    all" button, and a grid of multi-select toggle buttons for `options` --
    the embedded, no-popup version of the old ScreenSectionDialog, reused
    for every "click the affected location(s)" picker in this file (screen,
    touchscreen, touchpad, physical-defect locations, ...). `on_change` is
    called with the list of currently active options (in `options` order)
    every time a button is toggled."""
    row_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    row_box.set_margin_top(8)
    row_box.set_margin_bottom(8)
    row_box.set_margin_start(12)
    row_box.set_margin_end(12)

    title_label = Gtk.Label(label=title)
    title_label.set_halign(Gtk.Align.START)
    title_label.add_css_class("dim-label")
    row_box.append(title_label)

    buttons = {}

    def _on_toggle(button, option):
        _toggle_button_css(button)
        if on_change:
            on_change([opt for opt in options if buttons[opt].get_active()])

    if select_all_label:

        def _on_select_all(button):
            for b in buttons.values():
                if not b.get_active():
                    b.set_active(True)

        select_all_button = Gtk.Button(label=select_all_label)
        select_all_button.set_halign(Gtk.Align.START)
        select_all_button.connect("clicked", _on_select_all)
        row_box.append(select_all_button)

    grid = Gtk.Grid()
    grid.set_row_spacing(4)
    grid.set_column_spacing(4)
    for index, option in enumerate(options):
        row, col = divmod(index, columns)
        button = Gtk.ToggleButton(label=option)
        button.set_size_request(90, 40)
        button.connect("toggled", _on_toggle, option)
        grid.attach(button, col, row, 1, 1)
        buttons[option] = button
    row_box.append(grid)

    list_row = Gtk.ListBoxRow()
    list_row.set_selectable(False)
    list_row.set_activatable(False)
    list_row.set_child(row_box)
    return list_row


def _build_toggle_button_grid(title, options, on_toggle, columns=3):
    """Build a plain Gtk.Box holding a title and a grid of Gtk.ToggleButton
    -- one per entry in `options` -- for picking item(s) from a fixed list
    by clicking them directly instead of choosing one in a dropdown and
    pressing a separate "Add" button. A button lights up (see
    _toggle_button_css) when active; its toggled state IS the membership
    state, so toggling it back off is how an already-picked item gets
    un-picked -- no separate "Remove" affordance needed. `on_toggle(button,
    option)` fires on every toggle. Returns (container_box, {option:
    button}) so the caller can look up a button later (see
    TogglePage.suppress_reason_option)."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

    if title:
        title_label = Gtk.Label(label=title)
        title_label.set_halign(Gtk.Align.START)
        title_label.add_css_class("sub-question-label")
        box.append(title_label)

    grid = Gtk.Grid()
    grid.set_row_spacing(4)
    grid.set_column_spacing(4)
    buttons = {}
    for index, option in enumerate(options):
        row, col = divmod(index, columns)
        button = Gtk.ToggleButton(label=option)
        button.set_size_request(90, 40)
        button.connect("toggled", on_toggle, option)
        grid.attach(button, col, row, 1, 1)
        buttons[option] = button
    box.append(grid)
    return box, buttons


def _build_section_picker(
    owner,
    entry_row,
    data=None,
    options=None,
    title="Location",
    select_all_label=None,
    fullscreen=False,
):
    """Embed a "click the affected section(s)" picker into `entry_row` and
    keep `data["selected"]` in sync as the tech makes a selection. Shared by
    ScreenPage, TouchscreenPage, TouchpadPage, the generic default location
    picker, and Physical Defects' "Screen Cracked"/dents-scratches-etc
    pickers. `owner` just needs check_status(), called once a selection
    changes.

    `fullscreen=True` is for the call sites that are genuinely about
    pointing at the physical screen (ScreenSectionMixin, Physical Defects'
    "Screen Cracked") -- there the picker launches a fullscreen
    click-through window (screen_section_picker_runner.py) over the 6
    screen sections (see SCREEN_SECTIONS) instead of a small button grid.
    Everything else (touchpad zones, port locations, the generic
    default/custom-defect fallback) isn't a screen location, so it keeps
    the original embedded button-grid picker regardless of `options`."""
    options = options or SCREEN_SECTIONS
    if data is None:
        data = {"type": "sections", "selected": []}

    def _on_change(selected):
        data["selected"] = selected
        owner.check_status()

    if fullscreen:
        list_row = _build_fullscreen_section_row(
            title, select_all_label, data, on_change=_on_change
        )
    else:
        list_row = _build_section_row(
            title, options, select_all_label=select_all_label, on_change=_on_change
        )
    entry_row.add_row(list_row)
    return data


def _build_fullscreen_section_row(title, select_all_label, data, on_change=None):
    """Build the Gtk.ListBoxRow used by the default (screen-section)
    _build_section_picker case: a title, a status label showing the
    currently selected section(s), and a button that launches the
    fullscreen click-through picker in screen_section_picker_runner.py.
    `on_change` is called with the list of currently selected sections (in
    SCREEN_SECTIONS order) once the picker window closes."""
    row_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    row_box.set_margin_top(8)
    row_box.set_margin_bottom(8)
    row_box.set_margin_start(12)
    row_box.set_margin_end(12)

    title_label = Gtk.Label(label=title)
    title_label.set_halign(Gtk.Align.START)
    title_label.add_css_class("dim-label")
    row_box.append(title_label)

    status_label = Gtk.Label(label="No section selected yet.")
    status_label.set_halign(Gtk.Align.START)
    status_label.set_wrap(True)
    row_box.append(status_label)

    def _update_status():
        selected = data.get("selected") or []
        status_label.set_label(
            ", ".join(selected) if selected else "No section selected yet."
        )

    _update_status()

    launch_button = Gtk.Button(label="Mark Location on Screen")
    launch_button.set_halign(Gtk.Align.START)

    def _on_launch_clicked(button):
        button.set_sensitive(False)
        runner = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            "screen_section_picker_runner.py",
        )
        cmd = [sys.executable, runner, "--heading", title]
        if select_all_label:
            cmd += ["--select-all-label", select_all_label]
        initial = data.get("selected") or []
        if initial:
            cmd += ["--initial", ",".join(initial)]

        def _run():
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=600
                )
                if result.returncode != 0:
                    print(f"Section picker subprocess exited rc={result.returncode}")
                    if result.stderr:
                        print(result.stderr)
                    selected = data.get("selected") or []
                else:
                    line = result.stdout.strip()
                    selected = [s for s in line.split(",") if s] if line else []
            except Exception as exc:
                print(f"Section picker subprocess error: {exc}")
                selected = data.get("selected") or []
            GLib.idle_add(_on_picker_done, selected, button)

        threading.Thread(target=_run, daemon=True).start()

    def _on_picker_done(selected, button):
        data["selected"] = selected
        _update_status()
        if on_change:
            on_change(selected)
        button.set_sensitive(True)
        return False

    launch_button.connect("clicked", _on_launch_clicked)
    row_box.append(launch_button)

    # Launch the picker right away, as soon as the reason is added, instead
    # of leaving the tech to remember to press the button -- same "ask
    # immediately" pattern as KeyPickerDialog/_build_physical_damage_picker.
    # The button stays so the picker can still be reopened to redo/correct
    # the selection.
    GLib.idle_add(_on_launch_clicked, launch_button)

    list_row = Gtk.ListBoxRow()
    list_row.set_selectable(False)
    list_row.set_activatable(False)
    list_row.set_child(row_box)
    return list_row


def _rebuild_port_number_rows(
    owner, ports_box, port_type, selected_locations, port_numbers
):
    """Rebuild the per-location "Port #" entry rows inside `ports_box` for
    `port_type`'s currently `selected_locations` -- shared by Physical
    Defects' "Port Damaged" and "Broken Part" -> "Port Physically Broken"
    pickers (see PhysicalDefectsPage._build_port_damage_picker/
    _build_broken_part_port_block). `owner` just needs
    _on_port_number_insert_text()."""
    child = ports_box.get_first_child()
    while child is not None:
        next_child = child.get_next_sibling()
        ports_box.remove(child)
        child = next_child
    for location in selected_locations:
        port_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        label = Gtk.Label(label=f"{location} Port #")
        label.set_halign(Gtk.Align.START)
        label.set_hexpand(True)
        num_entry = Gtk.Entry()
        num_entry.set_max_length(1)
        num_entry.set_placeholder_text("optional")
        num_entry.set_tooltip_text(
            "Only needed if there are multiple of this type on this side"
        )
        num_entry.set_input_purpose(Gtk.InputPurpose.DIGITS)
        num_entry.set_size_request(48, -1)
        num_entry.set_text(port_numbers.get(port_type, {}).get(location, ""))
        num_entry.connect("insert-text", owner._on_port_number_insert_text)

        def _on_num_changed(entry, location=location):
            port_numbers.setdefault(port_type, {})[location] = entry.get_text().strip()

        num_entry.connect("changed", _on_num_changed)
        port_row.append(label)
        port_row.append(num_entry)
        ports_box.append(port_row)


def _build_note_row(text):
    """Plain, non-interactive Gtk.ListBoxRow holding a wrapped label -- for
    informational notes embedded in an expander row alongside (or instead
    of) a location picker (see WebcamPage.build_reason_locations)."""
    label = Gtk.Label(label=text)
    label.set_xalign(0)
    label.set_wrap(True)
    label.add_css_class("dim-label")
    label.set_margin_top(8)
    label.set_margin_bottom(8)
    label.set_margin_start(12)
    label.set_margin_end(12)
    row = Gtk.ListBoxRow()
    row.set_selectable(False)
    row.set_activatable(False)
    row.set_child(label)
    return row


def _set_status(label, text, is_error=False, auto_clear_ms=None):
    label.set_label(text)
    if is_error:
        label.add_css_class("text-error")
    elif label.has_css_class("text-error"):
        label.remove_css_class("text-error")
    if auto_clear_ms:
        GLib.timeout_add(auto_clear_ms, _clear_status_if_unchanged, label, text)


def _clear_status_if_unchanged(label, expected_text):
    # Only clear if nothing else has updated the label in the meantime.
    if label.get_label() == expected_text:
        label.set_label("")
    return False


# TEMPORARY: stand-in animation shown on every testing page until each page
# gets its own real inspection-step gif. Remove this and its call sites once
# actual per-page animations exist.
GIF_PLACEHOLDER_PATH = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "inspection_animation_placeholder.gif"
)


def _build_gif_placeholder_widget():
    try:
        animation = GdkPixbuf.PixbufAnimation.new_from_file(GIF_PLACEHOLDER_PATH)
    except GLib.Error as e:
        print(f"_build_gif_placeholder_widget: could not load placeholder gif: {e}")
        return None

    picture = Gtk.Picture()
    picture.set_can_shrink(True)
    picture.set_content_fit(Gtk.ContentFit.CONTAIN)
    picture.set_size_request(-1, 200)

    it = animation.get_iter(None)

    def _advance():
        it.advance(None)
        picture.set_paintable(Gdk.Texture.new_for_pixbuf(it.get_pixbuf()))
        delay = it.get_delay_time()
        GLib.timeout_add(delay if delay > 0 else 100, _advance)
        return False

    picture.set_paintable(Gdk.Texture.new_for_pixbuf(it.get_pixbuf()))
    GLib.timeout_add(it.get_delay_time() if it.get_delay_time() > 0 else 100, _advance)

    return picture


class KeyPickerDialog(Gtk.Window):
    """Small popup showing a simplified keyboard layout so the user can click
    the specific keys that failed, instead of picking from a generic preset
    location list."""

    def __init__(self, parent, initial_selection=None):
        super().__init__(transient_for=parent, modal=True, title="Select Affected Keys")
        self.set_default_size(480, 260)
        self.selected_keys = set(initial_selection or [])
        self.on_done_callback = None

        header = Gtk.HeaderBar()
        header.set_show_title_buttons(False)
        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", lambda b: self.close())
        done_button = Gtk.Button(label="Done")
        done_button.add_css_class("suggested-action")
        done_button.connect("clicked", self._on_done)
        header.pack_start(cancel_button)
        header.pack_end(done_button)
        self.set_titlebar(header)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)

        instructions = Gtk.Label(
            label="Click each key that failed to register or typed incorrectly."
        )
        instructions.set_wrap(True)
        content.append(instructions)

        select_all_button = Gtk.Button(label="Entire Keyboard Affected")
        select_all_button.set_halign(Gtk.Align.START)
        select_all_button.connect("clicked", self._on_select_all)
        content.append(select_all_button)

        self._buttons = {}
        for row_keys in KEYBOARD_LAYOUT:
            row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            row_box.set_halign(Gtk.Align.CENTER)
            for key in row_keys:
                key_button = Gtk.ToggleButton(label=key)
                if key == "Space":
                    width = 140
                elif len(key) > 5:
                    width = 90
                elif len(key) > 2:
                    width = 60
                else:
                    width = 36
                key_button.set_size_request(width, 36)
                key_button.set_active(key in self.selected_keys)
                if key_button.get_active():
                    key_button.add_css_class("toggle-fail-active")
                key_button.connect("toggled", self._on_key_toggled, key)
                row_box.append(key_button)
                self._buttons[key] = key_button
            content.append(row_box)

        self.set_child(content)

    def _on_select_all(self, button):
        for key_button in self._buttons.values():
            if not key_button.get_active():
                key_button.set_active(True)

    def _on_key_toggled(self, button, key):
        if button.get_active():
            self.selected_keys.add(key)
            button.add_css_class("toggle-fail-active")
        else:
            self.selected_keys.discard(key)
            button.remove_css_class("toggle-fail-active")

    def _on_done(self, button):
        if self.on_done_callback:
            if self._buttons and len(self.selected_keys) == len(self._buttons):
                self.on_done_callback(ENTIRE_KEYBOARD_MARKER)
            else:
                self.on_done_callback(sorted(self.selected_keys))
        self.close()


class _RowAdderBox:
    """Minimal duck-typed stand-in for Adw.ExpanderRow.add_row(), so a
    TogglePage's build_reason_locations()-style picker (which just calls
    entry_row.add_row(widget)) can be pointed at a plain Gtk.Box instead of
    that page's own expander row -- used by Physical Defects' "Broken
    Part" flow to embed another page's reason-detail picker directly
    inline instead of navigating there (see
    PhysicalDefectsPage._build_keys_physical_damage_block/
    _build_port_physical_damage_block)."""

    def __init__(self, box):
        self._box = box

    def add_row(self, widget):
        self._box.append(widget)


class TogglePage(Adw.Bin):
    """Base page: instructions placeholder, an optional subclass-provided test
    action, and a Yes/No "any defects?" toggle. When "Yes" is active, the
    user can add one or more failure reasons, each with its own set of
    affected locations.
    """

    def __init__(
        self,
        key,
        page_title,
        row_title,
        pass_label="Yes",
        fail_label="No",
        reason_options=None,
        instructions=PLACEHOLDER_INSTRUCTIONS,
        code_prefix=None,
        topic=None,
    ):
        super().__init__()
        self.key = key
        self.title = page_title
        self.skip = False
        self.passed = None
        self.state = None
        # Set externally by spec_v3.py so the wizard's Next button can
        # refresh (light up/dim, re-check completeness) the moment this
        # page's pass/fail or reason details change, not just on navigation.
        self.on_status_changed = None
        self._reason_entries = {}
        self.reason_options = reason_options or PLACEHOLDER_REASONS
        # Reasons temporarily hidden from the dropdown because another page
        # already reported them (see suppress_reason_option/
        # restore_reason_option, used by PhysicalDefectsPage's port-damage
        # picker).
        self._suppressed_reasons = set()
        # See CUSTOM_REASON_CODE_SUFFIX above for the tracking-sheet code
        # scheme this drives (e.g. "KB02: ...").
        self.code_prefix = code_prefix
        # What this page calls itself in the "Are there any {topic} defects
        # ..." question below -- defaults to row_title, but a subclass can
        # pass its own (see WiFiPage, BrowserPage, UsbAPage/UsbCPage) when
        # row_title doesn't read naturally in that sentence.
        self.topic = topic or row_title

        self.set_margin_top(24)
        self.set_margin_bottom(24)
        self.set_margin_start(24)
        self.set_margin_end(24)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)

        header = Gtk.Label(label=row_title)
        header.add_css_class("title-3")
        header.set_halign(Gtk.Align.START)
        vbox.append(header)

        # Instructions, specific to this page
        instructions_label = Gtk.Label(label=instructions)
        instructions_label.set_wrap(True)
        instructions_label.set_justify(Gtk.Justification.CENTER)
        instructions_label.set_halign(Gtk.Align.CENTER)
        instructions_label.add_css_class("instructions-label")
        vbox.append(instructions_label)

        # TEMPORARY placeholder animation -- see _build_gif_placeholder_widget.
        gif_placeholder = _build_gif_placeholder_widget()
        if gif_placeholder is not None:
            vbox.append(gif_placeholder)

        # Hook for subclasses to add a launcher button, typing box, etc.
        self.action_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.append(self.action_box)
        self.build_action(self.action_box)

        # Yes/No "any defects?" toggle
        result_group = Adw.PreferencesGroup(title="Result")
        toggle_row = Adw.ActionRow()
        toggle_row.set_title(DEFECT_QUESTION_TEMPLATE.format(topic=self.topic))

        toggle_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        toggle_box.add_css_class("linked")
        self.pass_button = Gtk.ToggleButton(label=pass_label)
        self.fail_button = Gtk.ToggleButton(label=fail_label)
        self.pass_button.set_valign(Gtk.Align.CENTER)
        self.fail_button.set_valign(Gtk.Align.CENTER)
        self.pass_button.connect("toggled", self._on_pass_toggled)
        self.fail_button.connect("toggled", self._on_fail_toggled)
        toggle_box.append(self.pass_button)
        toggle_box.append(self.fail_button)
        toggle_row.add_suffix(toggle_box)
        result_group.add(toggle_row)
        vbox.append(result_group)

        self.pass_warning_label = Gtk.Label(label="")
        self.pass_warning_label.set_xalign(0)
        self.pass_warning_label.set_wrap(True)
        self.pass_warning_label.add_css_class("text-error")
        self.pass_warning_label.set_visible(False)
        vbox.append(self.pass_warning_label)

        # Failure reasons, revealed only when "Yes" is selected.
        # Multiple reasons can be added, each with its own location detail.
        self.reason_revealer = Gtk.Revealer()
        self.reason_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)

        reasons_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        reason_buttons_box, self._reason_buttons = _build_toggle_button_grid(
            "What about it did not work?",
            self.reason_options + [CUSTOM_OPTION],
            self._on_reason_button_toggled,
        )
        reasons_content.append(reason_buttons_box)

        # Free-text entry, revealed only when "Custom..." is clicked above
        self.custom_reason_revealer = Gtk.Revealer()
        self.custom_reason_revealer.set_transition_type(
            Gtk.RevealerTransitionType.SLIDE_DOWN
        )
        custom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        custom_box.set_margin_start(12)
        custom_box.set_margin_end(12)
        custom_label = Gtk.Label(label="What isn't working?")
        self.custom_reason_entry = Gtk.Entry()
        self.custom_reason_entry.set_hexpand(True)
        self.custom_reason_entry.connect("activate", self._on_add_custom_reason_clicked)
        custom_add_button = Gtk.Button(label="Add")
        custom_add_button.connect("clicked", self._on_add_custom_reason_clicked)
        custom_box.append(custom_label)
        custom_box.append(self.custom_reason_entry)
        custom_box.append(custom_add_button)
        self.custom_reason_revealer.set_child(custom_box)
        self.custom_reason_revealer.set_reveal_child(False)
        reasons_content.append(self.custom_reason_revealer)

        self.reasons_list_box = Gtk.ListBox()
        self.reasons_list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.reasons_list_box.add_css_class("boxed-list")
        self.reasons_list_box.set_valign(Gtk.Align.START)
        reasons_content.append(self.reasons_list_box)

        self.reason_revealer.set_child(reasons_content)
        self.reason_revealer.set_reveal_child(False)
        vbox.append(self.reason_revealer)

        vbox.set_vexpand(True)
        vbox.set_hexpand(True)
        vbox.set_valign(Gtk.Align.START)

        self.scrolled = Gtk.ScrolledWindow()
        # Horizontal scrolling (rather than NEVER) keeps any unexpectedly
        # wide content -- e.g. a long button grid -- from forcing the whole
        # window wider than the screen; it scrolls instead of pushing the
        # window's minimum size out.
        self.scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.scrolled.set_vexpand(True)
        self.scrolled.set_hexpand(True)
        self.scrolled.set_child(vbox)
        self.set_child(self.scrolled)

    def build_action(self, box):
        """Override in subclasses to add page-specific test controls."""
        pass

    def build_reason_locations(self, entry_row, reason):
        """Override in subclasses to replace the default section picker
        with a custom one (see KeyboardPage, UsbPortLocationMixin), or to
        skip location entirely for reasons where it doesn't apply (see
        BrowserPage, WebcamPage)."""
        title = "Location" if reason in self.reason_options else "Location (optional)"
        return _build_section_picker(
            self, entry_row, title=title, select_all_label="Select All"
        )

    def _can_mark_no_issues(self):
        """Override in subclasses to require some condition (e.g. an actual
        test being run) before "No" can be selected."""
        return True

    def _pass_blocked_message(self):
        """Override alongside _can_mark_no_issues to explain why the button
        was blocked."""
        return "Please perform the test before marking it as having no issues."

    def _on_pass_toggled(self, button):
        if button.get_active():
            if not self._can_mark_no_issues():
                button.set_active(False)
                _set_status(
                    self.pass_warning_label, self._pass_blocked_message(), is_error=True
                )
                self.pass_warning_label.set_visible(True)
                return
            self.fail_button.set_active(False)
            button.add_css_class("toggle-pass-active")
            self.reason_revealer.set_reveal_child(False)
            self.pass_warning_label.set_visible(False)
            self.passed = True
            self.check_status()
        else:
            button.remove_css_class("toggle-pass-active")
            if not self.fail_button.get_active():
                # Neither button is selected anymore -- back to untested.
                self.passed = None
                self.check_status()

    def _on_fail_toggled(self, button):
        if button.get_active():
            self.pass_button.set_active(False)
            button.add_css_class("toggle-fail-active")
            self.reason_revealer.set_reveal_child(True)
            self.pass_warning_label.set_visible(False)
            self.passed = False
            self.check_status()
            _scroll_to_bottom(self.scrolled)
        else:
            button.remove_css_class("toggle-fail-active")
            if not self.pass_button.get_active():
                # Neither button is selected anymore -- back to untested.
                self.reason_revealer.set_reveal_child(False)
                self.passed = None
                self.check_status()

    def _on_reason_button_toggled(self, button, reason):
        _toggle_button_css(button)
        if reason == CUSTOM_OPTION:
            self.custom_reason_revealer.set_reveal_child(button.get_active())
            if button.get_active():
                self.custom_reason_entry.grab_focus()
                _scroll_to_bottom(self.scrolled)
            return
        if button.get_active():
            self._add_reason(reason)
        else:
            self._remove_reason(reason)

    def _on_add_custom_reason_clicked(self, widget):
        reason = self.custom_reason_entry.get_text().strip()
        if not reason:
            return
        self.custom_reason_entry.set_text("")
        self._add_reason(reason, removable=True)
        # Hides the custom entry box again (fires _on_reason_button_toggled).
        self._reason_buttons[CUSTOM_OPTION].set_active(False)

    def suppress_reason_option(self, reason):
        """Grey out a preset reason's button because it's already been
        reported elsewhere (e.g. Physical Defects' port-damage picker)."""
        if reason not in self._suppressed_reasons:
            self._suppressed_reasons.add(reason)
            button = self._reason_buttons.get(reason)
            if button is not None:
                button.set_sensitive(False)

    def restore_reason_option(self, reason):
        if reason in self._suppressed_reasons:
            self._suppressed_reasons.discard(reason)
            button = self._reason_buttons.get(reason)
            if button is not None:
                button.set_sensitive(True)

    def _add_reason(self, reason, removable=False):
        if reason in self._reason_entries:
            return

        entry_row = Adw.ExpanderRow(title=reason)

        # Preset reasons are un-added by toggling their button back off (see
        # _on_reason_button_toggled); only free-typed ("Custom...") reasons
        # have no corresponding button, so they get their own Remove action.
        if removable:
            remove_button = Gtk.Button(label="Remove")
            remove_button.set_valign(Gtk.Align.CENTER)
            remove_button.connect(
                "clicked", self._on_remove_custom_reason_clicked, reason
            )
            entry_row.add_action(remove_button)

        data = self.build_reason_locations(entry_row, reason)
        if removable:
            # Free-typed ("Custom...") reasons keep their location picker
            # for convenience, but since there's no preset text to fall
            # back on, don't force a location pick just to report them.
            data["location_optional"] = True

        entry_row.set_expanded(True)
        self.reasons_list_box.append(entry_row)
        self._reason_entries[reason] = (entry_row, data)
        self.check_status()
        _scroll_to_bottom(self.scrolled)

    def _remove_reason(self, reason):
        entry = self._reason_entries.pop(reason, None)
        if entry is None:
            return
        entry_row, _ = entry
        self.reasons_list_box.remove(entry_row)
        self.check_status()

    def _on_remove_custom_reason_clicked(self, button, reason):
        self._remove_reason(reason)

    def _locations_text(self, data):
        kind = data.get("type")
        if kind == "none":
            return None
        if kind == "keys":
            keys = data.get("selected") or []
            if keys == ENTIRE_KEYBOARD_MARKER:
                return "Entire Keyboard"
            return ", ".join(keys) if keys else "no keys specified"
        if kind == "key_categories":
            categories = data.get("categories") or {}
            if not categories:
                return "no damage type selected"
            parts = []
            for category, keys in categories.items():
                if keys == ENTIRE_KEYBOARD_MARKER:
                    key_text = "Entire Keyboard"
                else:
                    key_text = ", ".join(keys) if keys else "no keys specified"
                parts.append(f"{category}: {key_text}")
            return "; ".join(parts)
        if kind == "sections":
            selected = data.get("selected") or []
            return ", ".join(selected) if selected else "no location marked"
        if kind == "usb_port":
            locations = data.get("locations") or []
            if not locations:
                return "no location specified"
            return ", ".join(locations)
        if kind == "click_sides":
            # See TouchpadPage._build_click_picker -- "Touchpad click" has
            # no location, "Left click"/"Right click" each have their own
            # Top/Bottom selection.
            sides = data.get("sides") or []
            if not sides:
                return "no click type specified"
            parts = []
            for side in sides:
                if side in TOUCHPAD_CLICK_SIDES_WITH_LOCATION:
                    locations = data.get("locations", {}).get(side) or []
                    loc_text = (
                        ", ".join(locations) if locations else "no location specified"
                    )
                    parts.append(f"{side}: {loc_text}")
                else:
                    parts.append(side)
            return "; ".join(parts)
        return "no location specified"

    def _reason_is_filled(self, data):
        """Whether a given failure reason's location/detail was actually
        filled in, not just added with defaults left blank. "Yes" pages
        must have at least one fully-filled reason before they can
        count as complete -- see is_complete()."""
        kind = data.get("type")
        if kind == "none":
            return True
        if kind == "keys":
            selected = data.get("selected")
            return selected == ENTIRE_KEYBOARD_MARKER or bool(selected)
        if kind == "key_categories":
            categories = data.get("categories") or {}
            if not categories:
                return False
            return all(
                keys == ENTIRE_KEYBOARD_MARKER or bool(keys)
                for keys in categories.values()
            )
        if kind == "sections":
            return data.get("location_optional") or bool(data.get("selected"))
        if kind == "usb_port":
            return data.get("location_optional") or bool(data.get("locations"))
        if kind == "click_sides":
            # At least one side must be picked, and every side that needs
            # a Top/Bottom location (see TOUCHPAD_CLICK_SIDES_WITH_LOCATION)
            # must have one selected -- "Touchpad click" needs no location.
            sides = data.get("sides") or []
            if not sides:
                return False
            return all(
                bool(data.get("locations", {}).get(side))
                for side in sides
                if side in TOUCHPAD_CLICK_SIDES_WITH_LOCATION
            )
        return False

    def is_complete(self):
        if self.passed is None:
            return False
        if self.passed is False:
            if not self._reason_entries:
                return False
            return all(
                self._reason_is_filled(data)
                for _, data in self._reason_entries.values()
            )
        return True

    def has_reason(self, reason):
        """Whether the given failure reason (exact text match) was added --
        used by the tracking sheet to derive fields from a specific defect
        type rather than the page's overall pass/fail (see BrowserPage)."""
        return reason in self._reason_entries

    def check_status(self):
        if self.state is None:
            return
        state = self.state.get_value()
        state[self.key] = bool(self.passed)
        print(f"{self.key}:check_status {self.passed}")
        if self.on_status_changed:
            self.on_status_changed()

    def _reason_code(self, reason):
        """Short parseable code for a failure reason, e.g. "KB02" -- see the
        CUSTOM_REASON_CODE_SUFFIX comment near the top of this file."""
        if not self.code_prefix:
            return None
        try:
            return f"{self.code_prefix}{self.reason_options.index(reason) + 1:02d}"
        except ValueError:
            return f"{self.code_prefix}{CUSTOM_REASON_CODE_SUFFIX}"

    def _reason_label(self, reason):
        code = self._reason_code(reason)
        return f"{code}: {reason}" if code else reason

    def _code_sort_key(self, code):
        """Numeric part of a code like "KB06" -> 6, so codes/notes always
        sort in numeric order regardless of the order reasons were added.
        A code that doesn't parse (e.g. the CUSTOM_REASON_CODE_SUFFIX
        fallback, or None) sorts last."""
        if not code or not self.code_prefix:
            return 999
        try:
            return int(code[len(self.code_prefix) :])
        except (TypeError, ValueError):
            return 999

    def _failed_codes(self):
        """Data codes (e.g. "KB02") for every reported failure reason,
        deduped and sorted in numeric order -- used for the compact Spec
        Complete failure-summary row (get_failure_reasons) so it doesn't
        repeat the full reason/location text already on the tracking
        sheet. Override when a single reason can map to more than one
        code (see KeyboardPage._failed_codes for "Physical damage")."""
        codes = {self._reason_code(reason) for reason in self._reason_entries}
        codes.discard(None)
        return sorted(codes, key=self._code_sort_key)

    def _sorted_reason_items(self):
        """(reason, data) pairs from self._reason_entries sorted by each
        reason's numeric data code (its position in reason_options) so the
        tracking sheet always lists issues in code order (KB01, KB02, ...)
        regardless of the order they were added in the app. Custom
        free-text reasons have no fixed number (see CUSTOM_REASON_CODE_SUFFIX)
        and sort after every numbered one, in the order they were added."""

        def _sort_key(item):
            reason, _ = item
            try:
                return (0, self.reason_options.index(reason))
            except ValueError:
                return (1, 0)

        items = sorted(self._reason_entries.items(), key=_sort_key)
        return [(reason, data) for reason, (entry_row, data) in items]

    def get_failure_reasons(self):
        """Reported reasons are summarized as just their data codes (e.g.
        "Keyboard failed: KB01, KB04, KB09") rather than the full
        reason/location text -- that detail already lives on the tracking
        sheet (see get_notes_entries); this is just the compact Spec
        Complete screen summary."""
        if self.passed is False:
            if not self._reason_entries:
                return [f"{self.title} failed: no reason specified"]
            codes = self._failed_codes()
            if not codes:
                return [f"{self.title} failed"]
            return [f"{self.title} failed: " + ", ".join(codes)]
        if self.passed is None:
            return [f"{self.title} not completed"]
        return []

    def get_datacodes(self):
        """Data codes (e.g. "KB02") this page is reporting, for the
        machine-wide Data Codes string sent to Sortly -- see
        SpecCompleteV3._gather_datacodes. Same codes as
        get_failure_reasons' compact summary, just without the
        "<title> failed:" wrapper, and empty whenever this page passed,
        wasn't tested, or failed with no reason recorded."""
        if self.passed is not False:
            return []
        return self._failed_codes()

    def get_notes_entries(self):
        """Each reported reason becomes its own coded detail (e.g. "KB02:
        Key(s) Sticking (F, G)"), all joined onto a single line so multiple
        issues on the same test read as one grouped note."""
        if self.passed is not False:
            return []
        if not self._reason_entries:
            return [{"text": f"{self.title}: issue reported"}]
        details = []
        for reason, data in self._sorted_reason_items():
            label = self._reason_label(reason)
            loc_text = self._locations_text(data)
            if loc_text:
                details.append(f"{label} ({loc_text})")
            else:
                details.append(label)
        return [{"text": ", ".join(details)}]

    def get_result(self):
        if self.passed is None:
            return "Untested"
        return "Pass" if self.passed else "Fail"

    def on_shown(self):
        self.check_status()


class PhysicalDefectsPage(Adw.Bin):
    CODE_PREFIX = "PD"

    def __init__(self):
        super().__init__()
        self.key = "PhysicalDefects"
        self.title = "Physical Defects"
        self.skip = False
        self.has_defects = None
        self.state = None
        # Set externally by spec_v3.py -- see TogglePage.on_status_changed.
        self.on_status_changed = None
        self._defect_entries = {}
        # Set externally by spec_v3.py so a "Port Damaged" defect can
        # suppress the matching "Physically Damaged" reason on the right
        # USB-A/USB-C page (see _on_port_damage_type_changed). USB-C may be
        # None on devices without USB-C ports.
        self.usb_a_page = None
        self.usb_c_page = None
        # Set externally by spec_v3.py so "Broken Part" can hand off
        # Keys/Screen reports to their own dedicated test page instead of
        # recording them here -- see _delegate_broken_part.
        self.keyboard_page = None
        self.screen_page = None

        self.set_margin_top(24)
        self.set_margin_bottom(24)
        self.set_margin_start(24)
        self.set_margin_end(24)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)

        header = Gtk.Label(label="Physical Defects")
        header.add_css_class("title-3")
        header.set_halign(Gtk.Align.START)
        vbox.append(header)

        # Shown when the device appears to be charging only through a
        # secondary port (e.g. USB-C) rather than its primary barrel/DC-jack
        # port -- see _update_charging_port_banner.
        self.charging_port_banner = Adw.Banner()
        self.charging_port_banner.set_button_label("Re-check")
        self.charging_port_banner.connect(
            "button-clicked", self._on_charging_port_recheck_clicked
        )
        vbox.append(self.charging_port_banner)

        instructions_label = Gtk.Label(
            label="Please inspect the machine for any physical damage. Make "
            "sure to check the top, sides."
        )
        instructions_label.set_wrap(True)
        instructions_label.set_justify(Gtk.Justification.CENTER)
        instructions_label.set_halign(Gtk.Align.CENTER)
        instructions_label.add_css_class("instructions-label")
        vbox.append(instructions_label)

        # TEMPORARY placeholder animation -- see _build_gif_placeholder_widget.
        gif_placeholder = _build_gif_placeholder_widget()
        if gif_placeholder is not None:
            vbox.append(gif_placeholder)

        result_group = Adw.PreferencesGroup(title="Result")
        toggle_row = Adw.ActionRow()
        toggle_row.set_title("Is the laptop in good physical condition?")

        toggle_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        toggle_box.add_css_class("linked")
        self.no_defects_button = Gtk.ToggleButton(label="Yes")
        self.defects_present_button = Gtk.ToggleButton(label="No")
        self.no_defects_button.set_valign(Gtk.Align.CENTER)
        self.defects_present_button.set_valign(Gtk.Align.CENTER)
        self.no_defects_button.connect("toggled", self._on_no_defects_toggled)
        self.defects_present_button.connect("toggled", self._on_defects_present_toggled)
        toggle_box.append(self.no_defects_button)
        toggle_box.append(self.defects_present_button)
        toggle_row.add_suffix(toggle_box)
        result_group.add(toggle_row)
        vbox.append(result_group)

        # Revealed only when "Yes" is selected
        self.defects_revealer = Gtk.Revealer()
        self.defects_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)

        defects_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        defect_buttons_box, self._defect_buttons = _build_toggle_button_grid(
            "What type of damage is present? (Select all that apply)",
            PHYSICAL_DEFECT_TYPES + [CUSTOM_OPTION],
            self._on_defect_button_toggled,
        )
        defects_content.append(defect_buttons_box)

        # Free-text entry, revealed only when "Custom..." is clicked above
        self.custom_defect_revealer = Gtk.Revealer()
        self.custom_defect_revealer.set_transition_type(
            Gtk.RevealerTransitionType.SLIDE_DOWN
        )
        custom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        custom_box.set_margin_start(12)
        custom_box.set_margin_end(12)
        custom_label = Gtk.Label(label="Describe the defect:")
        self.custom_defect_entry = Gtk.Entry()
        self.custom_defect_entry.set_hexpand(True)
        self.custom_defect_entry.connect("activate", self._on_add_custom_defect_clicked)
        custom_add_button = Gtk.Button(label="Add")
        custom_add_button.connect("clicked", self._on_add_custom_defect_clicked)
        custom_box.append(custom_label)
        custom_box.append(self.custom_defect_entry)
        custom_box.append(custom_add_button)
        self.custom_defect_revealer.set_child(custom_box)
        self.custom_defect_revealer.set_reveal_child(False)
        defects_content.append(self.custom_defect_revealer)

        self.defects_list_box = Gtk.ListBox()
        self.defects_list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.defects_list_box.add_css_class("boxed-list")
        self.defects_list_box.set_valign(Gtk.Align.START)
        defects_content.append(self.defects_list_box)

        self.defects_revealer.set_child(defects_content)
        self.defects_revealer.set_reveal_child(False)
        vbox.append(self.defects_revealer)

        vbox.set_vexpand(True)
        vbox.set_hexpand(True)
        vbox.set_valign(Gtk.Align.START)

        self.scrolled = Gtk.ScrolledWindow()
        # Horizontal scrolling (rather than NEVER) keeps any unexpectedly
        # wide content -- e.g. a long button grid -- from forcing the whole
        # window wider than the screen; it scrolls instead of pushing the
        # window's minimum size out.
        self.scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.scrolled.set_vexpand(True)
        self.scrolled.set_hexpand(True)
        self.scrolled.set_child(vbox)
        self.set_child(self.scrolled)

    def _on_no_defects_toggled(self, button):
        if button.get_active():
            self.defects_present_button.set_active(False)
            button.add_css_class("toggle-pass-active")
            self.defects_revealer.set_reveal_child(False)
            self.has_defects = False
            self.check_status()
        else:
            button.remove_css_class("toggle-pass-active")
            if not self.defects_present_button.get_active():
                # Neither button is selected anymore -- back to untested.
                self.has_defects = None
                self.check_status()

    def _on_defects_present_toggled(self, button):
        if button.get_active():
            self.no_defects_button.set_active(False)
            button.add_css_class("toggle-fail-active")
            self.defects_revealer.set_reveal_child(True)
            self.has_defects = True
            self.check_status()
            _scroll_to_bottom(self.scrolled)
        else:
            button.remove_css_class("toggle-fail-active")
            if not self.no_defects_button.get_active():
                # Neither button is selected anymore -- back to untested.
                self.defects_revealer.set_reveal_child(False)
                self.has_defects = None
                self.check_status()

    def _on_defect_button_toggled(self, button, defect_type):
        _toggle_button_css(button)
        if defect_type == CUSTOM_OPTION:
            self.custom_defect_revealer.set_reveal_child(button.get_active())
            if button.get_active():
                self.custom_defect_entry.grab_focus()
                _scroll_to_bottom(self.scrolled)
            return
        if button.get_active():
            self._add_defect(defect_type)
        else:
            self._remove_defect(defect_type)

    def _on_add_custom_defect_clicked(self, widget):
        defect_type = self.custom_defect_entry.get_text().strip()
        if not defect_type:
            return
        self.custom_defect_entry.set_text("")
        self._add_defect(defect_type, removable=True)
        # Hides the custom entry box again (fires _on_defect_button_toggled).
        self._defect_buttons[CUSTOM_OPTION].set_active(False)

    def _add_defect(self, defect_type, removable=False):
        if defect_type in self._defect_entries:
            return

        entry_row = Adw.ExpanderRow(title=defect_type)

        # Preset defect types are un-added by toggling their button back off
        # (see _on_defect_button_toggled); only free-typed ("Custom...")
        # defects have no corresponding button, so they get their own
        # Remove action.
        if removable:
            remove_button = Gtk.Button(label="Remove")
            remove_button.set_valign(Gtk.Align.CENTER)
            remove_button.connect(
                "clicked", self._on_remove_custom_defect_clicked, defect_type
            )
            entry_row.add_action(remove_button)

        data = self._build_defect_details(defect_type, entry_row)
        if removable:
            # Free-typed ("Custom...") defects keep their location picker
            # for convenience, but since there's no preset text to fall
            # back on, don't force a location pick just to report them.
            data["location_optional"] = True

        entry_row.set_expanded(True)
        self.defects_list_box.append(entry_row)
        self._defect_entries[defect_type] = (entry_row, data)
        self.check_status()
        _scroll_to_bottom(self.scrolled)

    def _remove_defect(self, defect_type):
        entry = self._defect_entries.pop(defect_type, None)
        if entry is None:
            return
        entry_row, data = entry
        self.defects_list_box.remove(entry_row)
        if data and data.get("type") == "port_damage":
            for port_type, page in data.get("_suppressed_pages", {}).items():
                page.restore_reason_option(self._port_damage_reason_for_type(port_type))
        if data and data.get("type") == "broken_part":
            self._undelegate_all_broken_part(data)
        self.check_status()

    def _on_remove_custom_defect_clicked(self, button, defect_type):
        self._remove_defect(defect_type)

    def _build_defect_details(self, defect_type, entry_row):
        if defect_type in PHYSICAL_NO_LOCATION_TYPES:
            return {"type": "none"}

        if defect_type in PHYSICAL_SCREEN_SECTION_TYPES:
            return _build_section_picker(
                self,
                entry_row,
                title="Location of crack",
                select_all_label="Entire Screen",
                fullscreen=True,
            )

        if defect_type in PHYSICAL_PART_LOCATION_TYPES:
            return self._build_part_location_picker(entry_row)

        if defect_type in PHYSICAL_PORT_DAMAGE_TYPES:
            return self._build_port_damage_picker(entry_row)

        if defect_type in PHYSICAL_BROKEN_PART_TYPES:
            return self._build_broken_part_picker(entry_row)

        # Custom (typed-in) defect types fall back to a generic location
        # picker; unlike preset defects, picking a location here is optional.
        return _build_section_picker(
            self, entry_row, title="Location (optional)", select_all_label="Select All"
        )

    def _build_part_location_picker(self, entry_row):
        # Each affected part gets its own independent location grid (rather
        # than one grid shared across all of them), since e.g. a scratch on
        # the Case and a scratch on the Screen aren't necessarily in the
        # same sextant.
        data = {"type": "part_location", "parts": [], "locations": {}}

        locations_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        locations_list_row = Gtk.ListBoxRow()
        locations_list_row.set_selectable(False)
        locations_list_row.set_activatable(False)
        locations_list_row.set_child(locations_box)

        def _rebuild_part_location_rows(selected_parts):
            child = locations_box.get_first_child()
            while child is not None:
                next_child = child.get_next_sibling()
                locations_box.remove(child)
                child = next_child
            data["locations"] = {
                part: locations
                for part, locations in data["locations"].items()
                if part in selected_parts
            }
            for part in selected_parts:

                def _on_location_change(selected, part=part):
                    data["locations"][part] = selected
                    self.check_status()

                part_row = _build_section_row(
                    f"Location on {part}",
                    SCREEN_SECTIONS,
                    select_all_label="Select All",
                    on_change=_on_location_change,
                )
                locations_box.append(part_row)

        def _on_parts_change(selected):
            data["parts"] = selected
            _rebuild_part_location_rows(selected)
            self.check_status()
            _scroll_to_bottom(self.scrolled)

        parts_row = _build_section_row(
            f"Where is/are the {entry_row.get_title()}(s)?",
            PHYSICAL_AFFECTED_PARTS,
            columns=3,
            on_change=_on_parts_change,
        )
        entry_row.add_row(parts_row)
        entry_row.add_row(locations_list_row)
        return data

    def _build_port_damage_picker(self, entry_row):
        # Multiple port types can be damaged at once (e.g. a USB-A port and
        # the charging port), each with its own set of affected location(s)
        # and, per location, an optional port # -- same per-location Port #
        # pattern as UsbPortLocationMixin.build_reason_locations, just
        # nested one level deeper (per port type instead of a single type).
        data = {
            "type": "port_damage",
            "types": [],
            "locations": {},  # port_type -> [location, ...]
            "port_numbers": {},  # port_type -> {location: port_num}
            "custom_text": {},  # port_type ("Other") -> custom description
            "_suppressed_pages": {},  # port_type -> page it's suppressed on
        }

        types_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        types_list_row = Gtk.ListBoxRow()
        types_list_row.set_selectable(False)
        types_list_row.set_activatable(False)
        types_list_row.set_child(types_box)

        def _rebuild_type_blocks(selected_types):
            child = types_box.get_first_child()
            while child is not None:
                next_child = child.get_next_sibling()
                types_box.remove(child)
                child = next_child

            for port_type in list(data["_suppressed_pages"].keys()):
                if port_type not in selected_types:
                    data["_suppressed_pages"].pop(port_type).restore_reason_option(
                        self._port_damage_reason_for_type(port_type)
                    )
            data["locations"] = {
                t: v for t, v in data["locations"].items() if t in selected_types
            }
            data["port_numbers"] = {
                t: v for t, v in data["port_numbers"].items() if t in selected_types
            }
            data["custom_text"] = {
                t: v for t, v in data["custom_text"].items() if t in selected_types
            }

            for port_type in selected_types:
                block = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

                type_label = Gtk.Label(label=port_type)
                type_label.set_halign(Gtk.Align.START)
                type_label.add_css_class("heading")
                block.append(type_label)

                if port_type == "Other":
                    custom_entry = Gtk.Entry()
                    custom_entry.set_placeholder_text("Describe the port")
                    custom_entry.set_text(data["custom_text"].get(port_type, ""))

                    def _on_custom_changed(entry, port_type=port_type):
                        data["custom_text"][port_type] = entry.get_text().strip()
                        self.check_status()

                    custom_entry.connect("changed", _on_custom_changed)
                    block.append(custom_entry)

                ports_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

                def _rebuild_ports(
                    selected_locations, port_type=port_type, ports_box=ports_box
                ):
                    child = ports_box.get_first_child()
                    while child is not None:
                        next_child = child.get_next_sibling()
                        ports_box.remove(child)
                        child = next_child
                    for location in selected_locations:
                        port_row = Gtk.Box(
                            orientation=Gtk.Orientation.HORIZONTAL, spacing=8
                        )
                        label = Gtk.Label(label=f"{location} Port #")
                        label.set_halign(Gtk.Align.START)
                        label.set_hexpand(True)
                        num_entry = Gtk.Entry()
                        num_entry.set_max_length(1)
                        num_entry.set_placeholder_text("optional")
                        num_entry.set_tooltip_text(
                            "Only needed if there are multiple of this type on "
                            "this side"
                        )
                        num_entry.set_input_purpose(Gtk.InputPurpose.DIGITS)
                        num_entry.set_size_request(48, -1)
                        num_entry.set_text(
                            data["port_numbers"].get(port_type, {}).get(location, "")
                        )
                        num_entry.connect(
                            "insert-text", self._on_port_number_insert_text
                        )

                        def _on_num_changed(
                            entry, port_type=port_type, location=location
                        ):
                            data["port_numbers"].setdefault(port_type, {})[
                                location
                            ] = entry.get_text().strip()

                        num_entry.connect("changed", _on_num_changed)
                        port_row.append(label)
                        port_row.append(num_entry)
                        ports_box.append(port_row)

                def _on_locations_change(
                    selected, port_type=port_type, ports_box=ports_box
                ):
                    data["locations"][port_type] = selected
                    data["port_numbers"][port_type] = {
                        location: value
                        for location, value in data["port_numbers"]
                        .get(port_type, {})
                        .items()
                        if location in selected
                    }
                    _rebuild_ports(selected)
                    self.check_status()
                    _scroll_to_bottom(self.scrolled)

                location_row = _build_section_row(
                    "Location(s)",
                    USB_PORT_LOCATIONS,
                    columns=len(USB_PORT_LOCATIONS),
                    on_change=_on_locations_change,
                )
                block.append(location_row)
                block.append(ports_box)
                _rebuild_ports(data["locations"].get(port_type, []))

                types_box.append(block)

                # Suppress the matching "physically damage" reason on the
                # type's matching USB page right away so it isn't
                # double-reported there too.
                page = self._usb_page_for_type(port_type)
                if page is not None and port_type not in data["_suppressed_pages"]:
                    page.suppress_reason_option(
                        self._port_damage_reason_for_type(port_type)
                    )
                    data["_suppressed_pages"][port_type] = page

        def _on_types_change(selected):
            data["types"] = selected
            _rebuild_type_blocks(selected)
            self.check_status()
            _scroll_to_bottom(self.scrolled)

        types_row = _build_section_row(
            "Port Type(s)",
            PHYSICAL_PORT_TYPES,
            columns=len(PHYSICAL_PORT_TYPES),
            on_change=_on_types_change,
        )
        entry_row.add_row(types_row)
        entry_row.add_row(types_list_row)

        return data

    def _usb_page_for_type(self, port_type):
        if port_type == "USB-A":
            return self.usb_a_page
        if port_type == "USB-C":
            return self.usb_c_page
        return None

    def _port_damage_reason_for_type(self, port_type):
        if port_type == "USB-A":
            return USB_A_PORT_DAMAGE_REASON
        if port_type == "USB-C":
            return USB_C_PORT_DAMAGE_REASON
        return None

    def _on_port_number_insert_text(self, entry, text, length, position):
        if text and not text.isdigit():
            GObject.signal_stop_emission_by_name(entry, "insert-text")

    def _build_broken_part_picker(self, entry_row):
        """ "Broken Part" -> "Keys Have Physical Damage"/"Screen"/"Port
        Physically Broken" (for a USB-A/USB-C port) hand off to that
        page's own dedicated test instead of being recorded here -- see
        _delegate_broken_part/_build_broken_part_port_block. "Hinge" and
        "Other" (and any non-USB-A/C port type) have no dedicated page and
        stay Physical-Defects-coded -- see _broken_part_detail.

        Each sub-type's block is built once and kept in data["_blocks"]
        for as long as it stays selected -- toggling some *other* sub-type
        on/off must not tear down and rebuild an already-in-progress
        delegated picker (that would silently wipe out keys/locations the
        tech already picked -- see _sync_sub_type_blocks)."""
        data = {
            "type": "broken_part",
            "sub_types": [],
            "other_text": "",
            "port_damage": self._fresh_broken_part_port_data(),
            "_delegated": {},  # sub_type -> delegation info once handed off
            "_blocks": {},  # sub_type -> block widget, built once
        }

        types_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        types_list_row = Gtk.ListBoxRow()
        types_list_row.set_selectable(False)
        types_list_row.set_activatable(False)
        types_list_row.set_child(types_box)

        def _build_sub_type_block(sub_type):
            block = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            type_label = Gtk.Label(label=sub_type)
            type_label.set_halign(Gtk.Align.START)
            type_label.add_css_class("heading")
            block.append(type_label)

            if sub_type == BROKEN_PART_OTHER_TYPE:
                custom_entry = Gtk.Entry()
                custom_entry.set_placeholder_text("Describe the broken part")
                custom_entry.set_text(data.get("other_text", ""))

                def _on_custom_changed(entry):
                    data["other_text"] = entry.get_text().strip()
                    self.check_status()

                custom_entry.connect("changed", _on_custom_changed)
                block.append(custom_entry)
            elif sub_type == BROKEN_PART_HINGE_TYPE:
                pass  # Nothing further to record -- see PHYSICAL_NO_LOCATION_TYPES.
            elif sub_type == BROKEN_PART_PORT_TYPE:
                self._build_broken_part_port_block(block, data)
            else:
                # Keys Have Physical Damage / Screen -- delegated.
                status_label = Gtk.Label(label="")
                status_label.set_halign(Gtk.Align.START)
                status_label.set_wrap(True)
                status_label.add_css_class("dim-label")
                block.append(status_label)
                self._delegate_broken_part(sub_type, data, block, status_label)

            return block

        def _sync_sub_type_blocks(selected_types):
            for sub_type in data["sub_types"]:
                if sub_type in selected_types:
                    continue
                block = data["_blocks"].pop(sub_type, None)
                if block is not None:
                    types_box.remove(block)
                self._undelegate_broken_part(sub_type, data)
                if sub_type == BROKEN_PART_PORT_TYPE:
                    # The whole nested port picker was just torn down --
                    # start it clean next time it's re-selected instead of
                    # reusing now-destroyed widget references.
                    data["port_damage"] = self._fresh_broken_part_port_data()

            data["sub_types"] = selected_types

            for sub_type in selected_types:
                if sub_type in data["_blocks"]:
                    continue  # Already built -- leave it alone.
                block = _build_sub_type_block(sub_type)
                data["_blocks"][sub_type] = block
                self._insert_block_in_order(
                    types_box, data["_blocks"], BROKEN_PART_SUB_TYPES, sub_type
                )

        def _on_sub_types_change(selected):
            _sync_sub_type_blocks(selected)
            self.check_status()
            _scroll_to_bottom(self.scrolled)

        types_row = _build_section_row(
            "What is broken? (Add all that apply)",
            BROKEN_PART_SUB_TYPES,
            columns=2,
            on_change=_on_sub_types_change,
        )
        entry_row.add_row(types_row)
        entry_row.add_row(types_list_row)

        return data

    @staticmethod
    def _fresh_broken_part_port_data():
        return {
            "types": [],
            "locations": {},
            "port_numbers": {},
            "custom_text": {},
            "_delegated_pages": {},  # port_type -> delegation info
            "_blocks": {},  # port_type -> block widget, built once
        }

    def _insert_block_in_order(self, box, blocks, order, key):
        """Insert `blocks[key]` into `box` positioned according to `order`
        (the canonical list `key` belongs to), based on which other blocks
        already happen to be present in `blocks` -- keeps Broken Part's
        sub-type/port-type blocks in a stable, predictable order even
        though each is only ever built once and never rebuilt (see
        _sync_sub_type_blocks/_build_broken_part_port_block)."""
        sibling = None
        for candidate in reversed(order[: order.index(key)]):
            if candidate in blocks:
                sibling = blocks[candidate]
                break
        box.insert_child_after(blocks[key], sibling)

    def _build_broken_part_port_block(self, box, data):
        """ "Port Physically Broken" sub-block -- same port-type/location
        grid as the top-level "Port Damaged" defect (see
        _build_port_damage_picker), except a USB-A/USB-C selection is
        fully delegated to that port's own dedicated test page (its own
        datacode) instead of being recorded here; every other port type
        stays Physical-Defects-coded exactly like "Port Damaged" already
        does.

        Each port type's block is built once and kept in
        port_data["_blocks"] for as long as it stays selected -- same
        "don't tear down an in-progress block" rule as
        _sync_sub_type_blocks, so picking a second port type doesn't wipe
        out a location/delegation already set up for the first."""
        port_data = data["port_damage"]
        types_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)

        def _build_port_block(port_type):
            block = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            type_label = Gtk.Label(label=port_type)
            type_label.set_halign(Gtk.Align.START)
            type_label.add_css_class("heading")
            block.append(type_label)

            page = self._usb_page_for_type(port_type)
            if page is not None:
                reason = self._port_damage_reason_for_type(port_type)
                button = page._reason_buttons.get(reason)
                # Don't claim ownership of (or duplicate) a report the
                # tech already made directly on that page.
                if button is not None and button.get_active():
                    status_label = Gtk.Label(
                        label=f"Already reported on the {page.title} test page."
                    )
                    status_label.set_halign(Gtk.Align.START)
                    status_label.set_wrap(True)
                    status_label.add_css_class("dim-label")
                    block.append(status_label)
                    return block

                if not page.fail_button.get_active():
                    page.fail_button.set_active(True)
                page.suppress_reason_option(reason)
                port_data["_delegated_pages"][port_type] = (
                    self._build_port_physical_damage_block(block, page, reason)
                )
                return block

            if port_type == "Other":
                custom_entry = Gtk.Entry()
                custom_entry.set_placeholder_text("Describe the port")
                custom_entry.set_text(port_data["custom_text"].get(port_type, ""))

                def _on_custom_changed(entry, port_type=port_type):
                    port_data["custom_text"][port_type] = entry.get_text().strip()
                    self.check_status()

                custom_entry.connect("changed", _on_custom_changed)
                block.append(custom_entry)

            ports_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

            def _on_locations_change(
                selected, port_type=port_type, ports_box=ports_box
            ):
                port_data["locations"][port_type] = selected
                port_data["port_numbers"][port_type] = {
                    location: value
                    for location, value in port_data["port_numbers"]
                    .get(port_type, {})
                    .items()
                    if location in selected
                }
                _rebuild_port_number_rows(
                    self, ports_box, port_type, selected, port_data["port_numbers"]
                )
                self.check_status()
                _scroll_to_bottom(self.scrolled)

            location_row = _build_section_row(
                "Location(s)",
                USB_PORT_LOCATIONS,
                columns=len(USB_PORT_LOCATIONS),
                on_change=_on_locations_change,
            )
            block.append(location_row)
            block.append(ports_box)
            _rebuild_port_number_rows(
                self,
                ports_box,
                port_type,
                port_data["locations"].get(port_type, []),
                port_data["port_numbers"],
            )

            return block

        def _sync_port_blocks(selected_types):
            for port_type in port_data["types"]:
                if port_type in selected_types:
                    continue
                block = port_data["_blocks"].pop(port_type, None)
                if block is not None:
                    types_box.remove(block)
                self._undelegate_broken_part_port(port_type, port_data)
                port_data["locations"].pop(port_type, None)
                port_data["port_numbers"].pop(port_type, None)
                port_data["custom_text"].pop(port_type, None)

            port_data["types"] = selected_types

            for port_type in selected_types:
                if port_type in port_data["_blocks"]:
                    continue  # Already built -- leave it alone.
                block = _build_port_block(port_type)
                port_data["_blocks"][port_type] = block
                self._insert_block_in_order(
                    types_box, port_data["_blocks"], PHYSICAL_PORT_TYPES, port_type
                )

        def _on_port_types_change(selected):
            _sync_port_blocks(selected)
            self.check_status()
            _scroll_to_bottom(self.scrolled)

        types_row = _build_section_row(
            "Port Type(s)",
            PHYSICAL_PORT_TYPES,
            columns=len(PHYSICAL_PORT_TYPES),
            on_change=_on_port_types_change,
        )
        box.append(types_row)
        box.append(types_box)

    def _add_mirror_row(self, page, title):
        """Appends a read-only summary row to `page`'s own reasons list,
        kept in sync with the interactive picker embedded here in Physical
        Defects (see _wrap_check_status_for_mirror) -- so visiting that
        page directly shows the report already properly filled out,
        without a second, independently-editable copy of the picker."""
        mirror_row = Adw.ExpanderRow(title=title)
        mirror_row.set_expanded(True)
        mirror_label = Gtk.Label(label="")
        mirror_label.set_xalign(0)
        mirror_label.set_wrap(True)
        mirror_label.add_css_class("dim-label")
        mirror_status_row = Gtk.ListBoxRow()
        mirror_status_row.set_selectable(False)
        mirror_status_row.set_activatable(False)
        mirror_status_row.set_child(mirror_label)
        mirror_row.add_row(mirror_status_row)
        page.reasons_list_box.append(mirror_row)
        return mirror_row, mirror_label

    def _wrap_check_status_for_mirror(self, page, refresh_fn):
        """Every picker callback already ends with a self.check_status()
        call on `page` (see KeyboardPage._build_physical_damage_picker /
        UsbPortLocationMixin.build_reason_locations) -- wrapping the
        instance's check_status() piggybacks `refresh_fn` onto that same
        signal, so the mirror row on `page` (see _add_mirror_row) updates
        every time the tech edits the picker embedded here. Returns a
        function that undoes the wrap; call it when the delegation ends."""
        original = page.check_status

        def _wrapped():
            original()
            refresh_fn()

        page.check_status = _wrapped

        def _restore():
            if page.__dict__.get("check_status") is _wrapped:
                del page.check_status

        return _restore

    def _build_keys_physical_damage_block(self, block, keyboard_page, reason):
        """Embeds the exact same "Physical damage" category grid
        keyboard_page itself would show (see
        KeyboardPage._build_physical_damage_picker) directly inside this
        Physical Defects entry, so the tech never has to leave this page.
        The resulting data is registered as keyboard_page's own reason
        entry (tracked under the Keyboard test's own datacode --
        KB03/KB04/KB05), with a read-only mirror row on keyboard_page's own
        reasons list (see _add_mirror_row) keeping that page showing the
        same, correctly filled out report."""
        data = keyboard_page._build_physical_damage_picker(_RowAdderBox(block))
        keyboard_page._reason_entries[reason] = (None, data)

        mirror_row, mirror_label = self._add_mirror_row(keyboard_page, reason)

        def _refresh_mirror():
            notes = keyboard_page._physical_damage_notes(data)
            mirror_label.set_label(
                ", ".join(text for _, text in notes)
                if notes
                else "No keys selected yet."
            )

        restore_check_status = self._wrap_check_status_for_mirror(
            keyboard_page, _refresh_mirror
        )
        _refresh_mirror()

        return {
            "page": keyboard_page,
            "reason": reason,
            "mirror_row": mirror_row,
            "restore_check_status": restore_check_status,
        }

    def _build_port_physical_damage_block(self, block, usb_page, reason):
        """Embeds the same location/port-# picker usb_page itself would
        show (see UsbPortLocationMixin.build_reason_locations) directly
        inside this Physical Defects entry -- tracked under that page's
        own datacode (UA02/UC02) instead of a Physical Defects one, with a
        read-only mirror row on that page's own reasons list (see
        _add_mirror_row) so visiting it directly shows the same, correctly
        filled out report."""
        data = usb_page.build_reason_locations(_RowAdderBox(block), reason)
        usb_page._reason_entries[reason] = (None, data)

        mirror_row, mirror_label = self._add_mirror_row(usb_page, reason)

        def _refresh_mirror():
            loc_text = usb_page._locations_text(data)
            mirror_label.set_label(loc_text or "No location marked yet.")

        restore_check_status = self._wrap_check_status_for_mirror(
            usb_page, _refresh_mirror
        )
        _refresh_mirror()

        return {
            "page": usb_page,
            "reason": reason,
            "mirror_row": mirror_row,
            "restore_check_status": restore_check_status,
        }

    def _build_screen_broken_block(self, block, screen_page, reason):
        """Embeds the same fullscreen 6-section location picker
        screen_page itself would show for "Screen broken" (see
        ScreenSectionMixin.build_reason_locations) directly inside this
        Physical Defects entry -- tracked under the Screen test's own
        datacode (SC08) instead of a Physical Defects one, with a
        read-only mirror row on screen_page's own reasons list (see
        _add_mirror_row) so visiting it directly shows the same,
        correctly filled out report."""
        data = screen_page.build_reason_locations(_RowAdderBox(block), reason)
        screen_page._reason_entries[reason] = (None, data)

        mirror_row, mirror_label = self._add_mirror_row(screen_page, reason)

        def _refresh_mirror():
            loc_text = screen_page._locations_text(data)
            mirror_label.set_label(loc_text or "No location marked yet.")

        restore_check_status = self._wrap_check_status_for_mirror(
            screen_page, _refresh_mirror
        )
        _refresh_mirror()

        return {
            "page": screen_page,
            "reason": reason,
            "mirror_row": mirror_row,
            "restore_check_status": restore_check_status,
        }

    def _delegated_target_page(self, sub_type):
        if sub_type == BROKEN_PART_KEYS_TYPE:
            return self.keyboard_page
        if sub_type == BROKEN_PART_SCREEN_TYPE:
            return self.screen_page
        return None

    def _delegated_reason_for(self, sub_type):
        if sub_type == BROKEN_PART_KEYS_TYPE:
            return KEYBOARD_PHYSICAL_DAMAGE_REASON
        if sub_type == BROKEN_PART_SCREEN_TYPE:
            return SCREEN_BROKEN_REASON
        return None

    def _delegate_broken_part(self, sub_type, data, block, status_label):
        """ "Keys Have Physical Damage"/"Screen" are reported the same way
        the tech would on that page directly, right here in Physical
        Defects (see _build_keys_physical_damage_block/
        _build_screen_broken_block) -- tracked (and coded) under that
        page's own datacode, not a Physical Defects one. See
        _undelegate_broken_part for the reverse."""
        page = self._delegated_target_page(sub_type)
        reason = self._delegated_reason_for(sub_type)
        if page is None or reason is None:
            status_label.set_label("This device has no page to report this on.")
            return

        button = page._reason_buttons.get(reason)
        # If the reason was already reported directly on the dedicated page
        # (before this Broken Part entry existed), leave it alone as that
        # page's own report -- don't duplicate or take it over.
        if button is not None and button.get_active():
            status_label.set_label(f"Already reported on the {page.title} test page.")
            return

        if not page.fail_button.get_active():
            page.fail_button.set_active(True)
        page.suppress_reason_option(reason)
        status_label.set_label("")

        if sub_type == BROKEN_PART_KEYS_TYPE:
            data["_delegated"][sub_type] = self._build_keys_physical_damage_block(
                block, page, reason
            )
        else:
            data["_delegated"][sub_type] = self._build_screen_broken_block(
                block, page, reason
            )

    def _undelegate_broken_part(self, sub_type, data):
        if sub_type == BROKEN_PART_PORT_TYPE:
            port_data = data.get("port_damage") or {}
            for port_type in list(port_data.get("_delegated_pages", {}).keys()):
                self._undelegate_broken_part_port(port_type, port_data)
            return
        info = data.get("_delegated", {}).pop(sub_type, None)
        if not info:
            return
        self._undo_broken_part_delegation(info)

    def _undelegate_broken_part_port(self, port_type, port_data):
        info = port_data.get("_delegated_pages", {}).pop(port_type, None)
        if info is None:
            return
        self._undo_broken_part_delegation(info)

    def _undo_broken_part_delegation(self, info):
        # Every delegated report is embedded (entry_row=None on `page` --
        # see _build_keys_physical_damage_block/
        # _build_screen_broken_block/_build_port_physical_damage_block),
        # so there's no real widget on `page` for its own _remove_reason
        # to clean up; tear down the mirror row and drop the entry
        # directly instead.
        page = info["page"]
        reason = info["reason"]
        page.restore_reason_option(reason)
        info["restore_check_status"]()
        page.reasons_list_box.remove(info["mirror_row"])
        page._reason_entries.pop(reason, None)
        page.check_status()

    def _undelegate_all_broken_part(self, data):
        for sub_type in list(data.get("sub_types") or []):
            self._undelegate_broken_part(sub_type, data)

    def _broken_part_sub_is_filled(self, sub_type, data):
        if sub_type == BROKEN_PART_HINGE_TYPE:
            return True
        if sub_type == BROKEN_PART_OTHER_TYPE:
            return bool(data.get("other_text", "").strip())
        if sub_type in (BROKEN_PART_KEYS_TYPE, BROKEN_PART_SCREEN_TYPE):
            # Completeness for a delegated report lives on that page's own
            # is_complete() (see WizardWindow.update_buttons), not here.
            return True
        if sub_type == BROKEN_PART_PORT_TYPE:
            port_data = data.get("port_damage") or {}
            types = port_data.get("types") or []
            if not types:
                return False
            locations = port_data.get("locations") or {}
            custom_text = port_data.get("custom_text") or {}
            for port_type in types:
                if self._usb_page_for_type(port_type) is not None:
                    continue  # delegated -- that page's is_complete() gates it
                if not locations.get(port_type):
                    return False
                if port_type == "Other" and not custom_text.get(port_type, "").strip():
                    return False
            return True
        return False

    def _broken_part_has_own_content(self, data):
        """Whether "Broken Part" has anything left to report under its own
        Physical-Defects datacode -- False when every selected sub-type
        was fully handed off to a dedicated test page (see
        _broken_part_detail/get_failure_reasons/get_notes_entries)."""
        sub_types = data.get("sub_types") or []
        if BROKEN_PART_HINGE_TYPE in sub_types:
            return True
        if BROKEN_PART_OTHER_TYPE in sub_types and data.get("other_text", "").strip():
            return True
        if BROKEN_PART_PORT_TYPE in sub_types:
            port_data = data.get("port_damage") or {}
            for port_type in port_data.get("types") or []:
                if self._usb_page_for_type(port_type) is None:
                    return True
        return False

    def _broken_part_detail(self, data):
        """Tracking-sheet detail text for "Broken Part", covering only the
        sub-types with no dedicated test page (Hinge, Other, and any
        non-USB-A/C port type) -- Keys/Screen/USB-A/USB-C are reported on
        their own page under their own datacode instead (see
        _delegate_broken_part/_build_broken_part_port_block), so they're
        deliberately left out here. Returns None when nothing is left to
        report under Physical Defects' own code."""
        sub_types = data.get("sub_types") or []
        parts = []
        if BROKEN_PART_HINGE_TYPE in sub_types:
            parts.append(BROKEN_PART_HINGE_TYPE)
        if BROKEN_PART_OTHER_TYPE in sub_types:
            text = data.get("other_text", "").strip()
            if text:
                parts.append(text)
        if BROKEN_PART_PORT_TYPE in sub_types:
            port_data = data.get("port_damage") or {}
            locations = port_data.get("locations") or {}
            port_numbers = port_data.get("port_numbers") or {}
            custom_text = port_data.get("custom_text") or {}
            for port_type in port_data.get("types") or []:
                if self._usb_page_for_type(port_type) is not None:
                    continue
                name = port_type
                if port_type == "Other":
                    custom = custom_text.get(port_type, "").strip()
                    name = custom if custom else "Other"
                locs = locations.get(port_type) or []
                loc_parts = []
                for location in locs:
                    port_num = port_numbers.get(port_type, {}).get(location, "").strip()
                    loc_parts.append(
                        f"{location} (port #{port_num})" if port_num else location
                    )
                loc_text = (
                    ", ".join(loc_parts) if loc_parts else "no location specified"
                )
                parts.append(f"{name}: {loc_text}")
        if not parts:
            return None
        label = f"{self._defect_code('Broken Part')}: Broken Part"
        return f"{label} ({'; '.join(parts)})"

    def _defect_is_filled(self, data):
        """See TogglePage._reason_is_filled -- "Yes" requires at
        least one fully-filled defect before it counts as complete."""
        kind = data.get("type")
        if kind == "none":
            return True
        if kind == "sections":
            return data.get("location_optional") or bool(data.get("selected"))
        if kind == "part_location":
            parts = data.get("parts") or []
            locations = data.get("locations") or {}
            return bool(parts) and all(locations.get(part) for part in parts)
        if kind == "port_damage":
            # Every selected port type needs at least one location marked
            # (port # itself stays optional -- only needed to disambiguate
            # multiple same-side ports); "Other" additionally requires the
            # custom port description to be filled in.
            types = data.get("types") or []
            if not types:
                return False
            locations = data.get("locations") or {}
            custom_text = data.get("custom_text") or {}
            for port_type in types:
                if not locations.get(port_type):
                    return False
                if port_type == "Other" and not custom_text.get(port_type, "").strip():
                    return False
            return True
        if kind == "broken_part":
            sub_types = data.get("sub_types") or []
            if not sub_types:
                return False
            return all(
                self._broken_part_sub_is_filled(sub_type, data)
                for sub_type in sub_types
            )
        return False

    def is_complete(self):
        if self.has_defects is None:
            return False
        if self.has_defects:
            if not self._defect_entries:
                return False
            return all(
                self._defect_is_filled(data)
                for _, data in self._defect_entries.values()
            )
        return True

    def check_status(self):
        if self.state is None:
            return
        state = self.state.get_value()
        state[self.key] = self.has_defects is False
        print(f"{self.key}:check_status {self.has_defects}")
        if self.on_status_changed:
            self.on_status_changed()

    def _defect_code(self, defect_type):
        """See CUSTOM_REASON_CODE_SUFFIX near the top of this file. Most
        codes are just the defect's 1-based position in
        PHYSICAL_DEFECT_TYPES, but PHYSICAL_DEFECT_CODES overrides that for
        defect types whose code doesn't match their list position."""
        if defect_type in PHYSICAL_DEFECT_CODES:
            return PHYSICAL_DEFECT_CODES[defect_type]
        try:
            return (
                f"{self.CODE_PREFIX}{PHYSICAL_DEFECT_TYPES.index(defect_type) + 1:02d}"
            )
        except ValueError:
            return f"{self.CODE_PREFIX}{CUSTOM_REASON_CODE_SUFFIX}"

    def _sorted_defect_items(self):
        """(defect_type, data) pairs sorted by numeric PD-code position so
        the tracking sheet always lists defects in code order regardless
        of the order they were added in the app -- see
        TogglePage._sorted_reason_items."""

        def _sort_key(item):
            defect_type, _ = item
            try:
                return (0, PHYSICAL_DEFECT_TYPES.index(defect_type))
            except ValueError:
                return (1, 0)

        items = sorted(self._defect_entries.items(), key=_sort_key)
        return [(defect_type, data) for defect_type, (entry_row, data) in items]

    def _code_sort_key(self, code):
        """See TogglePage._code_sort_key -- numeric part of a "PDn" code."""
        if not code:
            return 999
        try:
            return int(code[len(self.CODE_PREFIX) :])
        except (TypeError, ValueError):
            return 999

    def _defect_detail(self, defect_type, data):
        label = f"{self._defect_code(defect_type)}: {defect_type}"
        kind = data.get("type")

        if kind == "none":
            return label

        if kind == "sections":
            selected = data.get("selected") or []
            loc_text = ", ".join(selected) if selected else "no location marked"
            return f"{label} ({loc_text})"

        if kind == "part_location":
            parts = data.get("parts") or []
            if not parts:
                return f"{label} (no part specified)"
            locations = data.get("locations") or {}
            part_details = []
            for part in parts:
                selected = locations.get(part) or []
                loc_text = ", ".join(selected) if selected else "no location specified"
                part_details.append(f"{part}: {loc_text}")
            return f"{label} ({'; '.join(part_details)})"

        if kind == "port_damage":
            types = data.get("types") or []
            if not types:
                return f"{label} (no port type specified)"
            locations = data.get("locations") or {}
            port_numbers = data.get("port_numbers") or {}
            custom_text = data.get("custom_text") or {}
            type_details = []
            for port_type in types:
                name = port_type
                if port_type == "Other":
                    custom = custom_text.get(port_type, "").strip()
                    name = custom if custom else "Other"
                locs = locations.get(port_type) or []
                loc_parts = []
                for location in locs:
                    port_num = port_numbers.get(port_type, {}).get(location, "").strip()
                    loc_parts.append(
                        f"{location} (port #{port_num})" if port_num else location
                    )
                loc_text = (
                    ", ".join(loc_parts) if loc_parts else "no location specified"
                )
                type_details.append(f"{name}: {loc_text}")
            return f"{label} ({'; '.join(type_details)})"

        if kind == "broken_part":
            return self._broken_part_detail(data)

        return label

    def _failed_codes(self):
        """Data codes (e.g. "PD01") for every reported defect, deduped and
        sorted in numeric order -- shared by get_failure_reasons' compact
        summary and get_datacodes' feed to the Sortly Data Codes string
        (see SpecCompleteV3._gather_datacodes). "Broken Part" is left out
        entirely when everything selected under it was handed off to a
        dedicated test page -- see _broken_part_has_own_content."""
        if not self.has_defects or not self._defect_entries:
            return []
        codes = set()
        for defect_type, (entry_row, data) in self._defect_entries.items():
            if defect_type == "Broken Part" and not self._broken_part_has_own_content(
                data
            ):
                continue
            codes.add(self._defect_code(defect_type))
        return sorted(codes, key=self._code_sort_key)

    def get_failure_reasons(self):
        """Reported defects are summarized as just their data codes (e.g.
        "PD01, PD05") rather than the full defect/location text -- that
        detail already lives on the tracking sheet (see get_notes_entries);
        this is just the compact Spec Complete screen summary."""
        if self.has_defects is None:
            return ["Physical defects check not completed"]
        if not self.has_defects:
            return []
        if not self._defect_entries:
            return ["Physical defects present"]
        codes = self._failed_codes()
        if not codes:
            return ["Physical defects present"]
        return [", ".join(codes)]

    def get_datacodes(self):
        """See TogglePage.get_datacodes -- same Data Codes feed, computed
        from _failed_codes() above."""
        return self._failed_codes()

    def get_notes_entries(self):
        """All reported defects are concatenated onto a single line (rather
        than one line per defect type) so damages affecting the device read
        as a single grouped note, e.g. "PD01: Hinge Broken, PD05: Deep
        Scratches (Keyboard: Top, Left)". "Broken Part" contributes nothing
        here when everything selected under it was handed off to a
        dedicated test page instead (see _broken_part_detail, which
        returns None in that case)."""
        if self.has_defects is not True:
            return []
        if not self._defect_entries:
            return [{"text": "PD: issue reported"}]
        details = []
        for defect_type, data in self._sorted_defect_items():
            detail = self._defect_detail(defect_type, data)
            if detail is not None:
                details.append(detail)
        if not details:
            return []
        return [{"text": ", ".join(details)}]

    def get_result(self):
        if self.has_defects is None:
            return "Untested"
        return "Fail" if self.has_defects else "Pass"

    def on_shown(self):
        self.check_status()
        self._update_charging_port_banner()

    def _on_charging_port_recheck_clicked(self, banner):
        self._update_charging_port_banner()

    def _update_charging_port_banner(self):
        if Utils.primary_charging_port_unused():
            self.charging_port_banner.set_title(
                "This device appears to be charging through a secondary "
                "port (e.g. USB-C) rather than its primary charging port. "
                "If the primary charging port is damaged, report it below "
                'under "Port Damaged" -> "Charging Port". '
                "Otherwise, please plug the charger into the primary port "
                "and use that instead."
            )
            self.charging_port_banner.set_revealed(True)
        else:
            self.charging_port_banner.set_revealed(False)


class WiFiPage(TogglePage):
    def __init__(self):
        super().__init__(
            "WiFi",
            "WiFi",
            "WiFi Connectivity",
            reason_options=WIFI_DEFECT_TYPES,
            code_prefix="WF",
            topic="WiFi",
            instructions=(
                "Connect to a Wi-Fi network and confirm the connection is "
                "stable. This page is skipped automatically once a "
                "connection is detected."
            ),
        )

    def on_shown(self):
        connected = Utils.is_wifi_connected()
        self.skip = connected
        if connected:
            self.passed = True
        if self.state is not None:
            state = self.state.get_value()
            state[self.key] = connected or bool(self.passed)
        print(f"WiFi:on_shown connected={connected} skip={self.skip}")

    def build_reason_locations(self, entry_row, reason):
        return {"type": "none"}


class TouchpadPage(TogglePage):
    def __init__(self):
        super().__init__(
            "Touchpad",
            "Touchpad",
            "Touchpad",
            reason_options=TOUCHPAD_DEFECT_TYPES,
            code_prefix="TP",
            instructions=(
                "When testing the touchpad, please make sure to test all left"
                " and right click buttons. Also ensure when moving"
                " your finger across the touchpad that the"
                " cursor moves cleanly and accurately. "
            ),
        )

    def build_reason_locations(self, entry_row, reason):
        if reason == TOUCHPAD_CLICK_REASON:
            return self._build_click_picker(entry_row)
        if reason == TOUCHPAD_CURSOR_REASON:
            return _build_section_picker(
                self,
                entry_row,
                options=TOUCHPAD_CURSOR_OPTIONS,
                title="What's the cursor doing wrong?",
            )
        if reason == TOUCHPAD_PARTIAL_REASON:
            return _build_section_picker(
                self,
                entry_row,
                title="Which part of the touchpad doesn't work?",
            )
        # "Touchpad does not work at all" / "Touchpad feels very tight"
        # apply to the whole touchpad -- no location to narrow down. Any
        # custom free-text reason gets no location picker either, to keep
        # custom entries simple.
        return {"type": "none"}

    def _build_click_picker(self, entry_row):
        """ "A problem with left or right click" expands into "Left
        click"/"Right click"/"Touchpad click" -- Left/Right each get their
        own independent Top/Bottom location grid (same "each gets its own
        grid" pattern as PhysicalDefectsPage._build_part_location_picker,
        since a left-click issue on Top and a right-click issue on Bottom
        aren't the same report); "Touchpad click" has no location to narrow
        down. See TOUCHPAD_CLICK_SIDE_CODES/_touchpad_click_notes for how
        each side reports under its own fixed code regardless of Top vs
        Bottom."""
        data = {"type": "click_sides", "sides": [], "locations": {}}

        locations_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        locations_list_row = Gtk.ListBoxRow()
        locations_list_row.set_selectable(False)
        locations_list_row.set_activatable(False)
        locations_list_row.set_child(locations_box)

        # Keyed by side so a side's Top/Bottom row is only built once and
        # left alone as long as that side stays selected -- toggling a
        # *different* side used to rebuild every row from scratch, which
        # reset every already-picked Top/Bottom button back to unchecked.
        location_rows = {}

        def _add_location_row(side):
            def _on_location_change(selected, side=side):
                data["locations"][side] = selected
                self.check_status()

            side_row = _build_section_row(
                f"Where is/are the {side} issue(s)?",
                TOUCHPAD_CLICK_LOCATION_OPTIONS,
                columns=len(TOUCHPAD_CLICK_LOCATION_OPTIONS),
                on_change=_on_location_change,
            )
            location_rows[side] = side_row
            locations_box.append(side_row)

        def _on_sides_change(selected):
            data["sides"] = selected
            for side in list(location_rows):
                if side not in selected:
                    locations_box.remove(location_rows.pop(side))
                    data["locations"].pop(side, None)
            for side in selected:
                if (
                    side in TOUCHPAD_CLICK_SIDES_WITH_LOCATION
                    and side not in location_rows
                ):
                    _add_location_row(side)
            self.check_status()
            _scroll_to_bottom(self.scrolled)

        sides_row = _build_section_row(
            "Which click(s) are broken?",
            TOUCHPAD_CLICK_SIDE_OPTIONS,
            columns=len(TOUCHPAD_CLICK_SIDE_OPTIONS),
            on_change=_on_sides_change,
        )
        entry_row.add_row(sides_row)
        entry_row.add_row(locations_list_row)
        return data

    def get_notes_entries(self):
        """Overrides TogglePage.get_notes_entries -- touchpad reasons get
        their own plain-English wording (see TOUCHPAD_REASON_NOTES /
        TOUCHPAD_CLICK_CODE_LABELS / TOUCHPAD_CURSOR_CODE_LABELS above),
        still prefixed with a "TP<n>" data code so the tracking sheet stays
        consistent with every other test's notes. "A problem with left or
        right click" and "Something is wrong with how the cursor moves"
        have no code of their own -- each selected sub-option maps to its
        own real code instead (see _touchpad_click_notes/
        _touchpad_cursor_notes), so entries are gathered across every
        reason and re-sorted by code at the end (same pattern as
        KeyboardPage.get_notes_entries for "Physical damage")."""
        if self.passed is not False:
            return []
        if not self._reason_entries:
            return [{"text": "Touchpad: issue reported"}]
        entries = []
        for reason, (entry_row, data) in self._reason_entries.items():
            entries.extend(self._touchpad_reason_notes(reason, data))
        entries.sort(key=lambda entry: self._code_sort_key(entry[0]))
        return [{"text": ", ".join(text for _, text in entries)}]

    def _failed_codes(self):
        """Overrides TogglePage._failed_codes -- the click/cursor reasons
        have no code of their own, so they contribute whichever real codes
        their selected sub-options map to instead of being skipped (see
        KeyboardPage._failed_codes for the same "Physical damage"
        pattern)."""
        codes = set()
        for reason, (entry_row, data) in self._reason_entries.items():
            if reason in (TOUCHPAD_CLICK_REASON, TOUCHPAD_CURSOR_REASON):
                codes.update(
                    code for code, _ in self._touchpad_reason_notes(reason, data)
                )
            else:
                code = self._reason_code(reason)
                if code:
                    codes.add(code)
        return sorted(codes, key=self._code_sort_key)

    def _reason_code(self, reason):
        """Overrides TogglePage._reason_code -- "A problem with left or
        right click" and "Something is wrong with how the cursor moves"
        get no single code of their own (see class docstring above).
        "Part of the touchpad doesn't work" gets a fixed code from
        TOUCHPAD_REASON_CODES rather than its position in
        TOUCHPAD_DEFECT_TYPES, since TP04-TP08 are already spoken for by
        the click/cursor sub-reasons. Every other touchpad reason keeps
        the default position-based code."""
        if reason in (TOUCHPAD_CLICK_REASON, TOUCHPAD_CURSOR_REASON):
            return None
        if reason in TOUCHPAD_REASON_CODES:
            return TOUCHPAD_REASON_CODES[reason]
        return super()._reason_code(reason)

    def _touchpad_click_notes(self, data):
        """Each selected click side reports under its own fixed code (see
        TOUCHPAD_CLICK_SIDE_CODES) regardless of Top vs Bottom -- Top/
        Bottom is just location detail on the tracking sheet, not a
        separate code."""
        sides = data.get("sides") or []
        notes = []
        for side in sides:
            code = TOUCHPAD_CLICK_SIDE_CODES[side]
            label = TOUCHPAD_CLICK_CODE_LABELS[code]
            if side in TOUCHPAD_CLICK_SIDES_WITH_LOCATION:
                locations = data.get("locations", {}).get(side) or []
                loc_text = (
                    ", ".join(locations) if locations else "no location specified"
                )
                notes.append((code, f"{code} {label}: {loc_text}"))
            else:
                notes.append((code, f"{code} {label}"))
        return notes

    def _touchpad_cursor_notes(self, data):
        """Each selected cursor behavior reports under its own fixed code
        (see TOUCHPAD_CURSOR_CODES) instead of one merged code/line for
        every behavior."""
        selected = data.get("selected") or []
        notes = []
        for opt in selected:
            code = TOUCHPAD_CURSOR_CODES[opt]
            label = TOUCHPAD_CURSOR_CODE_LABELS[code]
            addendum = (
                self._cursor_moves_addendum()
                if opt == "Cursor moves on its own"
                else ""
            )
            notes.append((code, f"{code} {label}{addendum}"))
        return notes

    def _touchpad_reason_notes(self, reason, data):
        if reason == TOUCHPAD_CLICK_REASON:
            return self._touchpad_click_notes(data)
        if reason == TOUCHPAD_CURSOR_REASON:
            return self._touchpad_cursor_notes(data)
        code = self._reason_code(reason)
        if reason == TOUCHPAD_PARTIAL_REASON:
            loc_text = self._locations_text(data)
            label = TOUCHPAD_REASON_NOTES[reason]
            text = f"{code} {label}: {loc_text}" if loc_text else f"{code} {label}"
            return [(code, text)]
        if reason in TOUCHPAD_REASON_NOTES:
            return [(code, f"{code} {TOUCHPAD_REASON_NOTES[reason]}")]
        # Custom free-text reason -- fall back to the generic coded label
        # (already includes a code, e.g. "TPO: some custom text").
        return [(code, self._reason_label(reason))]

    @staticmethod
    def _cursor_moves_addendum():
        """ "Cursor moves on its own" can be a symptom of a trackpoint or
        touchscreen sending stray input rather than an actual touchpad
        defect -- flag that possibility on the tracking sheet when either
        is present, so the diagnosis isn't pinned solely on the touchpad."""
        culprits = []
        if Utils.has_trackpoint():
            culprits.append("trackpoint")
        if Utils.has_touchscreen():
            culprits.append("touchscreen")
        if not culprits:
            return ""
        return f" (May be a {' or '.join(culprits)} issue)"


class ScreenSectionMixin:
    """Shared "click the affected screen section(s)" picker, used by both
    ScreenPage and TouchscreenPage. See _build_section_picker."""

    # Reasons that apply to the whole screen with no meaningful location to
    # ask for -- see TouchpadPage.build_reason_locations for a similar
    # "some reasons need no location" pattern.
    NO_LOCATION_REASONS = set()

    def build_reason_locations(self, entry_row, reason):
        if reason in self.NO_LOCATION_REASONS:
            return {"type": "none"}
        title = (
            "Location on screen"
            if reason in self.reason_options
            else "Location on screen (optional)"
        )
        return _build_section_picker(
            self,
            entry_row,
            title=title,
            select_all_label="Entire Screen",
            fullscreen=True,
        )


class ScreenPage(ScreenSectionMixin, TogglePage):
    # "Screen not responding" (no display at all), "Screen broken"
    # (physically cracked/shattered -- see
    # PhysicalDefectsPage._build_screen_broken_block for the "Broken Part"
    # -> "Screen" delegation, which gets "type": "none" the same way), and
    # "Screen glitches out" all apply to the whole screen with nothing
    # meaningful to point at.
    NO_LOCATION_REASONS = {
        "Screen not responding",
        "Screen broken",
        "Screen glitches out",
    }

    def __init__(self):
        super().__init__(
            "ScreenTest",
            "Screen",
            "Screen",
            reason_options=SCREEN_DEFECT_TYPES,
            code_prefix="SC",
            instructions=(
                "Click below to launch the screen test pattern to look "
                "for discoloration, light spots, or any other kind of issue. "
                "Pease make sure to wipe down the screen with a slightly damp "
                "rag when testing to help tell apart real damage and "
                "dirtiness. (Please never spray directly onto the screen)"
            ),
        )
        self.utils = Utils()

    def build_action(self, box):
        launch_row = Adw.ActionRow()
        launch_row.set_title("Launch the screen test pattern")
        launch_button = Gtk.Button(label="Click Here")
        launch_button.set_valign(Gtk.Align.CENTER)
        launch_button.connect("clicked", self._on_launch_clicked)
        launch_row.add_suffix(launch_button)
        group = Adw.PreferencesGroup()
        group.add(launch_row)
        box.append(group)

        self.launch_status = Gtk.Label(label="")
        self.launch_status.set_xalign(0)
        self.launch_status.set_wrap(True)
        box.append(self.launch_status)

    def _on_launch_clicked(self, button):
        _set_status(self.launch_status, "Launching screen test...", auto_clear_ms=4000)
        try:
            process = subprocess.Popen(
                ["screen-test"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError as exc:
            _set_status(
                self.launch_status,
                f"Could not launch screen-test: {exc}",
                is_error=True,
            )
            return
        GLib.timeout_add(400, self._check_launch_result, process)

    def _check_launch_result(self, process):
        rc = process.poll()
        if rc is not None and rc != 0:
            stderr = ""
            if process.stderr is not None:
                stderr = process.stderr.read().decode(errors="replace").strip()
            message = f"screen-test exited immediately (code {rc})"
            if stderr:
                message += f": {stderr}"
            _set_status(self.launch_status, message, is_error=True)
        return False


class BrowserPage(TogglePage):
    def __init__(self):
        super().__init__(
            "Browser",
            "Browser",
            "Browser (video and audio playback)",
            reason_options=BROWSER_DEFECT_TYPES,
            code_prefix="BR",
            topic="video/audio playback",
            instructions=(
                "Click below to open a test video in Firefox and confirm both "
                "video playback and audio play correctly."
            ),
        )
        self.utils = Utils()

    def build_action(self, box):
        launch_row = Adw.ActionRow()
        launch_row.set_title("Open the test video in a browser")
        launch_button = Gtk.Button(label="Click Here")
        launch_button.set_valign(Gtk.Align.CENTER)
        launch_button.connect("clicked", self._on_launch_clicked)
        launch_row.add_suffix(launch_button)
        group = Adw.PreferencesGroup()
        group.add(launch_row)
        box.append(group)

        self.launch_status = Gtk.Label(label="")
        self.launch_status.set_xalign(0)
        self.launch_status.set_wrap(True)
        box.append(self.launch_status)

    def _on_launch_clicked(self, button):
        _set_status(self.launch_status, "Opening browser...", auto_clear_ms=4000)
        self.utils.launch_app("xdg-open https://vimeo.com/116979416")

    def build_reason_locations(self, entry_row, reason):
        if reason == "Audio":
            return _build_section_picker(
                self,
                entry_row,
                options=SOUND_DEFECT_TYPES,
                title="What's wrong with the sound?",
            )
        return {"type": "none"}


class WebcamPage(TogglePage):
    def __init__(self):
        super().__init__(
            "WebCam",
            "Webcam",
            "Webcam",
            reason_options=WEBCAM_DEFECT_TYPES,
            code_prefix="WC",
            instructions=(
                "Click below to open the webcam test. During it, ensure the "
                "picture is clear and accurate."
            ),
        )
        self.utils = Utils()
        # Detected once at startup, since webcam hardware presence doesn't
        # change during a session -- "present"/"ir_only"/"absent". Anything
        # other than "present" auto-skips this page (see WizardWindow's use
        # of page.skip in spec_v3.py) and reports the hardware situation
        # instead of running the test -- see get_result/get_notes_entries.
        self.webcam_status = Utils.get_webcam_status()
        self.skip = self.webcam_status != "present"
        if self.webcam_status != "present":
            self.passed = True

    def build_action(self, box):
        launch_row = Adw.ActionRow()
        launch_row.set_title("Open the webcam viewer")
        launch_button = Gtk.Button(label="Click Here")
        launch_button.set_valign(Gtk.Align.CENTER)
        launch_button.connect("clicked", self._on_launch_clicked)
        launch_row.add_suffix(launch_button)
        group = Adw.PreferencesGroup()
        group.add(launch_row)
        box.append(group)

        self.launch_status = Gtk.Label(label="")
        self.launch_status.set_xalign(0)
        self.launch_status.set_wrap(True)
        box.append(self.launch_status)

    def _find_non_ir_video_device(self):
        ir_keywords = ["infrared", "ir camera", "windows hello", "ir sensor"]
        for video_path in sorted(glob.glob("/dev/video*")):
            name_file = f"/sys/class/video4linux/{os.path.basename(video_path)}/name"
            try:
                with open(name_file) as f:
                    name = f.read().strip().lower()
                if not any(kw in name for kw in ir_keywords):
                    return video_path
            except OSError:
                pass
        return None

    def _on_launch_clicked(self, button):
        if self.utils.file_exists_and_executable("/usr/bin/guvcview"):
            device = self._find_non_ir_video_device()
            cmd = f"guvcview --device={device}" if device else "guvcview"
            _set_status(self.launch_status, "Launching guvcview...", auto_clear_ms=4000)
            self.utils.launch_app(cmd)
        elif self.utils.file_exists_and_executable("/usr/bin/cheese"):
            _set_status(self.launch_status, "Launching cheese...", auto_clear_ms=4000)
            self.utils.launch_app("cheese")
        elif self.utils.file_exists_and_executable("/usr/bin/snapshot"):
            _set_status(self.launch_status, "Launching snapshot...", auto_clear_ms=4000)
            self.utils.launch_app("snapshot")
        else:
            _set_status(
                self.launch_status,
                "No webcam viewer (guvcview/cheese/snapshot) found on this system",
                is_error=True,
            )

    def build_reason_locations(self, entry_row, reason):
        # No webcam defect has a meaningful location to narrow down.
        if reason == WEBCAM_DEFECT_TYPES[1]:  # "...solid black screen"
            # Many laptops have a physical privacy shutter over the camera
            # lens -- easy to mistake for a dead webcam if it's slid shut.
            entry_row.add_row(
                _build_note_row(
                    "Before reporting this: check for a physical camera "
                    "cover with a moveable switch, and make sure it is "
                    "slid open."
                )
            )
        return {"type": "none"}

    def get_result(self):
        if self.webcam_status != "present":
            return "N/A"
        return super().get_result()

    def get_notes_entries(self):
        if self.webcam_status == "absent":
            return [{"text": WEBCAM_NO_DEVICE_NOTE}]
        if self.webcam_status == "ir_only":
            return [{"text": WEBCAM_IR_ONLY_NOTE}]
        return super().get_notes_entries()


class UsbPortLocationMixin:
    """Shared "pick a location" builder for the split USB-A / USB-C pages
    below -- each page only ever reports on its own port type, so (unlike
    the old combined UsbPortsPage) there's no USB-A/USB-C dropdown to pick
    here."""

    def build_reason_locations(self, entry_row, reason):
        data = {"type": "usb_port", "locations": []}

        def _on_locations_change(selected):
            data["locations"] = selected
            self.check_status()
            _scroll_to_bottom(self.scrolled)

        title = (
            "Location(s)" if reason in self.reason_options else "Location(s) (optional)"
        )
        location_row = _build_section_row(
            title,
            USB_PORT_LOCATIONS,
            columns=len(USB_PORT_LOCATIONS),
            on_change=_on_locations_change,
        )
        entry_row.add_row(location_row)

        return data


class UsbAPage(UsbPortLocationMixin, TogglePage):
    def __init__(self):
        super().__init__(
            "USBA",
            "USB-A Ports",
            "USB-A Ports",
            reason_options=USB_A_DEFECT_TYPES,
            code_prefix="UA",
            topic="USB-A port",
            instructions=(
                "Using a USB mouse, please plug the mouse into each USB-A port "
                "and move it around, ensuring that the cursor moves around on "
                "the screen. Place tape over any USB-A ports that do not work "
                "and report it below."
            ),
        )

    def _reason_code(self, reason):
        return USB_A_REASON_CODES.get(reason) or super()._reason_code(reason)


class UsbCPage(UsbPortLocationMixin, TogglePage):
    def __init__(self):
        super().__init__(
            "USBC",
            "USB-C Ports",
            "USB-C Ports",
            reason_options=USB_C_DEFECT_TYPES,
            code_prefix="UC",
            topic="USB-C port",
            instructions=(
                "Use a provided USB-C dock and USB mouse to test each USB-C "
                "port. Also, plug into each USB-C port upside-down and test "
                "it that way as well. If the only USB-C port present is the "
                "charging port, then you may select yes and move on. Place tape "
                "over any defective USB-C ports and report it below."
            ),
        )

    def _reason_code(self, reason):
        return USB_C_REASON_CODES.get(reason) or super()._reason_code(reason)


class TouchscreenPage(ScreenSectionMixin, TogglePage):
    # Only "Areas of the touchscreen aren't working" (and custom entries,
    # which never match a preset reason) need a location -- the other
    # three reasons apply to the whole touchscreen with nothing to point
    # at.
    NO_LOCATION_REASONS = {
        "The touchscreen doesn't work at all",
        "The cursor freaks out when I touch the screen",
        "Where I touch is not where it registers",
    }

    def __init__(self):
        super().__init__(
            "Touchscreen",
            "Touchscreen",
            "Touchscreen",
            reason_options=TOUCHSCREEN_DEFECT_TYPES,
            code_prefix="TS",
            instructions=(
                "Click below to launch the touchscreen test. During it, "
                "please tap each grey dot with your finger."
            ),
        )

    def build_action(self, box):
        launch_row = Adw.ActionRow()
        launch_row.set_title("Run the fullscreen touchscreen test")
        self.launch_button = Gtk.Button(label="Click Here")
        self.launch_button.set_valign(Gtk.Align.CENTER)
        self.launch_button.connect("clicked", self._on_launch_clicked)
        launch_row.add_suffix(self.launch_button)
        group = Adw.PreferencesGroup()
        group.add(launch_row)
        box.append(group)

    def _on_launch_clicked(self, button):
        # The touchscreen test runs in a subprocess. Touch event delivery
        # in GTK/GDK has been observed to SIGSEGV after a USB pointer
        # device is unplugged; isolating the test in its own process
        # means such a crash only fails the test rather than killing the
        # provisioning app.
        button.set_sensitive(False)
        self.pass_button.set_sensitive(False)
        self.fail_button.set_sensitive(False)

        runner = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            "touchscreen_test_runner.py",
        )

        def _run():
            try:
                result = subprocess.run(
                    [sys.executable, runner],
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
                if result.returncode != 0:
                    print(f"Touchscreen test subprocess exited rc={result.returncode}")
                    if result.stderr:
                        print(result.stderr)
                    passed = False
                else:
                    passed = result.stdout.strip().endswith("pass")
            except Exception as exc:
                print(f"Touchscreen test subprocess error: {exc}")
                passed = False
            GLib.idle_add(self._on_test_complete, passed, button)

        threading.Thread(target=_run, daemon=True).start()

    def _on_test_complete(self, passed, click_button):
        self.pass_button.set_sensitive(True)
        self.fail_button.set_sensitive(True)
        click_button.set_sensitive(True)
        if passed:
            self.pass_button.set_active(True)
        else:
            self.fail_button.set_active(True)
        return False


class KeyboardPage(TogglePage):
    def __init__(self):
        super().__init__(
            "Keyboard",
            "Keyboard",
            "Keyboard",
            reason_options=KEYBOARD_DEFECT_TYPES,
            code_prefix="KB",
            instructions=(
                "Type the sample text below using every key listed at least once, "
                "as well as Backspace, Period, Shift, and Enter, to confirm each key "
                "registers correctly. All keys should respond accurately and "
                "with a normal amount of effort."
            ),
        )

    def _can_mark_no_issues(self):
        return self.typing_test_complete

    def _pass_blocked_message(self):
        return (
            "Please perform the keyboard test before verifying it is in "
            "working condition."
        )

    def build_action(self, box):
        self.typing_test_complete = False
        self.period_pressed = False
        self.backspace_pressed = False
        self.enter_pressed = False
        self.shift_pressed = False
        self._all_chars_typed = False
        self._no_issues_auto_triggered = False
        self.original_text = "The quick brown fox jumps over the lazy dog. 1234567890"

        self.keyboard_template_buffer = Gtk.TextBuffer()
        self.keyboard_template_buffer.set_text(self.original_text)
        self.keyboard_template = Gtk.TextView(buffer=self.keyboard_template_buffer)
        self.keyboard_template.set_editable(False)
        self.keyboard_template.set_cursor_visible(False)
        self.keyboard_template.set_wrap_mode(Gtk.WrapMode.NONE)
        self.keyboard_template.set_hexpand(True)
        self.keyboard_template.set_margin_top(12)
        self.keyboard_template.set_margin_bottom(12)
        self.keyboard_template.set_margin_start(12)
        self.keyboard_template.set_margin_end(12)
        self.keyboard_template.add_css_class("transparent-textview")

        self.green_tag = self.keyboard_template_buffer.create_tag(
            "green", foreground="#3fe35a", weight=700
        )
        self.gray_tag = self.keyboard_template_buffer.create_tag(
            "gray", foreground="#c0c0c0"
        )

        self.ever_typed_chars = set()
        self.ever_typed_chars_lower = set()

        self.shift_label = Gtk.Label(label="Shift")
        self.shift_label.add_css_class("keyboard-key")
        self.shift_label.set_valign(Gtk.Align.CENTER)
        self.shift_label.set_margin_end(6)

        self.period_label = Gtk.Label(label="Period")
        self.period_label.add_css_class("keyboard-key")
        self.period_label.set_valign(Gtk.Align.CENTER)
        self.period_label.set_margin_end(6)

        self.backspace_label = Gtk.Label(label="Backspace")
        self.backspace_label.add_css_class("keyboard-key")
        self.backspace_label.set_valign(Gtk.Align.CENTER)
        self.backspace_label.set_margin_end(6)

        self.enter_label = Gtk.Label(label="Enter")
        self.enter_label.add_css_class("keyboard-key")
        self.enter_label.set_valign(Gtk.Align.CENTER)
        self.enter_label.set_margin_end(12)

        template_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        template_row.append(self.keyboard_template)
        template_row.append(self.shift_label)
        template_row.append(self.period_label)
        template_row.append(self.backspace_label)
        template_row.append(self.enter_label)
        box.append(template_row)

        input_label = Gtk.Label(label="Type here:")
        input_label.set_xalign(0)
        input_label.add_css_class("dim-label")
        box.append(input_label)

        self.keyboard_input_buffer = Gtk.TextBuffer()
        self.keyboard_input_buffer.connect("changed", self._on_keyboard_changed)

        self.keyboard_input_view = Gtk.TextView(buffer=self.keyboard_input_buffer)
        self.keyboard_input_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.keyboard_input_view.set_top_margin(8)
        self.keyboard_input_view.set_bottom_margin(8)
        self.keyboard_input_view.set_left_margin(8)
        self.keyboard_input_view.set_right_margin(8)
        self.keyboard_input_view.connect(
            "paste-clipboard",
            lambda w: GObject.signal_stop_emission_by_name(w, "paste-clipboard"),
        )
        _key_ctrl = Gtk.EventControllerKey()
        _key_ctrl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        _key_ctrl.connect("key-pressed", self._on_keyboard_key_pressed)
        self.keyboard_input_view.add_controller(_key_ctrl)

        input_scroller = Gtk.ScrolledWindow()
        input_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        input_scroller.set_min_content_height(80)
        input_scroller.set_child(self.keyboard_input_view)

        input_frame = Gtk.Frame()
        input_frame.set_child(input_scroller)
        box.append(input_frame)

        self.update_text_highlighting("")

    def _on_keyboard_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_BackSpace:
            self.backspace_label.add_css_class("keyboard-key-passed")
            self.backspace_pressed = True
        elif keyval == Gdk.KEY_period:
            self.period_label.add_css_class("keyboard-key-passed")
            self.period_pressed = True
        elif keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self.enter_label.add_css_class("keyboard-key-passed")
            self.enter_pressed = True
        elif keyval in (Gdk.KEY_Shift_L, Gdk.KEY_Shift_R):
            self.shift_label.add_css_class("keyboard-key-passed")
            self.shift_pressed = True
        self._check_typing_test_complete()
        return False

    def _on_keyboard_changed(self, buffer):
        start = buffer.get_start_iter()
        end = buffer.get_end_iter()
        self.update_text_highlighting(buffer.get_text(start, end, False))

    def update_text_highlighting(self, typed_text):
        self.ever_typed_chars.update(typed_text)
        self.ever_typed_chars_lower.update(c.lower() for c in typed_text)

        start = self.keyboard_template_buffer.get_start_iter()
        end = self.keyboard_template_buffer.get_end_iter()
        self.keyboard_template_buffer.remove_all_tags(start, end)

        all_chars_typed = True

        for index, char in enumerate(self.original_text):
            start_iter = self.keyboard_template_buffer.get_iter_at_offset(index)
            end_iter = self.keyboard_template_buffer.get_iter_at_offset(index + 1)

            matched = char.lower() in self.ever_typed_chars_lower

            if matched:
                self.keyboard_template_buffer.apply_tag(
                    self.green_tag, start_iter, end_iter
                )
            else:
                self.keyboard_template_buffer.apply_tag(
                    self.gray_tag, start_iter, end_iter
                )
                all_chars_typed = False

        self._all_chars_typed = all_chars_typed
        self._check_typing_test_complete()

    def _check_typing_test_complete(self):
        """Every listed key must be typed at least once, plus Period,
        Backspace, Shift, and Enter each pressed at least once, before the
        keyboard test counts as complete. "No" is only ever auto-selected
        the first time this becomes true -- if the tech has since clicked
        "Yes", further key presses must not silently flip it back to
        "No"."""
        if not (
            self._all_chars_typed
            and self.period_pressed
            and self.backspace_pressed
            and self.enter_pressed
            and self.shift_pressed
        ):
            return
        self.typing_test_complete = True
        if not self._no_issues_auto_triggered:
            self._no_issues_auto_triggered = True
            print("KeyboardPage:keyboard_test_completed")
            self.pass_button.set_active(True)

    def _reason_code(self, reason):
        """Overrides TogglePage._reason_code -- every keyboard reason
        except "Physical damage" has a fixed code from KEYBOARD_REASON_CODES
        (position-based numbering doesn't work here since "Physical
        damage" occupies one button but represents 3 codes). "Physical
        damage" itself gets no code (its categories carry their own, see
        PHYSICAL_DAMAGE_CATEGORY_CODES/_physical_damage_notes); a custom
        free-text reason falls back to the generic numberless code."""
        if reason == KEYBOARD_PHYSICAL_DAMAGE_REASON:
            return None
        if reason in KEYBOARD_REASON_CODES:
            return KEYBOARD_REASON_CODES[reason]
        return super()._reason_code(reason)

    def build_reason_locations(self, entry_row, reason):
        if reason == KEYBOARD_PHYSICAL_DAMAGE_REASON:
            return self._build_physical_damage_picker(entry_row)
        if reason in KEYBOARD_NO_KEYS_REASONS:
            # Applies to the whole keyboard -- nothing to point at, just
            # add the reason to the list (see KEYBOARD_NO_KEYS_REASONS).
            return {"type": "none"}
        return self._build_single_keys_picker(entry_row)

    def _build_single_keys_picker(self, entry_row):
        data = {"type": "keys", "selected": []}

        status_row = Adw.ActionRow(title="Affected keys")
        status_label = Gtk.Label(label="No keys selected")
        status_label.add_css_class("dim-label")
        pick_button = Gtk.Button(label="Select Keys")
        pick_button.set_valign(Gtk.Align.CENTER)
        pick_button.connect("clicked", self._on_pick_keys_clicked, data, status_label)
        status_row.add_suffix(status_label)
        status_row.add_suffix(pick_button)
        entry_row.add_row(status_row)

        # Ask which keys are affected right away, as soon as the reason is added.
        GLib.idle_add(self._on_pick_keys_clicked, pick_button, data, status_label)

        return data

    def _on_pick_keys_clicked(self, button, data, status_label):
        root = self.get_root()
        selected = data["selected"]
        initial = ALL_KEYBOARD_KEYS if selected == ENTIRE_KEYBOARD_MARKER else selected
        dialog = KeyPickerDialog(root, initial_selection=initial)

        def _on_done(selected_keys):
            data["selected"] = selected_keys
            if selected_keys == ENTIRE_KEYBOARD_MARKER:
                status_label.set_label("Entire Keyboard")
            else:
                status_label.set_label(
                    ", ".join(selected_keys) if selected_keys else "No keys selected"
                )
            self.check_status()

        dialog.on_done_callback = _on_done
        dialog.present()
        return False

    def _build_physical_damage_picker(self, entry_row):
        """ "Physical damage" doesn't point at a single set of keys -- the
        tech first picks which category/categories of damage apply
        (PHYSICAL_DAMAGE_CATEGORIES), and each category selected gets its
        own "Select Keys" popup (e.g. which keys are worn through vs. which
        are cracked) -- see the "key_categories" cases in
        TogglePage._locations_text/_reason_is_filled."""
        data = {"type": "key_categories", "categories": {}}
        status_widgets = {}

        def _on_category_toggled(button, category):
            status_row, status_label, pick_button = status_widgets[category]
            if button.get_active():
                status_row.set_visible(True)
                data["categories"].setdefault(category, [])
                # Ask which keys are affected right away, as soon as the
                # category is picked.
                GLib.idle_add(
                    self._on_pick_category_keys_clicked,
                    pick_button,
                    category,
                    data,
                    status_label,
                )
            else:
                status_row.set_visible(False)
                data["categories"].pop(category, None)
            self.check_status()

        grid_box, _buttons = _build_toggle_button_grid(
            "What type of damage is present? (Add all that apply)",
            PHYSICAL_DAMAGE_CATEGORIES,
            _on_category_toggled,
            columns=2,
        )
        grid_row = Gtk.ListBoxRow()
        grid_row.set_selectable(False)
        grid_row.set_activatable(False)
        grid_row.set_child(grid_box)
        entry_row.add_row(grid_row)

        for category in PHYSICAL_DAMAGE_CATEGORIES:
            status_row = Adw.ActionRow(title=category)
            status_label = Gtk.Label(label="No keys selected")
            status_label.add_css_class("dim-label")
            pick_button = Gtk.Button(label="Select Keys")
            pick_button.set_valign(Gtk.Align.CENTER)
            pick_button.connect(
                "clicked",
                self._on_pick_category_keys_clicked,
                category,
                data,
                status_label,
            )
            status_row.add_suffix(status_label)
            status_row.add_suffix(pick_button)
            status_row.set_visible(False)
            entry_row.add_row(status_row)
            status_widgets[category] = (status_row, status_label, pick_button)

        return data

    def _on_pick_category_keys_clicked(self, button, category, data, status_label):
        root = self.get_root()
        selected = data["categories"].get(category, [])
        initial = ALL_KEYBOARD_KEYS if selected == ENTIRE_KEYBOARD_MARKER else selected
        dialog = KeyPickerDialog(root, initial_selection=initial)

        def _on_done(selected_keys):
            data["categories"][category] = selected_keys
            if selected_keys == ENTIRE_KEYBOARD_MARKER:
                status_label.set_label("Entire Keyboard")
            else:
                status_label.set_label(
                    ", ".join(selected_keys) if selected_keys else "No keys selected"
                )
            self.check_status()

        dialog.on_done_callback = _on_done
        dialog.present()
        return False

    def get_notes_entries(self):
        """Overrides TogglePage.get_notes_entries -- tracking-sheet notes
        read "<code> <reason> (<keys>)" (e.g. "KB02 Keys do not work (F,
        G)"), or just "<code> <reason>" for the two reasons with no keys to
        list (see KEYBOARD_NO_KEYS_REASONS). "Physical damage" contributes
        one entry per real code its categories map to (see
        _physical_damage_notes). Entries always come out in KB01, KB02, ...
        order regardless of the order reasons/categories were added."""
        if self.passed is not False:
            return []
        if not self._reason_entries:
            return [{"text": "Keyboard: issue reported"}]
        entries = []
        for reason, (entry_row, data) in self._reason_entries.items():
            if reason == KEYBOARD_PHYSICAL_DAMAGE_REASON:
                entries.extend(self._physical_damage_notes(data))
                continue
            code = self._reason_code(reason)
            if data.get("type") == "none":
                entries.append((code, f"{code} {reason}"))
            else:
                loc_text = self._locations_text(data)
                entries.append((code, f"{code} {reason} ({loc_text})"))
        entries.sort(key=lambda entry: self._code_sort_key(entry[0]))
        return [{"text": ", ".join(text for _, text in entries)}]

    def _failed_codes(self):
        """Overrides TogglePage._failed_codes -- "Physical damage" has no
        code of its own, so it contributes whichever real codes its
        selected categories map to (see _physical_damage_notes) instead of
        being skipped entirely."""
        codes = set()
        for reason, (entry_row, data) in self._reason_entries.items():
            if reason == KEYBOARD_PHYSICAL_DAMAGE_REASON:
                codes.update(code for code, _ in self._physical_damage_notes(data))
            else:
                code = self._reason_code(reason)
                if code:
                    codes.add(code)
        return sorted(codes, key=self._code_sort_key)

    def _physical_damage_notes(self, data):
        """ "Physical damage" doesn't have its own code -- each selected
        category reports under its own real KB code instead (see
        PHYSICAL_DAMAGE_CATEGORY_CODES). "Keys are scratched" has no code
        of its own; per user direction it merges into the same KB04 entry
        as "Keys are cracked" (their key sets are combined)."""
        categories = data.get("categories") or {}
        code_keys = {}
        for category, keys in categories.items():
            code = PHYSICAL_DAMAGE_CATEGORY_CODES[category]
            existing = code_keys.setdefault(code, [])
            if keys == ENTIRE_KEYBOARD_MARKER or existing == ENTIRE_KEYBOARD_MARKER:
                code_keys[code] = ENTIRE_KEYBOARD_MARKER
            else:
                for key in keys:
                    if key not in existing:
                        existing.append(key)

        notes = []
        for code, keys in code_keys.items():
            label = PHYSICAL_DAMAGE_CODE_LABELS[code]
            if keys == ENTIRE_KEYBOARD_MARKER:
                key_text = "Entire Keyboard"
            else:
                key_text = ", ".join(keys) if keys else "no keys specified"
            notes.append((code, f"{code} {label} ({key_text})"))
        return notes
