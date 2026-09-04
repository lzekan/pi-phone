from tkinter import Frame

from app.controller.controller_brightness import apply_saved_brightness
from app.services.brightness_service import turn_off_backlight
from app.services.settings_service import (
    get_effective_screen_timeout,
    set_screen_timeout,
)


_root = None
_overlay = None
_timer_job = None
_timeout_seconds = 0
_sleeping = False


def _cancel_timer():
    global _timer_job

    if _root is not None and _timer_job is not None:
        _root.after_cancel(_timer_job)
    _timer_job = None


def _schedule_timer():
    global _timer_job

    _cancel_timer()
    if _root is not None and not _sleeping and _timeout_seconds > 0:
        _timer_job = _root.after(_timeout_seconds * 1000, _sleep)


def _sleep():
    global _sleeping, _timer_job

    _timer_job = None
    if _root is None or _overlay is None:
        return

    _sleeping = True
    _overlay.place(x=0, y=0, relwidth=1, relheight=1)
    _overlay.lift()

    try:
        turn_off_backlight()
    except OSError as error:
        print(f"[SCREEN TIMEOUT ERROR] {error}")


def _wake(_event=None):
    global _sleeping

    if not _sleeping:
        return

    _sleeping = False
    if _overlay is not None:
        _overlay.place_forget()

    try:
        apply_saved_brightness()
    except (OSError, ValueError) as error:
        print(f"[SCREEN WAKE ERROR] {error}")

    _schedule_timer()
    return "break"


def _register_activity(_event=None):
    if not _sleeping:
        _schedule_timer()


def start_screen_timeout(root):
    global _root, _overlay, _timeout_seconds, _sleeping

    _root = root
    _timeout_seconds = get_effective_screen_timeout()
    _sleeping = False

    _overlay = Frame(root, bg="black", cursor="none")
    _overlay.bind("<ButtonPress-1>", _wake)
    _overlay.bind("<ButtonRelease-1>", lambda _event: "break")

    root.bind_all("<ButtonPress-1>", _register_activity, add="+")
    root.bind_all("<MouseWheel>", _register_activity, add="+")
    _schedule_timer()


def save_screen_timeout(value):
    global _timeout_seconds

    preferred = set_screen_timeout(value)
    _timeout_seconds = get_effective_screen_timeout(preferred)

    if _sleeping and _timeout_seconds == 0:
        _wake()
    else:
        _schedule_timer()

    return preferred


def apply_saved_screen_timeout():
    global _timeout_seconds

    _timeout_seconds = get_effective_screen_timeout()

    if _sleeping and _timeout_seconds == 0:
        _wake()
    else:
        _schedule_timer()

    return _timeout_seconds
