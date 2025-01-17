import gi
gi.require_version('Adw', '1')
gi.require_version('Gtk', '4.0')
from gi.repository import Adw, Gtk
from utils import Utils

class SysInfo(Adw.Bin):
    def __init__(self):
        super().__init__()
        utils = Utils()
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
        hostname_row = Adw.EntryRow()
        hostname_row.set_title("K-Number")
        hostname_row.set_text(utils.get_hostname())
        hostname_row.set_editable(False)

        cpu_row = Adw.EntryRow()
        cpu_row.set_title("CPU")
        cpu_row.set_text(utils.get_cpu_info())
        cpu_row.set_editable(False)

        mem_row = Adw.EntryRow()
        mem_row.set_title("Memory")
        mem_row.set_text(utils.get_mem() + " GB")
        mem_row.set_editable(False)

        disk_row = Adw.EntryRow()
        disk_row.set_title("Disk")
        disk_row.set_text(utils.get_disk() + " GB")
        disk_row.set_editable(False)

        # Add rows to the list box
        list_box.append(hostname_row)
        list_box.append(cpu_row)
        list_box.append(mem_row)
        list_box.append(disk_row)

        # Add header and list box to the vertical box
        vbox.append(header)
        vbox.append(list_box)

        # Add the vertical box to the page
        self.set_child(vbox)
