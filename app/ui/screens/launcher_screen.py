import time

from datetime import datetime
from queue import Empty, Queue
from threading import Thread
from tkinter import BOTH, LEFT, RIGHT, X
from tkinter import Button, Canvas, Frame, Label

from app.controller.controller_navigation import go_home, go_settings
from app.features.local_audio.controller import open_library
from app.services.battery_service import get_battery_status
from app.ui.theme import (
    ACCENT,
    BG,
    CARD,
    DIVIDER,
    FONT,
    PAGE_PAD,
    SURFACE_ALT,
    TEXT,
    TEXT_DIM,
    TEXT_MUTED,
    DANGER,
)


def render_launcher(root, _state):
    frame = Frame(root, bg=BG)
    battery_results = Queue()

    notice_label = Label(
        frame,
        text="",
        fg=TEXT,
        bg=DANGER,
        font=(FONT, 11, "bold"),
        padx=18,
        pady=9,
        justify="center",
        wraplength=420,
    )

    def show_notice(message):
        _state["ui_notice"] = {
            "message": message,
            "expires_at": time.monotonic() + 3,
        }

    header = Frame(frame, bg=BG)
    header.pack(fill=X, padx=PAGE_PAD, pady=(24, 8))
    header_top = Frame(header, bg=BG)
    header_top.pack(fill=X)
    Label(
        header_top,
        text="PIPHONE",
        fg=ACCENT,
        bg=BG,
        anchor="w",
        font=(FONT, 10, "bold"),
    ).pack(side=LEFT)

    header_actions = Frame(header_top, bg=BG)
    header_actions.pack(side=RIGHT)

    battery_box = Frame(header_actions, bg=BG)
    battery_box.pack(side=LEFT, padx=(0, 10))
    battery_percentage = Label(
        battery_box,
        text="BAT --%",
        fg=TEXT,
        bg=BG,
        anchor="e",
        font=(FONT, 11, "bold"),
    )
    battery_percentage.pack()
    battery_status = Label(
        battery_box,
        text="Checking...",
        fg=TEXT_DIM,
        bg=BG,
        anchor="e",
        font=(FONT, 8),
    )
    battery_status.pack()

    Button(
        header_actions,
        text="⏻",
        command=root.destroy,
        fg=TEXT_MUTED,
        bg=SURFACE_ALT,
        activeforeground=TEXT,
        activebackground=DANGER,
        font=(FONT, 16, "bold"),
        relief="flat",
        borderwidth=0,
        highlightthickness=0,
        takefocus=False,
        width=3,
        pady=2,
    ).pack(side=RIGHT)

    time_label = Label(
        header,
        text="--:--",
        fg=TEXT,
        bg=BG,
        anchor="w",
        font=(FONT, 48, "bold"),
    )
    time_label.pack(fill=X, pady=(2, 0))
    date_label = Label(
        header,
        text="",
        fg=TEXT_MUTED,
        bg=BG,
        anchor="w",
        font=(FONT, 12),
    )
    date_label.pack(fill=X)

    Label(
        frame,
        text="Apps",
        fg=TEXT,
        bg=BG,
        anchor="w",
        font=(FONT, 19, "bold"),
    ).pack(fill=X, padx=PAGE_PAD, pady=(22, 8))

    apps = Frame(frame, bg=BG)
    apps.pack(fill=BOTH, expand=True, padx=PAGE_PAD)

    spotify_tile = Frame(
        apps,
        bg=CARD,
        height=180,
        cursor="hand2",
        highlightbackground=DIVIDER,
        highlightthickness=1,
    )
    spotify_tile.pack(fill=X, pady=(0, 10))
    spotify_tile.pack_propagate(False)

    spotify_icon = Canvas(
        spotify_tile,
        width=112,
        height=112,
        bg=CARD,
        cursor="hand2",
        highlightthickness=0,
    )
    spotify_icon.pack(side=LEFT, padx=(20, 14), pady=24)
    spotify_icon.create_oval(8, 8, 104, 104, fill=ACCENT, outline="")
    for top, width in ((35, 5), (48, 4), (61, 4)):
        spotify_icon.create_arc(
            26,
            top,
            88,
            top + 36,
            start=20,
            extent=140,
            style="arc",
            outline=BG,
            width=width,
        )

    spotify_text = Frame(spotify_tile, bg=CARD, cursor="hand2")
    spotify_text.pack(side=LEFT, fill=BOTH, expand=True, pady=43)
    Label(
        spotify_text,
        text="Spotify",
        fg=TEXT,
        bg=CARD,
        cursor="hand2",
        anchor="w",
        font=(FONT, 24, "bold"),
    ).pack(fill=X)
    Label(
        spotify_text,
        text="Streaming player",
        fg=TEXT_MUTED,
        bg=CARD,
        cursor="hand2",
        anchor="w",
        font=(FONT, 11),
    ).pack(fill=X, pady=(5, 0))

    def open_spotify(_event=None):
        network = _state.get("network", {})

        if not network.get("internet_available", False):
            show_notice("Spotify is unavailable while offline.")
            return

        go_home()

    for widget in (
        spotify_tile,
        spotify_icon,
        spotify_text,
        *spotify_text.winfo_children(),
    ):
        widget.bind("<Button-1>", open_spotify)

    secondary = Frame(apps, bg=BG)
    secondary.pack(fill=X)

    def create_placeholder_tile(
        parent,
        title,
        symbol,
        subtitle="COMING SOON",
        command=None,
    ):
        tile = Frame(
            parent,
            bg=SURFACE_ALT,
            width=218,
            height=210,
            cursor="hand2" if command else "",
            highlightbackground=DIVIDER,
            highlightthickness=1,
        )
        tile.pack(side=LEFT, fill=X, expand=True)
        tile.pack_propagate(False)
        Label(
            tile,
            text=symbol,
            fg=TEXT,
            bg=SURFACE_ALT,
            cursor="hand2" if command else "",
            font=(FONT, 42, "bold"),
        ).pack(pady=(26, 8))
        Label(
            tile,
            text=title,
            fg=TEXT,
            bg=SURFACE_ALT,
            cursor="hand2" if command else "",
            font=(FONT, 16, "bold"),
        ).pack()
        Label(
            tile,
            text=subtitle,
            fg=TEXT_DIM,
            bg=SURFACE_ALT,
            cursor="hand2" if command else "",
            font=(FONT, 8, "bold"),
        ).pack(pady=(8, 0))

        if command:
            for widget in (tile, *tile.winfo_children()):
                widget.bind("<Button-1>", lambda _event: command())

        return tile

    create_placeholder_tile(
        secondary,
        "Offline",
        "♫",
        subtitle="LOCAL LIBRARY",
        command=open_library,
    )
    spacer = Frame(secondary, bg=BG, width=10)
    spacer.pack(side=LEFT)
    create_placeholder_tile(
        secondary,
        "Settings",
        "⚙",
        subtitle="DEVICE CONTROLS",
        command=go_settings,
    )

    def update_clock():
        if not frame.winfo_exists():
            return
        now = datetime.now()
        time_label.config(text=now.strftime("%H:%M"))
        date_label.config(text=now.strftime("%d.%m.%Y"))
        root.after(1000, update_clock)

    def update_battery_labels(status):
        if not frame.winfo_exists():
            return

        if status is None:
            battery_percentage.config(text="BAT --%", fg=TEXT_MUTED)
            battery_status.config(text="Unavailable", fg=DANGER)
            return

        percentage = status["percentage"]
        if status["charging"]:
            status_text = "Charging"
            status_color = ACCENT
        elif status["power_plugged"]:
            status_text = "Plugged in"
            status_color = ACCENT
        else:
            status_text = "On battery"
            status_color = TEXT_DIM

        battery_percentage.config(text=f"BAT {percentage}%", fg=TEXT)
        battery_status.config(text=status_text, fg=status_color)

    def refresh_battery():
        def load():
            try:
                status = get_battery_status()
            except (OSError, ValueError, KeyError):
                status = None

            battery_results.put(status)

        Thread(target=load, daemon=True).start()

    def poll_battery_result():
        if not frame.winfo_exists():
            return

        try:
            status = battery_results.get_nowait()
        except Empty:
            root.after(100, poll_battery_result)
            return

        update_battery_labels(status)
        root.after(15000, refresh_battery)
        root.after(15100, poll_battery_result)

    update_clock()
    refresh_battery()
    poll_battery_result()

    def update(current_state):
        notice = current_state.get("ui_notice")

        if not isinstance(notice, dict):
            notice_label.place_forget()
            return

        message = notice.get("message", "")
        expires_at = notice.get("expires_at", 0)

        if not message or time.monotonic() >= expires_at:
            current_state["ui_notice"] = None
            notice_label.place_forget()
            return

        notice_label.config(text=message)
        notice_label.place(
            relx=0.5,
            rely=0.92,
            anchor="center",
        )
        notice_label.lift()

    return {
        "frame": frame,
        "update": update,
    }
