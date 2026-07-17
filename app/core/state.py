_state = {
    "song": {
        "track_id": None,
        "track": "",
        "artist": "",
        "progress_ms": 0,
        "duration_ms": 1,
        "is_playing": False,
        "image_url": None
    },
    "next_song": None,
    "screen": "home",
    "recent_tracks": [],
    "playlists": [],
    "user": {},
    "home_loading": False,
    "home_error": None
}


def get_state():
    return _state

def get_song_state():
    return _state["song"]

def update_song(data):
    _state["song"].update(data)

def set_screen(screen):
    _state["screen"] = screen

def set_home_data(tracks, playlists):
    _state["recent_tracks"] = tracks
    _state["playlists"] = playlists

def set_user(user):
    _state["user"] = user
