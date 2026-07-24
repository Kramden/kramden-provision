import glob
import os
import subprocess
import sys
import threading

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gdk, GLib, GObject, Gtk
from drawing_utils import draw_screen_outline_and_strokes
from utils import Utils

# The screen-defect drawing canvas hands cairo.Context objects across the
# GTK/Python boundary in its draw_func; that marshalling only works once the
# cairo foreign struct converter is registered, and only if python3-gi-cairo
# is installed. Handle its absence gracefully rather than crashing the app.
try:
    gi.require_foreign("cairo")
    _CAIRO_FOREIGN_AVAILABLE = True
except (ImportError, ValueError) as _cairo_exc:
    _CAIRO_FOREIGN_AVAILABLE = False
    print(
        "manualtest_v3: gi.require_foreign('cairo') unavailable "
        f"({_cairo_exc}); install python3-gi-cairo to enable the screen "
        "defect drawing tool"
    )

CUSTOM_OPTION = "Custom..."

# Placeholder option lists. Real content to be filled in later — these exist
# only so the dropdowns/checklists have something selectable to preview the
# layout with.
PLACEHOLDER_REASONS = ["Reason option 1", "Reason option 2", "Reason option 3"]
PLACEHOLDER_DEFECT_TYPES = [
    "Dents",
    "Deep Scratches",
    "Peeling Paint",
    "Cracks",
    "Broken Part",
]
PLACEHOLDER_LOCATIONS = [
    "Top",
    "Bottom",
    "Left Side",
    "Right Side",
    "A Corner(s)",
]
PLACEHOLDER_INSTRUCTIONS = "(Instructions for this test will go here)"

# Readable against both the app's dark theme and an accidental light theme --
# plain "dim-label" text was too low-contrast (grey on grey) to read easily.
INSTRUCTIONS_COLOR = "#62a0ea"

USB_DEFECT_TYPES = [
    "Not Detecting Device",
    "Loose Connection",
    "Physically Damaged",
]
USB_PORT_TYPES = ["USB-A", "USB-C"]
USB_PORT_LOCATIONS = ["Left Side", "Right Side", "Back"]

# "Audio" must be an exact defect-type option (not free text) so the tracking
# sheet can key off it directly to fill in the "Sound:" field -- see
# TogglePage.has_reason() and SpecCompleteV3._on_tracking_clicked.
BROWSER_DEFECT_TYPES = ["Video", "Audio"]

WIFI_DEFECT_TYPES = [
    "Won't Connect",
    "Connection Drops",
    "Slow/Unstable Speed",
    "No WiFi Adapter Detected",
]

TOUCHPAD_DEFECT_TYPES = [
    "Cursor Doesn't Move",
    "Erratic/Jumpy Cursor",
    "Left Click Not Working",
    "Right Click Not Working",
    "Physical Click Not Working",
]

TOUCHPAD_LOCATIONS = [
    "Top of touchpad",
    "Bottom of touchpad",
    "Right side of touchpad",
    "Left side of touchpad",
    "Center of touchpad",
    "Entire touchpad",
]

SCREEN_DEFECT_TYPES = [
    "Dead Pixels",
    "Discoloration",
    "Flickering",
    "Light Spots",
    "Dim/Won't Light",
    "Cracked/Physical Damage",
]

WEBCAM_DEFECT_TYPES = [
    "No Image",
    "Blurry/Out of Focus",
    "Discolored Image",
    "Frozen/Lagging Image",
]

TOUCHSCREEN_DEFECT_TYPES = [
    "Touch Not Registering",
    "Inaccurate Touch Location",
    "Unresponsive Area",
]

