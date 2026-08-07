import time
from datetime import datetime
from threading import Lock

from requests.exceptions import ConnectionError as RequestConnectionError
from requests.exceptions import Timeout as RequestTimeout

from app.features.spotify.services import spotify_service
from app.core.state import get_state

HOME_LOAD_ATTEMPTS = 3
HOME_LOAD_RETRY_DELAY = 1
RECENT_TRACKS_LIMIT = 5

_recent_tracks_lock = Lock()


def load_recently_played():
    if not _recent_tracks_lock.acquire(blocking=False):
        return

    try:
        api_tracks = []

        for item in spotify_service.get_recently_played():
            track = item.get("track") or {}
            track_id = track.get("id")
            if not track_id:
                continue

            album = track.get("album") or {}
            images = album.get("images") or []
            played_at = item.get("played_at")
            played_at_ms = 0
            if played_at:
                played_at_ms = int(
                    datetime.fromisoformat(played_at.replace("Z", "+00:00")).timestamp()
                    * 1000
                )

            api_tracks.append({
                "track_id": track_id,
                "name": track.get("name", ""),
                "artist": ", ".join(
                    artist.get("name", "")
                    for artist in track.get("artists", [])
                ),
                "uri": track.get("uri"),
                "image_url": images[0]["url"] if images else None,
                "album_name": album.get("name", ""),
                "album_id": album.get("id", ""),
                "duration_ms": track.get("duration_ms") or 1,
                "played_at_ms": played_at_ms,
            })

        combined_tracks = api_tracks + get_state().get("device_recent_tracks", [])
        combined_tracks.sort(
            key=lambda track: track.get("played_at_ms", 0),
            reverse=True,
        )

        recent_tracks = []
        seen_track_ids = set()
        for track in combined_tracks:
            track_id = track.get("track_id")
            if not track_id or track_id in seen_track_ids:
                continue
            seen_track_ids.add(track_id)
            recent_tracks.append(track)
            if len(recent_tracks) == RECENT_TRACKS_LIMIT:
                break

        get_state()["recent_tracks"] = recent_tracks
    except Exception as error:
        print(f"[RECENT TRACKS WARN] Spotify history refresh failed: {error}")
    finally:
        _recent_tracks_lock.release()


def load_home():
    state = get_state()
    state["home_loading"] = True
    state["home_error"] = None

    try:
        for attempt in range(HOME_LOAD_ATTEMPTS):
            try:
                playlists = []
                id_me = spotify_service.get_me()["id"]
                for item in spotify_service.get_user_playlists() or []:
                    images = item.get("images") or []
                    if(item.get("owner", {}).get("id") != id_me):
                        continue

                    playlists.append({
                        "name": item.get("name", ""),
                        "owner": item.get("owner", {}).get("display_name", ""),
                        "uri": item.get("uri"),
                        "image_url": images[0]["url"] if images else None
                    })

                albums = []
                for item in spotify_service.get_user_albums() or []:
                    album = item.get("album") or item.get("item") or {}
                    images = album.get("images") or []
                    albums.append({
                        "name": album.get("name", ""),
                        "artist": ", ".join(
                            artist.get("name", "")
                            for artist in album.get("artists", [])
                        ),
                        "uri": album.get("uri"),
                        "image_url": images[0]["url"] if images else None
                    })

                state["playlists"] = playlists
                state["albums"] = albums
                break
            except (RequestConnectionError, RequestTimeout) as error:
                if attempt == HOME_LOAD_ATTEMPTS - 1:
                    raise

                print(
                    f"[HOME WARN] Spotify connection failed: {error}. "
                    f"Retrying in {HOME_LOAD_RETRY_DELAY}s"
                )
                time.sleep(HOME_LOAD_RETRY_DELAY)
    except Exception as error:
        state["home_error"] = str(error)
    finally:
        state["home_loading"] = False


def get_user_profile():
    data = spotify_service.get_me()

    if not data:
        return None

    return {
        "name": data.get("display_name", "User"),
        "image_url": data["images"][0]["url"] if data.get("images") else None
    }
