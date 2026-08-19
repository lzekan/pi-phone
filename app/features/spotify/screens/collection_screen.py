from threading import Thread
from tkinter import BOTH, LEFT, RIGHT, X
from tkinter import Button, Canvas, Frame, Label

from app.controller.controller_navigation import go_home
from app.features.spotify.controllers.player import play_selected_track
from app.features.spotify.controllers.collection import (
    load_album,
    load_album_library_status,
    load_liked_tracks,
    load_more_collection,
    load_playlist,
    toggle_current_album_saved,
)
from app.features.spotify.controllers.queue import add_to_manual_queue
from app.core.state import get_state
from app.services.image_cache import get_photo_async
from app.ui.components.mini_player import create_mini_player
from app.ui.theme import (
    ACCENT,
    BG,
    CARD,
    DANGER,
    DIVIDER,
    FONT,
    PAGE_PAD,
    SURFACE,
    SURFACE_ALT,
    TEXT,
    TEXT_DIM,
    TEXT_MUTED,
)

def render_playlist(root, state, button_style):
    frame = Frame(root, bg=BG)
    header = Frame(frame, bg=BG)
    Button(
        header,
        text="‹  Home",
        command=go_home,
        **button_style,
    ).pack(side=LEFT)
    header.pack(fill=X, padx=PAGE_PAD, pady=(10, 6))

    collection_hero = Frame(
        frame,
        bg=SURFACE,
        height=148,
        highlightbackground=DIVIDER,
        highlightthickness=1,
    )
    collection_hero.pack(fill=X, padx=PAGE_PAD, pady=(2, 10))
    collection_hero.pack_propagate(False)
    collection_cover_frame = Frame(
        collection_hero,
        width=116,
        height=116,
        bg=SURFACE_ALT,
    )
    collection_cover_frame.pack(side=LEFT, padx=14, pady=15)
    collection_cover_frame.pack_propagate(False)
    collection_cover = Label(
        collection_cover_frame,
        bg=SURFACE_ALT,
        borderwidth=0,
        highlightthickness=0,
    )
    collection_cover.pack(fill=BOTH, expand=True)
    collection_meta = Frame(collection_hero, bg=SURFACE)
    collection_meta.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 12), pady=18)
    collection_type_label = Label(
        collection_meta,
        text="COLLECTION",
        fg=ACCENT,
        bg=SURFACE,
        anchor="w",
        font=(FONT, 9, "bold"),
    )
    collection_type_label.pack(fill=X, pady=(2, 7))
    playlist_name_label = Label(
        collection_meta,
        text="",
        fg=TEXT,
        bg=SURFACE,
        anchor="w",
        justify=LEFT,
        wraplength=285,
        font=(FONT, 18, "bold"),
    )
    playlist_name_label.pack(fill=X)
    collection_count_label = Label(
        collection_meta,
        text="",
        fg=TEXT_MUTED,
        bg=SURFACE,
        anchor="w",
        font=(FONT, 9),
    )
    collection_count_label.pack(fill=X, pady=(8, 0))

    def toggle_album_saved():
        current_state = get_state()
        if current_state.get("collection_library_loading"):
            return
        current_state["collection_library_loading"] = True
        Thread(target=toggle_current_album_saved, daemon=True).start()

    album_save_button = Button(
        collection_hero,
        text="＋",
        command=toggle_album_saved,
        fg=TEXT,
        bg=SURFACE,
        activeforeground=ACCENT,
        activebackground=CARD,
        disabledforeground=TEXT_MUTED,
        font=(FONT, 20, "bold"),
        relief="flat",
        borderwidth=0,
        highlightthickness=0,
        takefocus=False,
        width=3,
        pady=2,
        cursor="hand2",
    )

    tracks_box = Frame(frame, bg=BG)
    tracks_box.pack(fill=BOTH, expand=True)
    tracks_canvas = Canvas(tracks_box, bg=BG, highlightthickness=0)
    tracks_list = Frame(tracks_canvas, bg=BG)
    tracks_window = tracks_canvas.create_window((0, 0), window=tracks_list, anchor="nw")
    tracks_canvas.pack(side=LEFT, fill=BOTH, expand=True)

    def update_tracks_scrollregion(_event=None):
        bounds = tracks_canvas.bbox("all")
        if bounds is None:
            return
        tracks_canvas.configure(
            scrollregion=(
                0,
                0,
                bounds[2],
                max(bounds[3], tracks_canvas.winfo_height()),
            )
        )

    tracks_list.bind("<Configure>", update_tracks_scrollregion)
    tracks_canvas.bind(
        "<Configure>",
        lambda event: tracks_canvas.itemconfigure(tracks_window, width=event.width),
    )

    mini_player = create_mini_player(root, frame, button_style)

    loaded_collection_uri = None
    tracks_signature = None
    cover_rows = []
    rendered_collection_key = None
    rendered_track_count = 0
    placeholder_visible = False
    drag_start_x = 0
    drag_start_y = 0
    tracks_dragged = False
    drag_axis = None
    drag_started_at_top = False
    pull_offset = 0
    dragged_info_frame = None
    queue_toast_after_id = None
    collection_cover_key = None

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

    def ellipsize(value, limit):
        value = value or ""
        return value if len(value) <= limit else value[:limit - 1].rstrip() + "…"

    def load_visible_covers():
        if not tracks_canvas.winfo_exists():
            return

        visible_top = tracks_canvas.canvasy(0)
        visible_bottom = visible_top + tracks_canvas.winfo_height()

        for row in cover_rows:
            if row["requested"] or not row["frame"].winfo_exists():
                continue

            row_top = row["frame"].winfo_y()
            row_bottom = row_top + row["frame"].winfo_height()
            if row_bottom < visible_top or row_top > visible_bottom:
                continue

            row["requested"] = True

            def show_cover(
                photo,
                label=row["label"],
                expected_playlist_uri=row["playlist_uri"],
            ):
                if (
                    get_state().get("current_collection_uri") != expected_playlist_uri
                    or not label.winfo_exists()
                ):
                    return
                label.config(image=photo if photo is not None else "")
                label.image = photo

            get_photo_async(root, row["image_url"], (52, 52), show_cover)

    def schedule_visible_covers():
        root.after_idle(load_visible_covers)
        root.after_idle(maybe_load_more)

    def maybe_load_more():
        current_state = get_state()
        if (
            current_state.get("collection_loading")
            or current_state.get("current_collection_next_offset") is None
        ):
            return

        _first, last = tracks_canvas.yview()
        if last >= 0.85:
            Thread(target=load_more_collection, daemon=True).start()

    def scroll_tracks(*args):
        tracks_canvas.yview(*args)
        schedule_visible_covers()

    tracks_canvas.bind(
        "<Button-4>",
        lambda _event: scroll_tracks("scroll", -1, "units"),
    )
    tracks_canvas.bind(
        "<Button-5>",
        lambda _event: scroll_tracks("scroll", 1, "units"),
    )
    tracks_canvas.bind("<Configure>", lambda _event: schedule_visible_covers(), add="+")
    frame.bind("<Map>", lambda _event: schedule_visible_covers(), add="+")

    def tracks_canvas_y(event):
        return event.y_root - tracks_canvas.winfo_rooty()

    def start_tracks_drag(event, info_frame=None):
        nonlocal drag_start_x, drag_start_y, tracks_dragged
        nonlocal drag_axis, drag_started_at_top, pull_offset, dragged_info_frame
        drag_start_x = event.x_root
        drag_start_y = event.y_root
        tracks_dragged = False
        drag_axis = None
        drag_started_at_top = tracks_canvas.yview()[0] <= 0.001
        pull_offset = 0
        tracks_canvas.coords(tracks_window, 0, 0)
        dragged_info_frame = info_frame
        tracks_canvas.scan_mark(0, tracks_canvas_y(event))

    def drag_tracks(event):
        nonlocal tracks_dragged, drag_axis, pull_offset
        delta_x = event.x_root - drag_start_x
        delta_y = event.y_root - drag_start_y

        if drag_axis is None and max(abs(delta_x), abs(delta_y)) > 6:
            drag_axis = "horizontal" if abs(delta_x) > abs(delta_y) else "vertical"
            tracks_dragged = True

        if drag_axis == "horizontal":
            if dragged_info_frame is not None and dragged_info_frame.winfo_exists():
                dragged_info_frame.pack_configure(padx=(min(max(delta_x, 0), 76), 0))
            return

        if drag_axis == "vertical":
            current_state = get_state()
            if (
                drag_started_at_top
                and delta_y > 0
                and current_state.get("current_collection_type") == "liked"
            ):
                pull_offset = min(int(delta_y * 0.45), 58)
                tracks_canvas.coords(tracks_window, 0, pull_offset)
                return

            tracks_canvas.scan_dragto(0, tracks_canvas_y(event), gain=1)
            schedule_visible_covers()

    def reset_pull_offset():
        nonlocal pull_offset

        if pull_offset <= 0:
            pull_offset = 0
            tracks_canvas.coords(tracks_window, 0, 0)
            return

        pull_offset = max(0, pull_offset - 8)
        tracks_canvas.coords(tracks_window, 0, pull_offset)
        if pull_offset:
            root.after(16, reset_pull_offset)

    def finish_track_press(event, track_uri, collection_uri, track_data):
        nonlocal dragged_info_frame
        delta_x = event.x_root - drag_start_x
        delta_y = event.y_root - drag_start_y

        if dragged_info_frame is not None and dragged_info_frame.winfo_exists():
            dragged_info_frame.pack_configure(padx=0)
        dragged_info_frame = None
        reset_pull_offset()

        current_state = get_state()
        should_refresh_liked = (
            drag_axis == "vertical"
            and drag_started_at_top
            and delta_y >= 90
            and current_state.get("current_collection_type") == "liked"
            and not current_state.get("collection_loading")
        )
        if should_refresh_liked:
            current_state["collection_error"] = None
            current_state["liked_tracks_dirty"] = False
            Thread(target=load_liked_tracks, daemon=True).start()
            return

        if drag_axis == "horizontal" and delta_x >= 60 and track_uri:
            add_to_manual_queue(track_data)
            show_queue_toast()
        elif not tracks_dragged and track_uri:
            playback_context = (
                None
                if get_state().get("current_collection_type") == "liked"
                else collection_uri
            )
            play_selected_track(
                track_uri,
                playback_context,
                track_data=track_data,
            )

    for widget in (tracks_canvas, tracks_list):
        widget.bind("<ButtonPress-1>", start_tracks_drag)
        widget.bind("<B1-Motion>", drag_tracks)
        widget.bind(
            "<ButtonRelease-1>",
            lambda event: finish_track_press(event, None, None, None),
        )

    def rebuild_tracks(current_state):
        nonlocal tracks_signature, cover_rows
        nonlocal rendered_collection_key, rendered_track_count
        nonlocal placeholder_visible

        tracks = current_state.get("current_collection_tracks")
        collection_key = (
            current_state.get("current_collection_uri"),
            current_state.get("current_collection_type"),
        )
        new_signature = (
            collection_key,
            current_state.get("collection_error"),
            None if tracks is None else len(tracks),
        )
        if new_signature == tracks_signature:
            return

        tracks_signature = new_signature
        needs_reset = (
            collection_key != rendered_collection_key
            or tracks is None
            or current_state.get("collection_error")
            or (tracks is not None and len(tracks) < rendered_track_count)
        )
        if needs_reset:
            rendered_collection_key = collection_key
            rendered_track_count = 0
            placeholder_visible = False
            cover_rows = []
            for widget in tracks_list.winfo_children():
                widget.destroy()

        error = current_state.get("collection_error")
        if error:
            Label(
                tracks_list,
                text=f"Error: {error}",
                fg=DANGER,
                bg=BG,
                wraplength=400,
                font=(FONT, 13, "bold"),
            ).pack(fill=X, padx=12, pady=12)
            placeholder_visible = True
            return

        if tracks is None:
            Label(
                tracks_list,
                text="Loading...",
                fg=TEXT_MUTED,
                bg=BG,
                font=(FONT, 14, "bold"),
            ).pack(fill=X, padx=12, pady=12)
            placeholder_visible = True
            return


        if placeholder_visible:
            for widget in tracks_list.winfo_children():
                widget.destroy()
            cover_rows = []
            rendered_track_count = 0
            placeholder_visible = False

        if not tracks:
            Label(
                tracks_list,
                text="No tracks found in this collection.",
                fg=TEXT,
                bg=BG,
                font=(FONT, 14, "bold"),
            ).pack(fill=X, padx=12, pady=12)
            placeholder_visible = True
            return

        collection_uri = current_state.get("current_collection_uri")
        is_album = current_state.get("current_collection_type") == "album"
        for index, track in enumerate(
            tracks[rendered_track_count:],
            start=rendered_track_count + 1,
        ):
            track_frame = Frame(
                tracks_list,
                bg=CARD,
                cursor="hand2",
                highlightbackground=DIVIDER,
                highlightthickness=1,
            )
            track_frame.pack(fill=X, padx=PAGE_PAD, pady=2)

            image_frame = Frame(track_frame, bg=SURFACE_ALT, width=52, height=52)
            image_frame.pack(side=LEFT, padx=(7, 10), pady=7)
            image_frame.pack_propagate(False)
            image_label = Label(
                image_frame,
                text=str(index) if is_album else "",
                fg=TEXT_DIM,
                bg=SURFACE_ALT,
                font=(FONT, 10, "bold"),
                borderwidth=0,
                highlightthickness=0,
            )
            image_label.pack(fill=BOTH, expand=True)

            info_frame = Frame(track_frame, bg=CARD)
            info_frame.pack(side=LEFT, fill=X, expand=True)
            name_label = Label(
                info_frame,
                text=ellipsize(track.get("name", ""), 36),
                fg=TEXT,
                bg=CARD,
                anchor="w",
                font=(FONT, 12, "bold"),
            )
            artist_label = Label(
                info_frame,
                text=ellipsize(track.get("artist", ""), 42),
                fg=TEXT_MUTED,
                bg=CARD,
                anchor="w",
                font=(FONT, 10),
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
                artist_label
            ):
                widget.config(cursor="hand2")
                widget.bind(
                    "<ButtonPress-1>",
                    lambda event, swipe_frame=info_frame: (
                        start_tracks_drag(event, swipe_frame)
                    ),
                )
                widget.bind("<B1-Motion>", drag_tracks)
                widget.bind(
                    "<ButtonRelease-1>",
                    lambda event, uri=track_uri, context=collection_uri, selected_track=track: (
                        finish_track_press(
                            event,
                            uri,
                            context,
                            selected_track,
                        )
                    )
                )

            if not is_album:
                cover_rows.append({
                    "frame": track_frame,
                    "label": image_label,
                    "image_url": track.get("image_url"),
                    "playlist_uri": collection_uri,
                    "requested": False,
                })

        rendered_track_count = len(tracks)
        schedule_visible_covers()

    def set_collection_cover(cover_key, url):
        collection_cover.config(
            image="",
            text="",
            bg=SURFACE_ALT,
        )
        collection_cover.image = None

        def show_cover(photo):
            current_state = get_state()
            current_key = (
                current_state.get("current_collection_uri"),
                current_state.get("current_collection_image_url"),
            )
            if current_key != cover_key:
                return
            collection_cover.config(image=photo if photo is not None else "")
            collection_cover.image = photo

        get_photo_async(root, url, (116, 116), show_cover)

    def restore_cover(_event=None):
        collection_photo = getattr(collection_cover, "image", None)
        if collection_photo is not None:
            collection_cover.config(image=collection_photo)

    root.bind("<Map>", restore_cover, add="+")
    root.bind("<Configure>", restore_cover, add="+")

    def update(current_state):
        nonlocal loaded_collection_uri, tracks_signature
        nonlocal collection_cover_key

        playlist_name_label.config(
            text=current_state.get("current_collection_name") or ""
        )
        collection_type = current_state.get("current_collection_type") or "collection"
        collection_type_label.config(text=collection_type.upper())
        tracks = current_state.get("current_collection_tracks")
        total_tracks = current_state.get("current_collection_total")
        displayed_track_count = total_tracks if total_tracks is not None else len(tracks or [])
        collection_count_label.config(
            text=(
                "LOADING TRACKS"
                if tracks is None
                else f"{displayed_track_count} TRACK{'S' if displayed_track_count != 1 else ''}"
            )
        )

        new_collection_cover_key = (
            current_state.get("current_collection_uri"),
            current_state.get("current_collection_image_url"),
        )
        if collection_type == "liked":
            if new_collection_cover_key != collection_cover_key:
                collection_cover_key = new_collection_cover_key
                collection_cover.config(
                    image="",
                    text="♥",
                    fg=TEXT,
                    bg=ACCENT,
                    font=(FONT, 40, "bold"),
                )
                collection_cover.image = None
        elif new_collection_cover_key != collection_cover_key:
            collection_cover_key = new_collection_cover_key
            set_collection_cover(
                new_collection_cover_key,
                current_state.get("current_collection_image_url"),
            )

        current_uri = current_state.get("current_collection_uri")
        liked_tracks_dirty = (
            collection_type == "liked"
            and current_state.get("liked_tracks_dirty")
        )
        if current_uri and (
            current_uri != loaded_collection_uri
            or liked_tracks_dirty
        ):
            loaded_collection_uri = current_uri
            tracks_canvas.yview_moveto(0)
            current_state["collection_error"] = None
            current_state["current_collection_tracks"] = None
            current_state["current_collection_next_offset"] = None
            current_state["current_collection_total"] = None
            current_state["collection_loading"] = False
            current_state["current_collection_saved"] = None
            current_state["collection_library_loading"] = False
            current_state["collection_library_error"] = None
            if collection_type == "liked":
                current_state["liked_tracks_dirty"] = False
            tracks_signature = None

            if current_state.get("current_collection_type") == "album":
                target = load_album
            elif current_state.get("current_collection_type") == "liked":
                target = load_liked_tracks
            else:
                target = load_playlist

            Thread(target=target, daemon=True).start()

            if current_state.get("current_collection_type") == "album":
                current_state["collection_library_loading"] = True
                Thread(target=load_album_library_status, daemon=True).start()

        if collection_type == "album":
            album_save_button.place(relx=1, rely=1, x=-2, y=-12, anchor="se")
            collection_meta.pack_configure(padx=(0, 58))

            if current_state.get("collection_library_loading"):
                is_saved = bool(current_state.get("current_collection_saved"))
                album_save_button.config(
                    text="＋",
                    fg=ACCENT if is_saved else TEXT_MUTED,
                    state="disabled",
                    cursor="arrow",
                )
            else:
                is_saved = bool(current_state.get("current_collection_saved"))
                album_save_button.config(
                    text="＋",
                    fg=ACCENT if is_saved else TEXT,
                    state="normal",
                    cursor="hand2",
                )
        else:
            album_save_button.place_forget()
            collection_meta.pack_configure(padx=(0, 12))

        rebuild_tracks(current_state)
        mini_player["update"](current_state)

    update(state)
    return {"frame": frame, "update": update}
