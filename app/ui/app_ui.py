from tkinter import BOTH

from app.controller.controller_navigation import go_home
from app.core.state import get_state
from app.ui.screens.home_screen import render_home
from app.ui.screens.player_screen import render_player


BUTTON_STYLE = {
    "font": ("DejaVu Sans", 16, "bold"),
    "fg": "white",
    "bg": "#222222",
    "activeforeground": "white",
    "activebackground": "#444444",
    "disabledforeground": "white",
    "relief": "raised",
    "borderwidth": 2,
    "highlightthickness": 0,
    "state": "normal",
}


def start_ui(root):
    go_home()
    root.title("Pi Phone")
    root.attributes("-fullscreen", True)
    root.bind("<Escape>", lambda _event: root.attributes("-fullscreen", False))

    home_screen = render_home(root, get_state(), BUTTON_STYLE)
    player_screen = render_player(root, get_state(), BUTTON_STYLE)
    visible_screen = None

    def render():
        nonlocal visible_screen

        state = get_state()
        song = state["song"]
        screen = state.get("screen", "home")

        if not song.get("track_id") and screen == "player":
            state["screen"] = "home"
            screen = "home"

        if screen != visible_screen:
            visible_screen = screen
            home_screen["frame"].pack_forget()
            player_screen["frame"].pack_forget()
            current = player_screen if screen == "player" else home_screen
            current["frame"].pack(fill=BOTH, expand=True)

        home_screen["update"](state)
        player_screen["update"](state)
        root.after(100, render)

    root.after(100, render)
