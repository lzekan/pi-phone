from pathlib import Path


BACKLIGHT_DIR = Path("/sys/class/backlight/10-0045")
BRIGHTNESS_FILE = BACKLIGHT_DIR / "brightness"
MAX_BRIGHTNESS_FILE = BACKLIGHT_DIR / "max_brightness"

MIN_BRIGHTNESS_PERCENT = 10
MAX_BRIGHTNESS_PERCENT = 100


def get_brightness_percent():
    current = int(BRIGHTNESS_FILE.read_text().strip())
    maximum = int(MAX_BRIGHTNESS_FILE.read_text().strip())

    return round(current / maximum * 100)


def set_brightness_percent(percent):
    percent = max(
        MIN_BRIGHTNESS_PERCENT,
        min(MAX_BRIGHTNESS_PERCENT, int(percent)),
    )

    maximum = int(MAX_BRIGHTNESS_FILE.read_text().strip())
    raw_value = round(percent / 100 * maximum)

    BRIGHTNESS_FILE.write_text(str(raw_value))
    return percent