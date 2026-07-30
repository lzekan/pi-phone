from tkinter import Tk
from app.features.spotify.services.daemon_client import start_sync
from app.ui.app_ui import start_ui

root = Tk()
root.configure(bg="black")

start_sync(root)
start_ui(root)

root.mainloop()