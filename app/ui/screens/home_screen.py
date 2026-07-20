from threading import Thread
from tkinter import BOTH, BOTTOM, HORIZONTAL, LEFT, NORMAL, RIGHT, TOP, X
from tkinter import Button, Canvas, Frame, Label, Scrollbar

from app.controller.controller_home import get_playlist_tracks, load_home
from app.controller.controller_navigation import go_player
from app.controller.controller_player import on_toggle_play, play_selected_track
from app.core.state import get_state
from app.services.image_cache import get_photo_async


def _get_track_id(song):
    track_id = song.get("track_id")
    if track_id:
        return track_id
    if song.get("track") or song.get("artist"):
        return song.get("track"), song.get("artist"), song.get("duration_ms")
    return None


def render_home(root, state, button_style):
    frame = Frame(root, bg="black")

    header = Frame(frame, bg="black")
    Label(
        header,
        text="Home",
        fg="white",
        bg="black",
        font=("DejaVu Sans", 24, "bold"),
    ).pack(side=LEFT)
    header.pack(fill=X, padx=12, pady=(12, 6))

    content = Frame(frame, bg="black")
    content.pack(fill=BOTH, expand=True, padx=12)
    Label(
        content,
        text="Recently played",
        fg="white",
        bg="black",
        anchor="w",
        font=("DejaVu Sans", 16, "bold"),
    ).pack(fill=X, pady=(4, 4))
    recent_frame = Frame(content, bg="black")
    recent_frame.pack(fill=X)

    Label(
        content,
        text="Your playlists",
        fg="white",
        bg="black",
        anchor="w",
        font=("DejaVu Sans", 16, "bold"),
    ).pack(fill=X, pady=(12, 4))

    playlist_box = Frame(content, bg="#111111", height=190)
    playlist_box.pack(fill=X)
    playlist_box.pack_propagate(False)
    playlist_canvas = Canvas(playlist_box, bg="#111111", highlightthickness=0)
    playlist_scroll = Scrollbar(
        playlist_box, orient=HORIZONTAL, command=playlist_canvas.xview, width=24
    )
    playlist_list = Frame(playlist_canvas, bg="#111111")
    playlist_window = playlist_canvas.create_window((0, 0), window=playlist_list, anchor="nw")
    playlist_canvas.configure(xscrollcommand=playlist_scroll.set)
    playlist_canvas.pack(side=TOP, fill=BOTH, expand=True)
    playlist_scroll.pack(side=BOTTOM, fill=X)

    playlist_list.bind(
        "<Configure>",
        lambda _event: playlist_canvas.configure(scrollregion=playlist_canvas.bbox("all")),
    )
    playlist_canvas.bind(
        "<Configure>",
        lambda event: playlist_canvas.itemconfigure(playlist_window, height=event.height),
    )
    playlist_canvas.bind("<Button-4>", lambda _event: playlist_canvas.xview_scroll(-1, "units"))
    playlist_canvas.bind("<Button-5>", lambda _event: playlist_canvas.xview_scroll(1, "units"))

    playlist_drag_start_x = 0
    playlist_dragged = False

    def playlist_canvas_x(event):
        return event.x_root - playlist_canvas.winfo_rootx()

    def start_playlist_drag(event):
        nonlocal playlist_drag_start_x, playlist_dragged
        playlist_drag_start_x = event.x_root
        playlist_dragged = False
        playlist_canvas.scan_mark(playlist_canvas_x(event), 0)

    def drag_playlist(event):
        nonlocal playlist_dragged
        if abs(event.x_root - playlist_drag_start_x) > 5:
            playlist_dragged = True
        playlist_canvas.scan_dragto(playlist_canvas_x(event), 0, gain=1)

    def finish_playlist_press(_event, playlist_uri, playlist_name):
        if not playlist_dragged:
            print_playlist_tracks(playlist_uri, playlist_name)

    for widget in (playlist_canvas, playlist_list):
        widget.bind("<ButtonPress-1>", start_playlist_drag)
        widget.bind("<B1-Motion>", drag_playlist)

    mini_player = Frame(frame, bg="#181818", height=72, cursor="hand2")
    mini_player.pack_propagate(False)
    mini_cover_frame = Frame(mini_player, width=56, height=56, bg="black")
    mini_cover_frame.pack(side=LEFT, padx=8, pady=8)
    mini_cover_frame.pack_propagate(False)
    mini_cover = Label(mini_cover_frame, bg="black", borderwidth=0)
    mini_cover.pack(fill=BOTH, expand=True)
    mini_text = Frame(mini_player, bg="#181818")
    mini_text.pack(side=LEFT, fill=BOTH, expand=True, pady=10)
    mini_track = Label(
        mini_text, fg="white", bg="#181818", anchor="w", font=("DejaVu Sans", 12, "bold")
    )
    mini_artist = Label(
        mini_text, fg="#aaaaaa", bg="#181818", anchor="w", font=("DejaVu Sans", 10)
    )
    mini_track.pack(fill=X)
    mini_artist.pack(fill=X)
    mini_play = Button(
        mini_player, text="||", command=on_toggle_play, width=3, **button_style
    )
    mini_play.pack(side=RIGHT, padx=8, pady=10)

    for widget in (mini_player, mini_cover_frame, mini_cover, mini_text, mini_track, mini_artist):
        widget.bind("<Button-1>", lambda _event: go_player())

    recent_signature = None
    playlist_signature = None
    mini_cover_key = None

    def print_playlist_tracks(playlist_uri, playlist_name):
        def load_and_print():
            tracks = get_playlist_tracks(playlist_uri)
            if tracks is None:
                return
            print(f"\n[PLAYLIST] {playlist_name} ({len(tracks)} tracks)")
            for index, track in enumerate(tracks, start=1):
                print(
                    f'{index}. {track.get("name", "")} — '
                    f'{track.get("artist", "")} [{track.get("uri", "")}]'
                )

        Thread(target=load_and_print, daemon=True).start()

    def rebuild_lists(current_state):
        nonlocal recent_signature, playlist_signature

        tracks = current_state.get("recent_tracks", [])
        new_recent_signature = (
            current_state.get("home_loading"),
            current_state.get("home_error"),
            tuple((track.get("uri"), track.get("name"), track.get("artist")) for track in tracks),
        )
        if new_recent_signature != recent_signature:
            recent_signature = new_recent_signature
            for child in recent_frame.winfo_children():
                child.destroy()

            if not tracks:
                message = current_state.get("home_error") or (
                    "Loading..." if current_state.get("home_loading") else "No recently played tracks"
                )
                Label(recent_frame, text=message, fg="#aaaaaa", bg="black", anchor="w").pack(fill=X)
            else:
                for track in tracks:
                    text = f'{track.get("name", "")}  —  {track.get("artist", "")}'
                    Button(
                        recent_frame,
                        text=text,
                        command=lambda uri=track.get("uri"): play_selected_track(uri) if uri else None,
                        fg="white",
                        bg="#181818",
                        activeforeground="white",
                        activebackground="#333333",
                        anchor="w",
                        relief="flat",
                        borderwidth=0,
                        padx=8,
                        pady=4,
                    ).pack(fill=X, pady=1)

        playlists = current_state.get("playlists", [])
        new_playlist_signature = (
            current_state.get("home_loading"),
            current_state.get("home_error"),
            tuple(
                (
                    playlist.get("uri"),
                    playlist.get("name"),
                    playlist.get("owner"),
                    playlist.get("image_url"),
                )
                for playlist in playlists
            ),
        )
        if new_playlist_signature == playlist_signature:
            return

        playlist_signature = new_playlist_signature
        for child in playlist_list.winfo_children():
            child.destroy()

        if not playlists:
            message = current_state.get("home_error") or (
                "Loading..." if current_state.get("home_loading") else "No saved playlists"
            )
            Label(playlist_list, text=message, fg="#aaaaaa", bg="#111111", anchor="w").pack(
                fill=X, padx=8, pady=8
            )
            return

        for playlist in playlists:
            card = Frame(playlist_list, width=136, height=166, bg="#181818")
            card.pack(side=LEFT, padx=5, pady=5)
            card.pack_propagate(False)
            cover_frame = Frame(card, width=120, height=120, bg="#282828")
            cover_frame.pack(padx=8, pady=(8, 3))
            cover_frame.pack_propagate(False)
            cover = Label(cover_frame, bg="#282828", borderwidth=0, highlightthickness=0)
            cover.pack(fill=BOTH, expand=True)
            name_label = Label(
                card,
                text=playlist.get("name", ""),
                fg="white",
                bg="#181818",
                anchor="center",
                font=("DejaVu Sans", 9, "bold"),
            )
            name_label.pack(fill=X, padx=5)

            image_url = playlist.get("image_url")
            expected_uri = playlist.get("uri")
            if expected_uri:
                for widget in (card, cover_frame, cover, name_label):
                    widget.config(cursor="hand2")
                    widget.bind("<ButtonPress-1>", start_playlist_drag)
                    widget.bind("<B1-Motion>", drag_playlist)
                    widget.bind(
                        "<ButtonRelease-1>",
                        lambda event, uri=expected_uri, name=playlist.get("name", ""): (
                            finish_playlist_press(event, uri, name)
                        ),
                    )

            def show_playlist_cover(photo, label=cover, uri=expected_uri):
                current_uris = {item.get("uri") for item in get_state().get("playlists", [])}
                if uri not in current_uris or not label.winfo_exists():
                    return
                label.config(image=photo if photo is not None else "")
                label.image = photo

            get_photo_async(root, image_url, (120, 120), show_playlist_cover)

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

        get_photo_async(root, url, (56, 56), show_cover)

    def restore_cover(_event=None):
        photo = getattr(mini_cover, "image", None)
        if photo is not None:
            mini_cover.config(image=photo)

    root.bind("<Map>", restore_cover, add="+")
    root.bind("<Configure>", restore_cover, add="+")

    def update(current_state):
        nonlocal mini_cover_key

        song = current_state["song"]
        if song.get("track_id"):
            if not mini_player.winfo_manager():
                mini_player.pack(fill=X, side=BOTTOM, before=content)
        elif mini_player.winfo_manager():
            mini_player.pack_forget()

        rebuild_lists(current_state)

        cover_key = (_get_track_id(song), song.get("image_url"))
        if cover_key != mini_cover_key:
            mini_cover_key = cover_key
            set_mini_cover(cover_key, song.get("image_url"))

        mini_track.config(text=song.get("track", "") or "Nothing playing")
        mini_artist.config(text=song.get("artist", ""))
        mini_play.config(text="||" if song.get("is_playing", False) else ">", state=NORMAL)

    Thread(target=load_home, daemon=True).start()
    update(state)
    return {"frame": frame, "update": update}
