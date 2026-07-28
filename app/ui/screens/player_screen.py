import math
import time
from threading import Thread
from tkinter import BOTH, LEFT, NORMAL, RIGHT, X
from tkinter import Button, Canvas, Frame, Label
from tkinter import ttk

from app.controller.controller_navigation import go_home, go_playlist
from app.controller.controller_player import on_next, on_prev, on_seek, on_toggle_play
from app.controller.controller_volume import on_volume_down, on_volume_up
from app.core.state import get_state
from app.services import audio_output_service
from app.services.image_cache import get_photo_async


WHEEL_SIZE = 350
WHEEL_MARGIN = 14
WHEEL_RADIUS = (WHEEL_SIZE - WHEEL_MARGIN * 2) / 2
WHEEL_CENTER_RADIUS = 72
WHEEL_COLOR = "#242424"
WHEEL_ACTIVE_COLOR = "#1DB954"
WHEEL_CENTER_COLOR = "#1DB954"
WHEEL_CENTER_ACTIVE_COLOR = "#169C46"
WHEEL_OUTLINE_COLOR = "#3A3A3A"
WHEEL_TEXT_COLOR = "#FFFFFF"

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


def _format_time(milliseconds):
    milliseconds = max(0, int(milliseconds or 0))
    return f"{milliseconds // 60000}:{(milliseconds % 60000) // 1000:02d}"


def _seek_position_ms(x, width, duration_ms):
    if width <= 0 or duration_ms <= 0:
        return 0
    return int(min(max(x / width, 0), 1) * duration_ms)


