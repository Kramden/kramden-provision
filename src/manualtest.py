import gi

gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk
from utils import Utils


class ManualTest(Adw.Bin):
    def __init__(self):
        super().__init__()
        self.set_margin_top(20)
        self.set_margin_bottom(20)
        self.set_margin_start(20)
        self.set_margin_end(20)
        self.title = "Perform the following manual tests:"
        self.utils = Utils()
        self.required_tests = {"USB": False, "Browser": False}
        self.optional_tests = {
            "WebCam": False,
            "WiFi": False,
            "Touchpad": False,
            "ScreenTest": False,
        }
        self.skip = False

        # Create a box to hold the content
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        # Create window titles for required and optional list boxes
        required_windowtitle = Adw.WindowTitle()
        required_windowtitle.set_title("Required Tests")

        optional_windowtitle = Adw.WindowTitle()
        optional_windowtitle.set_title("Optional Tests")

        # Create required and option list boxes to hold the rows
        required_list_box = Gtk.ListBox()
        required_list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        optional_list_box = Gtk.ListBox()
        optional_list_box.set_selection_mode(Gtk.SelectionMode.NONE)

        # Create Adwaita rows
        usb_row = Adw.ActionRow()
        self.usb_button = Gtk.CheckButton()
        self.usb_button.connect("toggled", self.on_usb_toggled)
        usb_row.add_prefix(self.usb_button)
        usb_row.set_title(
            "USB Ports (Plug the mouse into each USB port and verify that it works)"
        )
        usb_row.set_activatable(True)
        usb_row.connect("activated", self.on_usb_row_activated)

        browser_row = Adw.ActionRow()
        self.browser_button = Gtk.CheckButton()
        self.browser_button.connect("toggled", self.on_browser_toggled)
        browser_row.add_prefix(self.browser_button)
        browser_row.set_title("Browser with video and audio playback")
        browser_row.set_activatable(True)
        browser_row.connect("activated", self.on_browser_row_activated)

        # Click here button to open a browser
        browser_clickhere = Gtk.Button(label="Click Here")
        browser_row.add_suffix(browser_clickhere)
        browser_clickhere.connect("clicked", self.on_browser_clicked)

        wifi_row = Adw.ActionRow()
        self.wifi_button = Gtk.CheckButton()
        self.wifi_button.connect("toggled", self.on_wifi_toggled)
        wifi_row.add_prefix(self.wifi_button)
        wifi_row.set_title(
            "WiFi connectivity (Can it connect to the internet wirelessly?)"
        )
        wifi_row.set_activatable(True)
        wifi_row.connect("activated", self.on_wifi_row_activated)

        webcam_row = Adw.ActionRow()
        self.webcam_button = Gtk.CheckButton()
        self.webcam_button.connect("toggled", self.on_webcam_toggled)
        webcam_row.add_prefix(self.webcam_button)
        webcam_row.set_title("Webcam")
        webcam_row.set_activatable(True)
        webcam_row.connect("activated", self.on_webcam_row_activated)

        # Click here button to open camera app
        webcam_clickhere = Gtk.Button(label="Click Here")
        webcam_row.add_suffix(webcam_clickhere)
        webcam_clickhere.connect("clicked", self.on_webcam_clicked)

        keyboard_row = Adw.ExpanderRow()
        keyboard_row.set_title(
            "Keyboard (Do all the keys work and report correctly? Test in the text box below.)"
        )
        keyboard_row.set_expanded(True)

        self.original_text = "The quick brown fox jumps over the lazy dog 1234567890"

        # Create a box to hold the label and text view
        keyboard_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        keyboard_box.set_margin_top(10)
        keyboard_box.set_margin_bottom(10)
        keyboard_box.set_margin_start(10)
        keyboard_box.set_margin_end(10)
        keyboard_box.set_vexpand(False)
        keyboard_box.set_valign(Gtk.Align.START)
        keyboard_row.add_row(keyboard_box)

        # Template text view (shows what to type)
        self.keyboard_template_buffer = Gtk.TextBuffer()
        self.keyboard_template_buffer.set_text(self.original_text)
        self.keyboard_template = Gtk.TextView(buffer=self.keyboard_template_buffer)
        self.keyboard_template.set_editable(False)
        self.keyboard_template.set_cursor_visible(False)
        self.keyboard_template.set_wrap_mode(Gtk.WrapMode.NONE)
        self.keyboard_template.set_vexpand(False)
        self.keyboard_template.set_valign(Gtk.Align.START)
        self.keyboard_template.set_size_request(-1, 30)

        # Create text tags for coloring
        self.green_tag = self.keyboard_template_buffer.create_tag(
            "green", foreground="green", weight=700
        )
        self.gray_tag = self.keyboard_template_buffer.create_tag(
            "gray", foreground="gray"
        )

        # Initialize template highlighting so it appears in the correct gray/green state
        self.update_text_highlighting("")
        keyboard_box.append(self.keyboard_template)

        # Input text view (where user types)
        keyboard_text_buffer = Gtk.TextBuffer()
        keyboard_text_buffer.set_text("")
        self.keyboard_text_view = Gtk.TextView(buffer=keyboard_text_buffer)
        self.keyboard_text_view.set_sensitive(True)
        self.keyboard_text_view.set_wrap_mode(Gtk.WrapMode.NONE)
        self.keyboard_text_view.set_vexpand(False)
        self.keyboard_text_view.set_valign(Gtk.Align.START)
        self.keyboard_text_view.set_size_request(-1, 30)

        # Store the buffer as instance variable
        self.keyboard_text_buffer = keyboard_text_buffer

        # Create an event controller for key events
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-released", self.on_key_release)
        self.keyboard_text_view.add_controller(key_controller)

        # Disable paste functionality
        self.keyboard_text_view.connect("paste-clipboard", self.on_paste_clipboard)

        keyboard_box.append(self.keyboard_text_view)

        # Click here button to open libre office writer
        # keyboard_clickhere = Gtk.Button(label = "Click Here")
        # keyboard_row.add_suffix(keyboard_clickhere)
        # keyboard_clickhere.connect("clicked", self.on_keyboard_clicked)

        touchpad_row = Adw.ActionRow()
        self.touchpad_button = Gtk.CheckButton()
        self.touchpad_button.connect("toggled", self.on_touchpad_toggled)
        touchpad_row.add_prefix(self.touchpad_button)
        touchpad_row.set_title("Touchpad (Does the touchpad feel responsive?)")
        touchpad_row.set_activatable(True)
        touchpad_row.connect("activated", self.on_touchpad_row_activated)

        screentest_row = Adw.ActionRow()
        self.screentest_button = Gtk.CheckButton()
        self.screentest_button.connect("toggled", self.on_screentest_toggled)
        screentest_row.add_prefix(self.screentest_button)
        screentest_row.set_title("Screen Test")
        screentest_row.set_activatable(True)
        screentest_row.connect("activated", self.on_screentest_row_activated)

        # Click here button to open screen-test
        screentest_clickhere = Gtk.Button(label="Click Here")
        screentest_row.add_suffix(screentest_clickhere)
        screentest_clickhere.connect("clicked", self.on_screentest_clicked)

        # Add Adwaita rows to the list box
        required_list_box.append(usb_row)
        required_list_box.append(browser_row)
        optional_list_box.append(wifi_row)
        optional_list_box.append(webcam_row)
        optional_list_box.append(keyboard_row)
        optional_list_box.append(touchpad_row)
        optional_list_box.append(screentest_row)

        # Add list boxes to the vertical box
        vbox.append(required_windowtitle)
        vbox.append(required_list_box)
        vbox.append(optional_windowtitle)
        vbox.append(optional_list_box)

        # Add the vertical box to the page
        self.set_child(vbox)

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
        # Stop the signal propagation to prevent paste
        return True

    def update_text_highlighting(self, typed_text):
        # Remove all tags first
        start = self.keyboard_template_buffer.get_start_iter()
        end = self.keyboard_template_buffer.get_end_iter()
        self.keyboard_template_buffer.remove_all_tags(start, end)

        # Apply tags character by character
        for index, char in enumerate(self.original_text):
            # Get the iterators for this character position in the template
            start_iter = self.keyboard_template_buffer.get_iter_at_offset(index)
            end_iter = self.keyboard_template_buffer.get_iter_at_offset(index + 1)

            # Check if this character exists anywhere in what the user has typed
            if char in typed_text:
                # This character has been typed somewhere - turn it green
                self.keyboard_template_buffer.apply_tag(
                    self.green_tag, start_iter, end_iter
                )
            else:
                # This character hasn't been typed yet - keep it gray
                self.keyboard_template_buffer.apply_tag(
                    self.gray_tag, start_iter, end_iter
                )

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

    # Make webcam row clickable
    def on_webcam_row_activated(self, row):
        current_state = self.webcam_button.get_active()
        self.webcam_button.set_active(not current_state)



    def on_touchpad_row_activated(self, row):
        current_state = self.touchpad_button.get_active()
        self.touchpad_button.set_active(not current_state)

    # Make screentest row clickable
    def on_screentest_row_activated(self, row):
        current_state = self.screentest_button.get_active()
        self.screentest_button.set_active(not current_state)

    # Handle toggled event for the screentest button
    def on_screentest_toggled(self, button):
        print("ManualTest:on_screentest_toggled")
        self.optional_tests["ScreenTest"] = button.get_active()
        print(self.optional_tests)
        self.check_status()



    # Handle toggled event for the webcam button
    def on_webcam_toggled(self, button):
        print("ManualTest:on_webcam_toggled")
        self.optional_tests["WebCam"] = button.get_active()
        print(self.optional_tests)
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
        self.optional_tests["Touchpad"] = button.get_active()
        print(self.optional_tests)
        self.check_status()

    # Handle toggled event for the wifi button
    def on_wifi_toggled(self, button):
        print("ManualTest:on_wifi_toggled")
        self.optional_tests["WiFi"] = button.get_active()
        print(self.optional_tests)
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

    # on_shown is called when the page is shown in the stack
    def on_shown(self):
        print("ManualTest:on_shown")
        self.check_status()
