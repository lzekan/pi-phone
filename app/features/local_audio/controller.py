import time
from queue import Queue
from threading import Lock, Thread

from app.controller.controller_navigation import go_local_library, go_player
from app.core.state import get_song_state, get_state
from app.features.local_audio.library_service import scan_library
from app.features.local_audio import playback_service
from app.services import playback_coordinator


_play_generation = 0
_generation_lock = Lock()
_launch_queue = Queue()
_pending_seek_position = None
_pending_seek_time = 0
_seek_lock = Lock()
_queue_lock = Lock()


def _launch_worker():
    while True:
        command = _launch_queue.get()
        try:
            command()
        finally:
            _launch_queue.task_done()


Thread(target=_launch_worker, daemon=True).start()


def _next_generation():
    global _play_generation
    with _generation_lock:
        _play_generation += 1
        return _play_generation


def _is_current(generation, track_path):
    song = get_song_state()
    return (
        generation == _play_generation
        and song.get("source") == "local"
        and song.get("track_id") == track_path
    )


def _accept_progress(status):
    global _pending_seek_position

    with _seek_lock:
        if _pending_seek_position is None:
            return True

        elapsed = time.monotonic() - _pending_seek_time
        expected = _pending_seek_position
        if status["is_playing"]:
            expected += elapsed * 1000

        confirmed = abs(status["progress_ms"] - expected) <= 1500
        if confirmed or elapsed >= 2:
            _pending_seek_position = None
            return True
        return False


def refresh_library():
    local_state = get_state()["local"]
    if local_state["loading"]:
        return

    local_state["loading"] = True
    local_state["error"] = None

    def worker():
        try:
            local_state["tracks"] = scan_library()
            local_state["loaded"] = True
        except Exception as error:
            local_state["error"] = str(error)
        finally:
            local_state["loading"] = False

    Thread(target=worker, daemon=True).start()


def open_library():
    go_local_library()
    local_state = get_state()["local"]
    if not local_state["loaded"]:
        refresh_library()


def add_to_queue(track):
    queue_item = {
        "queue_id": time.monotonic_ns(),
        "track_id": track["path"],
        "path": track["path"],
        "track": track.get("title", ""),
        "artist": track.get("artist", ""),
        "album_name": track.get("album", ""),
        "duration_ms": track.get("duration_ms", 1),
        "image_url": None,
        "committed": False,
    }
    with _queue_lock:
        get_state()["local"]["queue"].append(queue_item)
    return queue_item


def remove_from_queue(queue_id):
    with _queue_lock:
        queue = get_state()["local"]["queue"]
        for index, item in enumerate(queue):
            if item.get("queue_id") == queue_id:
                queue.pop(index)
                return True
    return False


def _pop_queued_track_index(tracks):
    with _queue_lock:
        queue = get_state()["local"]["queue"]
        while queue:
            queued_path = queue.pop(0).get("path")
            for index, track in enumerate(tracks):
                if track.get("path") == queued_path:
                    return index
    return None


def _next_track_target(current_index, tracks):
    queued_index = _pop_queued_track_index(tracks)
    if queued_index is not None:
        return queued_index, True

    sequence_index = get_state()["local"].get("sequence_index")
    if sequence_index is None:
        sequence_index = current_index
    next_index = sequence_index + 1
    if next_index < len(tracks):
        return next_index, False
    return None, False


def _start_track(index, from_queue=False):
    global _pending_seek_position

    state = get_state()
    tracks = state["local"]["tracks"]
    if index < 0 or index >= len(tracks):
        return

    track = tracks[index]
    track_path = track["path"]
    generation = _next_generation()
    with _seek_lock:
        _pending_seek_position = None

    state["local"]["current_index"] = index
    if not from_queue:
        state["local"]["sequence_index"] = index
    state["local"]["error"] = None
    state["next_song"] = None
    get_song_state().update({
        "source": "local",
        "track_id": track_path,
        "track": track["title"],
        "artist": track["artist"],
        "album_name": track.get("album", ""),
        "album_id": "",
        "progress_ms": 0,
        "duration_ms": max(1, track.get("duration_ms", 1) or 1),
        "is_playing": True,
        "image_url": None,
    })
    go_player()

    def monitor(process):
        try:
            while _is_current(generation, track_path) and process.poll() is None:
                try:
                    status = playback_service.get_status()
                    song = get_song_state()
                    if _accept_progress(status):
                        song["progress_ms"] = status["progress_ms"]
                    if status["duration_ms"] > 0:
                        song["duration_ms"] = status["duration_ms"]
                    song["is_playing"] = status["is_playing"]
                except (ConnectionError, OSError, RuntimeError, ValueError):
                    pass
                time.sleep(0.3)

            if not _is_current(generation, track_path):
                return

            next_index, next_from_queue = _next_track_target(index, tracks)
            if next_index is not None:
                _start_track(next_index, from_queue=next_from_queue)
            else:
                song = get_song_state()
                song["progress_ms"] = song["duration_ms"]
                song["is_playing"] = False
        except Exception as error:
            if _is_current(generation, track_path):
                get_song_state()["is_playing"] = False
                state["local"]["error"] = str(error)
                print(f"[LOCAL AUDIO ERROR] {error}")

    def launch():
        if not _is_current(generation, track_path):
            return
        try:
            process = playback_coordinator.play_local(track_path)
            if not playback_service.wait_until_ready(process):
                raise RuntimeError("mpv se nije pokrenuo")
            Thread(target=monitor, args=(process,), daemon=True).start()
        except Exception as error:
            if _is_current(generation, track_path):
                get_song_state()["is_playing"] = False
                state["local"]["error"] = str(error)
                print(f"[LOCAL AUDIO ERROR] {error}")

    _launch_queue.put(launch)


def play_selected_file(track_path):
    tracks = get_state()["local"]["tracks"]
    for index, track in enumerate(tracks):
        if track["path"] == track_path:
            _start_track(index)
            return


def on_toggle_play():
    song = get_song_state()
    desired_playing = not song.get("is_playing", False)
    song["is_playing"] = desired_playing

    def worker():
        try:
            playback_service.set_paused(not desired_playing)
        except Exception as error:
            song["is_playing"] = not desired_playing
            print(f"[LOCAL AUDIO ERROR] {error}")

    Thread(target=worker, daemon=True).start()


def on_seek(position_ms):
    global _pending_seek_position, _pending_seek_time

    get_song_state()["progress_ms"] = position_ms
    with _seek_lock:
        _pending_seek_position = position_ms
        _pending_seek_time = time.monotonic()

    def worker():
        try:
            playback_service.seek_to(position_ms)
        except Exception as error:
            print(f"[LOCAL AUDIO ERROR] {error}")

    Thread(target=worker, daemon=True).start()


def on_next():
    state = get_state()
    index = state["local"].get("current_index")
    if index is not None:
        next_index, next_from_queue = _next_track_target(
            index,
            state["local"]["tracks"],
        )
        if next_index is not None:
            _start_track(next_index, from_queue=next_from_queue)


def on_prev():
    state = get_state()
    index = state["local"].get("current_index")
    if index is None:
        return
    if get_song_state().get("progress_ms", 0) > 3000:
        on_seek(0)
    else:
        _start_track(index - 1)
