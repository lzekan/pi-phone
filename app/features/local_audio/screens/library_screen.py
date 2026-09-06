from tkinter import BOTH, LEFT, RIGHT, X
from tkinter import Button, Canvas, Frame, Label

from app.controller.controller_navigation import go_launcher
from app.features.local_audio.controller import (
    add_to_queue,
    play_selected_file,
    refresh_library,
)
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
    mini_player = create_mini_player(root, frame, button_style)

    queue_toast_after_id = None
    queue_toast = Label(
        frame,
        text="Added to queue",
        fg=TEXT,
        bg=ACCENT,
        font=(FONT, 10, "bold"),
        padx=14,
        pady=7,
    )

    def show_queue_toast():
        nonlocal queue_toast_after_id

        if queue_toast_after_id is not None:
            root.after_cancel(queue_toast_after_id)

        queue_toast.place(relx=0.5, rely=0.82, anchor="center")
        queue_toast.lift()

        def hide_toast():
            nonlocal queue_toast_after_id
            queue_toast.place_forget()
            queue_toast_after_id = None

        queue_toast_after_id = root.after(2000, hide_toast)

    drag_start_x = 0
    drag_start_y = 0
    drag_axis = None
    dragged_details = None

    def tracks_canvas_y(event):
        return event.y_root - tracks_canvas.winfo_rooty()

    def start_track_drag(event, details=None):
        nonlocal drag_start_x, drag_start_y, drag_axis, dragged_details
        drag_start_x = event.x_root
        drag_start_y = event.y_root
        drag_axis = None
        dragged_details = details
        tracks_canvas.scan_mark(0, tracks_canvas_y(event))

    def drag_track(event):
        nonlocal drag_axis
        delta_x = event.x_root - drag_start_x
        delta_y = event.y_root - drag_start_y

        if drag_axis is None and max(abs(delta_x), abs(delta_y)) > 6:
            drag_axis = "horizontal" if abs(delta_x) > abs(delta_y) else "vertical"

        if drag_axis == "horizontal":
            if dragged_details is not None and dragged_details.winfo_exists():
                dragged_details.pack_configure(
                    padx=(min(max(delta_x, 0), 76), 0)
                )
            return

        if drag_axis == "vertical":
            tracks_canvas.scan_dragto(0, tracks_canvas_y(event), gain=1)

    def finish_track_drag(event, track=None):
        nonlocal dragged_details
        delta_x = event.x_root - drag_start_x

        if dragged_details is not None and dragged_details.winfo_exists():
            dragged_details.pack_configure(padx=0)
        dragged_details = None

        if drag_axis == "horizontal" and delta_x >= 60 and track:
            add_to_queue(track)
            show_queue_toast()
        elif drag_axis is None and track:
            play_selected_file(track["path"])

    for widget in (tracks_canvas, tracks_frame):
        widget.bind("<ButtonPress-1>", start_track_drag)
        widget.bind("<B1-Motion>", drag_track)
        widget.bind("<ButtonRelease-1>", finish_track_drag)

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
                text="Add supported audio files to the Music folder.",
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

            index_label = Label(
                row,
                text=f"{index:02d}",
                fg=ACCENT,
                bg=CARD,
                width=4,
                font=(FONT, 11, "bold"),
            )
            index_label.pack(side=LEFT, padx=(8, 2))

            details = Frame(row, bg=CARD)
            details.pack(side=LEFT, fill=BOTH, expand=True, pady=13)
            name_label = Label(
                details,
                text=track["title"],
                fg=TEXT,
                bg=CARD,
                anchor="w",
                font=(FONT, 12, "bold"),
            )
            name_label.pack(fill=X)
            artist_label = Label(
                details,
                text=track["artist"],
                fg=TEXT_MUTED,
                bg=CARD,
                anchor="w",
                font=(FONT, 10),
            )
            artist_label.pack(fill=X, pady=(2, 0))

            metadata = "  •  ".join([
                track["format"],
                _format_time(track["duration_ms"]),
                _format_size(track["size_bytes"]),
            ])
            metadata_label = Label(
                details,
                text=metadata,
                fg=TEXT_DIM,
                bg=CARD,
                anchor="w",
                font=(FONT, 8),
            )
            metadata_label.pack(fill=X, pady=(3, 0))

            for widget in (
                row,
                index_label,
                details,
                name_label,
                artist_label,
                metadata_label,
            ):
                widget.bind(
                    "<ButtonPress-1>",
                    lambda event, info=details: start_track_drag(event, info),
                )
                widget.bind("<B1-Motion>", drag_track)
                widget.bind(
                    "<ButtonRelease-1>",
                    lambda event, selected_track=track: finish_track_drag(
                        event,
                        selected_track,
                    ),
                )

    def update(current_state):
        rebuild(current_state["local"])
        mini_player["update"](current_state)

    return {
        "frame": frame,
        "update": update,
    }
