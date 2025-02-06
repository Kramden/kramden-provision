import gi
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk

class FinalTestComplete(Adw.Bin):
    def __init__(self):
        super().__init__()
        self.set_margin_top(20)
        self.set_margin_bottom(20)
        self.set_margin_start(20)
        self.set_margin_end(20)
        self.title = "Final Test Complete!"
        
        self.label = Gtk.Label(label="Final Test Complete!")
        self.set_child(self.label)

    # on_shown is called when the page is shown in the stack
    def on_shown(self):
        state = self.state.get_value()
        if all(state.values()):
            print("All passed")
            self.label.set_text("Final Test Complete!")
        else:
            print("Failed")
            self.label.set_text("Final Test Failed")
