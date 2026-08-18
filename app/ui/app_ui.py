from app.controller.controller_navigation import go_launcher
from app.core.state import get_state
from app.ui.screens.launcher_screen import render_launcher
from app.ui.screens.player_screen import render_player
from app.ui.screens.settings_screen import render_settings
from app.features.spotify.screens.home_screen import render_home
from app.features.spotify.screens.collection_screen import render_playlist
from app.features.local_audio.screens.library_screen import render_local_library
from app.controller.controller_queue import update_queue
from app.ui.theme import SURFACE_ALT, SURFACE_ACTIVE, TEXT, FONT


BUTTON_STYLE = {
    "font": (FONT, 12, "bold"),
    "fg": TEXT,
    "bg": SURFACE_ALT,
    "activeforeground": TEXT,
    "activebackground": SURFACE_ACTIVE,
    "disabledforeground": TEXT,
    "relief": "flat",
    "borderwidth": 0,
    "highlightthickness": 0,
    "padx": 12,
    "pady": 7,
    "state": "normal",
}


def start_ui(root):
    go_launcher()
    root.title("Pi Phone")
    root.attributes("-fullscreen", True)

    screens = {
        "home": render_home(root, get_state(), BUTTON_STYLE),
        "launcher": render_launcher(root, get_state()),
        "player": render_player(root, get_state(), BUTTON_STYLE),
        "playlist": render_playlist(root, get_state(), BUTTON_STYLE),
        "local_library": render_local_library(root, get_state(), BUTTON_STYLE),
        "settings": render_settings(root, get_state()),
    }

    for screen in screens.values():
        screen["frame"].place(x=0, y=0, relwidth=1, relheight=1)

    visible_screen = None

    def render():
        nonlocal visible_screen

        state = get_state()
        song = state["song"]
        screen = state.get("screen", "home")

        if screen == "playlist" and not state.get("current_collection_uri"):
            state["screen"] = "home"
            screen = "home"

        if not song.get("track_id") and screen == "player":
            state["screen"] = "home"
            screen = "home"

        if screen not in screens:
            state["screen"] = "home"
            screen = "home"

        current = screens[screen]

        if screen != visible_screen:
            visible_screen = screen
            current["frame"].tkraise()
            on_show = current.get("on_show")
            if on_show:
                on_show()

        current["update"](state)
        root.after(100, render)

    def queue_tick():
        try:
            update_queue()
        except Exception as error:
            print(f"[QUEUE TICK ERROR] {error}")

        root.after(500, queue_tick)

    queue_tick()
    render()
