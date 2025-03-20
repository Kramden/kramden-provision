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
        self.skip = None

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

        self.disk_row = Adw.ActionRow()
        self.disk_row.set_title("Disk")
        self.disk_row.set_subtitle(utils.get_disk() + " GB")

        batteries = utils.get_battery_capacities()
        battery_row = None
        if len(batteries.keys()) == 1:
            battery_row = Adw.ActionRow()
            battery_row.set_title("Battery Capacity")
            battery_row.set_subtitle(f'{str(list(batteries.items())[0][1])}%')
            # Set Battery row to emblem-ok-symbolic if battery capacity is greater than 70%, else set row to emblem-important-symbolic
            if int(list(batteries.items())[0][1]) >= 70:
                battery_row.set_icon_name("emblem-ok-symbolic")
            else:
                battery_row.set_icon_name("emblem-important-symbolic")
        elif len(batteries.keys()) > 1:
            battery_row = Adw.ExpanderRow(title="Batteries")
            for battery in batteries.keys():
                row = Adw.ActionRow(title=battery, subtitle=f'{batteries[battery]}%')
                battery_row.add_row(row)
                # Set Battery row to emblem-ok-symbolic if battery capacity is greater than 70%, else set row to emblem-important-symbolic
                if int(batteries[battery]) >= 70:
                    battery_row.set_expanded(False)
                    row.set_icon_name("emblem-ok-symbolic")
                else:
                    battery_row.set_expanded(True)
                    row.set_icon_name("emblem-important-symbolic")

        batteries = utils.get_battery_capacities()
        battery_row = None
        if len(batteries.keys()) == 1:
            battery_row = Adw.ActionRow()
            battery_row.set_title("Battery Capacity")
            battery_list = list(batteries.items())[0][1]
            battery_row.set_subtitle(f'{str(battery_list)}%')
            # Set Battery row to emblem-ok-symbolic if battery capacity is greater than 70%, else set row to emblem-important-symbolic
            if int(battery_list) >= 70:
                battery_row.set_icon_name("emblem-ok-symbolic")
            else:
                battery_row.set_icon_name("emblem-important-symbolic")
        elif len(batteries.keys()) > 1:
            battery_row = Adw.ExpanderRow(title="Batteries")
            for battery in batteries.keys():
                row = Adw.ActionRow(title=battery, subtitle=f'{batteries[battery]}%')
                battery_row.add_row(row)
                # Set Battery row to emblem-ok-symbolic if battery capacity is greater than 70%, else set row to emblem-important-symbolic
                if int(batteries[battery]) >= 70:
                    battery_row.set_expanded(False)
                    row.set_icon_name("emblem-ok-symbolic")
                else:
                    battery_row.set_expanded(True)
                    row.set_icon_name("emblem-important-symbolic")

        # Add rows to the list box
        list_box.append(self.hostname_row)
        list_box.append(self.landscape_row)
        list_box.append(vender_row)
        list_box.append(model_row)
        list_box.append(cpu_row)
        list_box.append(os_row)
        list_box.append(self.mem_row)
        list_box.append(self.disk_row)
        if battery_row: 
            list_box.append(battery_row)

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
        else:
            self.hostname_row.set_icon_name("emblem-important-symbolic")
            passed = False

        # Landscape registration status
        if utils.is_registered():
            self.landscape_row.set_subtitle("Registered")
            self.landscape_row.set_icon_name("emblem-ok-symbolic")
        else:
            self.landscape_row.set_subtitle("Not registered")
            self.landscape_row.set_icon_name("emblem-important-symbolic")
            passed = False

        # Set Memory row to emblem-ok-symbolic if memory is greater than or equal to 7 GB, else set row to emblem-important-symbolic
        mem = int(utils.get_mem())
        if mem >= 7:
            self.mem_row.set_icon_name("emblem-ok-symbolic")
        else:
            self.mem_row.set_icon_name("emblem-important-symbolic")
            passed = False

        # Set Disk row to emblem-ok-symbolic if disk capacity is 120 GB or greater, else set row to emblem-important-symbolic
        disk = int(utils.get_disk())
        if disk >= 120:
            self.disk_row.set_icon_name("emblem-ok-symbolic")
        else:
            self.disk_row.set_icon_name("emblem-important-symbolic")
            passed = False

        state = self.state.get_value()
        state['SysInfo'] = passed
        print("sysinfo:on_shown " + str(self.state.get_value()))
