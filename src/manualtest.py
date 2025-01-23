import gi
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk

class ManualTest(Adw.Bin):
    def __init__(self):
        super().__init__()
        self.set_margin_top(20)
        self.set_margin_bottom(20)
        self.set_margin_start(20)
        self.set_margin_end(20)

        # Create a box to hold the header and content
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        # Create a header
        header = Adw.HeaderBar()
        header.set_decoration_layout("")  # Remove window controls
        header.set_title_widget(Gtk.Label(label="Perform the following manual tests:"))

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
        usb_row.add_prefix(usb_button)
        usb_row.set_title("USB Ports (Plug the mouse into each USB port and verify that it works)")

        browser_row = Adw.ActionRow()
        browser_button = Gtk.CheckButton()
        browser_row.add_prefix(browser_button)
        browser_row.set_title("Browser with video and audio playback")

        # Click here button to open a browser
        browser_clickhere = Gtk.Button(label = "Click Here")
        browser_row.add_suffix(browser_clickhere)

        wifi_row = Adw.ActionRow()
        wifi_button = Gtk.CheckButton()
        wifi_row.add_prefix(wifi_button)
        wifi_row.set_title("WiFi connectivity (Can it connect to the internet wirelessly?)")

        webcam_row = Adw.ActionRow()
        webcam_button = Gtk.CheckButton()
        webcam_row.add_prefix(webcam_button)
        webcam_row.set_title("Webcam")

        # Click here button to open camera app
        webcam_clickhere = Gtk.Button(label = "Click Here")
        webcam_row.add_suffix(webcam_clickhere)

        keyboard_row = Adw.ActionRow()
        keyboard_button = Gtk.CheckButton()
        keyboard_row.add_prefix(keyboard_button)
        keyboard_row.set_title("Keyboard (Do all the keys work and report correctly?)")

        # Click here button to open libre office writer
        keyboard_clickhere = Gtk.Button(label = "Click Here")
        keyboard_row.add_suffix(keyboard_clickhere)

        touchpad_row = Adw.ActionRow()
        touchpad_button = Gtk.CheckButton()
        touchpad_row.add_prefix(touchpad_button)
        touchpad_row.set_title("Touchpad (Does the touchpad feel responsive?)")

        screentest_row = Adw.ActionRow()
        screentest_button = Gtk.CheckButton()
        screentest_row.add_prefix(screentest_button)
        screentest_row.set_title("Screen Test")

        # Click here button to open screen-test
        screentest_clickhere = Gtk.Button(label = "Click Here")
        screentest_row.add_suffix(screentest_clickhere)

        # Add Adwaita rows to the list box
        required_list_box.append(usb_row)
        required_list_box.append(browser_row)
        optional_list_box.append(wifi_row)
        optional_list_box.append(webcam_row)
        optional_list_box.append(keyboard_row)
        optional_list_box.append(touchpad_row)
        optional_list_box.append(screentest_row)

        # Add headers and list boxes to the vertical box
        vbox.append(header)
        vbox.append(required_windowtitle)
        vbox.append(required_list_box)
        vbox.append(optional_windowtitle)
        vbox.append(optional_list_box)

        # Add the vertical box to the page
        self.set_child(vbox)
