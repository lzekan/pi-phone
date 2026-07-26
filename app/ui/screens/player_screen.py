import time
from threading import Thread
from tkinter import BOTH, LEFT, NORMAL, X
from tkinter import Button, Frame, Label
from tkinter import ttk

from app.controller.controller_navigation import go_home
from app.controller.controller_player import on_next, on_prev, on_seek, on_toggle_play
from app.core.state import get_state
from app.services import audio_output_service
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
        return song.get("track"), song.get("artist"), song.get("duration_ms")
    return None


def _get_progress_ms(song, now):
    global last_progress, last_update_time
    global last_source_progress, last_track_id, last_is_playing

    track_id = _get_track_id(song)
    incoming = max(0, song.get("progress_ms", 0) or 0)
    duration = max(1, song.get("duration_ms", 1) or 1)
    is_playing = bool(song.get("is_playing", False))

    if track_id != last_track_id or incoming != last_source_progress or is_playing != last_is_playing:
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
    return f"{int(progress_ms / 60000)}:{int((progress_ms % 60000) / 1000):02d}"


def _get_duration_min_sec(song):
    duration_ms = song.get("duration_ms", 0)
    return f"{int(duration_ms / 60000)}:{int((duration_ms % 60000) / 1000):02d}"


def _seek_position_ms(x, width, duration_ms):
    if width <= 0 or duration_ms <= 0:
        return 0
    return int(min(max(x / width, 0), 1) * duration_ms)