KEYBOARD_DEFECT_TYPES = [
    "Key(s) Not Registering",
    "Key(s) Sticking",
    "Key(s) Double-Typing",
    "Key(s) Physically Damaged/Missing",
    "Key(s) Require Extra Force to Register",
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


def _build_location_checkboxes(parent_expander_row, options=PLACEHOLDER_LOCATIONS):
    """Add a checkbox row per option to an Adw.ExpanderRow and return the
    (label, checkbutton) pairs so callers can read back what was checked.
    """
    items = []
    for location in options:
        location_row = Adw.ActionRow()
        checkbutton = Gtk.CheckButton()
        location_row.add_prefix(checkbutton)
        location_row.set_title(location)
        location_row.set_activatable(True)
        location_row.connect(
            "activated",
            lambda row, cb=checkbutton: cb.set_active(not cb.get_active()),
        )
        parent_expander_row.add_row(location_row)
        items.append((location, checkbutton))
    return items


def _checked_labels(items):
    return [label for label, checkbutton in items if checkbutton.get_active()]


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


class ScreenDrawDialog(Gtk.Window):
    """Small popup with a laptop-screen-shaped canvas the user can draw on
    (mouse drag) to mark where on the screen the defect is, instead of
    picking from a generic preset location list."""

    def __init__(self, parent, strokes=None, description=""):
        super().__init__(
            transient_for=parent, modal=True, title="Mark Location on Screen"
        )
        self.set_default_size(380, 340)
        self.strokes = strokes if strokes is not None else []
        self._current_stroke = None
        self.on_done_callback = None

        header = Gtk.HeaderBar()
        header.set_show_title_buttons(False)
        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", lambda b: self.close())
        clear_button = Gtk.Button(label="Clear")
        clear_button.connect("clicked", self._on_clear)
        done_button = Gtk.Button(label="Done")
        done_button.add_css_class("suggested-action")
        done_button.connect("clicked", self._on_done)
        header.pack_start(cancel_button)
        header.pack_start(clear_button)
        header.pack_end(done_button)
        self.set_titlebar(header)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)

        instructions = Gtk.Label(
            label="Draw on the screen outline below to mark the location of the issue."
        )
        instructions.set_wrap(True)
        content.append(instructions)

        entire_screen_button = Gtk.Button(label="Entire Screen")
        entire_screen_button.set_halign(Gtk.Align.START)
        entire_screen_button.connect("clicked", self._on_entire_screen)
        content.append(entire_screen_button)

        self.drawing_area = Gtk.DrawingArea()
        self.drawing_area.set_content_width(320)
        self.drawing_area.set_content_height(200)
        self.drawing_area.set_hexpand(True)
        self.drawing_area.set_vexpand(True)
        self.drawing_area.set_draw_func(self._draw, None)

        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", self._on_drag_begin)
        drag.connect("drag-update", self._on_drag_update)
        drag.connect("drag-end", self._on_drag_end)
        self.drawing_area.add_controller(drag)

        frame = Gtk.Frame()
        frame.set_child(self.drawing_area)
        content.append(frame)

        description_label = Gtk.Label(label="Description (optional):")
        description_label.set_halign(Gtk.Align.START)
        content.append(description_label)

        self.description_entry = Gtk.Entry()
        self.description_entry.set_hexpand(True)
        self.description_entry.set_placeholder_text(
            "e.g. hairline crack near top-left corner"
        )
        if description:
            self.description_entry.set_text(description)
        content.append(self.description_entry)

        self.set_child(content)

    def _draw(self, area, ctx, width, height, data):
        draw_screen_outline_and_strokes(ctx, width, height, self.strokes)

    def _on_drag_begin(self, gesture, start_x, start_y):
        width = self.drawing_area.get_width() or 1
        height = self.drawing_area.get_height() or 1
        self._current_stroke = [(start_x / width, start_y / height)]
        self.strokes.append(self._current_stroke)

    def _on_drag_update(self, gesture, offset_x, offset_y):
        if self._current_stroke is None:
            return
        ok, start_x, start_y = gesture.get_start_point()
        if not ok:
            return
        width = self.drawing_area.get_width() or 1
        height = self.drawing_area.get_height() or 1
        self._current_stroke.append(
            ((start_x + offset_x) / width, (start_y + offset_y) / height)
        )
        self.drawing_area.queue_draw()

    def _on_drag_end(self, gesture, offset_x, offset_y):
        self._current_stroke = None

    def _on_clear(self, button):
        self.strokes.clear()
        self.drawing_area.queue_draw()

    def _on_entire_screen(self, button):
        # Mark the whole screen with a clear corner-to-corner X rather than
        # inventing a separate "entire screen" data representation -- it's
        # still a normal strokes list, so every downstream consumer
        # (preview thumbnail, tracking sheet diagram embed) just works.
        self.strokes.clear()
        width = self.drawing_area.get_width() or 320
        height = self.drawing_area.get_height() or 200
        margin_px = max(3, min(width, height) * 0.06)
        mx = margin_px / width
        my = margin_px / height
        self.strokes.append([(mx, my), (1 - mx, 1 - my)])
        self.strokes.append([(1 - mx, my), (mx, 1 - my)])
        self.drawing_area.queue_draw()

    def _on_done(self, button):
        if self.on_done_callback:
            self.on_done_callback(self.strokes, self.description_entry.get_text().strip())
        self.close()


