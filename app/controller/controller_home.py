from app.services import spotify_service
from app.core.state import get_state

def load_home():
    state = get_state()
    state["home_loading"] = True
    state["home_error"] = None

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

        state["playlists"] = playlists
    except Exception as error:
        state["home_error"] = str(error)
    finally:
        state["home_loading"] = False


def get_recent_tracks():
    return get_state()["recent_tracks"]


def get_users_playlists():
    playlists = get_state()["playlists"]

    for playlist in playlists:
        playlist

def get_playlist_tracks(playlist_uri):

    try:
        tracks = []
        for item in spotify_service.get_playlist_tracks(playlist_uri) or []:

            track = item.get("item") or item.get("track") or {}
            images = track.get("album", {}).get("images") or []
            tracks.append({
                "name": track.get("name", ""),
                "artist": ", ".join([artist.get("name", "") for artist in track.get("artists", [])]),
                "uri": track.get("uri"),
                "image_url": images[0]["url"] if images else None
            })

        return tracks
    except Exception as error:
        response = getattr(error, "response", None)
        if response is not None and response.status_code == 403:
            print(
                "[PLAYLIST ERROR] Spotify only allows track access for "
                "playlists you own or collaborate on."
            )
        else:
            print(f"[SPOTIFY ERROR] {error}")
        return None


def get_user_profile():
    data = spotify_service.get_me()

    if not data:
        return None

    return {
        "name": data.get("display_name", "User"),
        "image_url": data["images"][0]["url"] if data.get("images") else None
    }
