from tkinter import BOTH, LEFT, RIGHT, X
from tkinter import Button, Canvas, Frame, Label

from app.controller.controller_navigation import go_launcher
from app.core.config import MUSIC_LIBRARY_DIR
from app.features.local_audio.controller import refresh_library, play_selected_file
from app.ui.components.mini_player import create_mini_player
from app.ui.theme import (
    ACCENT,
    BG,
    CARD,
    DIVIDER,
    FONT,
    PAGE_PAD,
    SURFACE_ALT,
    SURFACE_ACTIVE,
    TEXT,
    TEXT_DIM,
    TEXT_MUTED,
)


def _format_time(milliseconds):
    total_seconds = max(0, int(milliseconds or 0) // 1000)
    return f"{total_seconds // 60}:{total_seconds % 60:02d}"


def _format_size(size_bytes):
    return f"{max(0, size_bytes or 0) / (1024 * 1024):.1f} MB"


def render_local_library(root, _state, button_style):
    frame = Frame(root, bg=BG)

    header = Frame(frame, bg=BG)
    header.pack(fill=X, padx=PAGE_PAD, pady=(18, 8))

    Button(
        header,
        text="←",
        command=go_launcher,
        fg=TEXT,
        bg=SURFACE_ALT,
        activeforeground=TEXT,
        activebackground=SURFACE_ACTIVE,
        font=(FONT, 16, "bold"),
        relief="flat",
        borderwidth=0,
        highlightthickness=0,
        takefocus=False,
        width=3,
    ).pack(side=LEFT)

    title_frame = Frame(header, bg=BG)
    title_frame.pack(side=LEFT, fill=X, expand=True, padx=12)
    Label(
        title_frame,
        text="Offline Library",
        fg=TEXT,
        bg=BG,
        anchor="w",
        font=(FONT, 21, "bold"),
    ).pack(fill=X)
    Label(
        title_frame,
        text=MUSIC_LIBRARY_DIR,
        fg=TEXT_DIM,
        bg=BG,
        anchor="w",
        font=(FONT, 8),
    ).pack(fill=X)

    Button(
        header,
        text="↻",
        command=refresh_library,
        fg=ACCENT,
        bg=SURFACE_ALT,
        activeforeground=TEXT,
        activebackground=SURFACE_ACTIVE,
        font=(FONT, 17, "bold"),
        relief="flat",
        borderwidth=0,
        highlightthickness=0,
        takefocus=False,
        width=3,
    ).pack(side=RIGHT)

    status_label = Label(
        frame,
        text="Loading local music…",
        fg=TEXT_MUTED,
        bg=BG,
        anchor="w",
        font=(FONT, 10),
    )
    status_label.pack(fill=X, padx=PAGE_PAD, pady=(4, 8))

    tracks_canvas = Canvas(
        frame,
        bg=BG,
        highlightthickness=0,
        borderwidth=0,
    )
    tracks_canvas.pack(fill=BOTH, expand=True, padx=PAGE_PAD, pady=(0, 14))

    tracks_frame = Frame(tracks_canvas, bg=BG)
    tracks_window = tracks_canvas.create_window(
        (0, 0),
        window=tracks_frame,
        anchor="nw",
    )
    tracks_frame.bind(
        "<Configure>",
        lambda _event: tracks_canvas.configure(
            scrollregion=tracks_canvas.bbox("all")
        ),
    )
    tracks_canvas.bind(
        "<Configure>",
        lambda event: tracks_canvas.itemconfigure(
            tracks_window,
            width=event.width,
        ),
    )
    tracks_canvas.bind(
        "<ButtonPress-1>",
        lambda event: tracks_canvas.scan_mark(event.x, event.y),
    )
    tracks_canvas.bind(
        "<B1-Motion>",
        lambda event: tracks_canvas.scan_dragto(event.x, event.y, gain=1),
    )

    mini_player = create_mini_player(root, frame, button_style)

    def bind_play_file(widget, track_path):
        widget.bind(
            "<ButtonPress-1>",
            lambda _event: play_selected_file(track_path)
        )

    def bind_touch_scroll(widget):
        widget.bind(
            "<ButtonPress-1>",
            lambda event: tracks_canvas.scan_mark(event.x_root, event.y_root),
        )
        widget.bind(
            "<B1-Motion>",
            lambda event: tracks_canvas.scan_dragto(
                event.x_root,
                event.y_root,
                gain=1,
            ),
        )

    rendered_signature = None

    def rebuild(local_state):
        nonlocal rendered_signature

        tracks = local_state["tracks"]
        signature = (
            local_state["loading"],
            local_state["error"],
            tuple(                (
                    track["path"],
                    track["title"],
                    track["artist"],
                    track["duration_ms"],
                    track["size_bytes"],
                )
                for track in tracks
            ),
        )
        if signature == rendered_signature:
            return

        rendered_signature = signature
        for widget in tracks_frame.winfo_children():
            widget.destroy()

        if local_state["loading"]:
            status_label.config(text="Scanning Music folder…", fg=TEXT_MUTED)
        elif local_state["error"]:
            status_label.config(
                text=f"Library error: {local_state['error']}",
                fg="#FF626B",
            )
        else:
            status_label.config(
                text=f"{len(tracks)} local track{'s' if len(tracks) != 1 else ''}",
                fg=TEXT_MUTED,
            )

        if not tracks and not local_state["loading"]:
            empty = Frame(
                tracks_frame,
                bg=CARD,
                highlightbackground=DIVIDER,
                highlightthickness=1,
            )
            empty.pack(fill=X, pady=4)
            Label(
                empty,
                text="No music found",
                fg=TEXT,
                bg=CARD,
                font=(FONT, 15, "bold"),
            ).pack(pady=(28, 5))
            Label(
                empty,
                text=f"Copy audio files to\n{MUSIC_LIBRARY_DIR}",
                fg=TEXT_MUTED,
                bg=CARD,
                justify="center",
                font=(FONT, 10),
            ).pack(pady=(0, 28))
            return

        for index, track in enumerate(tracks, start=1):
            row = Frame(
                tracks_frame,
                bg=CARD,
                height=94,
                highlightbackground=DIVIDER,
                highlightthickness=1,
            )
            row.pack(fill=X, pady=4)
            row.pack_propagate(False)

            Label(
                row,
                text=f"{index:02d}",
                fg=ACCENT,
                bg=CARD,
                width=4,
                font=(FONT, 11, "bold"),
            ).pack(side=LEFT, padx=(8, 2))

            details = Frame(row, bg=CARD)
            details.pack(side=LEFT, fill=BOTH, expand=True, pady=13)
            Label(
                details,
                text=track["title"],
                fg=TEXT,
                bg=CARD,
                anchor="w",
                font=(FONT, 12, "bold"),
            ).pack(fill=X)
            Label(
                details,
                text=track["artist"],
                fg=TEXT_MUTED,
                bg=CARD,
                anchor="w",
                font=(FONT, 10),
            ).pack(fill=X, pady=(2, 0))

            metadata = "  •  ".join([
                track["format"],
                _format_time(track["duration_ms"]),
                _format_size(track["size_bytes"]),
            ])
            Label(
                details,
                text=metadata,
                fg=TEXT_DIM,
                bg=CARD,
                anchor="w",
                font=(FONT, 8),
            ).pack(fill=X, pady=(3, 0))

            bind_touch_scroll(row)
            for widget in (details, *row.winfo_children(), *details.winfo_children()):
                # bind_touch_scroll(widget)
                bind_play_file(widget, track["path"])

    def update(current_state):
        rebuild(current_state["local"])
        mini_player["update"](current_state)

    return {
        "frame": frame,
        "update": update,
    }
