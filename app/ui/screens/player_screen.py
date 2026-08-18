import math
import time
from queue import Empty, Queue
from threading import Thread
from tkinter import BOTH, LEFT, NORMAL, RIGHT, X
from tkinter import Button, Canvas, Frame, Label
from tkinter import font as tkfont
from tkinter import ttk

from app.controller.controller_player import (
    on_next,
    on_prev,
    on_seek,
    on_toggle_play,
)

from app.controller.controller_queue import remove_queue_item
from app.controller.controller_navigation import go_back, go_playlist
from app.controller.controller_volume import on_volume_down, on_volume_up
from app.core.state import get_state
from app.services import audio_output_service
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


WHEEL_SIZE = 344
WHEEL_MARGIN = 12
WHEEL_RADIUS = (WHEEL_SIZE - WHEEL_MARGIN * 2) / 2
WHEEL_CENTER_RADIUS = 72
WHEEL_COLOR = SURFACE_ALT
WHEEL_ACTIVE_COLOR = SURFACE_ACTIVE
WHEEL_CENTER_COLOR = ACCENT
WHEEL_CENTER_ACTIVE_COLOR = ACCENT_ACTIVE
WHEEL_OUTLINE_COLOR = DIVIDER
WHEEL_TEXT_COLOR = TEXT

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


def _ellipsize(text, text_font, max_width):
    text = str(text or "")
    if not text or text_font.measure(text) <= max_width:
        return text

    ellipsis = "..."
    available_width = max_width - text_font.measure(ellipsis)
    if available_width <= 0:
        return ellipsis

    low = 0
    high = len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if text_font.measure(text[:middle]) <= available_width:
            low = middle
        else:
            high = middle - 1

    return f"{text[:low].rstrip()}{ellipsis}"


def _seek_position_ms(x, width, duration_ms):
    if width <= 0 or duration_ms <= 0:
        return 0
    return int(min(max(x / width, 0), 1) * duration_ms)


