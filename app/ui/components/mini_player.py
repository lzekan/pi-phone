from tkinter import BOTH, BOTTOM, LEFT, NORMAL, RIGHT, X
from tkinter import Button, Frame, Label

from app.controller.controller_navigation import go_player
from app.controller.controller_player import on_toggle_play
from app.core.state import get_state
from app.services.image_cache import get_photo_async
from app.ui.theme import (
    ACCENT,
    ACCENT_ACTIVE,
    DIVIDER,
    FONT,
    SURFACE,
    SURFACE_ALT,
    TEXT,
    TEXT_DIM,
    TEXT_MUTED,
)


def _get_track_id(song):
    track_id = song.get("track_id")
    if track_id:
        return track_id
    if song.get("track") or song.get("artist"):
        return song.get("track"), song.get("artist"), song.get("duration_ms")
    return None


def create_mini_player(root, parent, button_style, before=None):
    frame = Frame(
        parent,
        bg=SURFACE_ALT,
        height=76,
        cursor="hand2",
        highlightbackground=DIVIDER,
        highlightthickness=1,
    )
    frame.pack_propagate(False)

    cover_frame = Frame(frame, width=58, height=58, bg=SURFACE)
    cover_frame.pack(side=LEFT, padx=8, pady=8)
    cover_frame.pack_propagate(False)
    cover = Label(cover_frame, bg=SURFACE, borderwidth=0)
    cover.pack(fill=BOTH, expand=True)

    text = Frame(frame, bg=SURFACE_ALT)
    text.pack(side=LEFT, fill=BOTH, expand=True, pady=10)
    track = Label(
        text,
        fg=TEXT,
        bg=SURFACE_ALT,
        anchor="w",
        font=(FONT, 12, "bold"),
    )
    artist = Label(
        text,
        fg=TEXT_MUTED,
        bg=SURFACE_ALT,
        anchor="w",
        font=(FONT, 10),
    )
    track.pack(fill=X)
    artist.pack(fill=X)

    play = Button(
        frame,
        text="Ⅱ",
        command=on_toggle_play,
        width=3,
        bg=ACCENT,
        activebackground=ACCENT_ACTIVE,
        **{
            key: value
            for key, value in button_style.items()
            if key not in ("bg", "activebackground")
        },
    )
    play.pack(side=RIGHT, padx=8, pady=10)

    for widget in (frame, cover_frame, cover, text, track, artist):
        widget.bind("<Button-1>", lambda _event: go_player())

    cover_key = None

    def set_cover(new_cover_key, song):
        source = song.get("source", "spotify")
        cover.config(image="", text="")
        cover.image = None

        if source == "local":
            cover.config(
                text="♫",
                fg=TEXT_DIM,
                bg=SURFACE,
                font=(FONT, 28, "bold"),
            )
            return

        def show_cover(photo):
            current_song = get_state()["song"]
            current_key = (
                current_song.get("source", "spotify"),
                _get_track_id(current_song),
                current_song.get("image_url"),
            )
            if current_key != new_cover_key or not cover.winfo_exists():
                return
            cover.config(image=photo if photo is not None else "", text="")
            cover.image = photo

        get_photo_async(root, song.get("image_url"), (58, 58), show_cover)

    def restore_cover(_event=None):
        photo = getattr(cover, "image", None)
        if photo is not None:
            cover.config(image=photo)

    root.bind("<Map>", restore_cover, add="+")
    root.bind("<Configure>", restore_cover, add="+")

    def update(current_state):
        nonlocal cover_key

        song = current_state["song"]
        if song.get("track_id"):
            if not frame.winfo_manager():
                pack_options = {"fill": X, "side": BOTTOM}
                if before is not None:
                    pack_options["before"] = before
                frame.pack(**pack_options)
        elif frame.winfo_manager():
            frame.pack_forget()

        new_cover_key = (
            song.get("source", "spotify"),
            _get_track_id(song),
            song.get("image_url"),
        )
        if new_cover_key != cover_key:
            cover_key = new_cover_key
            set_cover(new_cover_key, song)

        track.config(text=song.get("track", "") or "Nothing playing")
        artist.config(text=song.get("artist", ""))
        play.config(
            text="Ⅱ" if song.get("is_playing", False) else "▶",
            state=NORMAL,
        )

    return {
        "frame": frame,
        "update": update,
    }
