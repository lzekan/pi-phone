import time
from threading import Thread
from tkinter import *
from tkinter import ttk

from app.controller.controller_home import get_playlist_tracks, load_home
from app.controller.controller_navigation import go_home, go_player
from app.controller.controller_player import (
    on_next,
    on_prev,
    on_seek,
    on_toggle_play,
    play_selected_track,
)
from app.core.state import get_state
from app.services.image_cache import get_photo_async


last_progress = 0
last_update_time = 0
last_source_progress = None
last_track_id = None
last_is_playing = None


def _get_track_id(song):
    track_id = song.get("track_id")
    if track_id:
        return track_id
    if song.get("track") or song.get("artist"):
        return (
            song.get("track"),
            song.get("artist"),
            song.get("duration_ms")
        )
    return None


def _get_progress_ms(song, now):
    global last_progress, last_update_time
    global last_source_progress, last_track_id, last_is_playing

    track_id = _get_track_id(song)
    incoming = max(0, song.get("progress_ms", 0) or 0)
    duration = max(1, song.get("duration_ms", 1) or 1)
    is_playing = bool(song.get("is_playing", False))

    if (
        track_id != last_track_id
        or incoming != last_source_progress
        or is_playing != last_is_playing
    ):
        last_progress = incoming
        last_update_time = now

    last_track_id = track_id
    last_source_progress = incoming
    last_is_playing = is_playing

    progress_ms = last_progress
    if is_playing:
        progress_ms += (now - last_update_time) * 1000

    return min(max(0, progress_ms), duration)

def _get_progress_min_sec(song, now):
    progress_ms = _get_progress_ms(song, now)
    minutes = int(progress_ms / 60000)
    seconds = int((progress_ms % 60000) / 1000)
    return f"{minutes}:{seconds:02d}"

def _get_duration_min_sec(song):
    duration_ms = song.get("duration_ms", 0)
    minutes = int(duration_ms / 60000)
    seconds = int((duration_ms % 60000) / 1000)
    return f"{minutes}:{seconds:02d}"


def _seek_position_ms(x, width, duration_ms):
    if width <= 0 or duration_ms <= 0:
        return 0
    ratio = min(max(x / width, 0), 1)
    return int(ratio * duration_ms)


