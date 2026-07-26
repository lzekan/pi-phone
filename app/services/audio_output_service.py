import re
import subprocess


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
