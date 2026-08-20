from threading import Thread
from tkinter import BOTH, LEFT, NORMAL, RIGHT, X
from tkinter import Button, Canvas, Frame, Label

from app.controller.controller_navigation import go_launcher
from app.services import (
    audio_output_service,
    battery_service,
    bluetooth_service,
    device_info_service,
    settings_service,
)
from app.controller.controller_brightness import (
    preview_brightness,
    save_brightness,
)
from app.controller.controller_screen_timeout import save_screen_timeout
from app.ui.theme import (
    ACCENT,
    ACCENT_ACTIVE,
    BG,
    CARD,
    DANGER,
    DIVIDER,
    FONT,
    PAGE_PAD,
    SURFACE_ACTIVE,
    SURFACE_ALT,
    TEXT,
    TEXT_DIM,
    TEXT_MUTED,
)


SETTINGS_SECTIONS = (
    (
        "Connections",
        (
            ("WF", "Wi-Fi", "Manage networks"),
            ("BT", "Bluetooth", "Manage devices"),
        ),
    ),
    (
        "Audio",
        (
            ("AO", "Audio output", "Choose device"),
            ("VL", "Maximum volume", "100%"),
        ),
    ),
    (
        "Display",
        (
            ("BR", "Brightness", "80%"),
            ("SL", "Screen timeout", "5 min"),
        ),
    ),
    (
        "Power",
        (
            ("BA", "Battery", "Battery status"),
            ("LB", "Low battery shutdown", "10%"),
        ),
    ),
    (
        "System",
        (
            ("IN", "Device information", "PiPhone"),
            ("RS", "Restart", "Restart device"),
            ("PW", "Shutdown", "Power off"),
        ),
    ),
)


def _format_screen_timeout(seconds):
    if seconds == 0:
        return "Never"
    if seconds < 60:
        return f"{seconds} sec"
    return f"{seconds // 60} min"


