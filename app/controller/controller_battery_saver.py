from app.controller.controller_brightness import apply_saved_brightness
from app.controller.controller_screen_timeout import apply_saved_screen_timeout
from app.services.settings_service import set_battery_saver_enabled


def set_battery_saver(enabled):
    enabled = set_battery_saver_enabled(enabled)
    brightness = apply_saved_brightness()
    screen_timeout = apply_saved_screen_timeout()

    return {
        "enabled": enabled,
        "brightness": brightness,
        "screen_timeout": screen_timeout,
    }
