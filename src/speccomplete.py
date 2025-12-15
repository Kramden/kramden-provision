import gi
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk
from utils import Utils

class SpecComplete(Adw.Bin):
    def __init__(self):
        super().__init__()
        self.set_margin_top(20)
        self.set_margin_bottom(20)
        self.set_margin_start(20)
        self.set_margin_end(20)
        self.title = "Kramden Spec Complete"
        self.skip = False
        
        # Create a list box to hold the rows
        list_box = Gtk.ListBox()
        list_box.set_selection_mode(Gtk.SelectionMode.NONE)

        # Create Adwaita rows
        self.title_row = Adw.ActionRow()
        self.title_row.set_title("<b>Kramden Spec Complete</b>")
        
        self.complete_row = Adw.ActionRow()
        self.complete_row.set_title("")

        list_box.append(self.title_row)
        list_box.append(self.complete_row)

        self.set_child(list_box)

    def complete(self):
        print("SpecComplete: complete")
        utils = Utils()
        utils.complete_reset("spec")

    # on_shown is called when the page is shown in the stack
    def on_shown(self):
        print("SpecComplete: on_shown")
        state = self.state.get_value()
        if all(state.values()):
            print("SpecComplete: All passed")
            self.complete_row.set_title("Kramden Spec Complete: <b>PASSED</b>!")
            self.complete_row.set_subtitle(str(state))
        else:
            print("SpecComplete: Failed")
            self.complete_row.set_title("Kramden Spec Complete: <b>FAILED</b>!")
            self.complete_row.set_subtitle(str(state))
