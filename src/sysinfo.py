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
        hostname_row = Adw.ActionRow()
        hostname_row.set_title("K-Number")
        hostname_row.set_subtitle(utils.get_hostname())
        # If the K-Number doesn't start with a "K" show a problem
        if "K-" in hostname_row.get_subtitle() :
            hostname_row.set_icon_name("emblem-ok-symbolic")
        else :
            hostname_row.set_icon_name("emblem-important-symbolic")

        vender_row = Adw.ActionRow()
        vender_row.set_title("Manufacturer")
        vender_row.set_subtitle(utils.get_vender())
        # Manufacturer should be good no matter what, set it to good symbol
        vender_row.set_icon_name("emblem-ok-symbolic")

        model_row = Adw.ActionRow()
        model_row.set_title("Model")
        model_row.set_subtitle(utils.get_model())
        # Model should be good no matter what, set it to good symbol
        model_row.set_icon_name("emblem-ok-symbolic")

        os_row = Adw.ActionRow()
        os_row.set_title("OS")
        os_row.set_subtitle(utils.get_os())
        # Set to good symbol if Ubuntu is listed else bad symbol
        if "Ubuntu" in os_row.get_subtitle() :
            os_row.set_icon_name("emblem-ok-symbolic")
        else :
            os_row.set_icon_name("emblem-important-symbolic")

        cpu_row = Adw.ActionRow()
        cpu_row.set_title("CPU")
        cpu_row.set_subtitle(utils.get_cpu_info())

        mem_row = Adw.ActionRow()
        mem_row.set_title("Memory")
        mem_row.set_subtitle(utils.get_mem() + " GB")
        # If memory is 8 GB or more, display good symbol else display bad symbol
        mem = int(utils.get_mem())
        if mem >= 8 :
            mem_row.set_icon_name("emblem-ok-symbolic")
        else :
            mem_row.set_icon_name("emblem-important-symbolic")

        disk_row = Adw.ActionRow()
        disk_row.set_title("Disk")
        disk_row.set_subtitle(utils.get_disk() + " GB")
        # If disk capacity is 120 GB or more, display good symbol, else display bad symbol
        disk = int(utils.get_disk())
        if disk >= 120 :
            disk_row.set_icon_name("emblem-ok-symbolic")
        else :
            disk_row.set_icon_name("emblem-important-symbolic")

        # Add rows to the list box
        list_box.append(hostname_row)
        list_box.append(vender_row)
        list_box.append(model_row)
        list_box.append(cpu_row)
        list_box.append(os_row)
        list_box.append(mem_row)
        list_box.append(disk_row)

        # Add header and list box to the vertical box
        vbox.append(header)
        vbox.append(list_box)

        # Add the vertical box to the page
        self.set_child(vbox)