def render_player(root, state, button_style):
    frame = Frame(root, bg="black")

    header = Frame(frame, bg="black", height=52)
    header.pack(fill=X, padx=10, pady=(8, 0))
    Button(
        header,
        text="Home",
        command=go_home,
        takefocus=False,
        **button_style,
    ).pack(side=LEFT)
    Label(
        header,
        text="Now Playing",
        fg="white",
        bg="black",
        font=("DejaVu Sans", 18, "bold"),
    ).pack(side=LEFT, padx=14)

    output_panel = Frame(header, bg="#111111")
    output_button = Button(
        output_panel,
        text="Output",
        fg="white",
        bg="#222222",
        activeforeground="white",
        activebackground="#333333",
        font=("DejaVu Sans", 9, "bold"),
        relief="flat",
        borderwidth=0,
        highlightthickness=0,
        takefocus=False,
        padx=8,
        pady=5,
    )
    output_button.pack(fill=X)
    output_panel.pack(side=RIGHT, anchor="ne")
    output_results = Frame(frame, bg="#111111")

    now_playing = Frame(frame, bg="#101010", height=210)
    now_playing.pack(fill=X, padx=12, pady=(10, 8))
    now_playing.pack_propagate(False)

    cover_frame = Frame(now_playing, width=180, height=180, bg="black")
    cover_frame.pack(side=LEFT, padx=(10, 12), pady=15)
    cover_frame.pack_propagate(False)
    cover_label = Label(
        cover_frame,
        bg="black",
        borderwidth=0,
        highlightthickness=0,
    )
    cover_label.pack(fill=BOTH, expand=True)

    metadata = Frame(now_playing, bg="#101010")
    metadata.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 10), pady=18)
    Label(
        metadata,
        text="NOW PLAYING",
        fg="#1DB954",
        bg="#101010",
        anchor="w",
        font=("DejaVu Sans", 10, "bold"),
    ).pack(fill=X, pady=(4, 12))
    track_label = Label(
        metadata,
        fg="white",
        bg="#101010",
        anchor="w",
        justify=LEFT,
        wraplength=235,
        font=("DejaVu Sans", 18, "bold"),
    )
    track_label.pack(fill=X)
    artist_label = Label(
        metadata,
        fg="#A7A7A7",
        bg="#101010",
        anchor="w",
        justify=LEFT,
        wraplength=235,
        font=("DejaVu Sans", 13),
    )
    artist_label.pack(fill=X, pady=(10, 0))

    progress_area = Frame(frame, bg="black")
    progress_area.pack(fill=X, padx=22, pady=(0, 4))
    progress_style = ttk.Style()
    progress_style.configure(
        "Player.Horizontal.TProgressbar",
        troughcolor="#333333",
        background="#1DB954",
        bordercolor="#333333",
        lightcolor="#1DB954",
        darkcolor="#1DB954",
        thickness=14,
    )
    progress = ttk.Progressbar(
        progress_area,
        orient="horizontal",
        mode="determinate",
        style="Player.Horizontal.TProgressbar",
    )
    progress.pack(fill=X)

    time_row = Frame(progress_area, bg="black")
    time_row.pack(fill=X, pady=(4, 0))
    elapsed_label = Label(
        time_row,
        fg="#B3B3B3",
        bg="black",
        font=("DejaVu Sans", 10, "bold"),
    )
    elapsed_label.pack(side=LEFT)
    remaining_label = Label(
        time_row,
        fg="#B3B3B3",
        bg="black",
        font=("DejaVu Sans", 10, "bold"),
    )
    remaining_label.pack(side=RIGHT)

    wheel_holder = Frame(frame, bg="black")
    wheel_holder.pack(fill=BOTH, expand=True)
    wheel = Canvas(
        wheel_holder,
        width=WHEEL_SIZE,
        height=WHEEL_SIZE,
        bg="black",
        highlightthickness=0,
        borderwidth=0,
    )
    wheel.pack()

    bounds = (
        WHEEL_MARGIN,
        WHEEL_MARGIN,
        WHEEL_SIZE - WHEEL_MARGIN,
        WHEEL_SIZE - WHEEL_MARGIN,
    )
    segment_items = {
        "right": wheel.create_arc(
            *bounds,
            start=-45,
            extent=90,
            fill=WHEEL_COLOR,
            outline=WHEEL_OUTLINE_COLOR,
            width=2,
        ),
        "up": wheel.create_arc(
            *bounds,
            start=45,
            extent=90,
            fill=WHEEL_COLOR,
            outline=WHEEL_OUTLINE_COLOR,
            width=2,
        ),
        "left": wheel.create_arc(
            *bounds,
            start=135,
            extent=90,
            fill=WHEEL_COLOR,
            outline=WHEEL_OUTLINE_COLOR,
            width=2,
        ),
        "down": wheel.create_arc(
            *bounds,
            start=225,
            extent=90,
            fill=WHEEL_COLOR,
            outline=WHEEL_OUTLINE_COLOR,
            width=2,
        ),
    }

    wheel.create_oval(
        *bounds,
        outline="#1DB954",
        width=3,
    )

    center = WHEEL_SIZE / 2
    center_item = wheel.create_oval(
        center - WHEEL_CENTER_RADIUS,
        center - WHEEL_CENTER_RADIUS,
        center + WHEEL_CENTER_RADIUS,
        center + WHEEL_CENTER_RADIUS,
        fill=WHEEL_CENTER_COLOR,
        outline="#1ED760",
        width=3,
    )
    wheel.create_text(
        center,
        58,
        text="+",
        fill=WHEEL_TEXT_COLOR,
        font=("DejaVu Sans", 25, "bold"),
    )
    wheel.create_text(
        center,
        WHEEL_SIZE - 58,
        text="-",
        fill=WHEEL_TEXT_COLOR,
        font=("DejaVu Sans", 25, "bold"),
    )
    wheel.create_text(
        60,
        center,
        text="<<",
        fill=WHEEL_TEXT_COLOR,
        font=("DejaVu Sans", 18, "bold"),
    )
    wheel.create_text(
        WHEEL_SIZE - 60,
        center,
        text=">>",
        fill=WHEEL_TEXT_COLOR,
        font=("DejaVu Sans", 18, "bold"),
    )
    play_text = wheel.create_text(
        center,
        center,
        text="||",
        fill=WHEEL_TEXT_COLOR,
        font=("DejaVu Sans", 24, "bold"),
    )

    def open_current_album(_event=None):
        state = get_state()
        song = state["song"]
        album_id = song.get("album_id")

        if not album_id:
            return

        state["current_collection_type"] = "album"
        state["current_collection_uri"] = f"spotify:album:{album_id}"
        state["current_collection_name"] = song.get("album_name") or "Album"
        state["current_collection_image_url"] = song.get("image_url")
        state["current_collection_tracks"] = None
        state["collection_error"] = None

        go_playlist()

    for widget in (cover_frame, cover_label):
        widget.config(cursor="hand2")
        widget.bind("<Button-1>", open_current_album)

    def flash_wheel_control(control):
        if control == "center":
            wheel.itemconfig(center_item, fill=WHEEL_CENTER_ACTIVE_COLOR)
            root.after(
                100,
                lambda: wheel.itemconfig(center_item, fill=WHEEL_CENTER_COLOR),
            )
            return

        item = segment_items[control]
        wheel.itemconfig(item, fill=WHEEL_ACTIVE_COLOR)
        root.after(100, lambda: wheel.itemconfig(item, fill=WHEEL_COLOR))

    def handle_wheel_press(event):
        dx = event.x - center
        dy = event.y - center
        distance = math.hypot(dx, dy)

        if distance <= WHEEL_CENTER_RADIUS:
            control = "center"
            action = on_toggle_play
        elif distance > WHEEL_RADIUS:
            return
        elif abs(dx) > abs(dy):
            control = "right" if dx > 0 else "left"
            action = on_next if dx > 0 else on_prev
        else:
            control = "down" if dy > 0 else "up"
            action = on_volume_down if dy > 0 else on_volume_up

        flash_wheel_control(control)
        action()
        frame.focus_set()

    wheel.bind("<Button-1>", handle_wheel_press)

    def clear_output_results():
        for child in output_results.winfo_children():
            child.destroy()

    def open_output_results():
        output_results.place(relx=1, x=-10, y=55, anchor="ne")
        output_results.lift()

    def close_output_results():
        clear_output_results()
        output_results.place_forget()
        output_button.config(state=NORMAL)

    def show_output_devices(devices):
        clear_output_results()
        open_output_results()
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
            active_marker = "* " if device["active"] else ""
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
        open_output_results()
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
        open_output_results()
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
        seek_preview_ms = _seek_position_ms(
            event.x,
            progress.winfo_width(),
            duration,
        )
        progress["value"] = (seek_preview_ms / duration) * 100 if duration else 0
        elapsed_label.config(text=_format_time(seek_preview_ms))
        remaining_label.config(text=f"-{_format_time(duration - seek_preview_ms)}")

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

        get_photo_async(root, url, (180, 180), show_cover)

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
                get_photo_async(
                    root,
                    next_song.get("image_url"),
                    (180, 180),
                    lambda _photo: None,
                )
                get_photo_async(
                    root,
                    next_song.get("image_url"),
                    (56, 56),
                    lambda _photo: None,
                )

        cover_key = (_get_track_id(song), song.get("image_url"))
        if cover_key != player_cover_key:
            player_cover_key = cover_key
            set_cover(cover_key, song.get("image_url"))

        track_label.config(text=song.get("track", ""))
        artist_label.config(text=song.get("artist", ""))
        wheel.itemconfig(
            play_text,
            text="||" if song.get("is_playing", False) else ">",
        )

        now = time.time()
        duration = max(1, song.get("duration_ms", 1) or 1)
        progress_ms = _get_progress_ms(song, now)
        if not seeking:
            progress["value"] = (progress_ms / duration) * 100
            elapsed_label.config(text=_format_time(progress_ms))
            remaining_label.config(text=f"-{_format_time(duration - progress_ms)}")

    update(state)
    return {"frame": frame, "update": update}
