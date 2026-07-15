import os
import requests
import time
import json
from tkinter import *
from tkinter import ttk, Frame
from PIL import Image, ImageTk
from io import BytesIO

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

TOKEN_FILE = "/home/lukaz/pi-phone/software/tokens.json"
STATE_FILE = "/home/lukaz/pi-phone/software/state.json"

last_progress_ms = 0
last_update_time = time.time()
duration_ms = 1
is_playing = False

last_track_id = None

resetting = False
reset_start_time = 0
reset_duration = 0.5

ignore_state_updates_until = 0

last_image_url = None
cached_photo = None


def load_refresh_token():
    with open(TOKEN_FILE, "r") as f:
        return json.load(f)["refresh_token"]


def get_access_token():
    refresh_token = load_refresh_token()

    response = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET
        }
    )

    data = response.json()
    return data["access_token"]


def ms_to_min_sec(ms):
    seconds = ms // 1000
    return f"{seconds//60}:{seconds%60:02d}"


def toggle_play():
    global access_token
    headers = {"Authorization": f"Bearer {access_token}"}

    r = requests.get("https://api.spotify.com/v1/me/player", headers=headers)

    if r.status_code == 200:
        data = r.json()
        if data["is_playing"]:
            requests.put("https://api.spotify.com/v1/me/player/pause", headers=headers)
        else:
            requests.put("https://api.spotify.com/v1/me/player/play", headers=headers)


def next_track():
    headers = {"Authorization": f"Bearer {access_token}"}
    requests.post("https://api.spotify.com/v1/me/player/next", headers=headers)
    time.sleep(reset_duration)  # kratko čekanje da se promjena reflektira
    requests.put("https://api.spotify.com/v1/me/player/play", headers=headers)


def prev_track():
    headers = {"Authorization": f"Bearer {access_token}"}
    requests.post("https://api.spotify.com/v1/me/player/previous", headers=headers)
    time.sleep(reset_duration)  # kratko čekanje da se promjena reflektira
    requests.put("https://api.spotify.com/v1/me/player/play", headers=headers)


def seek(event):
    global last_progress_ms, last_update_time
    global ignore_state_updates_until

    ignore_state_updates_until = time.time() + 1.5

    width = progress.winfo_width()
    click_ratio = event.x / width

    click_ratio = max(0, min(click_ratio, 1))

    position_ms = int(click_ratio * duration_ms)

    headers = {"Authorization": f"Bearer {access_token}"}

    requests.put(
        f"https://api.spotify.com/v1/me/player/seek?position_ms={position_ms}",
        headers=headers
    )

    last_progress_ms = position_ms
    last_update_time = time.time()

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
progress.bind("<Button-1>", seek)

time_label = Label(root, text="", fg="white", bg="black", font=("Arial", 12))
time_label.pack()

controls_frame = Frame(root, bg="black")
controls_frame.pack(pady=20)

Button(controls_frame, text="⏮", font=("Arial", 20), command=prev_track).pack(side=LEFT, padx=20)
Button(controls_frame, text="⏯", font=("Arial", 20), command=toggle_play).pack(side=LEFT, padx=20)
Button(controls_frame, text="⏭", font=("Arial", 20), command=next_track).pack(side=LEFT, padx=20)

debug_frame = Frame(root, bg="black")
debug_frame.pack(side=RIGHT, fill=Y, padx=20)

debug_text = Text(
    debug_frame,
    width=40,
    height=30,
    bg="black",
    fg="lime",
    font=("Courier", 10)
)
debug_text.pack()

access_token = get_access_token()

def update_debug():
    try:
        with open("/home/lukaz/pi-phone/software/state.json", "r") as f:
            data = json.load(f)

        debug_text.delete("1.0", END)
        debug_text.insert(END, json.dumps(data, indent=2))

    except Exception as e:
        debug_text.delete("1.0", END)
        debug_text.insert(END, f"ERROR:\n{e}")

    root.after(200, update_debug)

def sync_spotify():
    global access_token, last_progress_ms, duration_ms, is_playing, last_update_time
    global last_track_id, resetting, reset_start_time
    global last_image_url, cached_photo


    with open(STATE_FILE, "r") as f:
        state = json.load(f)

    headers = {"Authorization": f"Bearer {access_token}"}

    if state:
        track_id = state["track_id"]

        if track_id != last_track_id:
            last_track_id = track_id
            resetting = True
            reset_start_time = time.time()

            track_label.config(text=state["track"])
            artist_label.config(text=state["artist"])

            image_url = state["image_url"]

            if image_url != last_image_url:
                img_data = requests.get(image_url).content
                img = Image.open(BytesIO(img_data)).resize((300, 300))
                cached_photo = ImageTk.PhotoImage(img)
                last_image_url = image_url

                cover_label.config(image=cached_photo)
                cover_label.image = cached_photo

        if time.time() > ignore_state_updates_until:
            last_progress_ms = state["progress_ms"]
            last_update_time = time.time()

        duration_ms = state["duration_ms"]
        is_playing = state["is_playing"]

    root.after(1000, sync_spotify)


def update_ui():
    global last_progress_ms, duration_ms, is_playing, last_update_time
    global resetting, reset_start_time, ignore_state_updates_until

    now = time.time()

    if resetting:
        t = (now - reset_start_time) / reset_duration

        if t >= 1:
            resetting = False
            target_progress = 0
            last_progress_ms = 0
            last_update_time = now
        else:
            target_progress = (1 - t) * last_progress_ms
    else:
        if is_playing:
            elapsed = (now - last_update_time) * 1000
            target_progress = min(last_progress_ms + elapsed, duration_ms)
        else:
            target_progress = last_progress_ms

    # SMOOTHING (lerp)
    current = progress["value"] / 100 * duration_ms
    smoothed_progress = current + (target_progress - current) * 0.4

    percent = min((smoothed_progress / duration_ms) * 100, 100)
    progress["value"] = percent

    current_time = ms_to_min_sec(int(smoothed_progress))
    total = ms_to_min_sec(duration_ms)

    time_label.config(text=f"{current_time} / {total}")

    root.after(100, update_ui)


sync_spotify()
update_ui()
update_debug()
root.mainloop()
