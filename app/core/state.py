_state = {
    "song": {
        "source": "spotify",
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
    "queue": [],
    "spotify_manual_queue": [],
    "screen": "launcher",
    "previous_screen": "home",
    "recent_tracks": [],
    "device_recent_tracks": [],
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
    "current_collection_next_offset": None,
    "current_collection_total": None,
    "collection_loading": False,
    "current_collection_image_url": "",
    "search_query": "",
    "search_type": "track",
    "search_results": [],
    "search_loading": False,
    "search_error": None,
    "local": {
        "tracks": [],
        "current_index": None,
        "loading": False,
        "loaded": False,
        "error": None
    },
    "playback_owner": None
}


def get_state():
    return _state

def get_song_state():
    return _state["song"]
