import requests
import time
import json
from tkinter import *
from tkinter import ttk
from tkinter import Frame
from PIL import Image, ImageTk
from io import BytesIO

CLIENT_ID = "82e8e1b184b54b5a9d534f6382a8f9e2"
CLIENT_SECRET = "93ed466fd50e498a8fb9c0e486ecebe7"

TOKEN_FILE = "/home/lukaz/pi-phone/software/tokens.json"


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
    print("TOGGLE CALLED")

    global access_token

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    r = requests.get(
        "https://api.spotify.com/v1/me/player",
        headers=headers
    )

    print("STATUS:", r.status_code)

    if r.status_code == 200:
        data = r.json()
        is_playing = data["is_playing"]
        print("IS PLAYING:", is_playing)

        if is_playing:
            print("PAUSE")
            requests.put(
                "https://api.spotify.com/v1/me/player/pause",
                headers=headers
            )
        else:
            print("PLAY")
            requests.put(
                "https://api.spotify.com/v1/me/player/play",
                headers=headers
            )

def next_track():
    headers = {"Authorization": f"Bearer {access_token}"}
    requests.post("https://api.spotify.com/v1/me/player/next", headers=headers)

def prev_track():
    headers = {"Authorization": f"Bearer {access_token}"}
    requests.post("https://api.spotify.com/v1/me/player/previous", headers=headers)


# UI setup
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

prev_btn = Button(controls_frame, text="⏮", font=("Arial", 20), command=lambda: prev_track())
prev_btn.pack(side=LEFT, padx=20)

play_btn = Button(controls_frame, text="⏯", font=("Arial", 20), command=lambda: toggle_play())
play_btn.pack(side=LEFT, padx=20)

next_btn = Button(controls_frame, text="⏭", font=("Arial", 20), command=lambda: next_track())
next_btn.pack(side=LEFT, padx=20)

access_token = get_access_token()


def update():
    global access_token

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    r = requests.get(
        "https://api.spotify.com/v1/me/player/currently-playing",
        headers=headers
    )

    if r.status_code == 401:
        access_token = get_access_token()
        return

    if r.status_code == 200:
        data = r.json()

        if data and data.get("item"):
            track = data["item"]["name"]
            artist = data["item"]["artists"][0]["name"]
            image_url = data["item"]["album"]["images"][0]["url"]

            # tekst
            track_label.config(text=track)
            artist_label.config(text=artist)

            # cover
            img_data = requests.get(image_url).content
            img = Image.open(BytesIO(img_data))
            img = img.resize((300, 300))

            progress_ms = data["progress_ms"]
            duration_ms = data["item"]["duration_ms"]

            # progress bar (0–100)
            percent = (progress_ms / duration_ms) * 100
            progress["value"] = percent

            # vrijeme
            current = ms_to_min_sec(progress_ms)
            total = ms_to_min_sec(duration_ms)

            time_label.config(text=f"{current} / {total}")

            photo = ImageTk.PhotoImage(img)
            cover_label.config(image=photo)
            cover_label.image = photo

    root.after(1000, update)


update()
root.mainloop()
