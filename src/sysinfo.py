import gi
gi.require_version('Adw', '1')
gi.require_version('Gtk', '4.0')
from gi.repository import Adw, Gtk

class SysInfo(Adw.Bin):
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
        header.set_title_widget(Gtk.Label(label="System Information"))

        # Create a list box to hold the rows
        list_box = Gtk.ListBox()
        list_box.set_selection_mode(Gtk.SelectionMode.NONE)

        # Create Adwaita rows
        row1 = Adw.EntryRow()
        row1.set_title("CPU")
        row1.set_text("Intel Core i7")
        row1.set_editable(False)

        row2 = Adw.EntryRow()
        row2.set_title("Memory")
        row2.set_text("16 GB")
        row2.set_editable(False)

        row3 = Adw.EntryRow()
        row3.set_title("Disk")
        row3.set_text("512 GB SSD")
        row3.set_editable(False)

        # Add rows to the list box
        list_box.append(row1)
        list_box.append(row2)
        list_box.append(row3)

        # Add header and list box to the vertical box
        vbox.append(header)
        vbox.append(list_box)

        # Add the vertical box to the page
        self.set_child(vbox)
