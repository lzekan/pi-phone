from app.services.brightness_service import set_brightness_percent
from app.services.settings_service import get_brightness, set_brightness


def apply_saved_brightness():
    brightness = get_brightness()
    return set_brightness_percent(brightness)


def save_brightness(value):
    brightness = set_brightness(value)
    return set_brightness_percent(brightness)



def preview_brightness(value):
    return set_brightness_percent(value)