class TogglePage(Adw.Bin):
    """Base page: instructions placeholder, an optional subclass-provided test
    action, and a No Issues/Has Issues toggle. When "Has Issues" is active,
    the user can add one or more failure reasons, each with its own set of
    affected locations.
    """

    def __init__(
        self,
        key,
        page_title,
        row_title,
        pass_label="No Issues",
        fail_label="Has Issues",
        reason_options=None,
        instructions=PLACEHOLDER_INSTRUCTIONS,
    ):
        super().__init__()
        self.key = key
        self.title = page_title
        self.skip = False
        self.passed = None
        self.state = None
        self._reason_entries = {}
        self.reason_options = reason_options or PLACEHOLDER_REASONS

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
        instructions_group = Adw.PreferencesGroup(title="Instructions")
        instructions_row = Adw.ActionRow()
        instructions_row.set_icon_name("dialog-information-symbolic")
        instructions_row.set_title(
            f"<span foreground='{INSTRUCTIONS_COLOR}'>"
            f"{GLib.markup_escape_text(instructions)}</span>"
        )
        instructions_group.add(instructions_row)
        vbox.append(instructions_group)

        # Hook for subclasses to add a launcher button, typing box, etc.
        self.action_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.append(self.action_box)
        self.build_action(self.action_box)

        # No Issues / Has Issues toggle
        result_group = Adw.PreferencesGroup(title="Result")
        toggle_row = Adw.ActionRow()
        toggle_row.set_title("No Issues / Has Issues")

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

        # Failure reasons, revealed only when "Has Issues" is selected.
        # Multiple reasons can be added, each with its own location detail.
        self.reason_revealer = Gtk.Revealer()
        self.reason_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)

        reasons_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        add_group = Adw.PreferencesGroup(title="Add a failure reason")
        add_row = Adw.ActionRow()
        add_row.set_title("Reason")
        self.reason_dropdown = Gtk.DropDown(
            model=Gtk.StringList.new(self.reason_options + [CUSTOM_OPTION])
        )
        self.reason_dropdown.set_valign(Gtk.Align.CENTER)
        self.reason_dropdown.connect(
            "notify::selected", self._on_reason_dropdown_changed
        )
        add_button = Gtk.Button(label="Add")
        add_button.set_valign(Gtk.Align.CENTER)
        add_button.connect("clicked", self._on_add_reason_clicked)
        add_row.add_suffix(self.reason_dropdown)
        add_row.add_suffix(add_button)
        add_group.add(add_row)
        reasons_content.append(add_group)

        # Free-text entry, revealed only when "Custom..." is selected above
        self.custom_reason_revealer = Gtk.Revealer()
        self.custom_reason_revealer.set_transition_type(
            Gtk.RevealerTransitionType.SLIDE_DOWN
        )
        custom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        custom_box.set_margin_start(12)
        custom_box.set_margin_end(12)
        custom_label = Gtk.Label(label="Describe the issue:")
        self.custom_reason_entry = Gtk.Entry()
        self.custom_reason_entry.set_hexpand(True)
        custom_box.append(custom_label)
        custom_box.append(self.custom_reason_entry)
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

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_child(vbox)
        self.set_child(scrolled)

    def build_action(self, box):
        """Override in subclasses to add page-specific test controls."""
        pass

    def build_reason_locations(self, entry_row, reason):
        """Override in subclasses to replace the default preset-location
        checkboxes with a custom picker (see KeyboardPage, ScreenPage), or to
        skip location entirely for reasons where it doesn't apply (see
        TouchpadPage)."""
        items = _build_location_checkboxes(entry_row)
        return {"type": "checkboxes", "items": items}

    def _can_mark_no_issues(self):
        """Override in subclasses to require some condition (e.g. an actual
        test being run) before "No Issues" can be selected."""
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

    def _on_fail_toggled(self, button):
        if button.get_active():
            self.pass_button.set_active(False)
            button.add_css_class("toggle-fail-active")
            self.reason_revealer.set_reveal_child(True)
            self.pass_warning_label.set_visible(False)
            self.passed = False
            self.check_status()
        else:
            button.remove_css_class("toggle-fail-active")
            if not self.pass_button.get_active():
                self.reason_revealer.set_reveal_child(False)

    def _on_reason_dropdown_changed(self, dropdown, param):
        item = dropdown.get_selected_item()
        is_custom = item is not None and item.get_string() == CUSTOM_OPTION
        self.custom_reason_revealer.set_reveal_child(is_custom)

    def _on_add_reason_clicked(self, button):
        item = self.reason_dropdown.get_selected_item()
        if item is None:
            return
        reason = item.get_string()
        if reason == CUSTOM_OPTION:
            reason = self.custom_reason_entry.get_text().strip()
            if not reason:
                return
            self.custom_reason_entry.set_text("")
        if reason in self._reason_entries:
            return

        entry_row = Adw.ExpanderRow(title=reason)

        remove_button = Gtk.Button(label="Remove")
        remove_button.set_valign(Gtk.Align.CENTER)
        remove_button.connect(
            "clicked", self._on_remove_reason_clicked, reason, entry_row
        )
        entry_row.add_action(remove_button)

        data = self.build_reason_locations(entry_row, reason)

        entry_row.set_expanded(True)
        self.reasons_list_box.append(entry_row)
        self._reason_entries[reason] = (entry_row, data)
        self.reason_dropdown.set_selected(0)
        self.check_status()

    def _on_remove_reason_clicked(self, button, reason, entry_row):
        self.reasons_list_box.remove(entry_row)
        self._reason_entries.pop(reason, None)
        self.check_status()

    def _locations_text(self, data):
        kind = data.get("type")
        if kind == "none":
            return None
        if kind == "checkboxes":
            labels = _checked_labels(data["items"])
            return ", ".join(labels) if labels else "no location specified"
        if kind == "keys":
            keys = data.get("selected") or []
            if keys == ENTIRE_KEYBOARD_MARKER:
                return "Entire Keyboard"
            return f"keys: {', '.join(keys)}" if keys else "no keys specified"
        if kind == "drawing":
            if not data.get("strokes"):
                return "no location marked"
            description = (data.get("description") or "").strip()
            return (
                f"custom location marked: {description}"
                if description
                else "custom location marked"
            )
        if kind == "usb_port":
            usb_type = data["type_dropdown"].get_selected_item().get_string()
            location = data["location_dropdown"].get_selected_item().get_string()
            port_num = data["number_entry"].get_text().strip()
            text = f"{usb_type}, {location}"
            if port_num:
                text += f" (port #{port_num})"
            return text
        return "no location specified"

    def is_complete(self):
        return self.passed is not None

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

    def get_failure_reasons(self):
        """All reported reasons are concatenated onto a single "{title}
        failed: ..." string (rather than one per reason) so the Spec
        Complete screen doesn't spend a row per reason on the same test."""
        if self.passed is False:
            if not self._reason_entries:
                return [f"{self.title} failed: no reason specified"]
            details = []
            for reason, (entry_row, data) in self._reason_entries.items():
                loc_text = self._locations_text(data)
                if loc_text:
                    details.append(f"{reason} ({loc_text})")
                else:
                    details.append(reason)
            return [f"{self.title} failed: " + ", ".join(details)]
        if self.passed is None:
            return [f"{self.title} not completed"]
        return []

    def get_notes_entries(self):
        """All reported reasons for this page are concatenated onto a
        single "{title}:" line (rather than one line per reason) so
        multiple issues on the same test read as a single grouped note.
        Each drawing-based reason keeps its own separate diagram (they mark
        up different defects), but all of them are placed side by side on
        one subsequent line rather than one diagram line per reason."""
        if self.passed is not False:
            return []
        if not self._reason_entries:
            return [{"text": f"{self.title}: issue reported"}]
        details = []
        diagrams = []
        for reason, (entry_row, data) in self._reason_entries.items():
            if data.get("type") == "drawing" and data.get("strokes"):
                description = (data.get("description") or "").strip()
                if description:
                    details.append(f"{reason} (see diagram: {description})")
                else:
                    details.append(f"{reason} (see diagram)")
                diagrams.append(data["strokes"])
            else:
                loc_text = self._locations_text(data)
                if loc_text:
                    details.append(f"{reason} ({loc_text})")
                else:
                    details.append(reason)
        entry = {"text": f"{self.title}: " + ", ".join(details)}
        if diagrams:
            entry["image_strokes_list"] = diagrams
        return [entry]

    def get_result(self):
        if self.passed is None:
            return "Untested"
        return "Pass" if self.passed else "Fail"

    def on_shown(self):
        self.check_status()


