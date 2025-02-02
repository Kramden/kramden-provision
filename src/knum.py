import gi
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk
from utils import Utils

class KramdenNumber(Adw.Bin):
    def __init__(self):
        super().__init__()
        self.utils = Utils()
        self.set_margin_top(20)
        self.set_margin_bottom(20)
        self.set_margin_start(20)
        self.set_margin_end(20)
        self.title = "Identify"
        
        #Create a Gtk.Entry
        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text("Enter K-Number...")

        #Create a Set Button
        set_button = Gtk.Button.new_with_label("Set")
        set_button.connect("clicked", self.on_set_clicked)
        set_button.add_css_class("button-green")

        hostname_label = Gtk.Label.new("K-Number: ")
        self.hostname = Gtk.Label.new(self.utils.get_hostname())
        knum_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        knum_box.append(hostname_label)
        knum_box.append(self.hostname)

        guide_text = Gtk.Label.new("Please enter K-Number")
        guide_text_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        guide_text_box.append(guide_text)

        #Add entry and button to a box
        entry_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        entry_box.append(self.entry)
        entry_box.append(set_button)

        #Add entry_box to the window
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.append(knum_box)
        vbox.append(guide_text_box)
        vbox.append(entry_box)

        alignment = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, hexpand=True)
        alignment.append(vbox)
        alignment.set_halign(Gtk.Align.CENTER)
        self.set_child(alignment)

    def on_set_clicked(self, button):
        entered_text = self.entry.get_text()
        if self.utils.set_hostname(entered_text):
            self.hostname.set_text(entered_text)
