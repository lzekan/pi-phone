import time
from queue import Queue
from threading import Thread
from app.core.state import get_song_state, get_state
from app.features.spotify.services import daemon_client, spotify_service

_command_queue = Queue()
_command_generation = 0


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
    next_song = get_state().get("next_song")
    generation = _next_command_generation()
    daemon_client.expect_track_change()

    if next_song:
        song_state.update(next_song)
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

    _run_async(spotify_service.next_track, rollback)


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


def play_selected_track(uri, context_uri=None):
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

    _run_async(lambda: spotify_service.play_track(uri, context_uri), rollback)
