from tkinter import BOTH, LEFT, RIGHT, X, Button, Canvas, Frame, Label, Entry

from app.controller.controller_wifi import WifiController
from app.ui.components.virtual_keyboard import VirtualKeyboard
from app.ui.theme import ACCENT, BG, CARD, DANGER, DIVIDER, FONT, PAGE_PAD
from app.ui.theme import SURFACE_ALT, TEXT, TEXT_MUTED


class WifiPanel:
    def __init__(self, parent, state, summary_label):
        self.state = state
        self.summary_label = summary_label
        self.controller = WifiController(state)
        self.last_networks = None
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
        self.connection = Label(card, text="Loading…", bg=CARD, fg=TEXT,
                                font=(FONT, 13, "bold"), anchor="w", justify=LEFT, wraplength=410)
        self.connection.pack(fill=X, padx=14, pady=(0, 12))
        Label(self.frame, text="AVAILABLE NETWORKS", bg=BG, fg=TEXT_MUTED,
              font=(FONT, 9, "bold"), anchor="w").pack(fill=X, padx=PAGE_PAD, pady=(6, 10))
        self.message = Label(self.frame, text="", bg=BG, fg=TEXT_MUTED,
                             font=(FONT, 10), anchor="w", justify=LEFT, wraplength=440)
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

        Label(
            self.connection_panel,
            text="Password",
            bg=BG,
            fg=TEXT_MUTED,
            font=(FONT, 11),
            anchor="w",
        ).pack(fill=X, padx=PAGE_PAD)

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


    def _open_connection_panel(self, network):
        if self.controller.busy:
            return

        self.selected_network = dict(network)
        self.network_name.config(text=network["ssid"])
        self.connection_message.config(text="", fg=TEXT_MUTED)
        self.password_entry.config(state="normal")
        self.password_entry.delete(0, "end")

        self.connection_panel.place(
            x=0, y=0, relwidth=1, relheight=1
        )
        self.connection_panel.lift()

        if network["security"] == "Open":
            self.password_entry.config(state="disabled")
            self.connection_message.config(
                text="This network does not require a password."
            )
            self.keyboard.hide()
        else:
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
        password = self.password_entry.get()

        if network["security"] != "Open" and not password:
            self.connection_message.config(
                text="Enter the network password.",
                fg=DANGER,
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
        self.connection_back_button.config(state=button_state)
        self.refresh_button.config(state=button_state)

        is_open = (
            self.selected_network is not None
            and self.selected_network["security"] == "Open"
        )
        self.password_entry.config(
            state="disabled" if active or is_open else "normal"
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
        # Deliver completed reads to Tk; do not start periodic network queries.
        self.controller.poll(self._render)
        self.job = self.frame.after(100, self._pump)

    def _render(self, snapshot, error):
        self.refresh_button.config(state="normal")
        if error:
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
        self.connection.config(text=name)
        self.summary_label.config(text="Connected" if snapshot["connected"] else "Not connected")
        networks = snapshot["networks"]
        scan_error = snapshot.get("scan_error")
        self._set_message(
            f"Scan failed; showing cached networks. {scan_error}" if scan_error else
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
        if event.widget is self.frame and self.job is not None:
            self.frame.after_cancel(self.job)
            self.job = None
