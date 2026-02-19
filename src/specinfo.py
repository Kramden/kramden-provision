import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
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
        self.disk_override = False
        self.bios_password_override = False
        self.asset_info_override = False
        self.has_disks = False
        self._disk_error_widgets = []
        self._bios_password_override_button = None
        self._asset_info_override_button = None
        self.sortly_register = None

        # Create a box to hold the content
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        # Create scrollable window
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        # Create a list box to hold the rows
        list_box = Gtk.ListBox()
        list_box.set_selection_mode(Gtk.SelectionMode.NONE)

        self.knumber_row = Adw.ActionRow()
        self.knumber_row.set_title("K-Number")

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

        gpu_row = Adw.ActionRow()
        gpu_row.set_title("Discrete GPU")
        discrete_gpu = utils.get_discrete_gpu()
        if discrete_gpu:
            gpu_row.set_subtitle(discrete_gpu)
        else:
            gpu_row.set_subtitle("None")
        gpu_row.set_icon_name("emblem-ok-symbolic")

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
        list_box.append(self.knumber_row)
        list_box.append(vendor_row)
        list_box.append(model_row)
        list_box.append(self.bios_password_row)
        list_box.append(self.asset_info_row)
        list_box.append(self.computrace_row)
        list_box.append(cpu_row)
        list_box.append(self.mem_row)
        list_box.append(gpu_row)
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

        # Read K-Number from the Sortly registration page
        knumber = ""
        if self.sortly_register:
            raw = self.sortly_register.knumber_entry.get_text().strip()
            formatted = Utils.format_knumber(raw)
            knumber = formatted or raw
        self.knumber_row.set_subtitle(knumber)
        if knumber and (
            knumber.lower().startswith("k") or knumber.lower().startswith("test")
        ):
            self.knumber_row.set_icon_name("emblem-ok-symbolic")
            if self.knumber_row.has_css_class("text-error"):
                self.knumber_row.remove_css_class("text-error")
        else:
            self.knumber_row.set_icon_name("emblem-important-symbolic")
            self.knumber_row.add_css_class("text-error")

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
        if bios_password and not self.bios_password_override:
            self.bios_password_row.set_subtitle("Has Password")
            self.bios_password_row.set_icon_name("emblem-important-symbolic")
            self.bios_password_row.add_css_class("text-error")
            if not self._bios_password_override_button:
                self._bios_password_override_button = self._add_override_button(
                    self.bios_password_row,
                    "BIOS Password Override",
                    self._on_bios_password_override_accepted,
                )
            passed = False
        else:
            self.bios_password_row.set_subtitle("No Password" if not bios_password else "Has Password (Overridden)")
            self.bios_password_row.set_icon_name("emblem-ok-symbolic")
            if self.bios_password_row.has_css_class("text-error"):
                self.bios_password_row.remove_css_class("text-error")

        asset_info = utils.has_asset_info()
        if asset_info and not self.asset_info_override:
            self.asset_info_row.set_subtitle("Has Asset Info")
            self.asset_info_row.set_icon_name("emblem-important-symbolic")
            self.asset_info_row.add_css_class("text-error")
            if not self._asset_info_override_button:
                self._asset_info_override_button = self._add_override_button(
                    self.asset_info_row,
                    "Asset Info Override",
                    self._on_asset_info_override_accepted,
                )
            passed = False
        else:
            self.asset_info_row.set_subtitle("No Asset Info" if not asset_info else "Has Asset Info (Overridden)")
            self.asset_info_row.set_icon_name("emblem-ok-symbolic")
            if self.asset_info_row.has_css_class("text-error"):
                self.asset_info_row.remove_css_class("text-error")

        computrace_activated = utils.has_computrace_enabled()
        if computrace_activated is True:
            self.computrace_row.set_subtitle("Activated")
            self.computrace_row.set_icon_name("emblem-important-symbolic")
            self.computrace_row.add_css_class("text-error")
            passed = False
        elif computrace_activated is False:
            self.computrace_row.set_subtitle("Not Activated")
            self.computrace_row.set_icon_name("emblem-ok-symbolic")
        else:
            self.computrace_row.set_subtitle("Unknown")
            self.computrace_row.set_icon_name("emblem-ok-symbolic")

        # Populate disk information
        if not self.disks_populated:
            disks = utils.get_disks()
            if len(disks.keys()) > 0:
                self.has_disks = True
            if len(disks.keys()) > 1:
                disks_row = Adw.ExpanderRow(title="Disks")
                disks_row.set_visible(True)
                disks_row.set_expanded(True)
                for disk in disks.keys():
                    row = Adw.ActionRow()
                    row.set_title(f"{str(disk)})")
                    disk_info = disks[disk]
                    row.set_subtitle(f"{disk_info['type']}: {disk_info['size']} GB")
                    disks_row.add_row(row)
                    disks_row.set_expanded(True)
                    disks_row.set_visible(True)
                    disks_row.set_icon_name("emblem-important-symbolic")
                    disks_row.add_css_class("text-error")
                self._disk_error_widgets.append(disks_row)
                self._add_disk_override_button(disks_row)
                self.disks_box.append(disks_row)
            elif len(disks.keys()) == 1:
                disk = list(disks.items())
                disk_row = Adw.ExpanderRow(title="Disk")
                disk_row.set_visible(True)
                disk_row.set_expanded(True)
                row = Adw.ActionRow()
                row.set_title(f"{str(disk[0][0])}")
                disk_info = disk[0][1]
                row.set_subtitle(f"{disk_info['type']}: {disk_info['size']} GB")
                row.set_icon_name("emblem-important-symbolic")
                row.add_css_class("text-error")
                self._disk_error_widgets.append(row)
                disk_row.add_row(row)
                self._add_disk_override_button(disk_row)
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

        # Check disk override status (runs every time on_shown is called)
        if self.has_disks and not self.disk_override:
            passed = False

        # Populate battery information
        if not self.batteries_populated:
            # Populate battery info
            batteries = utils.get_battery_capacities()
            if len(batteries) == 1:
                self.battery_row.set_title("Battery")
            for battery in batteries.keys():
                row = Adw.ActionRow()
                row.set_title(str(battery))
                row.set_subtitle(f"Capacity: {str(batteries[battery])}%")
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
        state["SpecInfo"] = passed
        print("specinfo:on_shown " + str(self.state.get_value()))

    def _add_override_button(self, parent_row, dialog_title, on_accepted):
        """Add an Override button to the given row. Returns the button."""
        override_button = Gtk.Button(label="Override")
        override_button.set_valign(Gtk.Align.CENTER)
        override_button.connect(
            "clicked",
            lambda b: self._show_override_dialog(dialog_title, override_button, on_accepted),
        )
        parent_row.add_suffix(override_button)
        return override_button

    def _add_disk_override_button(self, parent_row):
        """Add an Override button to the given disk row."""
        self._disk_override_button = Gtk.Button(label="Override")
        self._disk_override_button.set_valign(Gtk.Align.CENTER)
        self._disk_override_button.connect(
            "clicked",
            lambda b: self._show_override_dialog(
                "Disk Override", self._disk_override_button, self._on_disk_override_accepted
            ),
        )
        parent_row.add_suffix(self._disk_override_button)

    def _show_override_dialog(self, title, override_button, on_accepted):
        """Show a password dialog for overriding a check."""
        dialog = Gtk.Window()
        dialog.set_title(title)
        dialog.set_transient_for(self.get_root())
        dialog.set_modal(True)
        dialog.set_default_size(350, -1)
        dialog.set_resizable(False)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        label = Gtk.Label(label="Enter staff password to override:")
        box.append(label)

        entry = Gtk.PasswordEntry()
        entry.set_show_peek_icon(True)
        box.append(entry)

        error_label = Gtk.Label(label="")
        error_label.add_css_class("text-error")
        box.append(error_label)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda b: dialog.close())
        btn_box.append(cancel_btn)

        ok_btn = Gtk.Button(label="OK")
        ok_btn.add_css_class("suggested-action")
        ok_btn.connect(
            "clicked",
            self._on_override_ok, entry, error_label, dialog, override_button, on_accepted,
        )
        btn_box.append(ok_btn)

        entry.connect(
            "activate",
            lambda e: self._on_override_ok(
                ok_btn, entry, error_label, dialog, override_button, on_accepted
            ),
        )

        box.append(btn_box)
        dialog.set_child(box)
        dialog.present()

    def _on_override_ok(self, button, entry, error_label, dialog, override_button, on_accepted):
        if entry.get_text() == "kramdenok":
            on_accepted()
            override_button.set_visible(False)
            dialog.close()
            self.on_shown()
        else:
            error_label.set_label("Incorrect password")
            entry.set_text("")
            entry.grab_focus()

    def _on_disk_override_accepted(self):
        self.disk_override = True
        for widget in self._disk_error_widgets:
            widget.set_icon_name("emblem-ok-symbolic")
            if widget.has_css_class("text-error"):
                widget.remove_css_class("text-error")

    def _on_bios_password_override_accepted(self):
        self.bios_password_override = True

    def _on_asset_info_override_accepted(self):
        self.asset_info_override = True
