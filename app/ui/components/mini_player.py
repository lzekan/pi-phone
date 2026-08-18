from tkinter import BOTH, BOTTOM, LEFT, NORMAL, RIGHT, X
from tkinter import Button, Canvas, Frame, Label
from tkinter import font as tkfont

from app.controller.controller_navigation import go_player
from app.controller.controller_player import on_toggle_play
from app.core.state import get_state
from app.services.image_cache import get_photo_async
from app.ui.theme import (
    ACCENT,
    ACCENT_ACTIVE,
    FONT,
    SURFACE,
    SURFACE_ACTIVE,
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
    mini_bg = SURFACE_ACTIVE
    parent_bg = parent.cget("bg")
    frame = Frame(
        parent,
        bg=parent_bg,
        height=76,
        cursor="hand2",
        borderwidth=0,
        highlightthickness=0,
    )
    frame.pack_propagate(False)

    shell = Canvas(
        frame,
        bg=parent_bg,
        borderwidth=0,
        highlightthickness=0,
        cursor="hand2",
    )
    shell.pack(fill=BOTH, expand=True)

    rounded_background = shell.create_polygon(
        0,
        0,
        1,
        0,
        1,
        1,
        0,
        1,
        fill=mini_bg,
        outline=ACCENT,
        width=1,
        smooth=True,
    )
    body = Frame(shell, bg=mini_bg, borderwidth=0)
    body_window = shell.create_window(3, 3, window=body, anchor="nw")

    def resize_shell(event):
        radius = 11
        left = 1
        top = 1
        right = max(left, event.width - 1)
        bottom = max(top, event.height - 1)
        points = (
            left + radius, top,
            right - radius, top,
            right, top,
            right, top + radius,
            right, bottom - radius,
            right, bottom,
            right - radius, bottom,
            left + radius, bottom,
            left, bottom,
            left, bottom - radius,
            left, top + radius,
            left, top,
        )
        shell.coords(rounded_background, *points)
        shell.itemconfigure(
            body_window,
            width=max(1, event.width - 6),
            height=max(1, event.height - 6),
        )

    shell.bind("<Configure>", resize_shell)

    accent_bar = Frame(body, width=1, bg=ACCENT, cursor="hand2")
    accent_bar.pack(side=LEFT, fill=BOTH)
    accent_bar.pack_propagate(False)

    cover_frame = Frame(body, width=58, height=58, bg=SURFACE)
    cover_frame.pack(side=LEFT, padx=(8, 10), pady=6)
    cover_frame.pack_propagate(False)
    cover = Label(cover_frame, bg=SURFACE, borderwidth=0)
    cover.pack(fill=BOTH, expand=True)

    text = Frame(body, bg=mini_bg)
    track = Label(
        text,
        fg=TEXT,
        bg=mini_bg,
        anchor="w",
        font=(FONT, 12, "bold"),
    )
    artist = Label(
        text,
        fg=TEXT_MUTED,
        bg=mini_bg,
        anchor="w",
        font=(FONT, 10),
    )
    track.pack(fill=X)
    artist.pack(fill=X)

    track_font = tkfont.Font(font=track.cget("font"))
    artist_font = tkfont.Font(font=artist.cget("font"))

    def fit_text(value, label, label_font):
        value = value or ""
        available_width = label.winfo_width()

        if available_width <= 1 or label_font.measure(value) <= available_width:
            return value

        ellipsis = "\u2026"
        ellipsis_width = label_font.measure(ellipsis)
        low = 0
        high = len(value)

        while low < high:
            middle = (low + high + 1) // 2
            candidate_width = label_font.measure(value[:middle]) + ellipsis_width

            if candidate_width <= available_width:
                low = middle
            else:
                high = middle - 1

        return value[:low] + ellipsis

    play = Button(
        body,
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
    text.pack(side=LEFT, fill=BOTH, expand=True, pady=10)

    for widget in (
        frame,
        shell,
        body,
        accent_bar,
        cover_frame,
        cover,
        text,
        track,
        artist,
    ):
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

        track_text = song.get("track", "") or "Nothing playing"
        artist_text = song.get("artist", "")
        track.config(text=fit_text(track_text, track, track_font))
        artist.config(text=fit_text(artist_text, artist, artist_font))
        play.config(
            text="Ⅱ" if song.get("is_playing", False) else "▶",
            state=NORMAL,
        )

    return {
        "frame": frame,
        "update": update,
    }
