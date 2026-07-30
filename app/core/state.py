_state = {
    "song": {
        "track_id": None,
        "track": "",
        "artist": "",
        "album_name": "",
        "album_id": "",
        "progress_ms": 0,
        "duration_ms": 1,
        "is_playing": False,
        "image_url": None
    },
    "next_song": None,
    "screen": "launcher",
    "previous_screen": "home",
    "recent_tracks": [],
    "playlists": [],
    "albums": [],
    "user": {},
    "home_loading": False,
    "home_error": None,
    "collection_error": None,
    "current_collection_type": None,
    "current_collection_uri": None,
    "current_collection_name": None,
    "current_collection_tracks": None,
    "current_collection_image_url": "",
    "search_query": "",
    "search_results": [],
    "search_loading": False,
    "search_error": None
}


def get_state():
    return _state

def get_song_state():
    return _state["song"]
