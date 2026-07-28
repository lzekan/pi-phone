from app.core.state import get_state

def go_home():
    get_state()["screen"] = "home"

def go_player():
    state = get_state()
    if state["song"].get("track_id"):
        if state.get("screen") != "player":
            state["previous_screen"] = state.get("screen", "home")
        state["screen"] = "player"

def go_back():
    state = get_state()
    previous_screen = state.get("previous_screen", "home")
    state["screen"] = (
        previous_screen
        if previous_screen != "player"
        else "home"
    )

def go_playlist():
    get_state()["screen"] = "playlist"

def go_launcher():
    get_state()["screen"] = "launcher"