def start_ui(root):
    go_home()
    root.title("Pi Phone")

    button_style = {
        "font": ("DejaVu Sans", 16, "bold"),
        "fg": "white",
        "bg": "#222222",
        "activeforeground": "white",
        "activebackground": "#444444",
        "disabledforeground": "white",
        "relief": "raised",
        "borderwidth": 2,
        "highlightthickness": 0,
        "state": NORMAL,
    }

    home_frame = Frame(root, bg="black")
    player_frame = Frame(root, bg="black")

    # ----- HOME -----
    home_header = Frame(home_frame, bg="black")
    Label(
        home_header,
        text="Home",
        fg="white",
        bg="black",
        font=("DejaVu Sans", 24, "bold"),
    ).pack(side=LEFT)
    home_header.pack(fill=X, padx=12, pady=(12, 6))

    home_content = Frame(home_frame, bg="black")
    home_content.pack(fill=BOTH, expand=True, padx=12)

    Label(
        home_content,
        text="Recently played",
        fg="white",
        bg="black",
        anchor="w",
        font=("DejaVu Sans", 16, "bold"),
    ).pack(fill=X, pady=(4, 4))
    recent_frame = Frame(home_content, bg="black")
    recent_frame.pack(fill=X)

    Label(
        home_content,
        text="Your playlists",
        fg="white",
        bg="black",
        anchor="w",
        font=("DejaVu Sans", 16, "bold"),
    ).pack(fill=X, pady=(12, 4))

    playlist_box = Frame(home_content, bg="#111111", height=190)
    playlist_box.pack(fill=X)
    playlist_box.pack_propagate(False)
    playlist_canvas = Canvas(playlist_box, bg="#111111", highlightthickness=0)
    playlist_scroll = Scrollbar(playlist_box, orient=HORIZONTAL, command=playlist_canvas.xview)
    playlist_list = Frame(playlist_canvas, bg="#111111")
    playlist_window = playlist_canvas.create_window((0, 0), window=playlist_list, anchor="nw")
    playlist_canvas.configure(xscrollcommand=playlist_scroll.set)
    playlist_canvas.pack(side=TOP, fill=BOTH, expand=True)
    playlist_scroll.pack(side=BOTTOM, fill=X)

    def update_playlist_scroll(_event=None):
        playlist_canvas.configure(scrollregion=playlist_canvas.bbox("all"))

    def resize_playlist_height(event):
        playlist_canvas.itemconfigure(playlist_window, height=event.height)

    playlist_list.bind("<Configure>", update_playlist_scroll)
    playlist_canvas.bind("<Configure>", resize_playlist_height)
    playlist_canvas.bind("<Button-4>", lambda _event: playlist_canvas.xview_scroll(-1, "units"))
    playlist_canvas.bind("<Button-5>", lambda _event: playlist_canvas.xview_scroll(1, "units"))

    mini_player = Frame(home_frame, bg="#181818", height=72, cursor="hand2")
    mini_player.pack_propagate(False)
    mini_cover_frame = Frame(mini_player, width=56, height=56, bg="black")
    mini_cover_frame.pack(side=LEFT, padx=8, pady=8)
    mini_cover_frame.pack_propagate(False)
    mini_cover = Label(mini_cover_frame, bg="black", borderwidth=0)
    mini_cover.pack(fill=BOTH, expand=True)
    mini_text = Frame(mini_player, bg="#181818")
    mini_text.pack(side=LEFT, fill=BOTH, expand=True, pady=10)
    mini_track = Label(
        mini_text,
        fg="white",
        bg="#181818",
        anchor="w",
        font=("DejaVu Sans", 12, "bold"),
    )
    mini_artist = Label(
        mini_text,
        fg="#aaaaaa",
        bg="#181818",
        anchor="w",
        font=("DejaVu Sans", 10),
    )
    mini_track.pack(fill=X)
    mini_artist.pack(fill=X)
    mini_play = Button(
        mini_player,
        text="||",
        command=on_toggle_play,
        width=3,
        **button_style,
    )
    mini_play.pack(side=RIGHT, padx=8, pady=10)

    for widget in (mini_player, mini_cover_frame, mini_cover, mini_text, mini_track, mini_artist):
        widget.bind("<Button-1>", lambda _event: go_player())

    # ----- PLAYER -----
    player_header = Frame(player_frame, bg="black")
    Button(player_header, text="Home", command=go_home, **button_style).pack(side=LEFT)
    Label(
        player_header,
        text="Now playing",
        fg="white",
        bg="black",
        font=("DejaVu Sans", 18, "bold"),
    ).pack(side=LEFT, padx=14)
    player_header.pack(fill=X, padx=10, pady=(10, 0))

    cover_frame = Frame(player_frame, width=300, height=300, bg="black")
    cover_frame.pack_propagate(False)
    cover_label = Label(cover_frame, bg="black", borderwidth=0, highlightthickness=0)
    track_label = Label(player_frame, fg="white", bg="black", font=("Arial", 20))
    artist_label = Label(player_frame, fg="gray", bg="black", font=("Arial", 14))
    progess_min_sec_label = Label(player_frame, fg="gray", bg="black", font=("Arial", 10))
    progress = ttk.Progressbar(player_frame, orient="horizontal", length=300, mode="determinate")

    controls = Frame(player_frame, bg="black")
    prev_button = Button(controls, text="<<", command=on_prev, width=4, **button_style)
    play_button = Button(controls, text="||", command=on_toggle_play, width=4, **button_style)
    next_button = Button(controls, text=">>", command=on_next, width=4, **button_style)

    cover_frame.pack(pady=10)
    cover_label.pack(fill=BOTH, expand=True)
    track_label.pack(pady=10)
    artist_label.pack(pady=5)
    progess_min_sec_label.pack(pady=5)
    progress.pack(pady=20)
    controls.pack(pady=10)
    prev_button.pack(side=LEFT, padx=5)
    play_button.pack(side=LEFT, padx=5)
    next_button.pack(side=LEFT, padx=5)

    player_cover_key = None
    mini_cover_key = None
    preloaded_next_track_id = None
    visible_screen = None
    recent_signature = None
    playlist_signature = None
    seeking = False
    seek_preview_ms = 0

    def update_seek_preview(event):
        nonlocal seek_preview_ms
        duration = get_state()["song"].get("duration_ms", 1)
        seek_preview_ms = _seek_position_ms(event.x, progress.winfo_width(), duration)
        progress["value"] = (seek_preview_ms / duration) * 100 if duration else 0

    def start_seek(event):
        nonlocal seeking
        seeking = True
        update_seek_preview(event)

    def finish_seek(event):
        nonlocal seeking
        update_seek_preview(event)
        seeking = False
        on_seek(seek_preview_ms)

    progress.bind("<Button-1>", start_seek)
    progress.bind("<B1-Motion>", update_seek_preview)
    progress.bind("<ButtonRelease-1>", finish_seek)

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

    def rebuild_home_lists(state):
        nonlocal recent_signature, playlist_signature

        tracks = state.get("recent_tracks", [])
        new_recent_signature = (
            state.get("home_loading"),
            state.get("home_error"),
            tuple(
            (track.get("uri"), track.get("name"), track.get("artist")) for track in tracks
            ),
        )
        if new_recent_signature != recent_signature:
            recent_signature = new_recent_signature
            for child in recent_frame.winfo_children():
                child.destroy()

            if not tracks:
                message = state.get("home_error") or (
                    "Loading..." if state.get("home_loading") else "No recently played tracks"
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

        playlists = state.get("playlists", [])
        new_playlist_signature = (
            state.get("home_loading"),
            state.get("home_error"),
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
        if new_playlist_signature != playlist_signature:
            playlist_signature = new_playlist_signature
            for child in playlist_list.winfo_children():
                child.destroy()

            if not playlists:
                message = state.get("home_error") or (
                    "Loading..." if state.get("home_loading") else "No saved playlists"
                )
                Label(playlist_list, text=message, fg="#aaaaaa", bg="#111111", anchor="w").pack(fill=X, padx=8, pady=8)
            else:
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
                            widget.bind(
                                "<Button-1>",
                                lambda _event, uri=expected_uri, name=playlist.get("name", ""): (
                                    print_playlist_tracks(uri, name)
                                ),
                            )

                    def show_playlist_cover(photo, label=cover, uri=expected_uri):
                        current_uris = {item.get("uri") for item in get_state().get("playlists", [])}
                        if uri not in current_uris or not label.winfo_exists():
                            return
                        label.config(image=photo if photo is not None else "")
                        label.image = photo

                    get_photo_async(root, image_url, (120, 120), show_playlist_cover)

    def set_cover(label, cover_key, url, size, current_cover_key):
        label.config(image="")
        label.image = None

        def show_cover(photo):
            if current_cover_key() != cover_key:
                return
            label.config(image=photo if photo is not None else "")
            label.image = photo

        get_photo_async(root, url, size, show_cover)

    def restore_cover_images(_event=None):
        for label in (cover_label, mini_cover):
            photo = getattr(label, "image", None)
            if photo is not None:
                label.config(image=photo)

    root.bind("<Map>", restore_cover_images, add="+")
    root.bind("<Configure>", restore_cover_images, add="+")

    def render():
        nonlocal player_cover_key, mini_cover_key
        nonlocal preloaded_next_track_id, visible_screen

        state = get_state()
        song = state["song"]
        screen = state.get("screen", "home")
        has_active_track = bool(song.get("track_id"))

        if not has_active_track and screen == "player":
            state["screen"] = "home"
            screen = "home"

        if has_active_track:
            if not mini_player.winfo_manager():
                mini_player.pack(fill=X, side=BOTTOM)
        elif mini_player.winfo_manager():
            mini_player.pack_forget()

        if screen != visible_screen:
            visible_screen = screen
            home_frame.pack_forget()
            player_frame.pack_forget()
            (player_frame if screen == "player" else home_frame).pack(fill=BOTH, expand=True)

        rebuild_home_lists(state)

        next_song = state.get("next_song")
        next_track_id = _get_track_id(next_song) if next_song else None
        if next_track_id != preloaded_next_track_id:
            preloaded_next_track_id = next_track_id
            if next_song:
                get_photo_async(root, next_song.get("image_url"), (300, 300), lambda _photo: None)
                get_photo_async(root, next_song.get("image_url"), (56, 56), lambda _photo: None)

        track_id = _get_track_id(song)
        cover_key = (track_id, song.get("image_url"))
        if cover_key != player_cover_key:
            player_cover_key = cover_key
            set_cover(
                cover_label,
                cover_key,
                song.get("image_url"),
                (300, 300),
                lambda: (
                    _get_track_id(get_state()["song"]),
                    get_state()["song"].get("image_url"),
                ),
            )

        if cover_key != mini_cover_key:
            mini_cover_key = cover_key
            set_cover(
                mini_cover,
                cover_key,
                song.get("image_url"),
                (56, 56),
                lambda: (
                    _get_track_id(get_state()["song"]),
                    get_state()["song"].get("image_url"),
                ),
            )

        track = song.get("track", "")
        artist = song.get("artist", "")
        track_label.config(text=track)
        artist_label.config(text=artist)
        progess_min_sec_label.config(text=f"{_get_progress_min_sec(song, time.time())} / {(_get_duration_min_sec(song))}")
        mini_track.config(text=track or "Nothing playing")
        mini_artist.config(text=artist)

        is_playing = song.get("is_playing", False)
        play_text = "||" if is_playing else ">"
        play_button.config(text=play_text, state=NORMAL)
        mini_play.config(text=play_text, state=NORMAL)

        now = time.time()
        duration = song.get("duration_ms", 1)
        progress_ms = _get_progress_ms(song, now)
        if not seeking:
            progress["value"] = (progress_ms / duration) * 100 if duration else 0

        root.after(100, render)

    Thread(target=load_home, daemon=True).start()
    root.after(100, render)
