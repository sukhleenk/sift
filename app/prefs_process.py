import tkinter as tk
from app.wizard import load_config
from app.preferences import PreferencesWindow


def main():
    config = load_config() or {}

    root = tk.Tk()
    root.withdraw()  # hide the root, we only want the Toplevel from PreferencesWindow

    def on_save(new_config):
        root.quit()

    win = PreferencesWindow(config, on_save=on_save)
    win.show()
    win.root.protocol("WM_DELETE_WINDOW", root.quit)

    root.mainloop()


if __name__ == "__main__":
    main()
