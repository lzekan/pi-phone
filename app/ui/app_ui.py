from tkinter import BOTH

from app.controller.controller_navigation import go_launcher
from app.core.state import get_state
from app.ui.screens.home_screen import render_home
from app.ui.screens.launcher_screen import render_launcher
from app.ui.screens.player_screen import render_player
from app.ui.screens.playlist_screen import render_playlist
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

    home_screen = render_home(root, get_state(), BUTTON_STYLE)
    launcher_screen = render_launcher(root, get_state())
    player_screen = render_player(root, get_state(), BUTTON_STYLE)
    playlist_screen = render_playlist(root, get_state(), BUTTON_STYLE)
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

        if screen != visible_screen:
            visible_screen = screen
            home_screen["frame"].pack_forget()
            launcher_screen["frame"].pack_forget()
            player_screen["frame"].pack_forget()
            playlist_screen["frame"].pack_forget()

            if screen == "launcher":
                current = launcher_screen
            elif screen == "player":
                current = player_screen
            elif screen == "playlist":
                current = playlist_screen
            else:
                current = home_screen

            current["frame"].pack(fill=BOTH, expand=True)

        home_screen["update"](state)
        launcher_screen["update"](state)
        player_screen["update"](state)
        playlist_screen["update"](state)
        root.after(100, render)

    root.after(100, render)
