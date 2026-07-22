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


def get_user_profile():
    data = spotify_service.get_me()

    if not data:
        return None

    return {
        "name": data.get("display_name", "User"),
        "image_url": data["images"][0]["url"] if data.get("images") else None
    }
