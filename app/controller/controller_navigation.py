from app.core.state import get_state

def go_home():
    get_state()["screen"] = "home"

def go_player():
    state = get_state()
    if state["song"].get("track_id"):
        state["screen"] = "player"

def go_playlist():
    get_state()["screen"] = "playlist"

def go_launcher():
    get_state()["screen"] = "launcher"