def render_player(root, state, button_style):
    frame = Frame(root, bg="black")
    header = Frame(frame, bg="black")
    Button(header, text="Home", command=go_home, **button_style).pack(side=LEFT)
    Label(
        header,
        text="Now playing",
        fg="white",
        bg="black",
        font=("DejaVu Sans", 18, "bold"),
    ).pack(side=LEFT, padx=14)
    header.pack(fill=X, padx=10, pady=(10, 0))

    cover_frame = Frame(frame, width=300, height=300, bg="black")
    cover_frame.pack_propagate(False)
    cover_label = Label(cover_frame, bg="black", borderwidth=0, highlightthickness=0)
    track_label = Label(frame, fg="white", bg="black", font=("Arial", 20))
    artist_label = Label(frame, fg="gray", bg="black", font=("Arial", 14))
    progress_time = Label(frame, fg="gray", bg="black", font=("Arial", 10))
    progress = ttk.Progressbar(frame, orient="horizontal", length=300, mode="determinate")
    controls = Frame(frame, bg="black")
    prev_button = Button(controls, text="<<", width=4, **button_style)
    play_button = Button(controls, text="||", width=4, **button_style)
    next_button = Button(controls, text=">>", width=4, **button_style)

    control_bg = button_style.get("bg", "#222222")
    control_active_bg = button_style.get("activebackground", "#444444")

    def run_control(button, action):
        button.config(bg=control_active_bg, activebackground=control_active_bg)
        try:
            action()
        finally:
            def release_control():
                button.config(bg=control_bg, activebackground=control_bg)
                frame.focus_set()

            button.after(80, release_control)

    for button, action in (
        (prev_button, on_prev),
        (play_button, on_toggle_play),
        (next_button, on_next),
    ):
        button.config(
            command=lambda current_button=button, current_action=action: run_control(
                current_button,
                current_action,
            ),
            takefocus=False,
            activebackground=control_bg,
        )

    cover_frame.pack(pady=10)
    cover_label.pack(fill=BOTH, expand=True)
    track_label.pack(pady=10)
    artist_label.pack(pady=5)
    progress_time.pack(pady=5)
    progress.pack(pady=20)
    controls.pack(pady=10)
    prev_button.pack(side=LEFT, padx=5)
    play_button.pack(side=LEFT, padx=5)
    next_button.pack(side=LEFT, padx=5)

    output_panel = Frame(frame, bg="#111111")
    output_results = Frame(output_panel, bg="#111111")
    output_results.pack(fill=X, pady=(0, 4))
    output_button = Button(
        output_panel,
        text="Output",
        fg="white",
        bg="#222222",
        activeforeground="white",
        activebackground="#222222",
        font=("DejaVu Sans", 9, "bold"),
        relief="flat",
        borderwidth=0,
        highlightthickness=0,
        takefocus=False,
        padx=8,
        pady=5,
    )
    output_button.pack(anchor="w")
    output_panel.place(x=10, rely=1, y=-10, anchor="sw")

    def clear_output_results():
        for child in output_results.winfo_children():
            child.destroy()

    def close_output_results():
        clear_output_results()
        output_button.config(state=NORMAL)

    def show_output_devices(devices):
        clear_output_results()
        output_button.config(state=NORMAL)

        if not devices:
            Label(
                output_results,
                text="No audio outputs",
                fg="#AAAAAA",
                bg="#111111",
                anchor="w",
                font=("DejaVu Sans", 8),
            ).pack(fill=X)
            return

        for device in devices:
            device_type = "Bluetooth" if device["type"] == "bluetooth" else "3.5 mm"
            active_marker = "✓ " if device["active"] else ""
            Button(
                output_results,
                text=f'{active_marker}{device["name"]}\n{device_type}',
                fg="white",
                bg="#1DB954" if device["active"] else "#222222",
                activeforeground="white",
                activebackground="#169C46" if device["active"] else "#333333",
                anchor="w",
                justify=LEFT,
                font=("DejaVu Sans", 9, "bold"),
                relief="flat",
                borderwidth=0,
                highlightthickness=0,
                takefocus=False,
                padx=8,
                pady=5,
                command=lambda selected=device: select_output_device(selected),
            ).pack(fill=X)

    def show_output_error(message):
        clear_output_results()
        output_button.config(state=NORMAL)
        Label(
            output_results,
            text=f"Output error:\n{message}",
            fg="#FF6B6B",
            bg="#111111",
            anchor="w",
            justify=LEFT,
            font=("DejaVu Sans", 8),
        ).pack(fill=X)

    def show_output_loading(message):
        clear_output_results()
        output_button.config(state="disabled")
        Label(
            output_results,
            text=message,
            fg="#AAAAAA",
            bg="#111111",
            anchor="w",
            font=("DejaVu Sans", 8),
        ).pack(fill=X)

    def load_output_devices():
        show_output_loading("Loading...")

        def worker():
            try:
                devices = audio_output_service.get_output_devices()
                root.after(0, lambda: show_output_devices(devices))
            except Exception as error:
                message = str(error)
                root.after(0, lambda: show_output_error(message))

        Thread(target=worker, daemon=True).start()

    def select_output_device(device):
        if device["active"]:
            return

        show_output_loading(f'Switching to\n{device["name"]}...')

        def worker():
            try:
                audio_output_service.set_output_device(device["id"])
                root.after(0, close_output_results)
            except Exception as error:
                message = str(error)
                root.after(0, lambda: show_output_error(message))

        Thread(target=worker, daemon=True).start()

    def toggle_output_devices():
        if output_results.winfo_children():
            close_output_results()
        else:
            load_output_devices()

    output_button.config(command=toggle_output_devices)

    player_cover_key = None
    preloaded_next_track_id = None
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

    def set_cover(cover_key, url):
        cover_label.config(image="")
        cover_label.image = None

        def show_cover(photo):
            current_song = get_state()["song"]
            current_key = (_get_track_id(current_song), current_song.get("image_url"))
            if current_key != cover_key:
                return
            cover_label.config(image=photo if photo is not None else "")
            cover_label.image = photo

        get_photo_async(root, url, (300, 300), show_cover)

    def restore_cover(_event=None):
        photo = getattr(cover_label, "image", None)
        if photo is not None:
            cover_label.config(image=photo)

    root.bind("<Map>", restore_cover, add="+")
    root.bind("<Configure>", restore_cover, add="+")

    def update(current_state):
        nonlocal player_cover_key, preloaded_next_track_id

        song = current_state["song"]
        next_song = current_state.get("next_song")
        next_track_id = _get_track_id(next_song) if next_song else None
        if next_track_id != preloaded_next_track_id:
            preloaded_next_track_id = next_track_id
            if next_song:
                get_photo_async(root, next_song.get("image_url"), (300, 300), lambda _photo: None)
                get_photo_async(root, next_song.get("image_url"), (56, 56), lambda _photo: None)

        cover_key = (_get_track_id(song), song.get("image_url"))
        if cover_key != player_cover_key:
            player_cover_key = cover_key
            set_cover(cover_key, song.get("image_url"))

        track_label.config(text=song.get("track", ""))
        artist_label.config(text=song.get("artist", ""))
        progress_time.config(
            text=f"{_get_progress_min_sec(song, time.time())} / {_get_duration_min_sec(song)}"
        )
        play_button.config(text="||" if song.get("is_playing", False) else ">", state=NORMAL)

        now = time.time()
        duration = song.get("duration_ms", 1)
        progress_ms = _get_progress_ms(song, now)
        if not seeking:
            progress["value"] = (progress_ms / duration) * 100 if duration else 0

    update(state)
    return {"frame": frame, "update": update}
