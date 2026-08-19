import socket
from collections import deque
from threading import Lock


PISUGAR_SOCKET = "/tmp/pisugar-server.sock"
REQUEST_TIMEOUT = 1.0
BATTERY_CAPACITY_AH = 5.0

_current_samples = deque(maxlen=12)
_samples_lock = Lock()
_sample_mode = None


def _format_estimate(hours, suffix):
    total_minutes = max(1, round(hours * 60))
    whole_hours, minutes = divmod(total_minutes, 60)
    if whole_hours:
        value = f"{whole_hours} h {minutes} min"
    else:
        value = f"{minutes} min"
    return f"About {value} {suffix}"


def _estimate_time(percentage, current, charging, power_plugged):
    if power_plugged and percentage >= 99:
        return "Fully charged"
    if power_plugged and not charging:
        return "Not charging"

    current = abs(current)
    if current < 0.05:
        return "Calculating..."

    if charging:
        remaining_ah = BATTERY_CAPACITY_AH * (100 - percentage) / 100
        return _format_estimate(remaining_ah / current, "until full")

    remaining_ah = BATTERY_CAPACITY_AH * percentage / 100
    return _format_estimate(remaining_ah / current, "remaining")


def get_battery_status():
    commands = (
        "get battery\n"
        "get battery_power_plugged\n"
        "get battery_charging\n"
        "get battery_i\n"
    )

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(REQUEST_TIMEOUT)
        client.connect(PISUGAR_SOCKET)
        client.sendall(commands.encode("utf-8"))

        response = b""
        while response.count(b"\n") < 4:
            chunk = client.recv(1024)
            if not chunk:
                break
            response += chunk

    values = {}
    for line in response.decode("utf-8", errors="replace").splitlines():
        key, separator, value = line.partition(":")
        if separator:
            values[key.strip()] = value.strip()

    percentage = max(0, min(100, round(float(values["battery"]))))
    power_plugged = values.get("battery_power_plugged") == "true"
    # PiSugar 2 Pro can briefly report battery_charging=true while running
    # from the battery. Charging is only physically possible with input power.
    charging = (
        power_plugged
        and values.get("battery_charging") == "true"
    )
    current = float(values.get("battery_i", 0))

    if power_plugged and percentage >= 99:
        status = "Full"
    elif charging:
        status = "Charging"
    elif power_plugged:
        status = "Plugged in"
    else:
        status = "Discharging"

    mode = "charging" if charging else "plugged" if power_plugged else "battery"
    global _sample_mode
    with _samples_lock:
        if mode != _sample_mode:
            _current_samples.clear()
            _sample_mode = mode
        _current_samples.append(current)
        average_current = sum(_current_samples) / len(_current_samples)

    return {
        "percentage": percentage,
        "power_plugged": power_plugged,
        "charging": charging,
        "status": status,
        "power_source": "Charger" if power_plugged else "Battery",
        "estimated_time": _estimate_time(
            percentage,
            average_current,
            charging,
            power_plugged,
        ),
    }
