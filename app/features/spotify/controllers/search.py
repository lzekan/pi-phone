from app.features.spotify.services import spotify_service
from app.core.state import get_state


def load_search_results(query, search_type="track"):
    state = get_state()

    state["search_query"] = query
    state["search_type"] = search_type
    state["search_error"] = None

    if len(query) < 3:
        state["search_results"] = []
        state["search_loading"] = False
        return

    state["search_loading"] = True
    state["search_results"] = []

    try:
        results = []

        for item in spotify_service.search_items(query, search_type):
            if not item:
                continue

            if search_type == "track":
                album = item.get("album") or {}
                images = album.get("images") or []
                result = {
                    "result_type": "track",
                    "track_id": item.get("id"),
                    "name": item.get("name", ""),
                    "artist": ", ".join(
                        artist.get("name", "")
                        for artist in item.get("artists", [])
                    ),
                    "uri": item.get("uri"),
                    "album_id": album.get("id"),
                    "album_name": album.get("name", ""),
                    "image_url": images[0].get("url") if images else None,
                    "duration_ms": item.get("duration_ms", 0),
                }
            else:
                images = item.get("images") or []
                result = {
                    "result_type": "album",
                    "name": item.get("name", ""),
                    "artist": ", ".join(
                        artist.get("name", "")
                        for artist in item.get("artists", [])
                    ),
                    "uri": item.get("uri"),
                    "image_url": images[0].get("url") if images else None,
                }

            results.append(result)

        if (
            state["search_query"] == query
            and state["search_type"] == search_type
        ):
            # Older requests must not overwrite results from a newer query.
            state["search_results"] = results

    except Exception as error:
        if (
            state["search_query"] == query
            and state["search_type"] == search_type
        ):
            state["search_results"] = []
            state["search_error"] = str(error)


    finally:
        if (
            state["search_query"] == query
            and state["search_type"] == search_type
        ):
            state["search_loading"] = False
