import time
from queue import Queue
from threading import Lock, Thread

from app.core.state import get_song_state, get_state
from app.services import playback_coordinator
from app.features.spotify.services import daemon_client, spotify_service
from app.controller.controller_navigation import go_player
from app.features.spotify.controllers import queue as queue_controller

_command_queue = Queue()
_command_generation = 0
_library_lock = Lock()


def _command_worker():
    while True:
        command, on_error = _command_queue.get()
        try:
            command()
        except Exception as error:
            print(f"[SPOTIFY ERROR] {error}")
            if on_error:
                on_error()
        finally:
            _command_queue.task_done()


Thread(target=_command_worker, daemon=True).start()


def _next_command_generation():
    global _command_generation
    _command_generation += 1
    return _command_generation


def _run_async(command, on_error=None):
    _command_queue.put((command, on_error))


def load_current_track_library_status(track_id):
    state = get_state()
    song = state["song"]
    if song.get("source") != "spotify" or song.get("track_id") != track_id:
        return

    track_uri = f"spotify:track:{track_id}"
    state["track_library_loading"] = True
    state["track_library_error"] = None

    with _library_lock:
        try:
            saved = spotify_service.is_library_item_saved(track_uri)
            if get_song_state().get("track_id") == track_id:
                state["current_track_saved"] = saved
        except Exception as error:
            if get_song_state().get("track_id") == track_id:
                state["track_library_error"] = str(error)
        finally:
            if get_song_state().get("track_id") == track_id:
                state["track_library_loading"] = False


def toggle_current_track_saved():
    state = get_state()
    song = state["song"]
    track_id = song.get("track_id")
    if song.get("source") != "spotify" or not track_id:
        return

    track_uri = f"spotify:track:{track_id}"
    state["track_library_loading"] = True
    state["track_library_error"] = None

    with _library_lock:
        try:
            if get_song_state().get("track_id") != track_id:
                return

            was_saved = bool(state.get("current_track_saved"))
            if was_saved:
                spotify_service.remove_library_item(track_uri)
            else:
                spotify_service.save_library_item(track_uri)

            if get_song_state().get("track_id") != track_id:
                return

            state["current_track_saved"] = not was_saved
            state["liked_tracks_dirty"] = True

            return not was_saved

        except Exception as error:
            if get_song_state().get("track_id") == track_id:
                state["track_library_error"] = str(error)
        finally:
            if get_song_state().get("track_id") == track_id:
                state["track_library_loading"] = False

def on_toggle_play():
    song_state = get_song_state()
    desired_state = not song_state["is_playing"]
    generation = _next_command_generation()

    daemon_client.pending_play_state = desired_state
    daemon_client.play_start_time = time.time()

    song_state["is_playing"] = desired_state

    def rollback():
        if generation == _command_generation:
            daemon_client.pending_play_state = None

    _run_async(lambda: spotify_service.set_playing(desired_state), rollback)


def on_next():
    song_state = get_song_state()
    manual_queue = get_state().get("spotify_manual_queue", [])
    manual_next = manual_queue[0] if manual_queue else None
    next_song = manual_next or get_state().get("next_song")

    if manual_next:
        queue_controller.commit_next_manual_queue_item()

    generation = _next_command_generation()
    daemon_client.expect_track_change()

    if next_song:
        song_state.update({
            "track_id": (
                next_song.get("track_id")
                or next_song.get("uri", "").split(":")[-1]
            ),
            "track": next_song.get("track", ""),
            "artist": next_song.get("artist", ""),
            "album_id": next_song.get("album_id", ""),
            "album_name": next_song.get("album_name", ""),
            "duration_ms": next_song.get("duration_ms", 1),
            "image_url": next_song.get("image_url"),
        })
        get_state()["next_song"] = None

    song_state["progress_ms"] = 0
    daemon_client.pending_play_state = True
    daemon_client.play_start_time = time.time()
    song_state["is_playing"] = True

    def rollback():
        if generation == _command_generation:
            daemon_client.pending_track_change = False
            daemon_client.pending_seek_position = None
            daemon_client.pending_play_state = None

    def advance():
        if manual_next:
            queue_controller.ensure_next_manual_item_committed()

        spotify_service.next_track()

    _run_async(advance, rollback)


def on_prev():
    song_state = get_song_state()
    generation = _next_command_generation()
    song_state["progress_ms"] = 0

    daemon_client.expect_track_change()
    daemon_client.pending_play_state = True
    daemon_client.play_start_time = time.time()
    song_state["is_playing"] = True

    def rollback():
        if generation == _command_generation:
            daemon_client.pending_track_change = False
            daemon_client.pending_seek_position = None
            daemon_client.pending_play_state = None

    _run_async(spotify_service.prev_track, rollback)


def on_seek(position_ms):
    song_state = get_song_state()
    generation = _next_command_generation()
    daemon_client.pending_seek_position = position_ms
    daemon_client.seek_start_time = time.time()

    song_state["progress_ms"] = position_ms
    def rollback():
        if generation == _command_generation:
            daemon_client.pending_seek_position = None

    _run_async(lambda: spotify_service.seek(position_ms), rollback)


def play_selected_track(uri, context_uri=None, track_data=None):
    song_state = get_song_state()
    song_state["source"] = "spotify"
    generation = _next_command_generation()
    song_state["progress_ms"] = 0

    daemon_client.expect_track_change(uri.split(":")[-1])

    if track_data:
        song_state.update({
            "track_id": track_data.get("track_id") or uri.split(":")[-1],
            "track": track_data.get("name", ""),
            "artist": track_data.get("artist", ""),
            "album_name": track_data.get("album_name", ""),
            "album_id": track_data.get("album_id", ""),
            "duration_ms": track_data.get("duration_ms") or 1,
            "image_url": track_data.get("image_url"),
        })
    else:
        song_state.update({
            "track_id": uri.split(":")[-1],
            "track": "",
            "artist": "",
            "album_name": "",
            "album_id": "",
            "duration_ms": 1,
            "image_url": None,
        })

    daemon_client.pending_play_state = True
    daemon_client.play_start_time = time.time()

    song_state["is_playing"] = True
    go_player()
    
    def rollback():
        if generation == _command_generation:
            daemon_client.pending_track_change = False
            daemon_client.pending_seek_position = None
            daemon_client.pending_play_state = None
            daemon_client.expected_track_after_change = None

    _run_async(lambda: playback_coordinator.play_spotify(uri, context_uri), rollback)
