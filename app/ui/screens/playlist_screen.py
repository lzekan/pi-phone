from threading import Thread
from tkinter import BOTH, LEFT, RIGHT, X, Y
from tkinter import Button, Canvas, Frame, Label, Scrollbar

from app.controller.controller_navigation import go_home
from app.controller.controller_player import play_selected_track
from app.controller.controller_playlist import load_playlist
from app.core.state import get_state
from app.services.image_cache import get_photo_async


def render_playlist(root, state, button_style):
    frame = Frame(root, bg="black")
    header = Frame(frame, bg="black")
    Button(header, text="Home", command=go_home, **button_style).pack(side=LEFT)
    playlist_name_label = Label(
        header,
        text="",
        fg="white",
        bg="black",
        anchor="w",
        font=("DejaVu Sans", 20, "bold"),
    )
    playlist_name_label.pack(side=LEFT, fill=X, expand=True, padx=12)
    header.pack(fill=X, padx=12, pady=(12, 6))

    tracks_box = Frame(frame, bg="black")
    tracks_box.pack(fill=BOTH, expand=True)
    tracks_canvas = Canvas(tracks_box, bg="black", highlightthickness=0)
    tracks_scroll = Scrollbar(tracks_box, command=tracks_canvas.yview, width=24)
    tracks_list = Frame(tracks_canvas, bg="black")
    tracks_window = tracks_canvas.create_window((0, 0), window=tracks_list, anchor="nw")
    tracks_canvas.configure(yscrollcommand=tracks_scroll.set)
    tracks_canvas.pack(side=LEFT, fill=BOTH, expand=True)
    tracks_scroll.pack(side=RIGHT, fill=Y)

    tracks_list.bind(
        "<Configure>",
        lambda _event: tracks_canvas.configure(scrollregion=tracks_canvas.bbox("all")),
    )
    tracks_canvas.bind(
        "<Configure>",
        lambda event: tracks_canvas.itemconfigure(tracks_window, width=event.width),
    )
    tracks_canvas.bind("<Button-4>", lambda _event: tracks_canvas.yview_scroll(-1, "units"))
    tracks_canvas.bind("<Button-5>", lambda _event: tracks_canvas.yview_scroll(1, "units"))

    loaded_playlist_uri = None
    tracks_signature = None
    drag_start_y = 0
    tracks_dragged = False

    def tracks_canvas_y(event):
        return event.y_root - tracks_canvas.winfo_rooty()

    def start_tracks_drag(event):
        nonlocal drag_start_y, tracks_dragged
        drag_start_y = event.y_root
        tracks_dragged = False
        tracks_canvas.scan_mark(0, tracks_canvas_y(event))

    def drag_tracks(event):
        nonlocal tracks_dragged
        if abs(event.y_root - drag_start_y) > 5:
            tracks_dragged = True
        tracks_canvas.scan_dragto(0, tracks_canvas_y(event), gain=1)

    def finish_track_press(_event, track_uri, playlist_uri):
        if not tracks_dragged and track_uri:
            play_selected_track(track_uri, playlist_uri)

    for widget in (tracks_canvas, tracks_list):
        widget.bind("<ButtonPress-1>", start_tracks_drag)
        widget.bind("<B1-Motion>", drag_tracks)

    def rebuild_tracks(current_state):
        nonlocal tracks_signature

        tracks = current_state.get("current_playlist_tracks")
        new_signature = (
            current_state.get("current_playlist_uri"),
            current_state.get("playlist_error"),
            None if tracks is None else tuple(
                (
                    track.get("uri"),
                    track.get("name"),
                    track.get("artist"),
                    track.get("image_url"),
                )
                for track in tracks
            ),
        )
        if new_signature == tracks_signature:
            return

        tracks_signature = new_signature
        for widget in tracks_list.winfo_children():
            widget.destroy()

        error = current_state.get("playlist_error")
        if error:
            Label(
                tracks_list,
                text=f"Error: {error}",
                fg="red",
                bg="black",
                wraplength=400,
                font=("DejaVu Sans", 14, "bold"),
            ).pack(fill=X, padx=12, pady=12)
            return

        if tracks is None:
            Label(
                tracks_list,
                text="Loading...",
                fg="#aaaaaa",
                bg="black",
                font=("DejaVu Sans", 16, "bold"),
            ).pack(fill=X, padx=12, pady=12)
            return

        if not tracks:
            Label(
                tracks_list,
                text="No tracks found in this playlist.",
                fg="white",
                bg="black",
                font=("DejaVu Sans", 16, "bold"),
            ).pack(fill=X, padx=12, pady=12)
            return

        playlist_uri = current_state.get("current_playlist_uri")
        for track in tracks:
            track_frame = Frame(tracks_list, bg="#181818", cursor="hand2")
            track_frame.pack(fill=X, padx=12, pady=3)

            image_frame = Frame(track_frame, bg="#282828", width=56, height=56)
            image_frame.pack(side=LEFT, padx=(6, 10), pady=6)
            image_frame.pack_propagate(False)
            image_label = Label(
                image_frame, bg="#282828", borderwidth=0, highlightthickness=0
            )
            image_label.pack(fill=BOTH, expand=True)

            info_frame = Frame(track_frame, bg="#181818")
            info_frame.pack(side=LEFT, fill=BOTH, expand=True, pady=8)
            name_label = Label(
                info_frame,
                text=track.get("name", ""),
                fg="white",
                bg="#181818",
                anchor="w",
                font=("DejaVu Sans", 13, "bold"),
            )
            artist_label = Label(
                info_frame,
                text=track.get("artist", ""),
                fg="#aaaaaa",
                bg="#181818",
                anchor="w",
                font=("DejaVu Sans", 11),
            )
            name_label.pack(fill=X)
            artist_label.pack(fill=X)

            track_uri = track.get("uri")
            for widget in (
                track_frame,
                image_frame,
                image_label,
                info_frame,
                name_label,
                artist_label,
            ):
                widget.config(cursor="hand2")
                widget.bind("<ButtonPress-1>", start_tracks_drag)
                widget.bind("<B1-Motion>", drag_tracks)
                widget.bind(
                    "<ButtonRelease-1>",
                    lambda event, uri=track_uri, context=playlist_uri: (
                        finish_track_press(event, uri, context)
                    ),
                )

            def show_cover(photo, label=image_label, expected_playlist_uri=playlist_uri):
                if (
                    get_state().get("current_playlist_uri") != expected_playlist_uri
                    or not label.winfo_exists()
                ):
                    return
                label.config(image=photo if photo is not None else "")
                label.image = photo

            get_photo_async(root, track.get("image_url"), (56, 56), show_cover)

    def update(current_state):
        nonlocal loaded_playlist_uri, tracks_signature

        playlist_name_label.config(
            text=current_state.get("current_playlist_name") or ""
        )

        current_uri = current_state.get("current_playlist_uri")
        if current_uri and current_uri != loaded_playlist_uri:
            loaded_playlist_uri = current_uri
            current_state["playlist_error"] = None
            current_state["current_playlist_tracks"] = None
            tracks_signature = None
            Thread(target=load_playlist, daemon=True).start()

        rebuild_tracks(current_state)

    update(state)
    return {"frame": frame, "update": update}