class PhysicalDefectsPage(Adw.Bin):
    def __init__(self):
        super().__init__()
        self.key = "PhysicalDefects"
        self.title = "Physical Defects"
        self.skip = False
        self.has_defects = None
        self.state = None
        self._defect_entries = {}

        self.set_margin_top(24)
        self.set_margin_bottom(24)
        self.set_margin_start(24)
        self.set_margin_end(24)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)

        header = Gtk.Label(label="Physical Defects")
        header.add_css_class("title-3")
        header.set_halign(Gtk.Align.START)
        vbox.append(header)

        instructions_group = Adw.PreferencesGroup(title="Instructions")
        instructions_row = Adw.ActionRow()
        instructions_row.set_icon_name("dialog-information-symbolic")
        instructions_row.set_title(
            f"<span foreground='{INSTRUCTIONS_COLOR}'>"
            "Please inspect the machine for any physical damage. Make sure to "
            "open the laptop lid and look at the bottom, top, sides, and "
            "corners for possible defects. If you find none, click 'No Defects'. "
            "If you do find some, click 'Defects Present' and add the "
            "defects that you found, specifying where you found them."
            "</span>"
        )
        instructions_group.add(instructions_row)
        vbox.append(instructions_group)

        result_group = Adw.PreferencesGroup(title="Result")
        toggle_row = Adw.ActionRow()
        toggle_row.set_title("No Defects / Defects Present")

        toggle_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        toggle_box.add_css_class("linked")
        self.no_defects_button = Gtk.ToggleButton(label="No Defects")
        self.defects_present_button = Gtk.ToggleButton(label="Defects Present")
        self.no_defects_button.set_valign(Gtk.Align.CENTER)
        self.defects_present_button.set_valign(Gtk.Align.CENTER)
        self.no_defects_button.connect("toggled", self._on_no_defects_toggled)
        self.defects_present_button.connect("toggled", self._on_defects_present_toggled)
        toggle_box.append(self.no_defects_button)
        toggle_box.append(self.defects_present_button)
        toggle_row.add_suffix(toggle_box)
        result_group.add(toggle_row)
        vbox.append(result_group)

        # Revealed only when "Defects Present" is selected
        self.defects_revealer = Gtk.Revealer()
        self.defects_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)

        defects_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        add_group = Adw.PreferencesGroup(title="Add a defect")
        add_row = Adw.ActionRow()
        add_row.set_title("Defect type")
        self.defect_type_dropdown = Gtk.DropDown(
            model=Gtk.StringList.new(PLACEHOLDER_DEFECT_TYPES + [CUSTOM_OPTION])
        )
        self.defect_type_dropdown.set_valign(Gtk.Align.CENTER)
        self.defect_type_dropdown.connect(
            "notify::selected", self._on_defect_type_dropdown_changed
        )
        add_button = Gtk.Button(label="Add")
        add_button.set_valign(Gtk.Align.CENTER)
        add_button.connect("clicked", self._on_add_defect_clicked)
        add_row.add_suffix(self.defect_type_dropdown)
        add_row.add_suffix(add_button)
        add_group.add(add_row)
        defects_content.append(add_group)

        # Free-text entry, revealed only when "Custom..." is selected above
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
        custom_box.append(custom_label)
        custom_box.append(self.custom_defect_entry)
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

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_child(vbox)
        self.set_child(scrolled)

    def _on_no_defects_toggled(self, button):
        if button.get_active():
            self.defects_present_button.set_active(False)
            button.add_css_class("toggle-pass-active")
            self.defects_revealer.set_reveal_child(False)
            self.has_defects = False
            self.check_status()
        else:
            button.remove_css_class("toggle-pass-active")

    def _on_defects_present_toggled(self, button):
        if button.get_active():
            self.no_defects_button.set_active(False)
            button.add_css_class("toggle-fail-active")
            self.defects_revealer.set_reveal_child(True)
            self.has_defects = True
            self.check_status()
        else:
            button.remove_css_class("toggle-fail-active")
            if not self.no_defects_button.get_active():
                self.defects_revealer.set_reveal_child(False)

    def _on_defect_type_dropdown_changed(self, dropdown, param):
        item = dropdown.get_selected_item()
        is_custom = item is not None and item.get_string() == CUSTOM_OPTION
        self.custom_defect_revealer.set_reveal_child(is_custom)

    def _on_add_defect_clicked(self, button):
        item = self.defect_type_dropdown.get_selected_item()
        if item is None:
            return
        defect_type = item.get_string()
        if defect_type == CUSTOM_OPTION:
            defect_type = self.custom_defect_entry.get_text().strip()
            if not defect_type:
                return
            self.custom_defect_entry.set_text("")
        if defect_type in self._defect_entries:
            return

        entry_row = Adw.ExpanderRow(title=defect_type)

        remove_button = Gtk.Button(label="Remove")
        remove_button.set_valign(Gtk.Align.CENTER)
        remove_button.connect(
            "clicked", self._on_remove_defect_clicked, defect_type, entry_row
        )
        entry_row.add_action(remove_button)

        data = self._build_defect_details(defect_type, entry_row)

        entry_row.set_expanded(True)
        self.defects_list_box.append(entry_row)
        self._defect_entries[defect_type] = (entry_row, data)
        self.defect_type_dropdown.set_selected(0)
        self.check_status()

    def _build_defect_details(self, defect_type, entry_row):
        if defect_type.strip().lower() == "broken part":
            part_row = Adw.ActionRow(title="What part is broken?")
            part_entry = Gtk.Entry()
            part_entry.set_placeholder_text("e.g. hinge, keyboard, screen bezel")
            part_entry.set_hexpand(True)
            part_row.add_suffix(part_entry)
            entry_row.add_row(part_row)

            location_row = Adw.ActionRow(title="Where on the device? (optional)")
            location_entry = Gtk.Entry()
            location_entry.set_placeholder_text("optional")
            location_entry.set_hexpand(True)
            location_row.add_suffix(location_entry)
            entry_row.add_row(location_row)

            return {
                "type": "broken_part",
                "part_entry": part_entry,
                "location_entry": location_entry,
            }

        items = _build_location_checkboxes(entry_row)
        return {"type": "checkboxes", "items": items}

    def _on_remove_defect_clicked(self, button, defect_type, entry_row):
        self.defects_list_box.remove(entry_row)
        self._defect_entries.pop(defect_type, None)
        self.check_status()

    def is_complete(self):
        return self.has_defects is not None

    def check_status(self):
        if self.state is None:
            return
        state = self.state.get_value()
        state[self.key] = self.has_defects is False
        print(f"{self.key}:check_status {self.has_defects}")

    def get_failure_reasons(self):
        """All reported defects are concatenated onto a single "Physical:"
        string (rather than one per defect type), matching get_notes_entries
        and keeping the Spec Complete screen from spending a row per defect."""
        if self.has_defects is None:
            return ["Physical defects check not completed"]
        if not self.has_defects:
            return []
        if not self._defect_entries:
            return ["Physical defects present"]
        details = []
        for defect_type, (entry_row, data) in self._defect_entries.items():
            if data.get("type") == "broken_part":
                part = data["part_entry"].get_text().strip() or "unspecified part"
                location = data["location_entry"].get_text().strip()
                detail = f"{part}, {location}" if location else part
                details.append(f"{defect_type} ({detail})")
            else:
                locations = _checked_labels(data["items"])
                loc_text = (
                    ", ".join(locations) if locations else "no location specified"
                )
                details.append(f"{defect_type} ({loc_text})")
        return ["Physical: " + ", ".join(details)]

    def get_notes_entries(self):
        """All reported defects are concatenated onto a single "Physical:"
        line (rather than one line per defect type) so damages affecting
        the device read as a single grouped note, e.g. "Physical: Broken
        Part (hinge), Deep Scratches (Top, Left Side)"."""
        if self.has_defects is not True:
            return []
        if not self._defect_entries:
            return [{"text": "Physical: issue reported"}]
        details = []
        for defect_type, (entry_row, data) in self._defect_entries.items():
            if data.get("type") == "broken_part":
                part = data["part_entry"].get_text().strip() or "unspecified part"
                location = data["location_entry"].get_text().strip()
                detail = f"{part}, {location}" if location else part
                details.append(f"{defect_type} ({detail})")
            else:
                locations = _checked_labels(data["items"])
                loc_text = (
                    ", ".join(locations) if locations else "no location specified"
                )
                details.append(f"{defect_type} ({loc_text})")
        return [{"text": "Physical: " + ", ".join(details)}]

    def get_result(self):
        if self.has_defects is None:
            return "Untested"
        return "Fail" if self.has_defects else "Pass"

    def on_shown(self):
        self.check_status()


