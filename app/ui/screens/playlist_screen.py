from threading import Thread
from tkinter import BOTH, BOTTOM, LEFT, NORMAL, RIGHT, X
from tkinter import Button, Canvas, Frame, Label

from app.controller.controller_navigation import go_home, go_player
from app.controller.controller_player import play_selected_track, on_toggle_play
from app.controller.controller_playlist import load_playlist, load_album
from app.core.state import get_state
from app.services.image_cache import get_photo_async
from app.ui.theme import (
    ACCENT,
    ACCENT_ACTIVE,
    BG,
    CARD,
    DANGER,
    DIVIDER,
    FONT,
    PAGE_PAD,
    SURFACE,
    SURFACE_ACTIVE,
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


def render_playlist(root, state, button_style):
    frame = Frame(root, bg=BG)
    header = Frame(frame, bg=BG)
    Button(
        header,
        text="‹  Home",
        command=go_home,
        **button_style,
    ).pack(side=LEFT)
    Label(
        header,
        text="Collection",
        fg=TEXT,
        bg=BG,
        font=(FONT, 17, "bold"),
    ).pack(side=LEFT, padx=12)
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

    tracks_box = Frame(frame, bg=BG)
    tracks_box.pack(fill=BOTH, expand=True)
    tracks_canvas = Canvas(tracks_box, bg=BG, highlightthickness=0)
    tracks_list = Frame(tracks_canvas, bg=BG)
    tracks_window = tracks_canvas.create_window((0, 0), window=tracks_list, anchor="nw")
    tracks_canvas.pack(side=LEFT, fill=BOTH, expand=True)

    tracks_list.bind(
        "<Configure>",
        lambda _event: tracks_canvas.configure(scrollregion=tracks_canvas.bbox("all")),
    )
    tracks_canvas.bind(
        "<Configure>",
        lambda event: tracks_canvas.itemconfigure(tracks_window, width=event.width),
    )

    mini_player = Frame(
        frame,
        bg=SURFACE_ALT,
        height=76,
        cursor="hand2",
        highlightbackground=DIVIDER,
        highlightthickness=1,
    )
    mini_player.pack_propagate(False)
    mini_cover_frame = Frame(mini_player, width=58, height=58, bg=SURFACE)
    mini_cover_frame.pack(side=LEFT, padx=8, pady=8)
    mini_cover_frame.pack_propagate(False)
    mini_cover = Label(mini_cover_frame, bg=SURFACE, borderwidth=0)
    mini_cover.pack(fill=BOTH, expand=True)
    mini_text = Frame(mini_player, bg=SURFACE_ALT)
    mini_text.pack(side=LEFT, fill=BOTH, expand=True, pady=10)
    mini_track = Label(
        mini_text, fg=TEXT, bg=SURFACE_ALT, anchor="w", font=(FONT, 12, "bold")
    )
    mini_artist = Label(
        mini_text, fg=TEXT_MUTED, bg=SURFACE_ALT, anchor="w", font=(FONT, 10)
    )
    mini_track.pack(fill=X)
    mini_artist.pack(fill=X)
    mini_play = Button(
        mini_player,
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
    mini_play.pack(side=RIGHT, padx=8, pady=10)

    for widget in (mini_player, mini_cover_frame, mini_cover, mini_text, mini_track, mini_artist):
        widget.bind("<Button-1>", lambda _event: go_player())

    loaded_collection_uri = None
    tracks_signature = None
    cover_rows = []
    drag_start_y = 0
    tracks_dragged = False
    mini_cover_key = None
    collection_cover_key = None

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
        schedule_visible_covers()

    def finish_track_press(_event, track_uri, playlist_uri):
        if not tracks_dragged and track_uri:
            play_selected_track(track_uri, playlist_uri)

    for widget in (tracks_canvas, tracks_list):
        widget.bind("<ButtonPress-1>", start_tracks_drag)
        widget.bind("<B1-Motion>", drag_tracks)

    def rebuild_tracks(current_state):
        nonlocal tracks_signature, cover_rows

        tracks = current_state.get("current_collection_tracks")
        new_signature = (
            current_state.get("current_collection_uri"),
            current_state.get("current_collection_type"),
            current_state.get("collection_error"),
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
            return

        if tracks is None:
            Label(
                tracks_list,
                text="Loading...",
                fg=TEXT_MUTED,
                bg=BG,
                font=(FONT, 14, "bold"),
            ).pack(fill=X, padx=12, pady=12)
            return

        if not tracks:
            Label(
                tracks_list,
                text="No tracks found in this collection.",
                fg=TEXT,
                bg=BG,
                font=(FONT, 14, "bold"),
            ).pack(fill=X, padx=12, pady=12)
            return

        collection_uri = current_state.get("current_collection_uri")
        is_album = current_state.get("current_collection_type") == "album"
        for index, track in enumerate(tracks, start=1):
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
                font=(FONT, 12, "bold"),
                borderwidth=0,
                highlightthickness=0,
            )
            image_label.pack(fill=BOTH, expand=True)

            info_frame = Frame(track_frame, bg=CARD)
            info_frame.pack(side=LEFT, fill=BOTH, expand=True, pady=9)
            name_label = Label(
                info_frame,
                text=track.get("name", ""),
                fg=TEXT,
                bg=CARD,
                anchor="w",
                font=(FONT, 12, "bold"),
            )
            artist_label = Label(
                info_frame,
                text=track.get("artist", ""),
                fg=TEXT_MUTED,
                bg=CARD,
                anchor="w",
                font=(FONT, 10),
            )
            name_label.pack(fill=X)
            artist_label.pack(fill=X)
            action_label = Label(
                track_frame,
                text="›",
                fg=TEXT_DIM,
                bg=CARD,
                font=(FONT, 20),
            )
            action_label.pack(side=RIGHT, padx=10)

            track_uri = track.get("uri")
            for widget in (
                track_frame,
                image_frame,
                image_label,
                info_frame,
                name_label,
                artist_label,
                action_label,
            ):
                widget.config(cursor="hand2")
                widget.bind("<ButtonPress-1>", start_tracks_drag)
                widget.bind("<B1-Motion>", drag_tracks)
                widget.bind(
                    "<ButtonRelease-1>",
                    lambda event, uri=track_uri, context=collection_uri: (
                        finish_track_press(event, uri, context)
                    ),
                )

            if not is_album:
                cover_rows.append({
                    "frame": track_frame,
                    "label": image_label,
                    "image_url": track.get("image_url"),
                    "playlist_uri": collection_uri,
                    "requested": False,
                })

        schedule_visible_covers()

    def set_mini_cover(cover_key, url):
        mini_cover.config(image="")
        mini_cover.image = None

        def show_cover(photo):
            current_song = get_state()["song"]
            current_key = (_get_track_id(current_song), current_song.get("image_url"))
            if current_key != cover_key:
                return
            mini_cover.config(image=photo if photo is not None else "")
            mini_cover.image = photo

        get_photo_async(root, url, (58, 58), show_cover)

    def set_collection_cover(cover_key, url):
        collection_cover.config(image="")
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
        mini_photo = getattr(mini_cover, "image", None)
        if mini_photo is not None:
            mini_cover.config(image=mini_photo)
        collection_photo = getattr(collection_cover, "image", None)
        if collection_photo is not None:
            collection_cover.config(image=collection_photo)

    root.bind("<Map>", restore_cover, add="+")
    root.bind("<Configure>", restore_cover, add="+")

    def update(current_state):
        nonlocal loaded_collection_uri, tracks_signature
        nonlocal mini_cover_key, collection_cover_key

        playlist_name_label.config(
            text=current_state.get("current_collection_name") or ""
        )
        collection_type = current_state.get("current_collection_type") or "collection"
        collection_type_label.config(text=collection_type.upper())
        tracks = current_state.get("current_collection_tracks")
        collection_count_label.config(
            text=(
                "LOADING TRACKS"
                if tracks is None
                else f"{len(tracks)} TRACK{'S' if len(tracks) != 1 else ''}"
            )
        )

        new_collection_cover_key = (
            current_state.get("current_collection_uri"),
            current_state.get("current_collection_image_url"),
        )
        if new_collection_cover_key != collection_cover_key:
            collection_cover_key = new_collection_cover_key
            set_collection_cover(
                new_collection_cover_key,
                current_state.get("current_collection_image_url"),
            )

        current_uri = current_state.get("current_collection_uri")
        if current_uri and current_uri != loaded_collection_uri:
            loaded_collection_uri = current_uri
            tracks_canvas.yview_moveto(0)
            current_state["collection_error"] = None
            current_state["current_collection_tracks"] = None
            tracks_signature = None

            target = (
                load_album
                if current_state.get("current_collection_type") == "album"
                else load_playlist
            )

            Thread(target=target, daemon=True).start()

        rebuild_tracks(current_state)

        song = current_state["song"]
        if song.get("track_id"):
            if not mini_player.winfo_manager():
                mini_player.pack(fill=X, side=BOTTOM)
        elif mini_player.winfo_manager():
            mini_player.pack_forget()

        cover_key = (_get_track_id(song), song.get("image_url"))
        if cover_key != mini_cover_key:
            mini_cover_key = cover_key
            set_mini_cover(cover_key, song.get("image_url"))

        mini_track.config(text=song.get("track", "") or "Nothing playing")
        mini_artist.config(text=song.get("artist", ""))
        mini_play.config(
            text="Ⅱ" if song.get("is_playing", False) else "▶",
            state=NORMAL,
        )

    update(state)
    return {"frame": frame, "update": update}