def render_player(root, state, button_style):
    frame = Frame(root, bg=BG)

    volume_popup = Frame(
        frame,
        bg=CARD,
        width=142,
        height=42,
        highlightbackground=DIVIDER,
        highlightthickness=1,
    )
    volume_popup.pack_propagate(False)
    volume_value = Label(
        volume_popup,
        text="VOLUME  0",
        fg=TEXT,
        bg=CARD,
        font=(FONT, 11, "bold"),
        anchor="center",
    )
    volume_value.pack(fill=BOTH, expand=True)
    volume_popup_hide_job = None
    volume_updates = Queue()

    def hide_volume_popup():
        nonlocal volume_popup_hide_job
        volume_popup.place_forget()
        volume_popup_hide_job = None

    def show_volume_popup(volume_percent):
        nonlocal volume_popup_hide_job

        if volume_popup_hide_job is not None:
            root.after_cancel(volume_popup_hide_job)

        volume_value.config(text=f"VOLUME  {volume_percent}")
        volume_popup.place(relx=0.5, rely=1, y=-12, anchor="s")
        volume_popup.lift()
        volume_popup_hide_job = root.after(1400, hide_volume_popup)

    def report_volume(volume_percent):
        volume_updates.put(volume_percent)

    def process_volume_updates():
        latest_volume = None
        try:
            while True:
                latest_volume = volume_updates.get_nowait()
        except Empty:
            pass

        if latest_volume is not None:
            show_volume_popup(latest_volume)

        root.after(50, process_volume_updates)

    root.after(50, process_volume_updates)

    header = Frame(frame, bg=BG, height=52)
    header.pack(fill=X, padx=PAGE_PAD, pady=(10, 0))
    Button(
        header,
        text="‹  Back",
        command=go_back,
        takefocus=False,
        **button_style,
    ).pack(side=LEFT)
    output_button = Button(
        frame,
        text="◉  Output",
        fg=TEXT,
        bg=SURFACE_ALT,
        activeforeground=TEXT,
        activebackground=SURFACE_ACTIVE,
        font=(FONT, 10, "bold"),
        relief="flat",
        borderwidth=0,
        highlightbackground=DIVIDER,
        highlightthickness=1,
        takefocus=False,
        padx=12,
        pady=8,
    )
    output_results = Frame(frame, bg=SURFACE)

    queue_button = Button(
        frame,
        text="☷  Queue",
        fg=TEXT,
        bg=SURFACE_ALT,
        activeforeground=TEXT,
        activebackground=SURFACE_ACTIVE,
        font=(FONT, 10, "bold"),
        relief="flat",
        borderwidth=0,
        highlightbackground=DIVIDER,
        highlightthickness=1,
        takefocus=False,
        padx=12,
        pady=8,
    )
    queue_results = Frame(frame, bg=SURFACE)

    now_playing = Frame(
        frame,
        bg=SURFACE,
        height=214,
        highlightbackground=DIVIDER,
        highlightthickness=1,
    )
    now_playing.pack(fill=X, padx=PAGE_PAD, pady=(10, 10))
    now_playing.pack_propagate(False)

    cover_frame = Frame(now_playing, width=174, height=174, bg=SURFACE_ALT)
    cover_frame.pack(side=LEFT, padx=(12, 14), pady=19)
    cover_frame.pack_propagate(False)
    cover_label = Label(
        cover_frame,
        bg=SURFACE_ALT,
        borderwidth=0,
        highlightthickness=0,
    )
    cover_label.pack(fill=BOTH, expand=True)

    metadata = Frame(now_playing, bg=SURFACE)
    metadata.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 10), pady=17)
    track_text_font = tkfont.Font(family=FONT, size=18, weight="bold")
    artist_text_font = tkfont.Font(family=FONT, size=12)
    album_text_font = tkfont.Font(family=FONT, size=9)
    source_label = Label(
        metadata,
        text="NOW PLAYING",
        fg=ACCENT,
        bg=SURFACE,
        anchor="w",
        font=(FONT, 9, "bold"),
    )
    source_label.pack(fill=X, pady=(4, 10))
    track_label = Label(
        metadata,
        fg=TEXT,
        bg=SURFACE,
        anchor="w",
        justify=LEFT,
        height=1,
        font=track_text_font,
    )
    track_label.pack(fill=X)
    artist_label = Label(
        metadata,
        fg=TEXT_MUTED,
        bg=SURFACE,
        anchor="w",
        justify=LEFT,
        height=1,
        font=artist_text_font,
    )
    artist_label.pack(fill=X, pady=(8, 0))
    album_label = Label(
        metadata,
        fg=TEXT_DIM,
        bg=SURFACE,
        anchor="w",
        justify=LEFT,
        height=1,
        font=album_text_font,
    )
    album_label.pack(fill=X, pady=(5, 0))

    metadata_text = {
        "track": "",
        "artist": "",
        "album": "",
    }

    def refresh_metadata_labels(_event=None):
        available_width = metadata.winfo_width()
        if available_width <= 20:
            available_width = 235

        track_label.config(
            text=_ellipsize(
                metadata_text["track"],
                track_text_font,
                available_width,
            )
        )
        artist_label.config(
            text=_ellipsize(
                metadata_text["artist"],
                artist_text_font,
                available_width,
            )
        )
        album_label.config(
            text=_ellipsize(
                metadata_text["album"],
                album_text_font,
                available_width,
            )
        )

    metadata.bind("<Configure>", refresh_metadata_labels)

    progress_area = Frame(frame, bg=BG)
    progress_area.pack(fill=X, padx=22, pady=(0, 4))
    progress_style = ttk.Style()
    progress_style.configure(
        "Player.Horizontal.TProgressbar",
        troughcolor=DIVIDER,
        background=ACCENT,
        bordercolor=DIVIDER,
        lightcolor=ACCENT,
        darkcolor=ACCENT,
        thickness=7,
    )
    progress = ttk.Progressbar(
        progress_area,
        orient="horizontal",
        mode="determinate",
        style="Player.Horizontal.TProgressbar",
    )
    progress.pack(fill=X)

    time_row = Frame(progress_area, bg=BG)
    time_row.pack(fill=X, pady=(4, 0))
    elapsed_label = Label(
        time_row,
        fg=TEXT_MUTED,
        bg=BG,
        font=(FONT, 9, "bold"),
    )
    elapsed_label.pack(side=LEFT)
    remaining_label = Label(
        time_row,
        fg=TEXT_MUTED,
        bg=BG,
        font=(FONT, 9, "bold"),
    )
    remaining_label.pack(side=RIGHT)

    wheel_holder = Frame(frame, bg=BG)
    wheel_holder.pack(fill=BOTH, expand=True)
    wheel = Canvas(
        wheel_holder,
        width=WHEEL_SIZE,
        height=WHEEL_SIZE,
        bg=BG,
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
        outline=DIVIDER,
        width=2,
    )

    center = WHEEL_SIZE / 2
    center_item = wheel.create_oval(
        center - WHEEL_CENTER_RADIUS,
        center - WHEEL_CENTER_RADIUS,
        center + WHEEL_CENTER_RADIUS,
        center + WHEEL_CENTER_RADIUS,
        fill=WHEEL_CENTER_COLOR,
        outline=ACCENT_ACTIVE,
        width=2,
    )
    wheel.create_text(
        center,
        58,
        text="＋",
        fill=WHEEL_TEXT_COLOR,
        font=(FONT, 23, "bold"),
    )
    wheel.create_text(
        center,
        WHEEL_SIZE - 58,
        text="−",
        fill=WHEEL_TEXT_COLOR,
        font=(FONT, 23, "bold"),
    )
    wheel.create_text(
        60,
        center,
        text="‹‹",
        fill=WHEEL_TEXT_COLOR,
        font=(FONT, 20, "bold"),
    )
    wheel.create_text(
        WHEEL_SIZE - 60,
        center,
        text="››",
        fill=WHEEL_TEXT_COLOR,
        font=(FONT, 20, "bold"),
    )
    play_text = wheel.create_text(
        center,
        center,
        text="Ⅱ",
        fill=WHEEL_TEXT_COLOR,
        font=(FONT, 22, "bold"),
    )

    def open_current_album(_event=None):
        state = get_state()
        song = state["song"]
        if song.get("source") != "spotify":
            return
        album_id = song.get("album_id")

        if not album_id:
            return

        state["current_collection_type"] = "album"
        state["current_collection_uri"] = f"spotify:album:{album_id}"
        state["current_collection_name"] = song.get("album_name") or "Album"
        state["current_collection_image_url"] = song.get("image_url")

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
        if control in ("up", "down"):
            action(report_volume)
        else:
            action()
        frame.focus_set()

    wheel.bind("<Button-1>", handle_wheel_press)

    def clear_output_results():
        for child in output_results.winfo_children():
            child.destroy()

    def open_output_results():
        output_results.place(relx=0, rely=1, x=12, y=-58, anchor="sw")
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
                fg=TEXT_MUTED,
                bg=SURFACE,
                anchor="w",
                font=(FONT, 8),
            ).pack(fill=X)
            return

        for device in devices:
            device_type = "Bluetooth" if device["type"] == "bluetooth" else "3.5 mm"
            active_marker = "* " if device["active"] else ""
            Button(
                output_results,
                text=f'{active_marker}{device["name"]}\n{device_type}',
                fg=TEXT,
                bg=ACCENT if device["active"] else SURFACE_ALT,
                activeforeground=TEXT,
                activebackground=ACCENT_ACTIVE if device["active"] else SURFACE_ACTIVE,
                anchor="w",
                justify=LEFT,
                font=(FONT, 9, "bold"),
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
            fg=DANGER,
            bg=SURFACE,
            anchor="w",
            justify=LEFT,
            font=(FONT, 8),
        ).pack(fill=X)

    def show_output_loading(message):
        clear_output_results()
        open_output_results()
        output_button.config(state="disabled")
        Label(
            output_results,
            text=message,
            fg=TEXT_MUTED,
            bg=SURFACE,
            anchor="w",
            font=(FONT, 8),
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
            close_queue_results()
            load_output_devices()

    output_button.config(command=toggle_output_devices)

    def clear_queue_results():
        for child in queue_results.winfo_children():
            child.destroy()

    def close_queue_results():
        clear_queue_results()
        queue_results.place_forget()

    def remove_manual_item_and_refresh(queue_id):
        if remove_queue_item(queue_id):
            root.after_idle(open_queue_results)

    def open_queue_results():
        clear_queue_results()
        close_output_results()
        queue_results.place(
            relx=1,
            rely=1,
            x=-12,
            y=-58,
            width=456,
            height=430,
            anchor="se",
        )

        queue = get_state().get("spotify_manual_queue", [])
        Label(
            queue_results,
            text="UP NEXT",
            fg=ACCENT,
            bg=SURFACE,
            anchor="w",
            font=(FONT, 8, "bold"),
            padx=10,
            pady=7,
        ).pack(fill=X)

        if not queue:
            Label(
                queue_results,
                text="No tracks in queue",
                fg=TEXT_MUTED,
                bg=SURFACE,
                anchor="w",
                font=(FONT, 9),
                padx=10,
                pady=10,
            ).pack(fill=X)
        else:
            queue_canvas = Canvas(
                queue_results,
                bg=SURFACE,
                highlightthickness=0,
                borderwidth=0,
            )
            queue_canvas.pack(fill=BOTH, expand=True)
            queue_list = Frame(queue_canvas, bg=SURFACE)
            queue_window = queue_canvas.create_window(
                (0, 0),
                window=queue_list,
                anchor="nw",
            )

            queue_list.bind(
                "<Configure>",
                lambda _event: queue_canvas.configure(
                    scrollregion=queue_canvas.bbox("all")
                ),
            )
            queue_canvas.bind(
                "<Configure>",
                lambda event: queue_canvas.itemconfigure(
                    queue_window,
                    width=event.width,
                ),
            )

            def queue_canvas_y(event):
                return int(
                    queue_canvas.canvasy(
                        event.y_root - queue_canvas.winfo_rooty()
                    )
                )

            def start_queue_drag(event):
                queue_canvas.scan_mark(0, queue_canvas_y(event))

            def drag_queue(event):
                queue_canvas.scan_dragto(0, queue_canvas_y(event), gain=1)

            def scroll_queue(event):
                queue_canvas.yview_scroll(
                    -1 if event.delta > 0 else 1,
                    "units",
                )

            def bind_queue_drag(*widgets):
                for widget in widgets:
                    widget.bind("<ButtonPress-1>", start_queue_drag)
                    widget.bind("<B1-Motion>", drag_queue)
                    widget.bind("<MouseWheel>", scroll_queue)
                    widget.bind(
                        "<Button-4>",
                        lambda _event: queue_canvas.yview_scroll(-1, "units"),
                    )
                    widget.bind(
                        "<Button-5>",
                        lambda _event: queue_canvas.yview_scroll(1, "units"),
                    )

            queue_canvas.bind("<ButtonPress-1>", start_queue_drag)
            queue_canvas.bind("<B1-Motion>", drag_queue)
            queue_canvas.bind("<MouseWheel>", scroll_queue)
            queue_canvas.bind(
                "<Button-4>",
                lambda _event: queue_canvas.yview_scroll(-1, "units"),
            )
            queue_canvas.bind(
                "<Button-5>",
                lambda _event: queue_canvas.yview_scroll(1, "units"),
            )

            for queued_track in queue:
                row = Frame(queue_list, bg=SURFACE_ALT, height=64)
                row.pack(fill=X, pady=(0, 1))
                row.pack_propagate(False)

                cover_frame = Frame(row, bg=SURFACE, width=50, height=50)
                cover_frame.pack(side=LEFT, padx=(7, 10), pady=7)
                cover_frame.pack_propagate(False)
                cover = Label(cover_frame, bg=SURFACE, borderwidth=0)
                cover.pack(fill=BOTH, expand=True)

                is_committed = queued_track.get("committed", False)

                remove_button = Button(
                    row,
                    text="•" if is_committed else "×",
                    command=lambda queue_id=queued_track.get("queue_id"): (
                        remove_manual_item_and_refresh(queue_id)
                        if queue_id is not None
                        else None
                    ),
                    state="disabled" if is_committed else NORMAL,
                    disabledforeground=TEXT_DIM,
                    fg=TEXT_MUTED,
                    bg=SURFACE_ALT,
                    activeforeground=TEXT,
                    activebackground=SURFACE_ACTIVE,
                    font=(FONT, 15, "bold"),
                    relief="flat",
                    borderwidth=0,
                    highlightthickness=0,
                    takefocus=False,
                    padx=12,
                    pady=8,
                )
                remove_button.pack(side=RIGHT, padx=(4, 7))

                info = Frame(row, bg=SURFACE_ALT)
                info.pack(side=LEFT, fill=BOTH, expand=True, pady=8)
                name_label = Label(
                    info,
                    text=queued_track.get("track", "Unknown track"),
                    fg=TEXT,
                    bg=SURFACE_ALT,
                    anchor="w",
                    font=(FONT, 10, "bold"),
                )
                name_label.pack(fill=X)
                artist_label = Label(
                    info,
                    text=queued_track.get("artist", ""),
                    fg=TEXT_MUTED,
                    bg=SURFACE_ALT,
                    anchor="w",
                    font=(FONT, 9),
                )
                artist_label.pack(fill=X, pady=(3, 0))

                bind_queue_drag(
                    row,
                    cover_frame,
                    cover,
                    info,
                    name_label,
                    artist_label,
                )

                def show_queue_cover(
                    photo,
                    label=cover,
                    expected_queue_id=queued_track.get("queue_id"),
                ):
                    if not label.winfo_exists():
                        return

                    current_queue_ids = {
                        item.get("queue_id")
                        for item in get_state().get("spotify_manual_queue", [])
                    }

                    if expected_queue_id not in current_queue_ids:
                        return

                    label.config(image=photo if photo is not None else "")
                    label.image = photo

                get_photo_async(
                    root,
                    queued_track.get("image_url"),
                    (50, 50),
                    show_queue_cover,
                )

        queue_results.lift()

    def toggle_queue_results():
        if queue_results.winfo_children():
            close_queue_results()
        else:
            open_queue_results()

    queue_button.config(command=toggle_queue_results)
    output_button.place(relx=0, rely=1, x=12, y=-12, anchor="sw")
    queue_button.place(relx=1, rely=1, x=-12, y=-12, anchor="se")
    output_button.lift()
    queue_button.lift()

    def close_dropdowns():
        close_output_results()
        close_queue_results()

    def is_inside(widget, container):
        while widget is not None:
            if widget == container:
                return True
            widget = getattr(widget, "master", None)
        return False

    def close_dropdowns_on_outside_press(event):
        if get_state().get("screen") != "player":
            return
        if any(
            is_inside(event.widget, container)
            for container in (
                output_button,
                output_results,
                queue_button,
                queue_results,
            )
        ):
            return
        close_dropdowns()

    root.bind("<ButtonPress-1>", close_dropdowns_on_outside_press, add="+")

    def on_show():
        close_dropdowns()

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

    def set_cover(cover_key, song):
        source = song.get("source", "spotify")
        url = song.get("image_url")
        cover_label.config(image="", text="")
        cover_label.image = None

        if source == "local":
            cover_label.config(
                text="♫",
                fg=TEXT_DIM,
                bg=SURFACE_ALT,
                font=(FONT, 72, "bold"),
            )
            return

        def show_cover(photo):
            current_song = get_state()["song"]
            current_key = (
                current_song.get("source", "spotify"),
                _get_track_id(current_song),
                current_song.get("image_url"),
            )
            if current_key != cover_key:
                return
            cover_label.config(
                image=photo if photo is not None else "",
                text="",
            )
            cover_label.image = photo

        get_photo_async(root, url, (174, 174), show_cover)

    def restore_cover(_event=None):
        photo = getattr(cover_label, "image", None)
        if photo is not None:
            cover_label.config(image=photo)

    root.bind("<Map>", restore_cover, add="+")
    root.bind("<Configure>", restore_cover, add="+")

    def update(current_state):
        nonlocal player_cover_key, preloaded_next_track_id

        song = current_state["song"]
        source = song.get("source", "spotify")
        next_song = current_state.get("next_song")
        next_track_id = _get_track_id(next_song) if next_song else None
        if source == "spotify" and next_track_id != preloaded_next_track_id:
            preloaded_next_track_id = next_track_id
            if next_song:
                get_photo_async(
                    root,
                    next_song.get("image_url"),
                    (174, 174),
                    lambda _photo: None,
                )
                get_photo_async(
                    root,
                    next_song.get("image_url"),
                    (56, 56),
                    lambda _photo: None,
                )

        cover_key = (source, _get_track_id(song), song.get("image_url"))
        if cover_key != player_cover_key:
            player_cover_key = cover_key
            set_cover(cover_key, song)

        source_label.config(
            text="OFFLINE PLAYBACK" if source == "local" else "NOW PLAYING"
        )
        cover_cursor = "" if source == "local" else "hand2"
        cover_frame.config(cursor=cover_cursor)
        cover_label.config(cursor=cover_cursor)
        metadata_text["track"] = song.get("track", "")
        metadata_text["artist"] = song.get("artist", "")
        metadata_text["album"] = song.get("album_name", "")
        refresh_metadata_labels()
        wheel.itemconfig(
            play_text,
            text="Ⅱ" if song.get("is_playing", False) else "▶",
        )

        now = time.time()
        duration = max(1, song.get("duration_ms", 1) or 1)
        progress_ms = _get_progress_ms(song, now)
        if not seeking:
            progress["value"] = (progress_ms / duration) * 100
            elapsed_label.config(text=_format_time(progress_ms))
            remaining_label.config(text=f"-{_format_time(duration - progress_ms)}")

    update(state)
    return {"frame": frame, "update": update, "on_show": on_show}