class WiFiPage(TogglePage):
    def __init__(self):
        super().__init__(
            "WiFi",
            "WiFi",
            "WiFi Connectivity",
            reason_options=WIFI_DEFECT_TYPES,
            instructions=(
                "Connect to a Wi-Fi network and confirm the connection is "
                "stable. This page is skipped automatically once a "
                "connection is detected."
            ),
        )

    def _is_wifi_connected(self):
        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "TYPE,STATE", "device"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in result.stdout.strip().splitlines():
                parts = line.split(":")
                if len(parts) == 2 and parts[0] == "wifi" and parts[1] == "connected":
                    return True
            return False
        except Exception:
            return False

    def on_shown(self):
        connected = self._is_wifi_connected()
        self.skip = connected
        if connected:
            self.passed = True
        if self.state is not None:
            state = self.state.get_value()
            state[self.key] = connected or bool(self.passed)
        print(f"WiFi:on_shown connected={connected} skip={self.skip}")


class TouchpadPage(TogglePage):
    def __init__(self):
        super().__init__(
            "Touchpad",
            "Touchpad",
            "Touchpad",
            reason_options=TOUCHPAD_DEFECT_TYPES,
            instructions=(
                "When testing the touchpad, please make sure to test all left"
                " and right click buttons, including pressing down on the"
                " touchpad to click if that is a feature. Of course, also"
                " ensure when moving your finger across the touchpad that the"
                " cursor moves cleanly and accurately. If the touchpad works "
                "properly, click 'No Issues'. If it doesn't, click 'Has Issues' "
                "and make sure to specify what the issue is."
            ),
        )

    NO_LOCATION_REASONS = {
        "Left Click Not Working",
        "Right Click Not Working",
        "Physical Click Not Working",
    }

    def build_reason_locations(self, entry_row, reason):
        if reason in self.NO_LOCATION_REASONS:
            return {"type": "none"}
        items = _build_location_checkboxes(entry_row, options=TOUCHPAD_LOCATIONS)
        return {"type": "checkboxes", "items": items}


