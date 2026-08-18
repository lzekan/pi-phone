import json
import os
from threading import Lock

from app.core.config import DEVICE_SETTINGS_FILE


DEFAULT_MAXIMUM_VOLUME = 100

_settings_lock = Lock()


def _read_settings_unlocked():
    try:
        with open(DEVICE_SETTINGS_FILE, encoding="utf-8") as settings_file:
            settings = json.load(settings_file)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}

    return settings if isinstance(settings, dict) else {}


def _write_settings_unlocked(settings):
    directory = os.path.dirname(DEVICE_SETTINGS_FILE)
    os.makedirs(directory, exist_ok=True)
    temporary_file = f"{DEVICE_SETTINGS_FILE}.tmp"

    with open(temporary_file, "w", encoding="utf-8") as settings_file:
        json.dump(settings, settings_file, indent=2)
        settings_file.write("\n")

    os.replace(temporary_file, DEVICE_SETTINGS_FILE)


def get_maximum_volume():
    with _settings_lock:
        settings = _read_settings_unlocked()

    try:
        value = int(settings.get("maximum_volume", DEFAULT_MAXIMUM_VOLUME))
    except (TypeError, ValueError):
        value = DEFAULT_MAXIMUM_VOLUME

    return max(0, min(100, value))


def set_maximum_volume(value):
    value = max(0, min(100, int(value)))

    with _settings_lock:
        settings = _read_settings_unlocked()
        settings["maximum_volume"] = value
        _write_settings_unlocked(settings)

    return value
