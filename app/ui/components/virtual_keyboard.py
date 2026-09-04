from tkinter import BOTH
from tkinter import Button, Frame


class VirtualKeyboard:
    KEY_BG = "#2A2A2A"
    KEY_ACTIVE_BG = "#424242"
    ACCENT = "#1DB954"
    LAYOUTS = {
        "letters": "qwertyuiop" "asdfghjkl" "zxcvbnm",
        "numbers": "1234567890" "@#$%&-+()" "*\"':;!?",
        "symbols": "[]{}<>_=\\/" "~`^|€£¥•°" ".,:;!?+",
    }

    def __init__(self, parent):
        self.parent = parent
        self.target = None
        self.on_submit = None
        self.on_close = None
        self.strip_on_submit = True
        self.shifted = False
        self.layout = "letters"
        self.letter_buttons = []

        self.frame = Frame(
            parent,
            bg="#101010",
            highlightbackground="#333333",
            highlightthickness=1,
        )

        self._add_letter_row("qwertyuiop")
        self._add_letter_row("asdfghjkl", horizontal_padding=18)
        self._add_action_letter_row()
        self._add_bottom_row()

    def _button(self, parent, text, command, bg=None, active_bg=None, font_size=13):
        normal_bg = bg or self.KEY_BG
        pressed_bg = active_bg or self.KEY_ACTIVE_BG
        button = Button(
            parent,
            text=text,
            fg="white",
            bg=normal_bg,
            activeforeground="white",
            activebackground=normal_bg,
            font=("DejaVu Sans", font_size, "bold"),
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            takefocus=False,
        )

        def run_command():
            try:
                command()
            finally:
                resting_bg = button.cget("bg")
                button.config(bg=pressed_bg, activebackground=pressed_bg)
                button.after(
                    80,
                    lambda: button.config(
                        bg=resting_bg,
                        activebackground=resting_bg,
                    ),
                )

        button.config(command=run_command)
        return button

    def _add_letter_row(self, letters, horizontal_padding=4):
        row = Frame(self.frame, bg="#101010")
        row.pack(fill=BOTH, expand=True, padx=horizontal_padding, pady=2)

        for column, letter in enumerate(letters):
            index = len(self.letter_buttons)
            button = self._button(
                row,
                letter,
                lambda key=index: self._insert_key(key),
            )
            button.config(width=1)
            button.grid(row=0, column=column, sticky="nsew", padx=2)
            row.grid_columnconfigure(column, weight=1, uniform="keyboard_letter")
            self.letter_buttons.append((button, letter))

        row.grid_rowconfigure(0, weight=1)

    def _add_action_letter_row(self):
        row = Frame(self.frame, bg="#101010")
        row.pack(fill=BOTH, expand=True, padx=4, pady=2)

        self.shift_button = self._button(row, "SHIFT", self._toggle_shift, font_size=11)
        self.shift_button.grid(row=0, column=0, sticky="nsew", padx=2)
        row.grid_columnconfigure(0, weight=2)

        for column, letter in enumerate("zxcvbnm", start=1):
            index = len(self.letter_buttons)
            button = self._button(
                row,
                letter,
                lambda key=index: self._insert_key(key),
            )
            button.config(width=1)
            button.grid(row=0, column=column, sticky="nsew", padx=2)
            row.grid_columnconfigure(column, weight=1, uniform="keyboard_letter")
            self.letter_buttons.append((button, letter))

        backspace = self._button(row, "BACK", self._backspace, font_size=11)
        backspace.grid(row=0, column=8, sticky="nsew", padx=2)
        row.grid_columnconfigure(8, weight=2)
        row.grid_rowconfigure(0, weight=1)

    def _add_bottom_row(self):
        row = Frame(self.frame, bg="#101010")
        row.pack(fill=BOTH, expand=True, padx=4, pady=(2, 5))

        self.mode_button = self._button(row, "123", self._toggle_layout, font_size=11)
        self.mode_button.grid(row=0, column=0, sticky="nsew", padx=2)

        close = self._button(row, "CLOSE", self._close, font_size=11)
        close.grid(row=0, column=1, sticky="nsew", padx=2)

        space = self._button(row, "SPACE", lambda: self._insert_text(" "), font_size=11)
        space.grid(row=0, column=2, sticky="nsew", padx=2)

        self.submit_button = self._button(
            row,
            "SEARCH",
            self._submit,
            bg=self.ACCENT,
            active_bg="#169C46",
            font_size=11,
        )
        self.submit_button.grid(row=0, column=3, sticky="nsew", padx=2)

        row.grid_columnconfigure(0, weight=2)
        row.grid_columnconfigure(1, weight=2)
        row.grid_columnconfigure(2, weight=4)
        row.grid_columnconfigure(3, weight=3)
        row.grid_rowconfigure(0, weight=1)

    def show(
        self,
        target,
        on_submit=None,
        on_close=None,
        submit_text="SEARCH",
        strip_on_submit=True,
    ):
        self.target = target
        self.on_submit = on_submit
        self.on_close = on_close
        self.strip_on_submit = strip_on_submit
        self.submit_button.config(text=submit_text)

        self.layout = "letters"
        self._set_shift(False)

        self.frame.place(
            relx=0,
            rely=1,
            anchor="sw",
            relwidth=1,
            height=250,
        )
        self.frame.lift()
        target.focus_set()

    def hide(self):
        self.frame.place_forget()

    def _close(self):
        self.hide()
        if self.on_close is not None:
            self.on_close()

    def _selection_range(self):
        if self.target is None:
            return None
        try:
            return self.target.index("sel.first"), self.target.index("sel.last")
        except Exception:
            return None

    def _insert_text(self, value):
        if self.target is None:
            return

        selection = self._selection_range()
        if selection:
            self.target.delete(*selection)
            self.target.icursor(selection[0])

        self.target.insert("insert", value)
        self.target.focus_set()

    def _insert_key(self, index):
        value = self.LAYOUTS[self.layout][index]
        self._insert_text(value.upper() if self.layout == "letters" and self.shifted else value)
        if self.layout == "letters" and self.shifted:
            self._set_shift(False)

    def _backspace(self):
        if self.target is None:
            return

        selection = self._selection_range()
        if selection:
            self.target.delete(*selection)
        else:
            cursor = self.target.index("insert")
            if cursor > 0:
                self.target.delete(cursor - 1, cursor)

        self.target.focus_set()

    def _toggle_shift(self):
        if self.layout == "letters":
            self._set_shift(not self.shifted)
        else:
            self.layout = "symbols" if self.layout == "numbers" else "numbers"
            self._update_keys()

    def _toggle_layout(self):
        self.layout = "numbers" if self.layout == "letters" else "letters"
        self._set_shift(False)

    def _set_shift(self, shifted):
        self.shifted = shifted
        self._update_keys()

    def _update_keys(self):
        letters = self.layout == "letters"
        self.mode_button.config(text="123" if letters else "ABC")
        self.shift_button.config(
            text="SHIFT" if letters else "2/2" if self.layout == "numbers" else "1/2",
            bg=self.ACCENT if letters and self.shifted else self.KEY_BG,
        )
        for (button, _), value in zip(self.letter_buttons, self.LAYOUTS[self.layout]):
            button.config(text=value.upper() if letters and self.shifted else value)

    def _submit(self):
        value = self.target.get() if self.target is not None else ""

        if self.strip_on_submit:
            value = value.strip()

        callback = self.on_submit
        self.hide()

        if callback is not None:
            callback(value)