class DrawableLocationMixin:
    """Shared "draw the defect location on a laptop-screen-shaped canvas"
    picker, used by both ScreenPage and TouchscreenPage."""

    def build_reason_locations(self, entry_row, reason):
        data = {"type": "drawing", "strokes": [], "description": ""}

        status_row = Adw.ActionRow(title="Location on screen")
        status_label = Gtk.Label(label="No location marked")
        status_label.add_css_class("dim-label")
        mark_button = Gtk.Button(label="Mark Location")
        mark_button.set_valign(Gtk.Align.CENTER)
        mark_button.connect(
            "clicked", self._on_mark_location_clicked, data, status_label
        )
        status_row.add_suffix(status_label)
        status_row.add_suffix(mark_button)
        entry_row.add_row(status_row)

        preview_row = Adw.ActionRow()
        preview_area = Gtk.DrawingArea()
        preview_area.set_content_width(120)
        preview_area.set_content_height(75)
        preview_area.set_draw_func(
            lambda area, ctx, w, h, _: draw_screen_outline_and_strokes(
                ctx, w, h, data["strokes"]
            )
        )
        preview_row.add_suffix(preview_area)
        entry_row.add_row(preview_row)
        data["preview_area"] = preview_area

        # Ask for the location right away, as soon as the reason is added.
        GLib.idle_add(self._on_mark_location_clicked, mark_button, data, status_label)

        return data

    def _on_mark_location_clicked(self, button, data, status_label):
        if not _CAIRO_FOREIGN_AVAILABLE:
            _set_status(
                status_label,
                "Drawing tool unavailable (missing python3-gi-cairo package)",
                is_error=True,
            )
            return False
        root = self.get_root()
        dialog = ScreenDrawDialog(
            root, strokes=data["strokes"], description=data.get("description", "")
        )

        def _on_done(strokes, description):
            data["strokes"] = strokes
            data["description"] = description
            status_label.set_label(
                "Location marked" if strokes else "No location marked"
            )
            preview = data.get("preview_area")
            if preview:
                preview.queue_draw()
            self.check_status()

        dialog.on_done_callback = _on_done
        dialog.present()
        return False


