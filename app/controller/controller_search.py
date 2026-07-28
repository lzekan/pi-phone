from app.services import spotify_service
from app.core.state import get_state


def load_search_results(query):
    state = get_state()

    state["search_query"] = query
    state["search_error"] = None

    if len(query) < 3:
        state["search_results"] = []
        state["search_loading"] = False
        return

    state["search_loading"] = True
    state["search_results"] = []

    try:
        results = []

        for track in spotify_service.search_tracks(query):
            images = track.get("album", {}).get("images") or []

            results.append({
                "track_id": track.get("id"),
                "name": track.get("name", ""),
                "artist": ", ".join([artist.get("name", "") for artist in track.get("artists", [])]),
                "uri": track.get("uri"),
                "album_id": track.get("album", {}).get("id"),
                "image_url": images[0].get("url") if images else None,
                "duration_ms": track.get("duration_ms", 0)
            })

        if state["search_query"] == query:
            # Older requests must not overwrite results from a newer query.
            state["search_results"] = results

    except Exception as error:
        if state["search_query"] == query:
            state["search_results"] = []
            state["search_error"] = str(error)


    finally:
        if state["search_query"] == query:
            state["search_loading"] = False
