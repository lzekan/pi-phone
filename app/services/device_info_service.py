import os
import platform
import shutil
import socket
import subprocess
from pathlib import Path


PISUGAR_SOCKET = "/tmp/pisugar-server.sock"


def _read_text(path):
    return Path(path).read_text(encoding="utf-8", errors="replace").strip("\0\n ")


def _run(command):
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def _format_gib(size_bytes):
    return f"{size_bytes / (1024 ** 3):.1f} GB"


def _format_uptime(seconds):
    total_minutes = max(0, int(seconds)) // 60
    days, remaining_minutes = divmod(total_minutes, 24 * 60)
    hours, minutes = divmod(remaining_minutes, 60)

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


def _get_os_name():
    try:
        for line in _read_text("/etc/os-release").splitlines():
            if line.startswith("PRETTY_NAME="):
                return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return platform.system()


def _get_memory_usage():
    try:
        values = {}
        for line in _read_text("/proc/meminfo").splitlines():
            key, value = line.split(":", 1)
            if key in ("MemTotal", "MemAvailable"):
                values[key] = int(value.split()[0]) * 1024

        total = values["MemTotal"]
        used = total - values["MemAvailable"]
        return f"{_format_gib(used)} used of {_format_gib(total)}"
    except (KeyError, OSError, ValueError, IndexError):
        pass
    return "Unavailable"


def _pisugar_request(command):
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(1)
            connection.connect(PISUGAR_SOCKET)
            connection.sendall(f"{command}\n".encode("utf-8"))
            connection.shutdown(socket.SHUT_WR)

            response = b""
            while b"\n" not in response:
                chunk = connection.recv(1024)
                if not chunk:
                    break
                response += chunk
    except (OSError, TimeoutError):
        return ""

    text = response.decode("utf-8", errors="replace").strip()
    if ":" not in text:
        return ""
    return text.split(":", 1)[1].strip()


def get_device_information():
    try:
        model = _read_text("/proc/device-tree/model")
    except OSError:
        model = platform.machine()

    try:
        temperature = int(_read_text("/sys/class/thermal/thermal_zone0/temp")) / 1000
        temperature_text = f"{temperature:.1f} °C"
    except (OSError, ValueError):
        temperature_text = "Unavailable"

    try:
        uptime_text = _format_uptime(float(_read_text("/proc/uptime").split()[0]))
    except (OSError, ValueError, IndexError):
        uptime_text = "Unavailable"

    storage = shutil.disk_usage("/")
    storage_text = f"{_format_gib(storage.free)} free of {_format_gib(storage.total)}"

    ip_addresses = _run(["hostname", "-I"]).split()
    ip_address = ip_addresses[0] if ip_addresses else "Not connected"
    wifi_network = _run(
        ["nmcli", "-g", "GENERAL.CONNECTION", "device", "show", "wlan0"]
    ) or "Not connected"
    pisugar_model = _pisugar_request("get model")
    pisugar_version = _pisugar_request("get version")
    if pisugar_model and pisugar_version:
        pisugar = f"{pisugar_model} · server {pisugar_version}"
    else:
        pisugar = pisugar_model or "Unavailable"

    return (
        ("Device name", "PiPhone"),
        ("Board", model),
        ("Operating system", _get_os_name()),
        ("Memory", _get_memory_usage()),
        ("Storage", storage_text),
        ("Wi-Fi network", wifi_network),
        ("IP address", ip_address),
        ("CPU temperature", temperature_text),
        ("Uptime", uptime_text),
        ("Battery module", pisugar),
    )
