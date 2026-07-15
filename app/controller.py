import json
import time
import requests
from software import spotify_service

SONG_STATE_FILE = "/home/lukaz/pi-phone/state/song_state.json"

_state = {
    "track": "",
    "artist": "",
    "progress_ms": 0,
    "duration_ms": 1,
    "is_playing": False,
    "image_url": None
}

# ---- SEEK ----
pending_seek_position = None
seek_start_time = 0

# ---- PLAY ----
pending_play_state = None
play_start_time = 0


def start_sync():
    _sync()


def _sync():
    global _state
    global pending_play_state, play_start_time
    global pending_seek_position, seek_start_time

    try:
        with open(SONG_STATE_FILE, "r") as f:
            state = json.load(f)

        now = time.time()

        # ---- ALWAYS UPDATE ----
        _state["track"] = state.get("track")
        _state["artist"] = state.get("artist")
        _state["duration_ms"] = state.get("duration_ms", 1)
        _state["image_url"] = state.get("image_url")

        # ---- PROGRESS ----
        incoming_progress = state.get("progress_ms", 0)

        if pending_seek_position is None:
            _state["progress_ms"] = incoming_progress
        else:
            # prihvati kad smo blizu targeta
            if abs(incoming_progress - pending_seek_position) < 1500:
                _state["progress_ms"] = incoming_progress
                pending_seek_position = None

            # fallback ako daemon kasni
            elif now - seek_start_time > 2:
                _state["progress_ms"] = incoming_progress
                pending_seek_position = None

        # ---- PLAY STATE ----
        incoming_play = state.get("is_playing", False)

        if pending_play_state is None:
            _state["is_playing"] = incoming_play
        else:
            # očekivano stanje stiglo
            if incoming_play == pending_play_state:
                _state["is_playing"] = incoming_play
                pending_play_state = None

            # fallback ako nikad ne dođe expected state
            elif now - play_start_time > 2:
                _state["is_playing"] = incoming_play
                pending_play_state = None

    except:
        pass

    import tkinter as tk
    root = tk._default_root
    root.after(300, _sync)


def get_state():
    return _state


# -------- EVENTS --------

def on_toggle_play():
    global pending_play_state, play_start_time

    pending_play_state = not _state["is_playing"]
    play_start_time = time.time()

    # instant UI
    _state["is_playing"] = pending_play_state

    spotify_service.toggle()


def on_next():
    global pending_play_state, play_start_time
    global pending_seek_position, seek_start_time

    # reset progress odmah
    _state["progress_ms"] = 0

    # očekujemo play state
    pending_play_state = True
    play_start_time = time.time()
    _state["is_playing"] = True

    # reset seek
    pending_seek_position = 0
    seek_start_time = time.time()

    spotify_service.next_track()


def on_prev():
    global pending_play_state, play_start_time
    global pending_seek_position, seek_start_time

    _state["progress_ms"] = 0

    pending_play_state = True
    play_start_time = time.time()
    _state["is_playing"] = True

    pending_seek_position = 0
    seek_start_time = time.time()

    spotify_service.prev_track()


def on_seek(position_ms):
    global pending_seek_position, seek_start_time

    pending_seek_position = position_ms
    seek_start_time = time.time()

    # instant UI
    _state["progress_ms"] = position_ms

    spotify_service.seek(position_ms)


# -------- UTILS --------

def fetch_image(url):
    return requests.get(url).content