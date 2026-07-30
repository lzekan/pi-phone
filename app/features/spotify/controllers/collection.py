from app.features.spotify.services import spotify_service
from app.core.state import get_state

def load_playlist():
    state = get_state()

    try:
        playlist_tracks = []

        for track in spotify_service.get_playlist_tracks(state["current_collection_uri"]) or []:
            track = track.get("item") or track.get("track") or {}
            images = track.get("album", {}).get("images") or []
            playlist_tracks.append({
                "name": track.get("name", ""),
                "artist": ", ".join([artist.get("name", "") for artist in track.get("artists", [])]),
                "album_id": track.get("album", {}).get("id"),
                "uri": track.get("uri"),
                "image_url": images[0]["url"] if images else None
            })
        state["current_collection_tracks"] = playlist_tracks

    except Exception as e:
        state["collection_error"] = str(e)


def load_album():
    state = get_state()

    try:
        album_tracks = []
        album_id = state["current_collection_uri"].split(":")[-1]

        for track in spotify_service.get_album_tracks(album_id) or []:
            track = track.get("item") or track.get("track") or track
            images = track.get("album", {}).get("images") or []
            album_tracks.append({
                "name": track.get("name", ""),
                "artist": ", ".join([artist.get("name", "") for artist in track.get("artists", [])]),
                "album_id": album_id,
                "image_url": state.get("current_collection_image_url"),
                "uri": track.get("uri")
            })
        state["current_collection_tracks"] = album_tracks

    except Exception as e:
        state["collection_error"] = str(e)
