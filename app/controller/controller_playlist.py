from app.services import spotify_service
from app.core.state import get_state

def load_playlist():
    state = get_state()

    try:
        playlist_tracks = []

        for track in spotify_service.get_playlist_tracks(state["current_playlist_uri"]) or []:
            track = track.get("item") or track.get("track") or {}
            images = track.get("album", {}).get("images") or []
            playlist_tracks.append({
                "name": track.get("name", ""),
                "artist": ", ".join([artist.get("name", "") for artist in track.get("artists", [])]),
                "uri": track.get("uri"),
                "image_url": images[0]["url"] if images else None
            })
        state["current_playlist_tracks"] = playlist_tracks
    except Exception as e:
        state["playlist_error"] = str(e)