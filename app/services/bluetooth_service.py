import subprocess

AUDIO_SINK_UUID = "0000110b-0000-1000-8000-00805f9b34fb"


def _run(command, timeout=10):
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=True,
    )
    return result.stdout


def get_devices():
    output = _run(["bluetoothctl", "devices"])
    devices = []

    for line in output.splitlines():
        parts = line.split(maxsplit=2)
        if len(parts) != 3 or parts[0] != "Device":
            continue

        mac = parts[1]
        name = parts[2]

        try:
            info = _run(["bluetoothctl", "info", mac])
            if AUDIO_SINK_UUID not in info:
                continue
        except subprocess.CalledProcessError:
            continue

        devices.append({
            "mac": mac,
            "name": name,
            "paired": "Paired: yes" in info,
            "trusted": "Trusted: yes" in info,
            "connected": "Connected: yes" in info,
        })

    return sorted(
        devices,
        key=lambda device: (
            not device["connected"],
            not device["paired"],
            device["name"].lower(),
        ),
    )

def scan_devices():
    _run(["bluetoothctl", "power", "on"])
    _run(
        ["bluetoothctl", "--timeout", "8", "scan", "on"],
        timeout=12,
    )
    return get_devices()

def pair_device(mac):
    _run(["bluetoothctl", "pair", mac], timeout=30)
    _run(["bluetoothctl", "trust", mac])
    _run(["bluetoothctl", "connect", mac], timeout=15)

def connect_device(mac):
    _run(["bluetoothctl", "connect", mac], timeout=15)


def disconnect_device(mac):
    _run(["bluetoothctl", "disconnect", mac], timeout=15)

def remove_device(mac):
    _run(["bluetoothctl", "remove", mac], timeout=15)