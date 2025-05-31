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
        self.usb_button = Gtk.CheckButton()
        self.usb_button.connect("toggled", self.on_usb_toggled)
        usb_row.add_prefix(self.usb_button)
        usb_row.set_title("USB Ports (Plug the mouse into each USB port and verify that it works)")
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
        browser_clickhere = Gtk.Button(label = "Click Here")
        browser_row.add_suffix(browser_clickhere)
        browser_clickhere.connect("clicked", self.on_browser_clicked)

        wifi_row = Adw.ActionRow()
        self.wifi_button = Gtk.CheckButton()
        self.wifi_button.connect("toggled", self.on_wifi_toggled)
        wifi_row.add_prefix(self.wifi_button)
        wifi_row.set_title("WiFi connectivity (Can it connect to the internet wirelessly?)")
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
        webcam_clickhere = Gtk.Button(label = "Click Here")
        webcam_row.add_suffix(webcam_clickhere)
        webcam_clickhere.connect("clicked", self.on_webcam_clicked)

        keyboard_row = Adw.ActionRow()
        self.keyboard_button = Gtk.CheckButton()
        self.keyboard_button.connect("toggled", self.on_keyboard_toggled)
        keyboard_row.add_prefix(self.keyboard_button)
        keyboard_row.set_title("Keyboard (Do all the keys work and report correctly?)")
        keyboard_row.set_activatable(True)
        keyboard_row.connect("activated", self.on_keyboard_row_activated)

        # Click here button to open libre office writer
        keyboard_clickhere = Gtk.Button(label = "Click Here")
        keyboard_row.add_suffix(keyboard_clickhere)
        keyboard_clickhere.connect("clicked", self.on_keyboard_clicked)

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

    # Make keyboard row clickable
    def on_keyboard_row_activated(self, row):
        current_state = self.keyboard_button.get_active()
        self.keyboard_button.set_active(not current_state)

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
