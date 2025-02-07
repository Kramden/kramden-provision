import gi
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk
from utils import Utils
import os

class Landscape(Adw.Bin):
    def __init__(self):
        super().__init__()
        self.set_margin_top(20)
        self.set_margin_bottom(20)
        self.set_margin_start(20)
        self.set_margin_end(20)
        self.title = "Landscape Registration"
        
        # Add Landscape branding
        image_path = os.path.dirname(os.path.realpath(__file__)) + "/landscape_dark.png"
        landscape_image = Gtk.Picture.new_for_filename(image_path)
        landscape_image.set_content_fit(Gtk.ContentFit.CONTAIN)
        landscape_image.set_size_request(300, 0)  # Set desired width and height


        # Create a Register Button
        self.register_button = Gtk.Button.new_with_label("Register")
        self.register_button.set_sensitive(False)
        self.register_button.connect("clicked", self.on_register_clicked)
        self.register_button.add_css_class("button-green")

        self.hostname_label = Gtk.Label.new("K-Number: ")

        self.info_label = Gtk.Label(label="K-Number Invalid (Must start with a \'K\')")

        self.info_label.set_visible(False)

        # Add entry_box to the window
        alignment = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, hexpand=True)
        alignment.set_halign(Gtk.Align.CENTER)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.append(landscape_image)
        vbox.append(self.hostname_label)
        vbox.append(self.info_label)
        vbox.append(self.register_button)

        alignment.append(vbox)
        self.set_child(alignment)

    def on_register_clicked(self, button):
        print('Landscape: on_register_clicked')
        utils = Utils()
        result = utils.register_landscape()
        self.update_registration_status(result)

    def update_registration_status(self, registered, hostname=None):
        print('Landscape: update_registration_status' + str(registered))
        if registered:
            self.info_label.set_label("Registered with Landscape")
            self.info_label.set_visible(True)
            self.register_button.set_sensitive(False)
        else:
            if not hostname.lower().startswith('k'):
                self.info_label.set_label("K-Number Invalid (Must start with a \'K\')")
            else:
                self.info_label.set_label("Not registered")
            self.info_label.set_visible(True)
            self.register_button.set_sensitive(True)

    # on_shown is called when the page is shown in the stack
    def on_shown(self):
        utils = Utils()
        hostname = utils.get_hostname()
        registered = utils.is_registered()
        self.update_registration_status(registered, hostname)

        if hostname.lower().startswith('k') and not registered:
            self.info_label.set_visible(False)
            self.register_button.set_sensitive(True)
        else:
            self.info_label.set_visible(True)
            self.register_button.set_sensitive(False)
        state = self.state.get_value()
        state['Landscape'] = True
        self.hostname_label.set_label(f"K-Number: {hostname}")
        print("landscape:on_shown " + str(self.state.get_value()))