def render_settings(root, _state):
    frame = Frame(root, bg=BG)

    output_value_label = None
    output_row_widgets = ()

    maximum_value_label = None
    maximum_row_widgets = ()
    maximum_pending = settings_service.get_maximum_volume()

    brightness_value_label = None
    brightness_row_widgets = ()
    brightness_pending = settings_service.get_brightness()

    timeout_value_label = None
    timeout_row_widgets = ()
    timeout_pending = settings_service.get_screen_timeout()

    information_row_widgets = ()
    battery_value_label = None
    battery_row_widgets = ()

    bluetooth_value_label = None
    bluetooth_row_widgets = ()


    header = Frame(frame, bg=BG)
    header.pack(fill=X, padx=PAGE_PAD, pady=(20, 12))

    Button(
        header,
        text="‹",
        command=go_launcher,
        fg=TEXT,
        bg=SURFACE_ALT,
        activeforeground=TEXT,
        activebackground=CARD,
        font=(FONT, 22, "bold"),
        relief="flat",
        borderwidth=0,
        highlightthickness=0,
        takefocus=False,
        width=3,
        pady=0,
    ).pack(side=LEFT)

    heading = Frame(header, bg=BG)
    heading.pack(side=LEFT, padx=(12, 0))
    Label(
        heading,
        text="SETTINGS",
        fg=ACCENT,
        bg=BG,
        anchor="w",
        font=(FONT, 9, "bold"),
    ).pack(fill=X)
    Label(
        heading,
        text="Device settings",
        fg=TEXT,
        bg=BG,
        anchor="w",
        font=(FONT, 22, "bold"),
    ).pack(fill=X)

    canvas = Canvas(
        frame,
        bg=BG,
        highlightthickness=0,
        borderwidth=0,
    )
    canvas.pack(fill=BOTH, expand=True)

    content = Frame(canvas, bg=BG)
    content_window = canvas.create_window(
        0,
        0,
        anchor="nw",
        window=content,
    )

    def sync_scroll_region(_event=None):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def sync_content_width(event):
        canvas.itemconfigure(content_window, width=event.width)

    content.bind("<Configure>", sync_scroll_region)
    canvas.bind("<Configure>", sync_content_width)

    intro = Frame(
        content,
        bg=CARD,
        highlightbackground=DIVIDER,
        highlightthickness=1,
    )
    intro.pack(fill=X, padx=PAGE_PAD, pady=(2, 18))
    Label(
        intro,
        text="PIPHONE",
        fg=ACCENT,
        bg=CARD,
        anchor="w",
        font=(FONT, 9, "bold"),
    ).pack(fill=X, padx=16, pady=(13, 2))
    Label(
        intro,
        text="Control connectivity, sound, display and power.",
        fg=TEXT_MUTED,
        bg=CARD,
        anchor="w",
        justify="left",
        wraplength=400,
        font=(FONT, 11),
    ).pack(fill=X, padx=16, pady=(0, 14))

    def create_setting_row(parent, badge, title, value, is_last):
        row = Frame(parent, bg=CARD, height=66)
        row.pack(fill=X)
        row.pack_propagate(False)

        badge_box = Frame(
            row,
            bg=SURFACE_ALT,
            width=42,
            height=42,
        )
        badge_box.pack(side=LEFT, padx=(12, 11), pady=12)
        badge_box.pack_propagate(False)
        badge_label = Label(
            badge_box,
            text=badge,
            fg=ACCENT,
            bg=SURFACE_ALT,
            font=(FONT, 9, "bold"),
        )
        badge_label.pack(fill=BOTH, expand=True)

        title_label = Label(
            row,
            text=title,
            fg=TEXT,
            bg=CARD,
            anchor="w",
            font=(FONT, 11, "bold"),
        )
        title_label.pack(side=LEFT, fill=X, expand=True)

        right = Frame(row, bg=CARD)
        right.pack(side=RIGHT, padx=(8, 13))
        value_label = Label(
            right,
            text=value,
            fg=TEXT_MUTED,
            bg=CARD,
            anchor="e",
            font=(FONT, 9),
        )
        value_label.pack(side=LEFT)
        chevron = Label(
            right,
            text="›",
            fg=TEXT_DIM,
            bg=CARD,
            font=(FONT, 18),
        )
        chevron.pack(side=RIGHT, padx=(8, 0))

        if not is_last:
            Frame(parent, bg=DIVIDER, height=1).pack(
                fill=X,
                padx=(65, 0),
            )

        return (
            row,
            badge_box,
            badge_label,
            title_label,
            right,
            value_label,
            chevron,
        ), value_label

    for section_title, rows in SETTINGS_SECTIONS:
        section = Frame(content, bg=BG)
        section.pack(fill=X, padx=PAGE_PAD, pady=(0, 18))
        Label(
            section,
            text=section_title.upper(),
            fg=TEXT_DIM,
            bg=BG,
            anchor="w",
            font=(FONT, 9, "bold"),
        ).pack(fill=X, padx=3, pady=(0, 7))

        card = Frame(
            section,
            bg=CARD,
            highlightbackground=DIVIDER,
            highlightthickness=1,
        )
        card.pack(fill=X)

        for index, (badge, title, value) in enumerate(rows):
            row_widgets, value_label = create_setting_row(
                card,
                badge,
                title,
                value,
                index == len(rows) - 1,
            )
            if title == "Bluetooth":
                bluetooth_row_widgets = row_widgets
                bluetooth_value_label = value_label
            elif title == "Audio output":
                output_row_widgets = row_widgets
                output_value_label = value_label
            elif title == "Maximum volume":
                maximum_row_widgets = row_widgets
                maximum_value_label = value_label
            elif title == "Brightness":
                brightness_row_widgets = row_widgets
                brightness_value_label = value_label
                brightness_value_label.config(text=f"{brightness_pending}%")
            elif title == "Screen timeout":
                timeout_row_widgets = row_widgets
                timeout_value_label = value_label
                timeout_value_label.config(
                    text=_format_screen_timeout(timeout_pending)
                )
            elif title == "Device information":
                information_row_widgets = row_widgets
            elif title == "Battery":
                battery_row_widgets = row_widgets
                battery_value_label = value_label

    Label(
        content,
        text="Controls will be connected as each system service is added.",
        fg=TEXT_DIM,
        bg=BG,
        wraplength=390,
        justify="center",
        font=(FONT, 9),
    ).pack(padx=PAGE_PAD, pady=(0, 24))

    bluetooth_panel = Frame(frame, bg=BG)

    bluetooth_header = Frame(bluetooth_panel, bg=BG)
    bluetooth_header.pack(fill=X, padx=PAGE_PAD, pady=(20, 12))

    Button(
        bluetooth_header,
        text="‹",
        command=lambda: bluetooth_panel.place_forget(),
        fg=TEXT,
        bg=SURFACE_ALT,
        activeforeground=TEXT,
        activebackground=CARD,
        font=(FONT, 22, "bold"),
        relief="flat",
        borderwidth=0,
        highlightthickness=0,
        takefocus=False,
        width=3,
        pady=0,
    ).pack(side=LEFT)

    bluetooth_heading = Frame(bluetooth_header, bg=BG)
    bluetooth_heading.pack(side=LEFT, padx=(12, 0))

    Label(
        bluetooth_heading,
        text="CONNECTIONS",
        fg=ACCENT,
        bg=BG,
        anchor="w",
        font=(FONT, 9, "bold"),
    ).pack(fill=X)

    Label(
        bluetooth_heading,
        text="Bluetooth",
        fg=TEXT,
        bg=BG,
        anchor="w",
        font=(FONT, 22, "bold"),
    ).pack(fill=X)

    bluetooth_canvas = Canvas(
        bluetooth_panel,
        bg=BG,
        highlightthickness=0,
        borderwidth=0,
    )
    bluetooth_canvas.pack(
        fill=BOTH,
        expand=True,
        padx=PAGE_PAD,
        pady=(4, 18),
    )

    bluetooth_body = Frame(bluetooth_canvas, bg=BG)
    bluetooth_window = bluetooth_canvas.create_window(
        0,
        0,
        anchor="nw",
        window=bluetooth_body,
    )

    bluetooth_body.bind(
        "<Configure>",
        lambda _event: bluetooth_canvas.configure(
            scrollregion=bluetooth_canvas.bbox("all")
        ),
    )
    bluetooth_canvas.bind(
        "<Configure>",
        lambda event: bluetooth_canvas.itemconfigure(
            bluetooth_window,
            width=event.width,
        ),
    )

    bluetooth_drag_start_y = 0
    bluetooth_dragged = False

    def start_bluetooth_drag(event):
        nonlocal bluetooth_drag_start_y, bluetooth_dragged
        bluetooth_drag_start_y = event.y_root
        bluetooth_dragged = False
        bluetooth_canvas.scan_mark(
            0,
            event.y_root - bluetooth_canvas.winfo_rooty(),
        )

    def drag_bluetooth(event):
        nonlocal bluetooth_dragged
        if abs(event.y_root - bluetooth_drag_start_y) > 5:
            bluetooth_dragged = True
        bluetooth_canvas.scan_dragto(
            0,
            event.y_root - bluetooth_canvas.winfo_rooty(),
            gain=1,
        )

    def finish_bluetooth_device_press(_event, device):
        if not bluetooth_dragged:
            select_bluetooth_device(device)

    def bind_bluetooth_drag(widget, device=None):
        widget.bind("<ButtonPress-1>", start_bluetooth_drag)
        widget.bind("<B1-Motion>", drag_bluetooth)
        widget.bind(
            "<MouseWheel>",
            lambda event: bluetooth_canvas.yview_scroll(
                -1 if event.delta > 0 else 1,
                "units",
            ),
        )
        if device is not None:
            widget.bind(
                "<ButtonRelease-1>",
                lambda event, selected=device: (
                    finish_bluetooth_device_press(event, selected)
                ),
            )

    bind_bluetooth_drag(bluetooth_canvas)
    bind_bluetooth_drag(bluetooth_body)

    def clear_bluetooth_body():
        for child in bluetooth_body.winfo_children():
            child.destroy()
        bluetooth_canvas.yview_moveto(0)


    def show_bluetooth_message(message, color=TEXT_MUTED):
        clear_bluetooth_body()
        Label(
            bluetooth_body,
            text=message,
            fg=color,
            bg=BG,
            justify="center",
            wraplength=400,
            font=(FONT, 11),
        ).pack(fill=X, pady=60)


    def update_bluetooth_summary(devices):
        if (
            bluetooth_value_label is None
            or not bluetooth_value_label.winfo_exists()
        ):
            return

        connected = next(
            (device for device in devices if device["connected"]),
            None,
        )

        bluetooth_value_label.config(
            text=connected["name"] if connected else "Manage devices"
        )

    def select_bluetooth_device(device):
        if device["connected"]:
            action_text = f'Disconnecting {device["name"]}...'
        elif device["paired"]:
            action_text = f'Connecting to {device["name"]}...'
        else:
            action_text = f'Pairing with {device["name"]}...'

        show_bluetooth_message(action_text)

        def worker():
            try:
                if device["connected"]:
                    bluetooth_service.disconnect_device(device["mac"])
                elif device["paired"]:
                    bluetooth_service.connect_device(device["mac"])
                else:
                    bluetooth_service.pair_device(device["mac"])

                devices = bluetooth_service.get_devices()
                root.after(
                    0,
                    lambda found=devices: show_bluetooth_devices(found),
                )
            except Exception as error:
                message = str(error)
                root.after(
                    0,
                    lambda text=message: show_bluetooth_error(text),
                )

        Thread(target=worker, daemon=True).start()

    def show_bluetooth_error(message):
        show_bluetooth_message(
            f"Bluetooth unavailable\n\n{message}",
            DANGER,
        )

        Button(
            bluetooth_body,
            text="Try again",
            command=lambda: load_bluetooth_devices(),
            fg=TEXT,
            bg=SURFACE_ALT,
            activeforeground=TEXT,
            activebackground=SURFACE_ACTIVE,
            font=(FONT, 10, "bold"),
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            takefocus=False,
            padx=14,
            pady=9,
        ).pack()

    def show_bluetooth_devices(devices):
        clear_bluetooth_body()
        update_bluetooth_summary(devices)

        Label(
            bluetooth_body,
            text="AVAILABLE DEVICES",
            fg=TEXT_DIM,
            bg=BG,
            anchor="w",
            font=(FONT, 9, "bold"),
        ).pack(fill=X, padx=3, pady=(0, 7))

        if not devices:
            Label(
                bluetooth_body,
                text="No Bluetooth devices found.",
                fg=TEXT_MUTED,
                bg=CARD,
                font=(FONT, 11),
                padx=16,
                pady=22,
            ).pack(fill=X)
        else:
            for device in devices:
                if device["connected"]:
                    status = "Connected"
                    background = ACCENT
                elif device["paired"]:
                    status = "Paired"
                    background = CARD
                else:
                    status = "Tap to pair"
                    background = CARD

                device_row = Frame(
                    bluetooth_body,
                    bg=background,
                    height=62,
                    highlightbackground=DIVIDER,
                    highlightthickness=1,
                    cursor="hand2",
                )
                device_row.pack(fill=X, pady=(0, 8))
                device_row.pack_propagate(False)

                if device["paired"]:
                    forget_button = Button(
                        device_row,
                        text="Forget",
                        fg=DANGER,
                        bg=SURFACE_ALT,
                        activeforeground=TEXT,
                        activebackground=DANGER,
                        font=(FONT, 8, "bold"),
                        relief="flat",
                        borderwidth=0,
                        highlightthickness=0,
                        takefocus=False,
                        padx=9,
                        pady=6,
                    )
                    forget_button.config(
                        command=lambda selected=device, button=forget_button: (
                            confirm_forget_device(selected, button)
                        )
                    )
                    forget_button.pack(
                        side=RIGHT,
                        padx=(6, 10),
                        pady=12,
                    )

                device_name = Label(
                    device_row,
                    text=device["name"],
                    fg=TEXT,
                    bg=background,
                    anchor="w",
                    font=(FONT, 11, "bold"),
                    cursor="hand2",
                )
                device_name.pack(fill=X, padx=16, pady=(9, 0))

                device_status = Label(
                    device_row,
                    text=status,
                    fg=TEXT if device["connected"] else TEXT_MUTED,
                    bg=background,
                    anchor="w",
                    font=(FONT, 9),
                    cursor="hand2",
                )
                device_status.pack(fill=X, padx=16, pady=(1, 8))

                for widget in (device_row, device_name, device_status):
                    bind_bluetooth_drag(widget, device)

        Button(
            bluetooth_body,
            text="Scan for devices",
            command=lambda: load_bluetooth_devices(scan=True),
            fg=TEXT,
            bg=SURFACE_ALT,
            activeforeground=TEXT,
            activebackground=SURFACE_ACTIVE,
            font=(FONT, 10, "bold"),
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            takefocus=False,
            padx=14,
            pady=9,
        ).pack(pady=(12, 0))

    def load_bluetooth_devices(scan=False, show_panel=True):
        if show_panel:
            bluetooth_panel.place(
                x=0,
                y=0,
                relwidth=1,
                relheight=1,
            )
            bluetooth_panel.lift()

            show_bluetooth_message(
                "Scanning for Bluetooth devices..."
                if scan
                else "Loading Bluetooth devices..."
            )

        def worker():
            try:
                if scan:
                    devices = bluetooth_service.scan_devices()
                else:
                    devices = bluetooth_service.get_devices()

                if show_panel:
                    root.after(
                        0,
                        lambda found=devices: (
                            show_bluetooth_devices(found)
                        ),
                    )
                else:
                    root.after(
                        0,
                        lambda found=devices: (
                            update_bluetooth_summary(found)
                        ),
                    )
            except Exception as error:
                if show_panel:
                    message = str(error)
                    root.after(
                        0,
                        lambda text=message: (
                            show_bluetooth_error(text)
                        ),
                    )

        Thread(target=worker, daemon=True).start()

    def forget_bluetooth_device(device):
        show_bluetooth_message(
            f'Forgetting {device["name"]}...'
        )

        def worker():
            try:
                bluetooth_service.remove_device(device["mac"])
                devices = bluetooth_service.get_devices()

                root.after(
                    0,
                    lambda found=devices: (
                        show_bluetooth_devices(found)
                    ),
                )
            except Exception as error:
                message = str(error)
                root.after(
                    0,
                    lambda text=message: (
                        show_bluetooth_error(text)
                    ),
                )

        Thread(target=worker, daemon=True).start()

    def confirm_forget_device(device, button):
        if button.cget("text") == "Confirm":
            forget_bluetooth_device(device)
            return

        button.config(
            text="Confirm",
            fg=TEXT,
            bg=DANGER,
        )

        def reset_button():
            if button.winfo_exists():
                button.config(
                    text="Forget",
                    fg=DANGER,
                    bg=SURFACE_ALT,
                )

        root.after(2500, reset_button)

    output_panel = Frame(frame, bg=BG)
    output_header = Frame(output_panel, bg=BG)
    output_header.pack(fill=X, padx=PAGE_PAD, pady=(20, 12))
    Button(
        output_header,
        text="‹",
        command=lambda: output_panel.place_forget(),
        fg=TEXT,
        bg=SURFACE_ALT,
        activeforeground=TEXT,
        activebackground=CARD,
        font=(FONT, 22, "bold"),
        relief="flat",
        borderwidth=0,
        highlightthickness=0,
        takefocus=False,
        width=3,
        pady=0,
    ).pack(side=LEFT)

    output_heading = Frame(output_header, bg=BG)
    output_heading.pack(side=LEFT, padx=(12, 0))
    Label(
        output_heading,
        text="AUDIO",
        fg=ACCENT,
        bg=BG,
        anchor="w",
        font=(FONT, 9, "bold"),
    ).pack(fill=X)
    Label(
        output_heading,
        text="Output device",
        fg=TEXT,
        bg=BG,
        anchor="w",
        font=(FONT, 22, "bold"),
    ).pack(fill=X)

    output_body = Frame(output_panel, bg=BG)
    output_body.pack(fill=BOTH, expand=True, padx=PAGE_PAD, pady=(4, 18))

    def clear_output_body():
        for child in output_body.winfo_children():
            child.destroy()

    def show_output_message(message, color=TEXT_MUTED):
        clear_output_body()
        Label(
            output_body,
            text=message,
            fg=color,
            bg=BG,
            justify="center",
            wraplength=400,
            font=(FONT, 11),
        ).pack(fill=X, pady=60)

    def close_output_panel():
        output_panel.place_forget()

    def update_output_summary(devices):
        if output_value_label is None or not output_value_label.winfo_exists():
            return

        active = next(
            (device for device in devices if device.get("active")),
            None,
        )
        output_value_label.config(
            text=active["name"] if active else "Choose device"
        )

    def finish_output_selection(device):
        if output_value_label is not None and output_value_label.winfo_exists():
            output_value_label.config(text=device["name"])
        load_output_devices(True)

    def show_output_error(message):
        show_output_message(f"Output unavailable\n\n{message}", DANGER)
        Button(
            output_body,
            text="Try again",
            command=lambda: load_output_devices(True),
            fg=TEXT,
            bg=SURFACE_ALT,
            activeforeground=TEXT,
            activebackground=SURFACE_ACTIVE,
            font=(FONT, 10, "bold"),
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            takefocus=False,
            padx=14,
            pady=9,
        ).pack()

    def select_output_device(device):
        if device.get("active"):
            return

        show_output_message(f'Switching to {device["name"]}...')

        def worker():
            try:
                audio_output_service.set_output_device(device["id"])
                root.after(
                    0,
                    lambda selected=device: finish_output_selection(selected),
                )
            except Exception as error:
                message = str(error)
                root.after(0, lambda text=message: show_output_error(text))

        Thread(target=worker, daemon=True).start()

    def show_output_devices(devices):
        clear_output_body()
        update_output_summary(devices)

        Label(
            output_body,
            text="AVAILABLE OUTPUTS",
            fg=TEXT_DIM,
            bg=BG,
            anchor="w",
            font=(FONT, 9, "bold"),
        ).pack(fill=X, padx=3, pady=(0, 7))

        if not devices:
            Label(
                output_body,
                text="No connected audio outputs found.",
                fg=TEXT_MUTED,
                bg=CARD,
                font=(FONT, 11),
                padx=16,
                pady=22,
            ).pack(fill=X)
        else:
            for device in devices:
                active = bool(device.get("active"))
                device_type = (
                    "Bluetooth"
                    if device.get("type") == "bluetooth"
                    else "3.5 mm wired"
                )
                Button(
                    output_body,
                    text=(
                        f'{device["name"]}\n'
                        f'{device_type}'
                        f'{"  ·  Active" if active else ""}'
                    ),
                    command=lambda selected=device: select_output_device(selected),
                    fg=TEXT,
                    bg=ACCENT if active else CARD,
                    activeforeground=TEXT,
                    activebackground=ACCENT_ACTIVE if active else SURFACE_ACTIVE,
                    anchor="w",
                    justify=LEFT,
                    font=(FONT, 11, "bold"),
                    relief="flat",
                    borderwidth=0,
                    highlightbackground=DIVIDER,
                    highlightthickness=1,
                    takefocus=False,
                    padx=16,
                    pady=13,
                ).pack(fill=X, pady=(0, 8))

        Button(
            output_body,
            text="Refresh",
            command=lambda: load_output_devices(True),
            fg=TEXT,
            bg=SURFACE_ALT,
            activeforeground=TEXT,
            activebackground=SURFACE_ACTIVE,
            font=(FONT, 10, "bold"),
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            takefocus=False,
            padx=14,
            pady=9,
        ).pack(pady=(12, 0))

    def load_output_devices(show_panel=False):
        if show_panel:
            maximum_panel.place_forget()
            output_panel.place(x=0, y=0, relwidth=1, relheight=1)
            output_panel.lift()
            show_output_message("Finding audio outputs...")

        def worker():
            try:
                devices = audio_output_service.get_output_devices()
                if show_panel:
                    root.after(
                        0,
                        lambda found=devices: show_output_devices(found),
                    )
                else:
                    root.after(
                        0,
                        lambda found=devices: update_output_summary(found),
                    )
            except Exception as error:
                if show_panel:
                    message = str(error)
                    root.after(0, lambda text=message: show_output_error(text))

        Thread(target=worker, daemon=True).start()

    maximum_panel = Frame(frame, bg=BG)
    maximum_header = Frame(maximum_panel, bg=BG)
    maximum_header.pack(fill=X, padx=PAGE_PAD, pady=(20, 12))
    Button(
        maximum_header,
        text="‹",
        command=lambda: maximum_panel.place_forget(),
        fg=TEXT,
        bg=SURFACE_ALT,
        activeforeground=TEXT,
        activebackground=CARD,
        font=(FONT, 22, "bold"),
        relief="flat",
        borderwidth=0,
        highlightthickness=0,
        takefocus=False,
        width=3,
        pady=0,
    ).pack(side=LEFT)

    maximum_heading = Frame(maximum_header, bg=BG)
    maximum_heading.pack(side=LEFT, padx=(12, 0))
    Label(
        maximum_heading,
        text="AUDIO",
        fg=ACCENT,
        bg=BG,
        anchor="w",
        font=(FONT, 9, "bold"),
    ).pack(fill=X)
    Label(
        maximum_heading,
        text="Maximum volume",
        fg=TEXT,
        bg=BG,
        anchor="w",
        font=(FONT, 22, "bold"),
    ).pack(fill=X)

    maximum_body = Frame(maximum_panel, bg=BG)
    maximum_body.pack(fill=BOTH, expand=True, padx=PAGE_PAD, pady=(14, 18))

    maximum_percentage = Label(
        maximum_body,
        text="100%",
        fg=TEXT,
        bg=BG,
        font=(FONT, 42, "bold"),
    )
    maximum_percentage.pack(fill=X)

    maximum_slider = Canvas(
        maximum_body,
        height=86,
        bg=BG,
        highlightthickness=0,
        borderwidth=0,
        cursor="hand2",
    )
    maximum_slider.pack(fill=X, pady=(8, 4))

    def draw_maximum_slider():
        width = max(40, maximum_slider.winfo_width())
        left = 20
        right = width - 20
        center_y = 42
        ratio = (maximum_pending - 10) / 90
        knob_x = left + (right - left) * ratio

        maximum_slider.delete("all")
        maximum_slider.create_line(
            left,
            center_y,
            right,
            center_y,
            fill=DIVIDER,
            width=8,
            capstyle="round",
        )
        maximum_slider.create_line(
            left,
            center_y,
            knob_x,
            center_y,
            fill=ACCENT,
            width=8,
            capstyle="round",
        )
        maximum_slider.create_oval(
            knob_x - 13,
            center_y - 13,
            knob_x + 13,
            center_y + 13,
            fill=TEXT,
            outline=ACCENT,
            width=4,
        )

    def update_maximum_preview(value):
        nonlocal maximum_pending
        maximum_pending = max(10, min(100, int(value)))
        maximum_percentage.config(text=f"{maximum_pending}%")
        draw_maximum_slider()

    def set_maximum_from_pointer(event):
        width = max(40, maximum_slider.winfo_width())
        ratio = min(max((event.x - 20) / max(1, width - 40), 0), 1)
        value = round((10 + ratio * 90) / 5) * 5
        update_maximum_preview(value)

    maximum_slider.bind("<Button-1>", set_maximum_from_pointer)
    maximum_slider.bind("<B1-Motion>", set_maximum_from_pointer)
    maximum_slider.bind("<Configure>", lambda _event: draw_maximum_slider())

    maximum_status = Label(
        maximum_body,
        text="",
        fg=TEXT_MUTED,
        bg=BG,
        font=(FONT, 9),
    )
    maximum_status.pack(fill=X, pady=(0, 10))

    maximum_save = Button(
        maximum_body,
        text="Save maximum volume",
        fg=BG,
        bg=ACCENT,
        activeforeground=BG,
        activebackground=ACCENT_ACTIVE,
        font=(FONT, 11, "bold"),
        relief="flat",
        borderwidth=0,
        highlightthickness=0,
        takefocus=False,
        padx=16,
        pady=12,
    )
    maximum_save.pack(fill=X)

    def finish_maximum_save(value, error=None):
        maximum_save.config(state=NORMAL)
        if maximum_value_label is not None and maximum_value_label.winfo_exists():
            maximum_value_label.config(text=f"{value}%")

        if error:
            maximum_status.config(
                text=f"Saved, but could not apply now: {error}",
                fg=DANGER,
            )
        else:
            maximum_status.config(text="Maximum volume saved", fg=ACCENT)

    def save_maximum_volume():
        value = maximum_pending
        maximum_save.config(state="disabled")
        maximum_status.config(text="Saving...", fg=TEXT_MUTED)

        def worker():
            try:
                saved_value = settings_service.set_maximum_volume(value)
            except Exception as error:
                message = str(error)
                root.after(
                    0,
                    lambda: (
                        maximum_save.config(state=NORMAL),
                        maximum_status.config(text=message, fg=DANGER),
                    ),
                )
                return

            apply_error = None
            try:
                audio_output_service.enforce_maximum_volume()
            except Exception as error:
                apply_error = str(error)

            root.after(
                0,
                lambda saved=saved_value, error=apply_error: (
                    finish_maximum_save(saved, error)
                ),
            )

        Thread(target=worker, daemon=True).start()

    maximum_save.config(command=save_maximum_volume)

    def open_maximum_panel():
        nonlocal maximum_pending
        output_panel.place_forget()
        maximum_pending = settings_service.get_maximum_volume()
        maximum_status.config(text="", fg=TEXT_MUTED)
        maximum_panel.place(x=0, y=0, relwidth=1, relheight=1)
        maximum_panel.lift()
        maximum_panel.update_idletasks()
        update_maximum_preview(maximum_pending)

    brightness_panel = Frame(frame, bg=BG)

    brightness_header = Frame(brightness_panel, bg=BG)
    brightness_header.pack(fill=X, padx=PAGE_PAD, pady=(20, 12))

    Button(
        brightness_header,
        text="‹",
        command=lambda: close_brightness_panel(),
        fg=TEXT,
        bg=SURFACE_ALT,
        activeforeground=TEXT,
        activebackground=CARD,
        font=(FONT, 22, "bold"),
        relief="flat",
        borderwidth=0,
        highlightthickness=0,
        takefocus=False,
        width=3,
        pady=0,
    ).pack(side=LEFT)

    brightness_heading = Frame(brightness_header, bg=BG)
    brightness_heading.pack(side=LEFT, padx=(12, 0))

    Label(
        brightness_heading,
        text="DISPLAY",
        fg=ACCENT,
        bg=BG,
        anchor="w",
        font=(FONT, 9, "bold"),
    ).pack(fill=X)

    Label(
        brightness_heading,
        text="Brightness",
        fg=TEXT,
        bg=BG,
        anchor="w",
        font=(FONT, 22, "bold"),
    ).pack(fill=X)

    brightness_body = Frame(brightness_panel, bg=BG)
    brightness_body.pack(
        fill=BOTH,
        expand=True,
        padx=PAGE_PAD,
        pady=(14, 18),
    )

    brightness_percentage = Label(
        brightness_body,
        text=f"{brightness_pending}%",
        fg=TEXT,
        bg=BG,
        font=(FONT, 42, "bold"),
    )
    brightness_percentage.pack(fill=X)

    brightness_slider = Canvas(
        brightness_body,
        height=86,
        bg=BG,
        highlightthickness=0,
        borderwidth=0,
        cursor="hand2",
    )
    brightness_slider.pack(fill=X, pady=(8, 4))

    brightness_status = Label(
        brightness_body,
        text="",
        fg=TEXT_MUTED,
        bg=BG,
        font=(FONT, 9),
    )
    brightness_status.pack(fill=X, pady=(0, 10))

    brightness_save = Button(
        brightness_body,
        text="Save brightness",
        fg=BG,
        bg=ACCENT,
        activeforeground=BG,
        activebackground=ACCENT_ACTIVE,
        font=(FONT, 11, "bold"),
        relief="flat",
        borderwidth=0,
        highlightthickness=0,
        takefocus=False,
        padx=16,
        pady=12,
    )
    brightness_save.pack(fill=X)

    def draw_brightness_slider():
        width = max(40, brightness_slider.winfo_width())
        left = 20
        right = width - 20
        center_y = 42

        ratio = (brightness_pending - 10) / 90
        knob_x = left + (right - left) * ratio

        brightness_slider.delete("all")

        brightness_slider.create_line(
            left,
            center_y,
            right,
            center_y,
            fill=DIVIDER,
            width=8,
            capstyle="round",
        )

        brightness_slider.create_line(
            left,
            center_y,
            knob_x,
            center_y,
            fill=ACCENT,
            width=8,
            capstyle="round",
        )

        brightness_slider.create_oval(
            knob_x - 13,
            center_y - 13,
            knob_x + 13,
            center_y + 13,
            fill=TEXT,
            outline=ACCENT,
            width=4,
        )

    def update_brightness_preview(value):
        nonlocal brightness_pending

        brightness_pending = max(10, min(100, int(value)))
        brightness_percentage.config(text=f"{brightness_pending}%")
        draw_brightness_slider()

        try:
            preview_brightness(brightness_pending)
            brightness_status.config(text="", fg=TEXT_MUTED)
        except OSError as error:
            brightness_status.config(text=str(error), fg=DANGER)

    def set_brightness_from_pointer(event):
        width = max(40, brightness_slider.winfo_width())
        ratio = min(
            max((event.x - 20) / max(1, width - 40), 0),
            1,
        )

        value = round((10 + ratio * 90) / 5) * 5
        update_brightness_preview(value)

    brightness_slider.bind(
        "<Button-1>",
        set_brightness_from_pointer,
    )
    brightness_slider.bind(
        "<B1-Motion>",
        set_brightness_from_pointer,
    )
    brightness_slider.bind(
        "<Configure>",
        lambda _event: draw_brightness_slider(),
    )

    def close_brightness_panel():
        nonlocal brightness_pending

        saved_value = settings_service.get_brightness()
        brightness_pending = saved_value

        try:
            preview_brightness(saved_value)
        except OSError as error:
            print(f"[BRIGHTNESS ERROR] {error}")

        brightness_panel.place_forget()

    def save_current_brightness():
        nonlocal brightness_pending

        brightness_save.config(state="disabled")
        brightness_status.config(text="Saving...", fg=TEXT_MUTED)

        try:
            saved_value = save_brightness(brightness_pending)
        except (OSError, ValueError) as error:
            brightness_status.config(text=str(error), fg=DANGER)
            brightness_save.config(state=NORMAL)
            return

        brightness_pending = saved_value
        brightness_value_label.config(text=f"{saved_value}%")
        brightness_status.config(
            text="Brightness saved",
            fg=ACCENT,
        )
        brightness_save.config(state=NORMAL)

    def open_brightness_panel():
        nonlocal brightness_pending

        close_output_panel()
        maximum_panel.place_forget()
        timeout_panel.place_forget()

        brightness_pending = settings_service.get_brightness()
        brightness_status.config(text="", fg=TEXT_MUTED)

        brightness_panel.place(
            x=0,
            y=0,
            relwidth=1,
            relheight=1,
        )
        brightness_panel.lift()
        brightness_panel.update_idletasks()

        brightness_percentage.config(
            text=f"{brightness_pending}%"
        )
        draw_brightness_slider()

    brightness_save.config(command=save_current_brightness)

    timeout_panel = Frame(frame, bg=BG)

    timeout_header = Frame(timeout_panel, bg=BG)
    timeout_header.pack(fill=X, padx=PAGE_PAD, pady=(20, 12))

    Button(
        timeout_header,
        text="‹",
        command=timeout_panel.place_forget,
        fg=TEXT,
        bg=SURFACE_ALT,
        activeforeground=TEXT,
        activebackground=CARD,
        font=(FONT, 22, "bold"),
        relief="flat",
        borderwidth=0,
        highlightthickness=0,
        takefocus=False,
        width=3,
        pady=0,
    ).pack(side=LEFT)

    timeout_heading = Frame(timeout_header, bg=BG)
    timeout_heading.pack(side=LEFT, padx=(12, 0))
    Label(
        timeout_heading,
        text="DISPLAY",
        fg=ACCENT,
        bg=BG,
        anchor="w",
        font=(FONT, 9, "bold"),
    ).pack(fill=X)
    Label(
        timeout_heading,
        text="Screen timeout",
        fg=TEXT,
        bg=BG,
        anchor="w",
        font=(FONT, 22, "bold"),
    ).pack(fill=X)

    timeout_body = Frame(timeout_panel, bg=BG)
    timeout_body.pack(fill=BOTH, expand=True, padx=PAGE_PAD, pady=(14, 18))

    timeout_choice_buttons = {}

    def refresh_timeout_choices():
        for seconds, button in timeout_choice_buttons.items():
            selected = seconds == timeout_pending
            button.config(
                fg=BG if selected else TEXT,
                bg=ACCENT if selected else CARD,
                activeforeground=BG if selected else TEXT,
                activebackground=ACCENT_ACTIVE if selected else SURFACE_ACTIVE,
            )

    def choose_timeout(seconds):
        nonlocal timeout_pending

        try:
            timeout_pending = save_screen_timeout(seconds)
        except (OSError, TypeError, ValueError) as error:
            print(f"[SCREEN TIMEOUT ERROR] {error}")
            return

        if timeout_value_label is not None and timeout_value_label.winfo_exists():
            timeout_value_label.config(
                text=_format_screen_timeout(timeout_pending)
            )
        refresh_timeout_choices()

    for seconds in settings_service.SCREEN_TIMEOUT_OPTIONS:
        button = Button(
            timeout_body,
            text=_format_screen_timeout(seconds),
            command=lambda value=seconds: choose_timeout(value),
            fg=TEXT,
            bg=CARD,
            activeforeground=TEXT,
            activebackground=SURFACE_ACTIVE,
            font=(FONT, 12, "bold"),
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            takefocus=False,
            pady=13,
        )
        button.pack(fill=X, pady=4)
        timeout_choice_buttons[seconds] = button

    def open_timeout_panel():
        nonlocal timeout_pending

        close_output_panel()
        maximum_panel.place_forget()
        brightness_panel.place_forget()
        timeout_pending = settings_service.get_screen_timeout()
        refresh_timeout_choices()
        timeout_panel.place(x=0, y=0, relwidth=1, relheight=1)
        timeout_panel.lift()

    information_panel = Frame(frame, bg=BG)

    information_header = Frame(information_panel, bg=BG)
    information_header.pack(fill=X, padx=PAGE_PAD, pady=(20, 12))
    Button(
        information_header,
        text="‹",
        command=information_panel.place_forget,
        fg=TEXT,
        bg=SURFACE_ALT,
        activeforeground=TEXT,
        activebackground=CARD,
        font=(FONT, 22, "bold"),
        relief="flat",
        borderwidth=0,
        highlightthickness=0,
        takefocus=False,
        width=3,
        pady=0,
    ).pack(side=LEFT)

    information_heading = Frame(information_header, bg=BG)
    information_heading.pack(side=LEFT, padx=(12, 0))
    Label(
        information_heading,
        text="SYSTEM",
        fg=ACCENT,
        bg=BG,
        anchor="w",
        font=(FONT, 9, "bold"),
    ).pack(fill=X)
    Label(
        information_heading,
        text="Device information",
        fg=TEXT,
        bg=BG,
        anchor="w",
        font=(FONT, 22, "bold"),
    ).pack(fill=X)

    information_canvas = Canvas(
        information_panel,
        bg=BG,
        highlightthickness=0,
        borderwidth=0,
    )
    information_canvas.pack(fill=BOTH, expand=True, padx=PAGE_PAD, pady=(4, 18))
    information_body = Frame(information_canvas, bg=BG)
    information_window = information_canvas.create_window(
        0,
        0,
        anchor="nw",
        window=information_body,
    )
    information_body.bind(
        "<Configure>",
        lambda _event: information_canvas.configure(
            scrollregion=information_canvas.bbox("all")
        ),
    )
    information_canvas.bind(
        "<Configure>",
        lambda event: information_canvas.itemconfigure(
            information_window,
            width=event.width,
        ),
    )

    information_drag_start_y = 0

    def start_information_drag(event):
        nonlocal information_drag_start_y
        information_drag_start_y = event.y_root
        information_canvas.scan_mark(
            0,
            event.y_root - information_canvas.winfo_rooty(),
        )

    def drag_information(event):
        if abs(event.y_root - information_drag_start_y) > 4:
            information_canvas.scan_dragto(
                0,
                event.y_root - information_canvas.winfo_rooty(),
                gain=1,
            )

    information_canvas.bind("<ButtonPress-1>", start_information_drag)
    information_canvas.bind("<B1-Motion>", drag_information)

    def render_device_information(items):
        if not information_panel.winfo_ismapped():
            return

        for child in information_body.winfo_children():
            child.destroy()

        card = Frame(
            information_body,
            bg=CARD,
            highlightbackground=DIVIDER,
            highlightthickness=1,
        )
        card.pack(fill=X)

        for index, (label, value) in enumerate(items):
            row = Frame(card, bg=CARD)
            row.pack(fill=X, padx=14, pady=10)
            Label(
                row,
                text=label,
                fg=TEXT_MUTED,
                bg=CARD,
                anchor="w",
                font=(FONT, 9),
            ).pack(fill=X)
            Label(
                row,
                text=value,
                fg=TEXT,
                bg=CARD,
                anchor="w",
                justify="left",
                wraplength=405,
                font=(FONT, 11, "bold"),
            ).pack(fill=X, pady=(2, 0))

            if index != len(items) - 1:
                Frame(card, bg=DIVIDER, height=1).pack(fill=X, padx=14)

            for widget in (row, *row.winfo_children()):
                widget.bind("<ButtonPress-1>", start_information_drag)
                widget.bind("<B1-Motion>", drag_information)

    def open_information_panel():
        close_output_panel()
        maximum_panel.place_forget()
        brightness_panel.place_forget()
        timeout_panel.place_forget()

        for child in information_body.winfo_children():
            child.destroy()
        Label(
            information_body,
            text="Loading device information…",
            fg=TEXT_MUTED,
            bg=BG,
            font=(FONT, 11),
        ).pack(pady=32)

        information_canvas.yview_moveto(0)
        information_panel.place(x=0, y=0, relwidth=1, relheight=1)
        information_panel.lift()

        def worker():
            items = device_info_service.get_device_information()
            root.after(0, lambda: render_device_information(items))

        Thread(target=worker, daemon=True).start()

    battery_panel = Frame(frame, bg=BG)
    battery_refresh_job = None
    battery_generation = 0

    battery_header = Frame(battery_panel, bg=BG)
    battery_header.pack(fill=X, padx=PAGE_PAD, pady=(20, 12))

    battery_heading = Frame(battery_header, bg=BG)
    battery_heading.pack(side=LEFT, padx=(12, 0))
    Label(
        battery_heading,
        text="POWER",
        fg=ACCENT,
        bg=BG,
        anchor="w",
        font=(FONT, 9, "bold"),
    ).pack(fill=X)
    Label(
        battery_heading,
        text="Battery",
        fg=TEXT,
        bg=BG,
        anchor="w",
        font=(FONT, 22, "bold"),
    ).pack(fill=X)

    battery_body = Frame(battery_panel, bg=BG)
    battery_body.pack(fill=BOTH, expand=True, padx=PAGE_PAD, pady=(4, 18))

    battery_summary = Frame(
        battery_body,
        bg=CARD,
        highlightbackground=DIVIDER,
        highlightthickness=1,
    )
    battery_summary.pack(fill=X, pady=(0, 12))

    battery_percentage = Label(
        battery_summary,
        text="--%",
        fg=TEXT,
        bg=CARD,
        font=(FONT, 42, "bold"),
    )
    battery_percentage.pack(pady=(18, 0))
    battery_status_label = Label(
        battery_summary,
        text="Loading...",
        fg=TEXT_MUTED,
        bg=CARD,
        font=(FONT, 11, "bold"),
    )
    battery_status_label.pack(pady=(0, 10))

    battery_bar = Canvas(
        battery_summary,
        height=34,
        bg=CARD,
        highlightthickness=0,
        borderwidth=0,
    )
    battery_bar.pack(fill=X, padx=28, pady=(0, 18))

    battery_details = Frame(
        battery_body,
        bg=CARD,
        highlightbackground=DIVIDER,
        highlightthickness=1,
    )
    battery_details.pack(fill=X)
    battery_detail_values = {}

    for index, detail_name in enumerate(("Status", "Charger", "Estimated time")):
        detail_row = Frame(battery_details, bg=CARD)
        detail_row.pack(fill=X, padx=14, pady=11)
        Label(
            detail_row,
            text=detail_name,
            fg=TEXT_MUTED,
            bg=CARD,
            anchor="w",
            font=(FONT, 9),
        ).pack(fill=X)
        detail_value = Label(
            detail_row,
            text="--",
            fg=TEXT,
            bg=CARD,
            anchor="w",
            justify="left",
            wraplength=405,
            font=(FONT, 11, "bold"),
        )
        detail_value.pack(fill=X, pady=(2, 0))
        battery_detail_values[detail_name] = detail_value

        if index != 2:
            Frame(battery_details, bg=DIVIDER, height=1).pack(fill=X, padx=14)

    def draw_battery_bar(percentage):
        width = max(40, battery_bar.winfo_width())
        right = width - 10
        battery_bar.delete("all")
        battery_bar.create_rectangle(
            2,
            4,
            right,
            30,
            outline=TEXT_MUTED,
            width=2,
        )
        battery_bar.create_rectangle(
            right,
            11,
            width - 2,
            23,
            fill=TEXT_MUTED,
            outline="",
        )
        fill_width = 5 + max(0, right - 9) * percentage / 100
        battery_bar.create_rectangle(
            6,
            8,
            fill_width,
            26,
            fill=ACCENT if percentage > 20 else DANGER,
            outline="",
        )

    def render_battery_status(status, generation):
        nonlocal battery_refresh_job

        if generation != battery_generation or not battery_panel.winfo_manager():
            return

        if status is None:
            battery_percentage.config(text="--%")
            battery_status_label.config(text="Unavailable", fg=DANGER)
            for value_label in battery_detail_values.values():
                value_label.config(text="--")
        else:
            percentage = status["percentage"]
            status_text = status["status"]
            battery_percentage.config(text=f"{percentage}%")
            battery_status_label.config(
                text=status_text,
                fg=ACCENT if status["power_plugged"] else TEXT_MUTED,
            )
            battery_detail_values["Status"].config(text=status_text)
            battery_detail_values["Charger"].config(
                text="Connected" if status["power_plugged"] else "Not connected"
            )
            battery_detail_values["Estimated time"].config(
                text=status["estimated_time"]
            )
            draw_battery_bar(percentage)
            if battery_value_label is not None and battery_value_label.winfo_exists():
                battery_value_label.config(text=f"{percentage}%")

        battery_refresh_job = root.after(
            5000,
            lambda: refresh_battery_panel(generation),
        )

    def refresh_battery_panel(generation):
        if generation != battery_generation or not battery_panel.winfo_manager():
            return

        def worker():
            try:
                status = battery_service.get_battery_status()
            except (KeyError, OSError, ValueError):
                status = None
            root.after(0, lambda: render_battery_status(status, generation))

        Thread(target=worker, daemon=True).start()

    def close_battery_panel():
        nonlocal battery_refresh_job, battery_generation
        battery_generation += 1
        if battery_refresh_job is not None:
            root.after_cancel(battery_refresh_job)
            battery_refresh_job = None
        battery_panel.place_forget()

    Button(
        battery_header,
        text="‹",
        command=close_battery_panel,
        fg=TEXT,
        bg=SURFACE_ALT,
        activeforeground=TEXT,
        activebackground=CARD,
        font=(FONT, 22, "bold"),
        relief="flat",
        borderwidth=0,
        highlightthickness=0,
        takefocus=False,
        width=3,
        pady=0,
    ).pack(side=LEFT, before=battery_heading)

    battery_bar.bind(
        "<Configure>",
        lambda _event: draw_battery_bar(
            int(battery_percentage.cget("text").rstrip("%"))
            if battery_percentage.cget("text") != "--%"
            else 0
        ),
    )

    def open_battery_panel():
        nonlocal battery_generation

        close_output_panel()
        maximum_panel.place_forget()
        brightness_panel.place_forget()
        timeout_panel.place_forget()
        information_panel.place_forget()
        close_battery_panel()

        battery_generation += 1
        generation = battery_generation
        battery_percentage.config(text="--%")
        battery_status_label.config(text="Loading...", fg=TEXT_MUTED)
        for value_label in battery_detail_values.values():
            value_label.config(text="--")
        draw_battery_bar(0)

        battery_panel.place(x=0, y=0, relwidth=1, relheight=1)
        battery_panel.lift()
        refresh_battery_panel(generation)

    drag_start_y = 0

    def start_drag(event):
        nonlocal drag_start_y
        drag_start_y = event.y_root
        canvas.scan_mark(0, event.y_root - canvas.winfo_rooty())

    def drag(event):
        if abs(event.y_root - drag_start_y) > 4:
            canvas.scan_dragto(
                0,
                event.y_root - canvas.winfo_rooty(),
                gain=1,
            )

    def mousewheel(event):
        canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    def finish_bluetooth_press(event):
        if abs(event.y_root - drag_start_y) <= 4:
            load_bluetooth_devices()

    def finish_output_press(event):
        if abs(event.y_root - drag_start_y) <= 4:
            load_output_devices(True)

    def finish_maximum_press(event):
        if abs(event.y_root - drag_start_y) <= 4:
            open_maximum_panel()

    def finish_brightness_press(event):
        if abs(event.y_root - drag_start_y) <= 4:
            open_brightness_panel()

    def finish_timeout_press(event):
        if abs(event.y_root - drag_start_y) <= 4:
            open_timeout_panel()

    def finish_information_press(event):
        if abs(event.y_root - drag_start_y) <= 4:
            open_information_panel()

    def finish_battery_press(event):
        if abs(event.y_root - drag_start_y) <= 4:
            open_battery_panel()

    def bind_scroll(widget):
        widget.bind("<ButtonPress-1>", start_drag)
        widget.bind("<B1-Motion>", drag)
        widget.bind("<MouseWheel>", mousewheel)
        for child in widget.winfo_children():
            bind_scroll(child)

    bind_scroll(content)
    canvas.bind("<ButtonPress-1>", start_drag)
    canvas.bind("<B1-Motion>", drag)
    canvas.bind("<MouseWheel>", mousewheel)

    for widget in bluetooth_row_widgets:
        widget.config(cursor="hand2")
        widget.bind(
            "<ButtonRelease-1>",
            finish_bluetooth_press,
        )

    for widget in output_row_widgets:
        widget.config(cursor="hand2")
        widget.bind("<ButtonRelease-1>", finish_output_press)

    for widget in maximum_row_widgets:
        widget.config(cursor="hand2")
        widget.bind("<ButtonRelease-1>", finish_maximum_press)

    for widget in brightness_row_widgets:
        widget.config(cursor="hand2")
        widget.bind(
            "<ButtonRelease-1>",
            finish_brightness_press,
        )

    for widget in timeout_row_widgets:
        widget.config(cursor="hand2")
        widget.bind(
            "<ButtonRelease-1>",
            finish_timeout_press,
        )

    for widget in information_row_widgets:
        widget.config(cursor="hand2")
        widget.bind(
            "<ButtonRelease-1>",
            finish_information_press,
        )

    for widget in battery_row_widgets:
        widget.config(cursor="hand2")
        widget.bind(
            "<ButtonRelease-1>",
            finish_battery_press,
        )

    def on_show():
        bluetooth_panel.place_forget()
        close_output_panel()
        maximum_panel.place_forget()
        brightness_panel.place_forget()
        timeout_panel.place_forget()
        information_panel.place_forget()
        close_battery_panel()
        canvas.yview_moveto(0)
        if maximum_value_label is not None and maximum_value_label.winfo_exists():
            maximum_value_label.config(
                text=f"{settings_service.get_maximum_volume()}%"
            )

        if (brightness_value_label is not None and brightness_value_label.winfo_exists()):
            brightness_value_label.config(
                text=f"{settings_service.get_brightness()}%"
            )

        if timeout_value_label is not None and timeout_value_label.winfo_exists():
            timeout_value_label.config(
                text=_format_screen_timeout(
                    settings_service.get_screen_timeout()
                )
            )

        load_bluetooth_devices(show_panel=False)
        load_output_devices()

    return {
        "frame": frame,
        "update": lambda _current_state: None,
        "on_show": on_show,
    }
