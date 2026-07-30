from datetime import datetime
from tkinter import BOTH, LEFT, RIGHT, X
from tkinter import Button, Canvas, Frame, Label

from app.controller.controller_navigation import go_home
from app.ui.theme import (
    ACCENT,
    BG,
    CARD,
    DIVIDER,
    FONT,
    PAGE_PAD,
    SURFACE_ALT,
    TEXT,
    TEXT_DIM,
    TEXT_MUTED,
    DANGER,
)


def render_launcher(root, _state):
    frame = Frame(root, bg=BG)

    header = Frame(frame, bg=BG)
    header.pack(fill=X, padx=PAGE_PAD, pady=(24, 8))
    header_top = Frame(header, bg=BG)
    header_top.pack(fill=X)
    Label(
        header_top,
        text="PIPHONE",
        fg=ACCENT,
        bg=BG,
        anchor="w",
        font=(FONT, 10, "bold"),
    ).pack(side=LEFT)
    Button(
        header_top,
        text="⏻",
        command=root.destroy,
        fg=TEXT_MUTED,
        bg=SURFACE_ALT,
        activeforeground=TEXT,
        activebackground=DANGER,
        font=(FONT, 16, "bold"),
        relief="flat",
        borderwidth=0,
        highlightthickness=0,
        takefocus=False,
        width=3,
        pady=2,
    ).pack(side=RIGHT)

    time_label = Label(
        header,
        text="--:--",
        fg=TEXT,
        bg=BG,
        anchor="w",
        font=(FONT, 48, "bold"),
    )
    time_label.pack(fill=X, pady=(2, 0))
    date_label = Label(
        header,
        text="",
        fg=TEXT_MUTED,
        bg=BG,
        anchor="w",
        font=(FONT, 12),
    )
    date_label.pack(fill=X)

    Label(
        frame,
        text="Apps",
        fg=TEXT,
        bg=BG,
        anchor="w",
        font=(FONT, 19, "bold"),
    ).pack(fill=X, padx=PAGE_PAD, pady=(22, 8))

    apps = Frame(frame, bg=BG)
    apps.pack(fill=BOTH, expand=True, padx=PAGE_PAD)

    spotify_tile = Frame(
        apps,
        bg=CARD,
        height=180,
        cursor="hand2",
        highlightbackground=DIVIDER,
        highlightthickness=1,
    )
    spotify_tile.pack(fill=X, pady=(0, 10))
    spotify_tile.pack_propagate(False)

    spotify_icon = Canvas(
        spotify_tile,
        width=112,
        height=112,
        bg=CARD,
        cursor="hand2",
        highlightthickness=0,
    )
    spotify_icon.pack(side=LEFT, padx=(20, 14), pady=24)
    spotify_icon.create_oval(8, 8, 104, 104, fill=ACCENT, outline="")
    for top, width in ((35, 5), (48, 4), (61, 4)):
        spotify_icon.create_arc(
            26,
            top,
            88,
            top + 36,
            start=20,
            extent=140,
            style="arc",
            outline=BG,
            width=width,
        )

    spotify_text = Frame(spotify_tile, bg=CARD, cursor="hand2")
    spotify_text.pack(side=LEFT, fill=BOTH, expand=True, pady=43)
    Label(
        spotify_text,
        text="Spotify",
        fg=TEXT,
        bg=CARD,
        cursor="hand2",
        anchor="w",
        font=(FONT, 24, "bold"),
    ).pack(fill=X)
    Label(
        spotify_text,
        text="Streaming player",
        fg=TEXT_MUTED,
        bg=CARD,
        cursor="hand2",
        anchor="w",
        font=(FONT, 11),
    ).pack(fill=X, pady=(5, 0))

    for widget in (
        spotify_tile,
        spotify_icon,
        spotify_text,
        *spotify_text.winfo_children(),
    ):
        widget.bind("<Button-1>", lambda _event: go_home())

    secondary = Frame(apps, bg=BG)
    secondary.pack(fill=X)

    def create_placeholder_tile(parent, title, symbol):
        tile = Frame(
            parent,
            bg=SURFACE_ALT,
            width=218,
            height=210,
            highlightbackground=DIVIDER,
            highlightthickness=1,
        )
        tile.pack(side=LEFT, fill=X, expand=True)
        tile.pack_propagate(False)
        Label(
            tile,
            text=symbol,
            fg=TEXT,
            bg=SURFACE_ALT,
            font=(FONT, 42, "bold"),
        ).pack(pady=(26, 8))
        Label(
            tile,
            text=title,
            fg=TEXT,
            bg=SURFACE_ALT,
            font=(FONT, 16, "bold"),
        ).pack()
        Label(
            tile,
            text="COMING SOON",
            fg=TEXT_DIM,
            bg=SURFACE_ALT,
            font=(FONT, 8, "bold"),
        ).pack(pady=(8, 0))
        return tile

    create_placeholder_tile(secondary, "Offline", "♫")
    spacer = Frame(secondary, bg=BG, width=10)
    spacer.pack(side=LEFT)
    create_placeholder_tile(secondary, "Settings", "⚙")

    Label(
        frame,
        text="Local music and device controls are the next step.",
        fg=TEXT_DIM,
        bg=BG,
        font=(FONT, 9),
    ).pack(pady=(8, 18))

    def update_clock():
        if not frame.winfo_exists():
            return
        now = datetime.now()
        time_label.config(text=now.strftime("%H:%M"))
        date_label.config(text=now.strftime("%d.%m.%Y"))
        root.after(1000, update_clock)

    update_clock()

    return {
        "frame": frame,
        "update": lambda _current_state: None,
    }
