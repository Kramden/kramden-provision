import gi

gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
from gi.repository import Adw, Gdk, GLib, GObject, Gtk
from utils import Utils

# Fixed display order for all tests
TEST_DISPLAY_ORDER = [
    "USB",
    "Browser",
    "WiFi",
    "WebCam",
    "Keyboard",
    "Touchpad",
    "Touchscreen",
    "ScreenTest",
    "Battery",
]

# Tests that are always required regardless of chassis type
ALWAYS_REQUIRED = {"USB", "Browser"}

# Tests that become required on laptops
LAPTOP_PROMOTED = {"WiFi", "WebCam", "Keyboard", "Touchpad", "ScreenTest"}

_TEST_LABELS = {
    "USB": "USB port test",
    "Browser": "Browser test",
    "WiFi": "WiFi test",
    "WebCam": "Webcam test",
    "Keyboard": "Keyboard test",
    "Touchpad": "Touchpad test",
    "Touchscreen": "Touchscreen test",
    "ScreenTest": "Screen test",
    "Battery": "Battery test",
}


class ManualTest(Adw.Bin):
    def __init__(self, show_battery_test=False):
        super().__init__()
        self.set_margin_top(24)
        self.set_margin_bottom(24)
        self.set_margin_start(24)
        self.set_margin_end(24)
        self.title = "Perform the following manual tests:"
        self.utils = Utils()
        self.show_battery_test = show_battery_test
        self.skip = False

        # Detect chassis type to determine which tests are required
        chassis_type = Utils.get_chassis_type()
        self.is_laptop = chassis_type == "Laptop"
        self.has_touchscreen = Utils.has_touchscreen()

        # Build required and optional test dicts based on chassis type
        self.required_tests = {"USB": False, "Browser": False}
        self.optional_tests = {}

        if self.is_laptop:
            for name in LAPTOP_PROMOTED:
                self.required_tests[name] = False
            if show_battery_test:
                self.required_tests["Battery"] = False
        else:
            for name in LAPTOP_PROMOTED:
                self.optional_tests[name] = False
            if show_battery_test:
                self.optional_tests["Battery"] = False

        # Touchscreen test: required if detected, otherwise omitted entirely
        if self.has_touchscreen:
            self.required_tests["Touchscreen"] = False

        # Create a box to hold the content
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        # Section headers
        required_header = Gtk.Label(label="Required Tests")
        required_header.add_css_class("title-3")
        required_header.set_halign(Gtk.Align.START)

        self.optional_header = Gtk.Label(label="Optional Tests")
        self.optional_header.add_css_class("title-3")
        self.optional_header.set_halign(Gtk.Align.START)

        # Create required and optional list boxes to hold the rows
        required_list_box = Gtk.ListBox()
        required_list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        required_list_box.add_css_class("boxed-list")
        required_list_box.set_valign(Gtk.Align.START)
        self.optional_list_box = Gtk.ListBox()
        self.optional_list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.optional_list_box.add_css_class("boxed-list")
        self.optional_list_box.set_valign(Gtk.Align.START)

        # --- Build all test rows ---

        # USB row
        usb_row = Adw.ActionRow()
        self.usb_button = Gtk.CheckButton()
        self.usb_button.connect("toggled", self.on_usb_toggled)
        usb_row.add_prefix(self.usb_button)
        usb_row.set_title(
            "USB Ports (Plug the mouse into each USB port and verify that it works)"
        )
        usb_row.set_activatable(True)
        usb_row.connect("activated", self.on_usb_row_activated)

        # Browser row
        browser_row = Adw.ActionRow()
        self.browser_button = Gtk.CheckButton()
        self.browser_button.connect("toggled", self.on_browser_toggled)
        browser_row.add_prefix(self.browser_button)
        browser_row.set_title("Browser with video and audio playback")
        browser_row.set_activatable(True)
        browser_row.connect("activated", self.on_browser_row_activated)

        browser_clickhere = Gtk.Button(label="Click Here")
        browser_row.add_suffix(browser_clickhere)
        browser_clickhere.connect("clicked", self.on_browser_clicked)

        # WiFi row
        wifi_row = Adw.ActionRow()
        self.wifi_button = Gtk.CheckButton()
        self.wifi_button.connect("toggled", self.on_wifi_toggled)
        wifi_row.add_prefix(self.wifi_button)
        wifi_row.set_title(
            "WiFi connectivity (Can it connect to the internet wirelessly?)"
        )
        wifi_row.set_activatable(True)
        wifi_row.connect("activated", self.on_wifi_row_activated)

        # WebCam row — uses a DropDown instead of a CheckButton
        webcam_row = Adw.ActionRow()
        self.webcam_options = Gtk.StringList.new(["Untested", "Pass", "Fail", "N/A"])
        self.webcam_dropdown = Gtk.DropDown(model=self.webcam_options)
        self.webcam_dropdown.set_valign(Gtk.Align.CENTER)
        self.webcam_dropdown.connect("notify::selected", self.on_webcam_selected)
        webcam_row.add_prefix(self.webcam_dropdown)
        webcam_row.set_title("Webcam")

        webcam_clickhere = Gtk.Button(label="Click Here")
        webcam_row.add_suffix(webcam_clickhere)
        webcam_clickhere.connect("clicked", self.on_webcam_clicked)

        # Keyboard row
        keyboard_row = Adw.ExpanderRow()
        keyboard_row.set_title(
            "Keyboard (Do all the keys work and report correctly? Test in the text box below.)"
        )
        keyboard_row.set_expanded(True)
        keyboard_row.connect(
            "notify::expanded",
            lambda row, _: row.set_expanded(True) if not row.get_expanded() else None,
        )

        self.original_text = "The quick brown fox jumps over the lazy dog 1234567890"

        # Template — added directly as a row so it spans the full width
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

        self.update_text_highlighting("")

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
        keyboard_row.add_row(template_row)

        # Input row — native Adwaita entry row
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
        keyboard_row.add_row(self.keyboard_entry_row)

        # Touchpad row
        touchpad_row = Adw.ActionRow()
        self.touchpad_button = Gtk.CheckButton()
        self.touchpad_button.connect("toggled", self.on_touchpad_toggled)
        touchpad_row.add_prefix(self.touchpad_button)
        touchpad_row.set_title("Touchpad (Does the touchpad feel responsive?)")
        touchpad_row.set_activatable(True)
        touchpad_row.connect("activated", self.on_touchpad_row_activated)

        # Touchscreen row (only created if touchscreen detected)
        if self.has_touchscreen:
            touchscreen_row = Adw.ActionRow()
            self.touchscreen_button = Gtk.CheckButton()
            self.touchscreen_button.set_sensitive(False)
            self.touchscreen_button.connect("toggled", self.on_touchscreen_toggled)
            touchscreen_row.add_prefix(self.touchscreen_button)
            touchscreen_row.set_title("Touchscreen")

            touchscreen_clickhere = Gtk.Button(label="Click Here")
            touchscreen_row.add_suffix(touchscreen_clickhere)
            touchscreen_clickhere.connect("clicked", self.on_touchscreen_clicked)

        # ScreenTest row
        screentest_row = Adw.ActionRow()
        self.screentest_button = Gtk.CheckButton()
        self.screentest_button.connect("toggled", self.on_screentest_toggled)
        screentest_row.add_prefix(self.screentest_button)
        screentest_row.set_title("Screen Test")
        screentest_row.set_activatable(True)
        screentest_row.connect("activated", self.on_screentest_row_activated)

        screentest_clickhere = Gtk.Button(label="Click Here")
        screentest_row.add_suffix(screentest_clickhere)
        screentest_clickhere.connect("clicked", self.on_screentest_clicked)

        # Map test names to their row widgets
        test_rows = {
            "USB": usb_row,
            "Browser": browser_row,
            "WiFi": wifi_row,
            "WebCam": webcam_row,
            "Keyboard": keyboard_row,
            "Touchpad": touchpad_row,
            "ScreenTest": screentest_row,
        }

        if self.has_touchscreen:
            test_rows["Touchscreen"] = touchscreen_row

        # Battery test row - only shown when running from spec.py
        if self.show_battery_test:
            battery_row = Adw.ActionRow()
            self.battery_button = Gtk.CheckButton()
            self.battery_button.connect("toggled", self.on_battery_toggled)
            battery_row.add_prefix(self.battery_button)
            battery_row.set_title(
                "Battery test (Unplug power and confirm system doesn't shutdown)"
            )
            battery_row.set_activatable(True)
            battery_row.connect("activated", self.on_battery_row_activated)
            test_rows["Battery"] = battery_row

        # Append rows in fixed display order to the correct list box
        for name in TEST_DISPLAY_ORDER:
            if name not in test_rows:
                continue
            row = test_rows[name]
            if name in self.required_tests:
                required_list_box.append(row)
            elif name in self.optional_tests:
                self.optional_list_box.append(row)

        # Add list boxes to the vertical box
        vbox.append(required_header)
        vbox.append(required_list_box)

        # Hide optional section when all tests have been promoted to required
        if self.optional_tests:
            vbox.append(self.optional_header)
            vbox.append(self.optional_list_box)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(400)
        scrolled.set_vexpand(True)
        scrolled.set_child(vbox)
        self.set_child(scrolled)

    def _test_dict_for(self, name):
        """Return the dict (required or optional) that contains this test."""
        if name in self.required_tests:
            return self.required_tests
        return self.optional_tests

    def get_failure_reasons(self):
        return [
            f"{_TEST_LABELS.get(name, name)} not completed"
            for name, passed in self.required_tests.items()
            if not passed
        ]

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

        d = self._test_dict_for("Keyboard")
        if all_chars_typed and not d["Keyboard"]:
            print("ManualTest:keyboard_test_completed")
            d["Keyboard"] = True
            print(d)
            self.check_status()

    # Make usb row clickable
    def on_usb_row_activated(self, row):
        current_state = self.usb_button.get_active()
        self.usb_button.set_active(not current_state)

    # Make browser row clickable
    def on_browser_row_activated(self, row):
        current_state = self.browser_button.get_active()
        self.browser_button.set_active(not current_state)

    # Make wifi row clickable
    def on_wifi_row_activated(self, row):
        current_state = self.wifi_button.get_active()
        self.wifi_button.set_active(not current_state)

    def on_touchpad_row_activated(self, row):
        current_state = self.touchpad_button.get_active()
        self.touchpad_button.set_active(not current_state)

    # Make screentest row clickable
    def on_screentest_row_activated(self, row):
        current_state = self.screentest_button.get_active()
        self.screentest_button.set_active(not current_state)

    # Handle selection changed for the webcam dropdown
    def on_webcam_selected(self, dropdown, _pspec):
        selected = dropdown.get_selected()
        # 0=Untested, 1=Pass, 2=Fail, 3=N/A
        # Pass and N/A count as passing
        value = selected in (1, 3)
        d = self._test_dict_for("WebCam")
        print("ManualTest:on_webcam_selected")
        d["WebCam"] = value
        print(d)
        self.check_status()

    # Handle toggled event for the screentest button
    def on_screentest_toggled(self, button):
        print("ManualTest:on_screentest_toggled")
        d = self._test_dict_for("ScreenTest")
        d["ScreenTest"] = button.get_active()
        print(d)
        self.check_status()

    # Handle toggled event for the usb button
    def on_usb_toggled(self, button):
        print("ManualTest:on_usb_toggled")
        self.required_tests["USB"] = button.get_active()
        print(self.required_tests)
        self.check_status()

    # Handle toggled event for the touchpad button
    def on_touchpad_toggled(self, button):
        print("ManualTest:on_touchpad_toggled")
        d = self._test_dict_for("Touchpad")
        d["Touchpad"] = button.get_active()
        print(d)
        self.check_status()

    # Handle toggled event for the touchscreen button
    def on_touchscreen_toggled(self, button):
        print("ManualTest:on_touchscreen_toggled")
        d = self._test_dict_for("Touchscreen")
        d["Touchscreen"] = button.get_active()
        print(d)
        self.check_status()

    # Launch the fullscreen touchscreen test
    def on_touchscreen_clicked(self, button):
        print("ManualTest:on_touchscreen_clicked")
        # The touchscreen test runs in a subprocess. Touch event delivery
        # in GTK/GDK has been observed to SIGSEGV after a USB pointer
        # device is unplugged; isolating the test in its own process
        # means such a crash only fails the test rather than killing the
        # provisioning app.
        import os
        import subprocess
        import sys
        import threading

        button.set_sensitive(False)
        self.touchscreen_button.set_sensitive(False)

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
                    print(
                        f"Touchscreen test subprocess exited rc={result.returncode}"
                    )
                    if result.stderr:
                        print(result.stderr)
                    passed = False
                else:
                    passed = result.stdout.strip().endswith("pass")
            except Exception as exc:
                print(f"Touchscreen test subprocess error: {exc}")
                passed = False
            GLib.idle_add(self._on_touchscreen_test_complete, passed, button)

        threading.Thread(target=_run, daemon=True).start()

    def _on_touchscreen_test_complete(self, passed, click_button=None):
        self.touchscreen_button.set_active(passed)
        self.touchscreen_button.set_sensitive(True)
        if click_button is not None:
            click_button.set_sensitive(True)
        return False

    # Make battery row clickable
    def on_battery_row_activated(self, row):
        current_state = self.battery_button.get_active()
        self.battery_button.set_active(not current_state)

    # Handle toggled event for the battery button
    def on_battery_toggled(self, button):
        print("ManualTest:on_battery_toggled")
        d = self._test_dict_for("Battery")
        d["Battery"] = button.get_active()
        print(d)
        self.check_status()

    # Handle toggled event for the wifi button
    def on_wifi_toggled(self, button):
        print("ManualTest:on_wifi_toggled")
        d = self._test_dict_for("WiFi")
        d["WiFi"] = button.get_active()
        print(d)
        self.check_status()

    # Launch the screen-test app when clicked
    def on_screentest_clicked(self, button):
        print("ManualTest:on_screentest_clicked")
        self.utils.launch_app("screen-test")

    # Launch the gnome-text-editor app when clicked
    def on_keyboard_clicked(self, button):
        print("ManualTest:on_keyboard_clicked")
        self.utils.launch_app("gnome-text-editor")

    # Launch the cheese app when clicked
    def on_webcam_clicked(self, button):
        print("ManualTest:on_webcam_clicked")
        if self.utils.file_exists_and_executable("/usr/bin/guvcview"):
            self.utils.launch_app("guvcview")
        elif self.utils.file_exists_and_executable("/usr/bin/cheese"):
            self.utils.launch_app("cheese")
        elif self.utils.file_exists_and_executable("/usr/bin/snapshot"):
            self.utils.launch_app("snapshot")

    # Handle toggled event for the browser button
    def on_browser_toggled(self, button):
        print("ManualTest:on_browser_toggled")
        self.required_tests["Browser"] = button.get_active()
        print(self.required_tests)
        self.check_status()

    # Launch the xdg-open app to open https://vimeo.com/116979416 in browser
    def on_browser_clicked(self, button):
        print("Manual:on_browser_clicked")
        self.utils.launch_app("xdg-open https://vimeo.com/116979416")

    def check_status(self):
        print("ManualTest:check_status")
        state = self.state.get_value()
        state["ManualTest"] = all(self.required_tests.values())
        print("manualtest:check_status State:" + str(state))

    def get_all_test_results(self):
        """Return a dict of all test names to their status for the tracking sheet.

        Boolean tests map to True/False.
        WebCam maps to "Pass", "Fail", "N/A", or "Untested" based on dropdown selection.
        Only includes tests that are active (required or optional).
        """
        results = {}
        # Merge both dicts — required first, then optional
        all_tests = {**self.required_tests, **self.optional_tests}

        # Map webcam dropdown index to label
        webcam_labels = {0: "Untested", 1: "Pass", 2: "Fail", 3: "N/A"}

        for name in TEST_DISPLAY_ORDER:
            if name not in all_tests:
                continue
            if name == "WebCam":
                results[name] = webcam_labels.get(
                    self.webcam_dropdown.get_selected(), "Untested"
                )
            else:
                results[name] = all_tests[name]
        return results

    # on_shown is called when the page is shown in the stack
    def on_shown(self):
        print("ManualTest:on_shown")
        self.check_status()

