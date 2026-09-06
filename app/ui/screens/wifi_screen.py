from tkinter import BOTH, LEFT, RIGHT, X, Button, Canvas, Frame, Label, Entry

from app.controller.controller_wifi import WifiController
from app.ui.components.virtual_keyboard import VirtualKeyboard
from app.ui.theme import ACCENT, BG, CARD, DANGER, DIVIDER, FONT, PAGE_PAD
from app.ui.theme import SURFACE_ALT, TEXT, TEXT_MUTED


def _valid_wifi_password(password):
    # WPA/WPA2/WPA3 Personal accepts an 8-63 character passphrase or
    # an exactly 64-character hexadecimal pre-shared key.
    if 8 <= len(password) <= 63:
        return True
    return (
        len(password) == 64
        and all(character in "0123456789abcdefABCDEF" for character in password)
    )


class WifiPanel:
    def __init__(self, parent, state, summary_label):
        self.state = state
        self.summary_label = summary_label
        self.controller = WifiController(state)
        self.last_networks = None
        self.radio_enabled = None
        self.radio_refresh_job = None
        self.drag_y = 0
        self.frame = Frame(parent, bg=BG)
        header = Frame(self.frame, bg=BG)
        header.pack(fill=X, padx=PAGE_PAD, pady=(20, 12))
        self._button(header, "‹", self.hide).pack(side=LEFT)
        Label(header, text="Wi-Fi", bg=BG, fg=TEXT,
              font=(FONT, 22, "bold")).pack(side=LEFT, padx=12)
        self.refresh_button = self._button(header, "Refresh", lambda: self.refresh(True))
        self.refresh_button.pack(side=RIGHT)

        card = Frame(self.frame, bg=CARD, highlightbackground=DIVIDER, highlightthickness=1)
        card.pack(fill=X, padx=PAGE_PAD, pady=(2, 10))
        Label(card, text="CURRENT CONNECTION", bg=CARD, fg=ACCENT,
              font=(FONT, 9, "bold"), anchor="w").pack(fill=X, padx=14, pady=(12, 4))
        status_row = Frame(card, bg=CARD)
        status_row.pack(fill=X, padx=14, pady=(0, 12))
        self.connection = Label(
            status_row,
            text="Loading…",
            bg=CARD,
            fg=TEXT,
            font=(FONT, 13, "bold"),
            anchor="w",
            justify=LEFT,
            wraplength=300,
        )
        self.connection.pack(side=LEFT, fill=X, expand=True)
        self.radio_toggle = self._button(
            status_row,
            "…",
            self._toggle_wifi,
        )
        self.radio_toggle.config(
            state="disabled",
            width=7,
            padx=8,
            pady=8,
        )
        self.radio_toggle.pack(side=RIGHT, padx=(10, 0))
        Label(self.frame, text="AVAILABLE NETWORKS", bg=BG, fg=TEXT_MUTED,
              font=(FONT, 9, "bold"), anchor="w").pack(fill=X, padx=PAGE_PAD, pady=(6, 10))
        self.message = Label(self.frame, text="", bg=BG, fg=TEXT_MUTED,
                             font=(FONT, 10), anchor="w", justify=LEFT, wraplength=440)
        self.spotify_status = Label(
            self.frame,
            text="",
            bg=BG,
            fg=TEXT_MUTED,
            font=(FONT, 10),
            anchor="w",
            justify=LEFT,
            wraplength=440,
        )
        self.canvas = Canvas(self.frame, bg=BG, highlightthickness=0)
        self.canvas.pack(fill=BOTH, expand=True, padx=PAGE_PAD, pady=(0, 14))
        self.body = Frame(self.canvas, bg=BG)
        window = self.canvas.create_window(0, 0, anchor="nw", window=self.body)
        self.body.bind("<Configure>", lambda _: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(window, width=e.width))
        self._bind_scroll(self.canvas)
        self.selected_network = None
        self.connecting = False
        self._create_connection_panel()
        self.validation_popup_job = None
        self.job = self.frame.after(100, self._pump)
        self.frame.bind("<Destroy>", self._destroy, add="+")

    @staticmethod
    def _button(parent, text, command):
        return Button(parent, text=text, command=command, bg=SURFACE_ALT, fg=TEXT,
                      activebackground=CARD, activeforeground=TEXT, font=(FONT, 12, "bold"),
                      relief="flat", borderwidth=0, highlightthickness=0,
                      takefocus=False, padx=14, pady=12)

    def show(self):
        self.frame.place(x=0, y=0, relwidth=1, relheight=1)
        self.frame.lift()
        self.refresh(False)

    def _toggle_wifi(self):
        if self.controller.busy or self.radio_enabled is None:
            return

        enable = not self.radio_enabled
        started = self.controller.set_radio_enabled(
            enable,
            on_done=self._on_radio_done,
        )
        if not started:
            return

        self.radio_toggle.config(
            text="…",
            state="disabled",
            bg=SURFACE_ALT,
        )
        self.refresh_button.config(state="disabled")
        self._set_message(
            "Turning Wi-Fi on…" if enable else "Turning Wi-Fi off…"
        )

    def _on_radio_done(self, snapshot, error):
        if snapshot is not None:
            self._render(snapshot, None)
        else:
            self._render(
                None,
                "Could not read the current Wi-Fi status.",
            )

        if error:
            self._set_message(error, DANGER)
            return

        if snapshot["radio_enabled"]:
            self._set_message("Wi-Fi turned on. Reconnecting…", ACCENT)

            if self.radio_refresh_job is not None:
                self.frame.after_cancel(self.radio_refresh_job)
            self.radio_refresh_job = self.frame.after(
                2000,
                self._refresh_after_radio_on,
            )
        else:
            self._set_message("Wi-Fi is turned off.")

    def _refresh_after_radio_on(self):
        self.radio_refresh_job = None
        if self.frame.winfo_ismapped() and not self.controller.busy:
            self.refresh(False)

    def _create_connection_panel(self):
        self.connection_panel = Frame(self.frame, bg=BG)

        header = Frame(self.connection_panel, bg=BG)
        header.pack(fill=X, padx=PAGE_PAD, pady=(20, 12))

        self.connection_back_button = self._button(
            header, "‹", self._close_connection_panel
        )
        self.connection_back_button.pack(side=LEFT)

        Label(
            header,
            text="Connect to Wi-Fi",
            bg=BG,
            fg=TEXT,
            font=(FONT, 18, "bold"),
        ).pack(side=LEFT, padx=12)

        self.network_name = Label(
            self.connection_panel,
            bg=BG,
            fg=ACCENT,
            font=(FONT, 14, "bold"),
            wraplength=440,
            justify=LEFT,
            anchor="w",
        )
        self.network_name.pack(
            fill=X, padx=PAGE_PAD, pady=(10, 20)
        )

        self.use_saved_profile = False

        self.password_label = Label(
            self.connection_panel,
            text="Password",
            bg=BG,
            fg=TEXT_MUTED,
            font=(FONT, 11),
            anchor="w",
        )
        self.password_label.pack(fill=X, padx=PAGE_PAD)

        self.password_entry = Entry(
            self.connection_panel,
            show="*",
            bg=CARD,
            fg=TEXT,
            insertbackground=TEXT,
            font=(FONT, 14),
            relief="flat",
        )
        self.password_entry.pack(
            fill=X, padx=PAGE_PAD, pady=(8, 16), ipady=10
        )
        self.password_entry.bind(
            "<ButtonRelease-1>",
            lambda event: self._show_password_keyboard(),
        )

        self.connect_button = self._button(
            self.connection_panel,
            "CONNECT",
            self._connect_selected,
        )
        self.connect_button.pack(anchor="e", padx=PAGE_PAD)

        self.change_password_button = self._button(
            self.connection_panel,
            "Change password",
            self._change_password,
        )

        self.connection_message = Label(
            self.connection_panel,
            text="",
            bg=BG,
            fg=TEXT_MUTED,
            font=(FONT, 11),
            wraplength=440,
            justify=LEFT,
            anchor="w",
        )
        self.connection_message.pack(
            fill=X, padx=PAGE_PAD, pady=12
        )

        self.keyboard = VirtualKeyboard(self.connection_panel)

        self.validation_popup = Label(
            self.connection_panel,
            text="",
            bg=CARD,
            fg=DANGER,
            font=(FONT, 11, "bold"),
            justify="center",
            wraplength=360,
            padx=18,
            pady=12,
            relief="solid",
            borderwidth=1,
        )


    def _hide_validation_popup(self):
        self.validation_popup_job = None
        self.validation_popup.place_forget()


    def _show_validation_popup(self, text):
        if self.validation_popup_job is not None:
            self.frame.after_cancel(self.validation_popup_job)

        self.validation_popup.config(text=text)
        self.validation_popup.place(
            relx=0.5,
            rely=0.12,
            anchor="n",
        )
        self.validation_popup.lift()
        self.validation_popup_job = self.frame.after(
            2500,
            self._hide_validation_popup,
        )


    def _open_connection_panel(self, network):
        if self.controller.busy:
            return

        self.selected_network = dict(network)
        is_open = network["security"] == "Open"
        self.use_saved_profile = (
            bool(network.get("saved")) and not is_open
        )

        self.keyboard.hide()
        if self.validation_popup_job is not None:
            self.frame.after_cancel(self.validation_popup_job)
            self.validation_popup_job = None
        self.validation_popup.place_forget()
        self.network_name.config(text=network["ssid"])
        self.connection_message.config(text="", fg=TEXT_MUTED)

        self.password_entry.config(state="normal")
        self.password_entry.delete(0, "end")
        self.password_label.pack_forget()
        self.password_entry.pack_forget()
        self.change_password_button.pack_forget()

        self._set_connecting(False)

        self.connection_panel.place(
            x=0, y=0, relwidth=1, relheight=1
        )
        self.connection_panel.lift()

        if is_open:
            self.connection_message.config(
                text="This network does not require a password."
            )
        elif self.use_saved_profile:
            self.connection_message.config(
                text="CONNECT will use the saved network profile."
            )
            self.change_password_button.pack(
                anchor="e",
                padx=PAGE_PAD,
                pady=(10, 0),
                before=self.connection_message,
            )
        else:
            self._show_password_fields()
            self._show_password_keyboard()

    def _show_password_fields(self):
        self.password_label.pack(
            fill=X,
            padx=PAGE_PAD,
            before=self.connect_button,
        )
        self.password_entry.pack(
            fill=X,
            padx=PAGE_PAD,
            pady=(8, 16),
            ipady=10,
            before=self.connect_button,
        )

    def _change_password(self):
        if self.connecting or self.selected_network is None:
            return

        self.use_saved_profile = False
        self.change_password_button.pack_forget()
        self.password_entry.config(state="normal")
        self.password_entry.delete(0, "end")
        self.connection_message.config(
            text="Enter the new network password.",
            fg=TEXT_MUTED,
        )
        self._show_password_fields()
        self._show_password_keyboard()


    def _show_password_keyboard(self):
        if self.password_entry.cget("state") == "disabled":
            return

        self.keyboard.show(
            self.password_entry,
            on_submit=lambda password: self._connect_selected(),
            submit_text="CONNECT",
            strip_on_submit=False,
        )


    def _close_connection_panel(self):
        if self.connecting:
            return
        
        self.keyboard.hide()
        if self.validation_popup_job is not None:
            self.frame.after_cancel(self.validation_popup_job)
            self.validation_popup_job = None
        self.validation_popup.place_forget()
        self.password_entry.config(state="normal")
        self.password_entry.delete(0, "end")
        self.selected_network = None
        self.connection_panel.place_forget()


    def _connect_selected(self):
        if self.connecting or self.controller.busy:
            return

        if self.selected_network is None:
            return

        interface = self.state.get("wifi", {}).get("interface")
        if not interface:
            self.connection_message.config(
                text="Return to the network list and press Refresh.",
                fg=DANGER,
            )
            return

        network = dict(self.selected_network)

        password = (
            "" if self.use_saved_profile
            else self.password_entry.get()
        )

        if (
            network["security"] != "Open"
            and not self.use_saved_profile
            and not password
        ):
            self._show_validation_popup(
                "Enter the network password."
            )
            return

        if (
            network["security"] != "Open"
            and not self.use_saved_profile
            and not _valid_wifi_password(password)
        ):
            self._show_validation_popup(
                "Password must contain at least 8 characters."
            )
            return

        started = self.controller.connect(
            interface,
            network,
            password,
            on_done=self._on_connection_done,
        )

        if not started:
            return

        self.keyboard.hide()
        self._set_connecting(True)
        self.connection_message.config(
            text="Connecting…",
            fg=TEXT_MUTED,
        )


    def _set_connecting(self, active):
        self.connecting = active
        button_state = "disabled" if active else "normal"

        self.connect_button.config(state=button_state)
        self.change_password_button.config(state=button_state)
        self.connection_back_button.config(state=button_state)
        self.refresh_button.config(state=button_state)

        is_open = (
            self.selected_network is not None
            and self.selected_network["security"] == "Open"
        )

        self.password_entry.config(
            state=(
                "disabled"
                if active or is_open or self.use_saved_profile
                else "normal"
            )
        )


    def _on_connection_done(self, snapshot, error):
        self._set_connecting(False)

        # Osvježi stvarno stanje i ako povezivanje nije uspjelo.
        if snapshot is not None:
            self._render(snapshot, None)
        else:
            self._render(
                None,
                "Could not read the current Wi-Fi status. Press Refresh.",
            )

        if error:
            self.connection_message.config(
                text=error,
                fg=DANGER,
            )
            return

        self._close_connection_panel()
        self._set_message("Connected to Wi-Fi.", ACCENT)

    def hide(self):
        self._close_connection_panel()
        self.frame.place_forget()

    def refresh(self, rescan=False):
        if rescan and self.radio_enabled is False:
            self._set_message("Turn Wi-Fi on before scanning for networks.")
            return

        if self.controller.refresh(rescan):
            self.refresh_button.config(state="disabled")
            self._set_message("Scanning…" if rescan else "Reading networks…")

    def _set_message(self, text, color=TEXT_MUTED):
        self.message.config(text=text, fg=color)
        if text:
            self.message.pack(fill=X, padx=PAGE_PAD, pady=(0, 10), before=self.canvas)
        else:
            self.message.pack_forget()

    def _pump(self):
        self.controller.poll(self._render)

        reconnecting = self.state.get(
            "spotify_reconnecting", False
        )
        error = self.state.get("spotify_reconnect_error")

        if reconnecting and not self.connecting:
            text = (
                "Reconnecting Spotify… "
            )
            color = TEXT_MUTED
        elif not reconnecting and error:
            text = (
                f"Spotify: {error}\n"
                "You can retry CONNECT or choose another Wi-Fi network."
            )
            color = DANGER
        else:
            text = ""
            color = TEXT_MUTED

        if self.spotify_status.cget("text") != text:
            self.spotify_status.config(text=text, fg=color)

            if text:
                self.spotify_status.pack(
                    fill=X,
                    padx=PAGE_PAD,
                    pady=(0, 10),
                    before=self.canvas,
                )
            else:
                self.spotify_status.pack_forget()

        self.job = self.frame.after(100, self._pump)

    def _render(self, snapshot, error):
        if error:
            self.refresh_button.config(state="normal")
            self.radio_toggle.config(state="disabled", text="…")
            self.radio_enabled = None
            self._set_message(error, DANGER)
            self.connection.config(text="Status unavailable")
            self.summary_label.config(text="Unavailable")
            self.last_networks = None
            for child in self.body.winfo_children():
                child.destroy()
            return
        name = snapshot["connection"] if snapshot["connected"] else "Not connected"
        if snapshot["interface"] is None:
            name = "No Wi-Fi adapter found"
        elif not snapshot["radio_enabled"]:
            name = "Wi-Fi is off"
        self.radio_enabled = snapshot["radio_enabled"]
        self.connection.config(text=name)
        self.summary_label.config(
            text=(
                "Off"
                if not snapshot["radio_enabled"]
                else "Connected" if snapshot["connected"] else "Not connected"
            )
        )
        self.radio_toggle.config(
            text="ON" if snapshot["radio_enabled"] else "OFF",
            state="normal" if snapshot["interface"] is not None else "disabled",
            bg=ACCENT if snapshot["radio_enabled"] else SURFACE_ALT,
        )
        self.refresh_button.config(
            state=(
                "normal"
                if snapshot["interface"] is not None
                and snapshot["radio_enabled"]
                else "disabled"
            )
        )
        networks = snapshot["networks"]
        scan_error = snapshot.get("scan_error")
        self._set_message(
            f"Scan failed; showing cached networks. {scan_error}" if scan_error else
            "Wi-Fi is turned off." if not snapshot["radio_enabled"] else
            "" if networks else "No visible networks found.",
            DANGER if scan_error else TEXT_MUTED)
        if networks == self.last_networks:
            return
        self.last_networks = networks
        position = self.canvas.yview()[0]
        for child in self.body.winfo_children():
            child.destroy()
        for network in networks:
            row = Frame(self.body, bg=CARD, highlightbackground=DIVIDER, highlightthickness=1)
            row.pack(fill=X, pady=(0, 7))
            Label(row, text=network["ssid"], bg=CARD,
                  fg=ACCENT if network["connected"] else TEXT,
                  font=(FONT, 12, "bold"), anchor="w", justify=LEFT, wraplength=410
                  ).pack(fill=X, padx=14, pady=(12, 5))
            detail = f"{network['security']}  ·  Signal {network['signal']}%"
            if network["connected"]:
                detail = "Connected  ·  " + detail
            Label(row, text=detail, bg=CARD, fg=TEXT_MUTED, font=(FONT, 10),
                  anchor="w", wraplength=410, justify=LEFT).pack(fill=X, padx=14, pady=(0, 12))
            self._bind_scroll(row, network)
        self.canvas.update_idletasks()
        self.canvas.yview_moveto(position)

    def _start_drag(self, event):
        self.drag_y = event.y_root
        self.canvas.scan_mark(0, event.y_root - self.canvas.winfo_rooty())

    def _drag(self, event):
        if abs(event.y_root - self.drag_y) > 4:
            self.canvas.scan_dragto(0, event.y_root - self.canvas.winfo_rooty(), gain=1)

    def _bind_scroll(self, widget, network=None):
        widget.bind("<ButtonPress-1>", self._start_drag)
        widget.bind("<B1-Motion>", self._drag)

        widget.bind(
            "<MouseWheel>",
            lambda e: self.canvas.yview_scroll(
                -1 if e.delta > 0 else 1, "units"
            ),
        )
        widget.bind(
            "<Button-4>",
            lambda _: self.canvas.yview_scroll(-1, "units"),
        )
        widget.bind(
            "<Button-5>",
            lambda _: self.canvas.yview_scroll(1, "units"),
        )

        if network is not None:
            widget.bind(
                "<ButtonRelease-1>",
                lambda event, item=network:
                    self._on_network_release(event, item),
            )

        for child in widget.winfo_children():
            self._bind_scroll(child, network)


    def _on_network_release(self, event, network):
        if abs(event.y_root - self.drag_y) <= 4:
            self._open_connection_panel(network)

    def _destroy(self, event):
        if event.widget is self.frame:
            if self.validation_popup_job is not None:
                self.frame.after_cancel(self.validation_popup_job)
                self.validation_popup_job = None
            if self.job is not None:
                self.frame.after_cancel(self.job)
                self.job = None
            if self.radio_refresh_job is not None:
                self.frame.after_cancel(self.radio_refresh_job)
                self.radio_refresh_job = None
