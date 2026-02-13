import gi

gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk
from utils import Utils

# Fixed display order for all tests
TEST_DISPLAY_ORDER = [
    "USB",
    "Browser",
    "WiFi",
    "WebCam",
    "Keyboard",
    "Touchpad",
    "ScreenTest",
    "Battery",
]

# Tests that are always required regardless of chassis type
ALWAYS_REQUIRED = {"USB", "Browser"}

# Tests that become required on laptops
LAPTOP_PROMOTED = {"WiFi", "WebCam", "Keyboard", "Touchpad", "ScreenTest"}


class ManualTest(Adw.Bin):
    def __init__(self, show_battery_test=False):
        super().__init__()
        self.set_margin_top(20)
        self.set_margin_bottom(20)
        self.set_margin_start(20)
        self.set_margin_end(20)
        self.title = "Perform the following manual tests:"
        self.utils = Utils()
        self.show_battery_test = show_battery_test
        self.skip = False

        # Detect chassis type to determine which tests are required
        chassis_type = Utils.get_chassis_type()
        self.is_laptop = chassis_type == "Laptop"

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

        # Create a box to hold the content
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        # Create window titles for required and optional list boxes
        required_windowtitle = Adw.WindowTitle()
        required_windowtitle.set_title("Required Tests")

        self.optional_windowtitle = Adw.WindowTitle()
        self.optional_windowtitle.set_title("Optional Tests")

        # Create required and optional list boxes to hold the rows
        required_list_box = Gtk.ListBox()
        required_list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.optional_list_box = Gtk.ListBox()
        self.optional_list_box.set_selection_mode(Gtk.SelectionMode.NONE)

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

        keyboard_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        keyboard_box.set_margin_top(10)
        keyboard_box.set_margin_bottom(10)
        keyboard_box.set_margin_start(10)
        keyboard_box.set_margin_end(10)
        keyboard_box.set_vexpand(False)
        keyboard_box.set_valign(Gtk.Align.START)
        keyboard_row.add_row(keyboard_box)

        self.keyboard_template_buffer = Gtk.TextBuffer()
        self.keyboard_template_buffer.set_text(self.original_text)
        self.keyboard_template = Gtk.TextView(buffer=self.keyboard_template_buffer)
        self.keyboard_template.set_editable(False)
        self.keyboard_template.set_cursor_visible(False)
        self.keyboard_template.set_wrap_mode(Gtk.WrapMode.NONE)
        self.keyboard_template.set_vexpand(False)
        self.keyboard_template.set_valign(Gtk.Align.START)
        self.keyboard_template.set_size_request(-1, 30)

        self.green_tag = self.keyboard_template_buffer.create_tag(
            "green", foreground="green", weight=700
        )
        self.gray_tag = self.keyboard_template_buffer.create_tag(
            "gray", foreground="gray"
        )

        self.update_text_highlighting("")
        keyboard_box.append(self.keyboard_template)

        keyboard_text_buffer = Gtk.TextBuffer()
        keyboard_text_buffer.set_text("")
        self.keyboard_text_view = Gtk.TextView(buffer=keyboard_text_buffer)
        self.keyboard_text_view.set_sensitive(True)
        self.keyboard_text_view.set_wrap_mode(Gtk.WrapMode.NONE)
        self.keyboard_text_view.set_vexpand(False)
        self.keyboard_text_view.set_valign(Gtk.Align.START)
        self.keyboard_text_view.set_size_request(-1, 30)

        self.keyboard_text_buffer = keyboard_text_buffer

        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-released", self.on_key_release)
        self.keyboard_text_view.add_controller(key_controller)

        self.keyboard_text_view.connect("paste-clipboard", self.on_paste_clipboard)

        keyboard_box.append(self.keyboard_text_view)

        # Touchpad row
        touchpad_row = Adw.ActionRow()
        self.touchpad_button = Gtk.CheckButton()
        self.touchpad_button.connect("toggled", self.on_touchpad_toggled)
        touchpad_row.add_prefix(self.touchpad_button)
        touchpad_row.set_title("Touchpad (Does the touchpad feel responsive?)")
        touchpad_row.set_activatable(True)
        touchpad_row.connect("activated", self.on_touchpad_row_activated)

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
        vbox.append(required_windowtitle)
        vbox.append(required_list_box)

        # Hide optional section when all tests have been promoted to required
        if self.optional_tests:
            vbox.append(self.optional_windowtitle)
            vbox.append(self.optional_list_box)

        self.set_child(vbox)

    def _test_dict_for(self, name):
        """Return the dict (required or optional) that contains this test."""
        if name in self.required_tests:
            return self.required_tests
        return self.optional_tests

    # When key is released, do something
    def on_key_release(self, controller, keyval, keycode, state):
        typed_text = self.keyboard_text_buffer.get_text(
            self.keyboard_text_buffer.get_start_iter(),
            self.keyboard_text_buffer.get_end_iter(),
            False,
        )
        self.update_text_highlighting(typed_text)

    # Prevent paste operations in the keyboard test text view
    def on_paste_clipboard(self, _text_view):
        return True

    def update_text_highlighting(self, typed_text):
        start = self.keyboard_template_buffer.get_start_iter()
        end = self.keyboard_template_buffer.get_end_iter()
        self.keyboard_template_buffer.remove_all_tags(start, end)

        all_chars_typed = True

        for index, char in enumerate(self.original_text):
            start_iter = self.keyboard_template_buffer.get_iter_at_offset(index)
            end_iter = self.keyboard_template_buffer.get_iter_at_offset(index + 1)

            if char in typed_text:
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
