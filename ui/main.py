import time
import json
from tkinter import *
from tkinter import ttk, Frame
from PIL import Image, ImageTk
from io import BytesIO
from app import controller

SONG_STATE_FILE = "/home/lukaz/pi-phone/state/song_state.json"

root = Tk()
root.attributes('-fullscreen', True)
root.configure(bg="black")
root.bind("<Escape>", lambda e: root.destroy())

cover_label = Label(root, bg="black")
cover_label.pack(pady=20)

track_label = Label(root, text="", fg="white", bg="black", font=("Arial", 20))
track_label.pack()

artist_label = Label(root, text="", fg="gray", bg="black", font=("Arial", 16))
artist_label.pack()

progress = ttk.Progressbar(root, orient="horizontal", length=300, mode="determinate")
progress.pack(pady=20)

time_label = Label(root, text="", fg="white", bg="black", font=("Arial", 12))
time_label.pack()

controls_frame = Frame(root, bg="black")
controls_frame.pack(pady=20)

def on_toggle_play():
    controller.on_toggle_play()

Button(controls_frame, text="⏮", font=("Arial", 20), command=controller.on_prev).pack(side=LEFT, padx=20)
play_button = Button(controls_frame, text="⏸", font=("Arial", 20), command=on_toggle_play)
play_button.pack(side=LEFT, padx=20)
Button(controls_frame, text="⏭", font=("Arial", 20), command=controller.on_next).pack(side=LEFT, padx=20)

# SEEK wrapper (UI računa, controller izvršava)
def on_seek(event):
    width = progress.winfo_width()
    ratio = max(0, min(event.x / width, 1))
    position_ms = int(ratio * controller.get_state()["duration_ms"])
    controller.on_seek(position_ms)

progress.bind("<Button-1>", on_seek)

last_image_url = None
cached_photo = None

def ms_to_min_sec(ms):
    seconds = ms // 1000
    return f"{seconds//60}:{seconds%60:02d}"

def update_ui():
    global last_image_url, cached_photo

    state = controller.get_state()

    if not state:
        root.after(200, update_ui)
        return

    playing = state.get("is_playing", False)
    play_button.config(text="⏸" if playing else "▶")


    track_label.config(text=state["track"])
    artist_label.config(text=state["artist"])

    # image caching
    if state["image_url"] != last_image_url and state["image_url"]:
        img_data = controller.fetch_image(state["image_url"])
        img = Image.open(BytesIO(img_data)).resize((300, 300))
        cached_photo = ImageTk.PhotoImage(img)
        last_image_url = state["image_url"]

    if cached_photo:
        cover_label.config(image=cached_photo)
        cover_label.image = cached_photo

    percent = (state["progress_ms"] / state["duration_ms"]) * 100 if state["duration_ms"] else 0
    progress["value"] = percent

    current = ms_to_min_sec(int(state["progress_ms"]))
    total = ms_to_min_sec(state["duration_ms"])

    time_label.config(text=f"{current} / {total}")

    root.after(100, update_ui)

controller.start_sync()
update_ui()
root.mainloop()