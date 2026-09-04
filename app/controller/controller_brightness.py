from app.services.brightness_service import set_brightness_percent
from app.services.settings_service import (
    get_effective_brightness,
    set_brightness,
)


def apply_saved_brightness():
    brightness = get_effective_brightness()
    return set_brightness_percent(brightness)


def save_brightness(value):
    preferred = set_brightness(value)
    set_brightness_percent(get_effective_brightness(preferred))
    return preferred



def preview_brightness(value):
    return set_brightness_percent(get_effective_brightness(value))
