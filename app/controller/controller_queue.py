from app.core.state import get_song_state
from app.features.spotify.controllers import queue as spotify_queue_controller


def update_queue():
    source = get_song_state().get("source")

    if source == "spotify":
        spotify_queue_controller.remove_started_committed_item()
        return spotify_queue_controller.maybe_commit_next_manual_item()

    return False


def remove_queue_item(queue_id):
    source = get_song_state().get("source")

    if source == "spotify":
        return spotify_queue_controller.remove_from_manual_queue(queue_id)

    return False