from threading import Lock

from app.features.spotify.services import spotify_service
from app.core.state import get_state

PAGE_SIZE = 10
_requests_lock = Lock()
_active_requests = set()


def _load_collection_page(collection_type, reset):
    state = get_state()
    collection_uri = state.get("current_collection_uri")

    if not collection_uri or state.get("current_collection_type") != collection_type:
        return

    offset = 0 if reset else state.get("current_collection_next_offset")
    if not reset and offset is None:
        return

    request_key = (collection_uri, offset)
    with _requests_lock:
        if request_key in _active_requests:
            return
        _active_requests.add(request_key)

    state["collection_loading"] = True
    state["collection_error"] = None

    try:
        if collection_type == "album":
            album_id = collection_uri.split(":")[-1]
            page = spotify_service.get_album_tracks(album_id, PAGE_SIZE, offset)
        else:
            album_id = None
            page = spotify_service.get_playlist_tracks(collection_uri, PAGE_SIZE, offset)

        loaded_tracks = []
        for track in page["items"]:
            track = track.get("item") or track.get("track") or track
            images = track.get("album", {}).get("images") or []
            loaded_tracks.append({
                "name": track.get("name", ""),
                "artist": ", ".join([artist.get("name", "") for artist in track.get("artists", [])]),
                "album_id": album_id or track.get("album", {}).get("id"),
                "album_name": (
                    state.get("current_collection_name", "")
                    if collection_type == "album"
                    else track.get("album", {}).get("name", "")
                ),
                "image_url": (
                    state.get("current_collection_image_url")
                    if collection_type == "album"
                    else images[0]["url"] if images else None
                ),
                "uri": track.get("uri"),
                "track_id": track.get("id")
            })

        if state.get("current_collection_uri") != collection_uri:
            return

        existing_tracks = [] if reset else state.get("current_collection_tracks") or []
        state["current_collection_tracks"] = existing_tracks + loaded_tracks
        state["current_collection_next_offset"] = page["next_offset"]
        state["current_collection_total"] = page["total"]

    except Exception as e:
        if state.get("current_collection_uri") == collection_uri:
            state["collection_error"] = str(e)
    finally:
        if state.get("current_collection_uri") == collection_uri:
            state["collection_loading"] = False
        with _requests_lock:
            _active_requests.discard(request_key)


def load_playlist():
    _load_collection_page("playlist", reset=True)


def load_album():
    _load_collection_page("album", reset=True)


def load_more_collection():
    collection_type = get_state().get("current_collection_type")
    if collection_type in ("playlist", "album"):
        _load_collection_page(collection_type, reset=False)
