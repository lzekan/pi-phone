import re
import subprocess

from app.services.settings_service import get_maximum_volume


WIRED_NODE_PREFIX = "alsa_output.platform-fe00b840.mailbox"
BLUETOOTH_NODE_PREFIX = "bluez_output."


def _run(command):
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=3,
        check=True,
    ).stdout


def _get_connected_bluetooth_names():
    output = _run(
        ["bluetoothctl", "devices", "Connected"],
    )

    names = {}
    for line in output.splitlines():
        parts = line.split(maxsplit=2)
        if len(parts) == 3 and parts[0] == "Device":
            names[parts[1].upper()] = parts[2]
    return names


def get_output_devices():
    status = _run(
        ["wpctl", "status", "-n"],
    )
    bluetooth_names = _get_connected_bluetooth_names()
    devices = []
    inside_sinks = False

    for line in status.splitlines():
        if "Sinks:" in line:
            inside_sinks = True
            continue

        if inside_sinks and "Sources:" in line:
            break

        if not inside_sinks:
            continue

        match = re.search(r"(\d+)\.\s+(\S+)", line)
        if not match:
            continue

        device_id = int(match.group(1))
        node_name = match.group(2)
        active = "*" in line[:match.start()]

        if node_name.startswith(WIRED_NODE_PREFIX):
            devices.append({
                "id": device_id,
                "node_name": node_name,
                "name": "Wired headphones",
                "type": "wired",
                "active": active,
            })
            continue

        if not node_name.startswith(BLUETOOTH_NODE_PREFIX):
            continue

        mac_match = re.search(
            r"bluez_output\.([0-9A-Fa-f_]{17})\.",
            node_name,
        )
        if not mac_match:
            continue

        mac = mac_match.group(1).replace("_", ":").upper()
        devices.append({
            "id": device_id,
            "node_name": node_name,
            "name": bluetooth_names.get(mac, f"Bluetooth {mac}"),
            "type": "bluetooth",
            "active": active,
        })

    return devices


def set_output_device(device_id):
    _run(["wpctl", "set-default", str(int(device_id))])
    enforce_maximum_volume()


def get_volume_percent():
    output = _run([
        "wpctl",
        "get-volume",
        "@DEFAULT_AUDIO_SINK@",
    ])
    match = re.search(r"Volume:\s+([0-9]+(?:\.[0-9]+)?)", output)
    if not match:
        raise RuntimeError("Unable to read PipeWire volume")
    return round(float(match.group(1)) * 100)


def set_volume_percent(volume_percent):
    maximum_volume = get_maximum_volume()
    volume_percent = max(0, min(maximum_volume, int(volume_percent)))
    _run([
        "wpctl",
        "set-volume",
        "-l",
        f"{maximum_volume / 100:.2f}",
        "@DEFAULT_AUDIO_SINK@",
        f"{volume_percent / 100:.2f}",
    ])
    return volume_percent


def enforce_maximum_volume():
    maximum_volume = get_maximum_volume()
    current_volume = get_volume_percent()
    if current_volume > maximum_volume:
        set_volume_percent(maximum_volume)
        return maximum_volume
    return current_volume


def change_volume(step_percent):
    step = abs(int(step_percent))
    direction = "+" if step_percent > 0 else "-"
    maximum_volume = get_maximum_volume()
    _run([
        "wpctl",
        "set-volume",
        "-l",
        f"{maximum_volume / 100:.2f}",
        "@DEFAULT_AUDIO_SINK@",
        f"{step}%{direction}",
    ])
    return get_volume_percent()
