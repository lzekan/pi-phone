import time
from threading import Thread, Lock
from app.core.state import get_state
from app.features.spotify.services import spotify_service

COMMIT_BEFORE_END_MS = 20000

_commit_lock = Lock()

def add_to_manual_queue(track_data):
    uri = track_data.get("uri", "")
    track_id = track_data.get("track_id") or uri.split(":")[-1]

    queue_item = {
        "queue_id": time.monotonic_ns(),
        "track_id": track_id,
        "uri": uri,
        "track": track_data.get("track") or track_data.get("name", ""),
        "artist": track_data.get("artist", ""),
        "image_url": track_data.get("image_url"),
        "duration_ms": track_data.get("duration_ms", 1),
        "committed": False,
        "album_id": track_data.get("album_id", ""),
        "album_name": track_data.get("album_name", ""),
    }

    get_state()["spotify_manual_queue"].append(queue_item)


def remove_from_manual_queue(queue_id):
    queue = get_state()["spotify_manual_queue"]

    for index, item in enumerate(queue):
        if item.get("queue_id") != queue_id:
            continue

        if item.get("committed", False):
            return False

        queue.pop(index)
        return True

    return False

def maybe_commit_next_manual_item():
    state = get_state()
    song = state["song"]

    if song.get("source") != "spotify":
        return False

    if not song.get("is_playing", False):
        return False

    duration_ms = song.get("duration_ms", 1) or 1
    progress_ms = song.get("progress_ms", 0) or 0

    if duration_ms <= 1:
        return False

    remaining_ms = duration_ms - progress_ms

    if remaining_ms > COMMIT_BEFORE_END_MS:
        return False

    return commit_next_manual_queue_item()


def commit_next_manual_queue_item():
    queue = get_state()["spotify_manual_queue"]

    if not queue:
        return False

    if any(item.get("committed", False) for item in queue):
        return False

    item = queue[0]
    uri = item.get("uri")

    if not uri:
        return False

    item["committed"] = True
    item["committed_from_track_id"] = get_state()["song"].get("track_id")

    def worker():
        try:
            ensure_next_manual_item_committed()
        except Exception as error:
            print(f"[QUEUE ERROR] Commit failed: {error}")

    Thread(target=worker, daemon=True).start()
    return True

def remove_started_committed_item():
    queue = get_state()["spotify_manual_queue"]

    if not queue:
        return False

    item = queue[0]

    if not item.get("committed", False):
        return False

    if not item.get("spotify_confirmed", False):
        return False

    song = get_state()["song"]
    current_track_id = song.get("track_id")
    queued_track_id = item.get("track_id")
    committed_from_track_id = item.get("committed_from_track_id")

    if current_track_id != queued_track_id:
        return False

    # Ista pjesma može biti queueana iza same sebe.
    # Dok stara reprodukcija još traje pri kraju, ne uklanjamo je.
    if (
        current_track_id == committed_from_track_id
        and song.get("progress_ms", 0) > 10000
    ):
        return False

    queue.pop(0)
    return True


def ensure_next_manual_item_committed():
    with _commit_lock:
        queue = get_state()["spotify_manual_queue"]

        if not queue:
            return None

        item = queue[0]

        if item.get("spotify_confirmed", False):
            return item

        uri = item.get("uri")
        if not uri:
            return None

        if not item.get("committed", False):
            item["committed"] = True
            item["committed_from_track_id"] = (
                get_state()["song"].get("track_id")
            )

        try:
            spotify_service.add_to_queue(uri)
        except Exception:
            if item in get_state()["spotify_manual_queue"]:
                item["committed"] = False
                item["spotify_confirmed"] = False
                item.pop("committed_from_track_id", None)
            raise

        item["spotify_confirmed"] = True
        return item