import gi
gi.require_version('Adw', '1')
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
        self.optional_tests = {"WebCam": False, "Keyboard": False, "WiFi": False, "Touchpad": False, "ScreenTest": False}

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
        usb_button = Gtk.CheckButton()
        usb_button.connect("toggled", self.on_usb_toggled)
        usb_row.add_prefix(usb_button)
        usb_row.set_title("USB Ports (Plug the mouse into each USB port and verify that it works)")

        browser_row = Adw.ActionRow()
        browser_button = Gtk.CheckButton()
        browser_button.connect("toggled", self.on_browser_toggled)
        browser_row.add_prefix(browser_button)
        browser_row.set_title("Browser with video and audio playback")

        # Click here button to open a browser
        browser_clickhere = Gtk.Button(label = "Click Here")
        browser_row.add_suffix(browser_clickhere)
        browser_clickhere.connect("clicked", self.on_browser_clicked)

        wifi_row = Adw.ActionRow()
        wifi_button = Gtk.CheckButton()
        wifi_button.connect("toggled", self.on_wifi_toggled)
        wifi_row.add_prefix(wifi_button)
        wifi_row.set_title("WiFi connectivity (Can it connect to the internet wirelessly?)")

        webcam_row = Adw.ActionRow()
        webcam_button = Gtk.CheckButton()
        webcam_button.connect("toggled", self.on_webcam_toggled)
        webcam_row.add_prefix(webcam_button)
        webcam_row.set_title("Webcam")

        # Click here button to open camera app
        webcam_clickhere = Gtk.Button(label = "Click Here")
        webcam_row.add_suffix(webcam_clickhere)
        webcam_clickhere.connect("clicked", self.on_webcam_clicked)

        keyboard_row = Adw.ActionRow()
        keyboard_button = Gtk.CheckButton()
        keyboard_button.connect("toggled", self.on_keyboard_toggled)
        keyboard_row.add_prefix(keyboard_button)
        keyboard_row.set_title("Keyboard (Do all the keys work and report correctly?)")

        # Click here button to open libre office writer
        keyboard_clickhere = Gtk.Button(label = "Click Here")
        keyboard_row.add_suffix(keyboard_clickhere)
        keyboard_clickhere.connect("clicked", self.on_keyboard_clicked)

        touchpad_row = Adw.ActionRow()
        touchpad_button = Gtk.CheckButton()
        touchpad_button.connect("toggled", self.on_touchpad_toggled)
        touchpad_row.add_prefix(touchpad_button)
        touchpad_row.set_title("Touchpad (Does the touchpad feel responsive?)")

        screentest_row = Adw.ActionRow()
        screentest_button = Gtk.CheckButton()
        screentest_button.connect("toggled", self.on_screentest_toggled)
        screentest_row.add_prefix(screentest_button)
        screentest_row.set_title("Screen Test")

        # Click here button to open screen-test
        screentest_clickhere = Gtk.Button(label = "Click Here")
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

    # Handle toggled event for the screentest button
    def on_screentest_toggled(self, button):
        print("ManualTest:on_screentest_toggled")
        self.optional_tests["ScreenTest"] = button.get_active()
        print(self.optional_tests)
        self.check_status()

    # Handle toggled event for the keyboard button
    def on_keyboard_toggled(self, button):
        print("ManualTest:on_keyboard_toggled")
        self.optional_tests["Keyboard"] = button.get_active()
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
    def on_webcam_clicked(self,button):
        print("ManualTest:on_webcam_clicked")
        self.utils.launch_app("cheese")

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
        state['ManualTest'] = all(self.required_tests.values())
        print("manualtest:check_status State:" + str(state))

    # on_shown is called when the page is shown in the stack
    def on_shown(self):
        print("ManualTest:on_shown")
        self.check_status()
