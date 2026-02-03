import gi
gi.require_version('Adw', '1')
gi.require_version('Gtk', '4.0')
from gi.repository import Adw, Gtk
from utils import Utils

class SpecInfo(Adw.Bin):
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

        vendor_row = Adw.ActionRow()
        vendor_row.set_title("Manufacturer")
        vendor_row.set_subtitle(utils.get_vendor())
        # Set Vender row to emblem-ok-symbolic
        vendor_row.set_icon_name("emblem-ok-symbolic")

        model_row = Adw.ActionRow()
        model_row.set_title("Model")
        model_row.set_subtitle(utils.get_model())
        # Set Model row to emblem-ok-symbolic
        model_row.set_icon_name("emblem-ok-symbolic")

        cpu_row = Adw.ActionRow()
        cpu_row.set_title("CPU")
        cpu_row.set_subtitle(utils.get_cpu_info())
        # Set CPU row to emblem-ok-symbolic
        cpu_row.set_icon_name("emblem-ok-symbolic")

        self.mem_row = Adw.ActionRow()
        self.mem_row.set_title("Memory")
        self.mem_row.set_subtitle(utils.get_mem() + " GB")

        self.disks_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self.battery_row = Adw.ExpanderRow(title="Batteries")
        self.battery_row.set_visible(False)
        self.battery_row.set_expanded(True)

        self.bios_password_row = Adw.ActionRow()
        self.bios_password_row.set_title("BIOS Password")

        self.asset_info_row = Adw.ActionRow()
        self.asset_info_row.set_title("Asset Info")

        self.computrace_row = Adw.ActionRow()
        self.computrace_row.set_title("Computrace/Absolute")

        # Add rows to the list box
        list_box.append(vendor_row)
        list_box.append(model_row)
        list_box.append(self.bios_password_row)
        list_box.append(self.asset_info_row)
        list_box.append(self.computrace_row)
        list_box.append(cpu_row)
        list_box.append(self.mem_row)
        list_box.append(self.disks_box)
        list_box.append(self.battery_row)

        vbox.append(list_box)
        scrolled_window.set_child(vbox)
        self.set_child(scrolled_window)

    # on_shown is called when the page is shown in the stack
    def on_shown(self):
        utils = Utils()
        utils.sync_clock()

        # Start with default of passed and set to False if we find any failures
        passed = True

        # Set Memory row to emblem-ok-symbolic if memory is greater than or equal to 7 GB, else set row to emblem-important-symbolic
        mem = int(utils.get_mem())
        if mem >= 7:
            self.mem_row.set_icon_name("emblem-ok-symbolic")
            if self.mem_row.has_css_class("text-error"):
                self.mem_row.remove_css_class("text-error")
        else:
            self.mem_row.set_icon_name("emblem-important-symbolic")
            self.mem_row.add_css_class("text-error")

        bios_password = utils.has_bios_password()
        if bios_password:
            self.bios_password_row.set_subtitle("Has Password")
            self.bios_password_row.set_icon_name("emblem-important-symbolic")
            self.bios_password_row.add_css_class("text-error")
            passed = False
        else:
            self.bios_password_row.set_subtitle("No Password")
            self.bios_password_row.set_icon_name("emblem-ok-symbolic")

        asset_info = utils.has_asset_info()
        if asset_info:
            self.asset_info_row.set_subtitle("Has Asset Info")
            self.asset_info_row.set_icon_name("emblem-important-symbolic")
            self.asset_info_row.add_css_class("text-error")
            passed = False
        else:
            self.asset_info_row.set_subtitle("No Asset Info")
            self.asset_info_row.set_icon_name("emblem-ok-symbolic")

        computrace_enabled = utils.has_computrace_enabled()
        if computrace_enabled is True:
            self.computrace_row.set_subtitle("Enabled")
            self.computrace_row.set_icon_name("emblem-important-symbolic")
            self.computrace_row.add_css_class("text-error")
            passed = False
        elif computrace_enabled is False:
            self.computrace_row.set_subtitle("Disabled")
            self.computrace_row.set_icon_name("emblem-ok-symbolic")
        else:
            self.computrace_row.set_subtitle("Unknown")
            self.computrace_row.set_icon_name("emblem-ok-symbolic")

        # Populate disk information
        if not self.disks_populated:
            disks = utils.get_disks()
            if len(disks.keys()) > 0:
                passed = False
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
            elif len(disks.keys()) == 1:
                disk = list(disks.items())
                disk_row = Adw.ExpanderRow(title="Disk")
                disk_row.set_visible(True)
                disk_row.set_expanded(True)
                row = Adw.ActionRow()
                row.set_title(f"{str(disk[0][0])}")
                row.set_subtitle(f"{str(disk[0][1])} GB")
                row.set_icon_name("emblem-important-symbolic")
                row.add_css_class("text-error")
                disk_row.add_row(row)
                self.disks_box.append(disk_row)
            else:
                disk_row = Adw.ActionRow(title="Disk")
                disk_row.set_subtitle(f"No Disks Found")
                disk_row.set_icon_name("emblem-ok-symbolic")
                if disk_row.has_css_class("text-error"):
                    disk_row.remove_css_class("text-error")
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
        state['SpecInfo'] = passed
        print("specinfo:on_shown " + str(self.state.get_value()))
