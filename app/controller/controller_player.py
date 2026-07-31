from app.core.state import get_song_state
from app.features.local_audio import controller as local_controller
from app.features.spotify.controllers import player as spotify_controller


def _active_controller():
    if get_song_state().get("source") == "local":
        return local_controller
    return spotify_controller


def on_toggle_play():
    _active_controller().on_toggle_play()


def on_next():
    _active_controller().on_next()


def on_prev():
    _active_controller().on_prev()


def on_seek(position_ms):
    _active_controller().on_seek(position_ms)
