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
        self.title = "System Information"
        self.skip = False
        self.batteries_populated = False
        self.disks_populated = False

        # Create a box to hold the content
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        # Create scrollable window
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        # Create a list box to hold the rows
        list_box = Gtk.ListBox()
        list_box.set_selection_mode(Gtk.SelectionMode.NONE)

        # Create Adwaita rows
        self.hostname_row = Adw.ActionRow()
        self.hostname_row.set_title("K-Number")

        self.landscape_row = Adw.ActionRow()
        self.landscape_row.set_title("Landscape Status")

        vender_row = Adw.ActionRow()
        vender_row.set_title("Manufacturer")
        vender_row.set_subtitle(utils.get_vender())
        # Set Vender row to emblem-ok-symbolic
        vender_row.set_icon_name("emblem-ok-symbolic")

        model_row = Adw.ActionRow()
        model_row.set_title("Model")
        model_row.set_subtitle(utils.get_model())
        # Set Model row to emblem-ok-symbolic
        model_row.set_icon_name("emblem-ok-symbolic")

        os_row = Adw.ActionRow()
        os_row.set_title("OS")
        os_row.set_subtitle(utils.get_os())
        # Set OS row to emblem-ok-symbolic if the OS is Ubuntu, else set row to emblem-important-symbolic
        if "Ubuntu" in os_row.get_subtitle():
            os_row.set_icon_name("emblem-ok-symbolic")
        else:
            os_row.set_icon_name("emblem-important-symbolic")

        cpu_row = Adw.ActionRow()
        cpu_row.set_title("CPU")
        cpu_row.set_subtitle(utils.get_cpu_info())
        # Set CPU row to emblem-ok-symbolic
        cpu_row.set_icon_name("emblem-ok-symbolic")

        self.mem_row = Adw.ActionRow()
        self.mem_row.set_title("Memory")
        self.mem_row.set_subtitle(utils.get_mem() + " GB")

        self.disks_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        #self.disk_row = Adw.ExpanderRow(title="Disks")
        #self.disk_row.set_visible(False)
        #self.disk_row.set_expanded(False)

        self.battery_row = Adw.ExpanderRow(title="Batteries")
        self.battery_row.set_visible(False)
        self.battery_row.set_expanded(True)

        # Add rows to the list box
        list_box.append(self.hostname_row)
        list_box.append(self.landscape_row)
        list_box.append(vender_row)
        list_box.append(model_row)
        list_box.append(cpu_row)
        list_box.append(os_row)
        list_box.append(self.mem_row)
        list_box.append(self.disks_box)
        list_box.append(self.battery_row)

        vbox.append(list_box)
        scrolled_window.set_child(vbox)
        self.set_child(scrolled_window)

    # on_shown is called when the page is shown in the stack
    def on_shown(self):
        utils = Utils()

        # Start with default of passed and set to False if we find any failures
        passed = True
        self.hostname_row.set_subtitle(utils.get_hostname())
        # If the K-Number doesn't start with a "k" show a problem
        if self.hostname_row.get_subtitle().lower().startswith("k"):
            self.hostname_row.set_icon_name("emblem-ok-symbolic")
            if self.hostname_row.has_css_class("text-error"):
                self.hostname_row.remove_css_class("text-error")
        else:
            self.hostname_row.set_icon_name("emblem-important-symbolic")
            self.hostname_row.add_css_class("text-error")
            passed = False

        # Landscape registration status
        if utils.is_registered():
            self.landscape_row.set_subtitle("Registered")
            self.landscape_row.set_icon_name("emblem-ok-symbolic")
            if self.landscape_row.has_css_class("text-error"):
                self.landscape_row.remove_css_class("text-error")
        else:
            self.landscape_row.set_subtitle("Not registered")
            self.landscape_row.set_icon_name("emblem-important-symbolic")
            self.landscape_row.add_css_class("text-error")
            passed = False

        # Set Memory row to emblem-ok-symbolic if memory is greater than or equal to 7 GB, else set row to emblem-important-symbolic
        mem = int(utils.get_mem())
        if mem >= 7:
            self.mem_row.set_icon_name("emblem-ok-symbolic")
            if self.mem_row.has_css_class("text-error"):
                self.mem_row.remove_css_class("text-error")
        else:
            self.mem_row.set_icon_name("emblem-important-symbolic")
            self.mem_row.add_css_class("text-error")

        # Populate disk information
        if not self.disks_populated:
            disks = utils.get_disks()
            if len(disks.keys()) > 1:
                disks_row = Adw.ExpanderRow(title="Disks")
                disks_row.set_visible(True)
                disks_row.set_expanded(True)
                for disk in disks.keys():
                    row = Adw.ActionRow()
                    row.set_title(f"{str(disk)})")
                    row.set_subtitle(f"{str(disks[disk])} GB")
                    disks_row.add_row(row)
                    disks_row.set_expanded(True)
                    disks_row.set_visible(True)
                    disks_row.set_icon_name("emblem-important-symbolic")
                    disks_row.add_css_class("text-error")
                self.disks_box.append(disks_row)
            else:
                disk = list(disks.items())
                disk_row = Adw.ExpanderRow(title="Disk")
                disk_row.set_visible(True)
                disk_row.set_expanded(True)
                row = Adw.ActionRow()
                row.set_title(f"{str(disk[0][0])}")
                row.set_subtitle(f"{str(disk[0][1])} GB")
                if int(disk[0][1]) >= 100:
                    row.set_icon_name("emblem-ok-symbolic")
                    if row.has_css_class("text-error"):
                        row.remove_css_class("text-error")
                else:
                    row.set_icon_name("emblem-important-symbolic")
                    row.add_css_class("text-error")
                disk_row.add_row(row)
                self.disks_box.append(disk_row)
            # Ensure we only create disk info once
            self.disks_populated = True

        # Populate battery information
        if not self.batteries_populated:
            # Populate battery info
            batteries = utils.get_battery_capacities()
            if len(batteries) == 1:
                self.battery_row.set_title("Battery")
            for battery in batteries.keys():
                row = Adw.ActionRow()
                row.set_title(f"{str(battery)})")
                row.set_subtitle(f'{str(batteries[battery])}%')
                self.battery_row.add_row(row)
                self.battery_row.set_expanded(True)
                # Set Battery row to emblem-ok-symbolic if battery capacity is greater than 70%, else set row to emblem-important-symbolic
                if int(batteries[battery]) >= 70:
                    row.set_icon_name("emblem-ok-symbolic")
                else:
                    row.set_icon_name("emblem-important-symbolic")
                self.battery_row.set_visible(True)
            # Ensure we only create battery info once
            self.batteries_populated = True

        state = self.state.get_value()
        state['SysInfo'] = passed
        print("sysinfo:on_shown " + str(self.state.get_value()))