class ScreenPage(DrawableLocationMixin, TogglePage):
    def __init__(self):
        super().__init__(
            "ScreenTest",
            "Screen",
            "Screen",
            reason_options=SCREEN_DEFECT_TYPES,
            instructions=(
                "Click below to launch the screen test pattern and check "
                "for dead pixels, discoloration, flickering, and light spots. "
                "During the screen test, please make sure to wipe down the "
                "screen with a slightly damp rag to help ensure that flaws "
                "on the screen are real damage rather than just dirtiness."
                "If there are no issues, click 'No Issues'. Otherwise, click "
                "'Has Issues' and choose which issues are present and, on the "
                "pop-up, draw where the issue is on the screen or click "
                "'Entire Screen' if it affects the whole screen."
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
            instructions=(
                "Click below to open a test video in Firefox and confirm both "
                "video playback and audio play correctly. If both work, click "
                "'No Issues'. Otherwise, click 'Has Issues', and choose which "
                "problem(s) was present."
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
        return {"type": "none"}


class WebcamPage(TogglePage):
    def __init__(self):
        super().__init__(
            "WebCam",
            "Webcam",
            "Webcam",
            reason_options=WEBCAM_DEFECT_TYPES,
            instructions=(
                "Click below to open the webcam viewer and confirm the "
                "camera captures a clear, working image. If the webcam works "
                "click 'No Issues'. Otherwise, click 'Has Issues', and specify "
                "what the issue is."
            ),
        )
        self.utils = Utils()

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
        return {"type": "none"}


class UsbPortsPage(TogglePage):
    def __init__(self):
        super().__init__(
            "USB",
            "USB Ports",
            "USB Ports",
            reason_options=USB_DEFECT_TYPES,
            instructions=(
                "Using a USB mouse, please plug the mouse into each USB port and "
                "move it around, ensuring that the cursor moves around on screen. "
                "For the USB-C port, use a provided USB-C dock and USB mouse "
                "to test the USB-C ports the same way, also flip the USB-C plug "
                "on the dock around and plug into the USB-C port to ensure the "
                "port works both ways. If there are multiple USB ports of the "
                "same type (USB-A vs. USB-C) on the same side of the device, "
                "specify a number to indicate this. USB ports closer to the "
                "screen hinge are lower numbers and increase with distance "
                "from the hinge. USB ports on the back of the laptop will "
                "increase as they move from left to right."
            ),
        )

    def build_reason_locations(self, entry_row, reason):
        data = {"type": "usb_port"}

        type_row = Adw.ActionRow(title="USB Type")
        type_dropdown = Gtk.DropDown(model=Gtk.StringList.new(USB_PORT_TYPES))
        type_dropdown.set_valign(Gtk.Align.CENTER)
        type_row.add_suffix(type_dropdown)
        entry_row.add_row(type_row)
        data["type_dropdown"] = type_dropdown

        location_row = Adw.ActionRow(title="Location")
        location_dropdown = Gtk.DropDown(model=Gtk.StringList.new(USB_PORT_LOCATIONS))
        location_dropdown.set_valign(Gtk.Align.CENTER)
        location_row.add_suffix(location_dropdown)
        entry_row.add_row(location_row)
        data["location_dropdown"] = location_dropdown

        number_row = Adw.ActionRow(
            title="Port #",
            subtitle="Only needed if there are multiple of this type on this side",
        )
        number_entry = Gtk.Entry()
        number_entry.set_max_length(1)
        number_entry.set_placeholder_text("optional")
        number_entry.set_input_purpose(Gtk.InputPurpose.DIGITS)
        number_entry.set_size_request(48, -1)
        number_entry.connect("insert-text", self._on_port_number_insert_text)
        number_row.add_suffix(number_entry)
        entry_row.add_row(number_row)
        data["number_entry"] = number_entry

        return data

    def _on_port_number_insert_text(self, entry, text, length, position):
        if text and not text.isdigit():
            GObject.signal_stop_emission_by_name(entry, "insert-text")


class TouchscreenPage(DrawableLocationMixin, TogglePage):
    def __init__(self):
        super().__init__(
            "Touchscreen",
            "Touchscreen",
            "Touchscreen",
            reason_options=TOUCHSCREEN_DEFECT_TYPES,
            instructions=(
                "Click below to run the fullscreen touchscreen test and "
                "confirm touch input registers accurately across the "
                "entire screen. If the touchscreen works, click 'No Issues'. "
                "Otherwise, click 'Has Issues' and, on the pop-up, use the "
                "touchpad or a USB mouse to draw where on the screen the "
                "touchscreen doesn't work or click the button 'Entire Screen'."
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
            instructions=(
                "Type the sample text below using every key listed at least once, "
                "as well as Backspace and Period, to confirm each key "
                "registers correctly. If the keyboard works, click 'No Issues'. "
                "If any keys have a problem, click 'Has Issues' and fill in "
                "what the issue(s) is and which keys it affects using the popup "
                "keyboard."
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
        self.original_text = "The quick brown fox jumps over the lazy dog 1234567890"

        template_group = Adw.PreferencesGroup()

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
            "green", foreground="green", weight=700
        )
        self.gray_tag = self.keyboard_template_buffer.create_tag(
            "gray", foreground="#c0c0c0"
        )

        self.ever_typed_chars = set()
        self.ever_typed_chars_lower = set()

        self.period_label = Gtk.Label(label="Period")
        self.period_label.add_css_class("keyboard-key")
        self.period_label.set_valign(Gtk.Align.CENTER)
        self.period_label.set_margin_end(6)

        self.backspace_label = Gtk.Label(label="Backspace")
        self.backspace_label.add_css_class("keyboard-key")
        self.backspace_label.set_valign(Gtk.Align.CENTER)
        self.backspace_label.set_margin_end(12)

        template_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        template_row.append(self.keyboard_template)
        template_row.append(self.period_label)
        template_row.append(self.backspace_label)
        box.append(template_row)

        self.keyboard_entry_row = Adw.EntryRow()
        self.keyboard_entry_row.set_title("Type here:")
        self.keyboard_entry_row.connect("changed", self._on_keyboard_changed)
        _text = self.keyboard_entry_row.get_delegate()
        if _text is not None:
            _text.connect(
                "paste-clipboard",
                lambda w: GObject.signal_stop_emission_by_name(w, "paste-clipboard"),
            )
        _key_ctrl = Gtk.EventControllerKey()
        _key_ctrl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        _key_ctrl.connect("key-pressed", self._on_keyboard_key_pressed)
        self.keyboard_entry_row.add_controller(_key_ctrl)
        template_group.add(self.keyboard_entry_row)
        box.append(template_group)

        self.update_text_highlighting("")

    def _on_keyboard_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_BackSpace:
            self.backspace_label.add_css_class("keyboard-key-passed")
        elif keyval == Gdk.KEY_period:
            self.period_label.add_css_class("keyboard-key-passed")
        return False

    def _on_keyboard_changed(self, entry_row):
        self.update_text_highlighting(entry_row.get_text())

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

            if index == 0:
                matched = char in self.ever_typed_chars
            else:
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

        if all_chars_typed:
            self.typing_test_complete = True
            if self.passed is not True:
                print("KeyboardPage:keyboard_test_completed")
                self.pass_button.set_active(True)

    def build_reason_locations(self, entry_row, reason):
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
