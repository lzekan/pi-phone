import time

from requests.exceptions import ConnectionError as RequestConnectionError
from requests.exceptions import Timeout as RequestTimeout

from app.features.spotify.services import spotify_service
from app.core.state import get_state

HOME_LOAD_ATTEMPTS = 3
HOME_LOAD_RETRY_DELAY = 1


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
