from threading import Lock

from app.core.state import get_state
from app.features.local_audio import playback_service
from app.features.spotify.services import spotify_service

_switch_lock = Lock()               # stiti prijelaz Spotify -> MPV i obrnuto

def play_local(path):
    with _switch_lock:
        state = get_state()

        if state.get("playback_owner") == "spotify":
            spotify_service.set_playing(False)

        process = playback_service.play_file(path)
        state["playback_owner"] = "local"

        return process

def play_spotify(uri, context_uri=None):
    with _switch_lock:
        state = get_state()

        if state.get("playback_owner") == "local":
            playback_service.stop_playback()
            state["playback_owner"] = None

        spotify_service.play_track(uri, context_uri)
        state["playback_owner"] = "spotify"