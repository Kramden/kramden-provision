import gi
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk
from utils import Utils

class FinalTestComplete(Adw.Bin):
    def __init__(self):
        super().__init__()
        self.set_margin_top(20)
        self.set_margin_bottom(20)
        self.set_margin_start(20)
        self.set_margin_end(20)
        self.title = "Final Test Complete"
        
        # Create a list box to hold the rows
        list_box = Gtk.ListBox()
        list_box.set_selection_mode(Gtk.SelectionMode.NONE)

        # Create Adwaita rows
        self.title_row = Adw.ActionRow()
        self.title_row.set_title("<b>Final Test Complete</b>")
        
        self.complete_row = Adw.ActionRow()
        self.complete_row.set_title("")

        list_box.append(self.title_row)
        list_box.append(self.complete_row)

        self.set_child(list_box)

    def complete(self):
        print("FinatTestComplete: complete")
        utils = Utils()
        utils.complete_reset("finaltest")

    # on_shown is called when the page is shown in the stack
    def on_shown(self):
        print("FinalTestComplete: on_shown")
        state = self.state.get_value()
        if all(state.values()):
            print("FinalTestComplete: All passed")
            self.complete_row.set_title("Final Test Complete: <b>PASSED</b>!")
            self.complete_row.set_subtitle(str(state))
        else:
            print("FinalTestComplete: Failed")
            self.complete_row.set_title("Final Test Complete: <b>FAILED</b>!")
            self.complete_row.set_subtitle(str(state))
