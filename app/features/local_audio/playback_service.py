import json
import os
import socket
import subprocess
import time
from threading import Lock


MPV_SOCKET = "/tmp/piphone-mpv.sock"

_process = None
_process_lock = Lock()
_launch_lock = Lock()
_ipc_lock = Lock()


def _remove_socket():
    try:
        os.unlink(MPV_SOCKET)
    except FileNotFoundError:
        pass


def _stop_playback_unlocked():
    global _process

    with _process_lock:
        process = _process
        _process = None

    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=1)

    # Also clean up an mpv left behind by a previous UI process.
    subprocess.run(
        ["pkill", "-x", "mpv"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )

    _remove_socket()


def stop_playback():
    with _launch_lock:
        _stop_playback_unlocked()


def is_playback_active():
    with _process_lock:
        process = _process

    return (
        process is not None and process.poll() is None
    ) or os.path.exists(MPV_SOCKET)


def play_file(path):
    global _process

    with _launch_lock:
        _stop_playback_unlocked()
        _remove_socket()

        process = subprocess.Popen([
            "mpv",
            "--no-video",
            "--audio-display=no",
            "--really-quiet",
            f"--input-ipc-server={MPV_SOCKET}",
            path,
        ])

        with _process_lock:
            _process = process

    return process


def _send_command(command):
    message = json.dumps({"command": command}).encode("utf-8") + b"\n"

    with _ipc_lock:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(1)
            connection.connect(MPV_SOCKET)
            connection.sendall(message)

            response = b""
            while b"\n" not in response:
                chunk = connection.recv(4096)
                if not chunk:
                    break
                response += chunk

    if not response:
        return None

    data = json.loads(response.split(b"\n", 1)[0].decode("utf-8"))
    if data.get("error") != "success":
        raise RuntimeError(data.get("error") or "mpv command failed")
    return data.get("data")


def wait_until_ready(process, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        if os.path.exists(MPV_SOCKET):
            return True
        time.sleep(0.05)
    return False


def set_paused(paused):
    _send_command(["set_property", "pause", bool(paused)])


def seek_to(position_ms):
    _send_command(["seek", max(0, position_ms) / 1000, "absolute"])


def get_status():
    return {
        "progress_ms": int((_send_command(["get_property", "time-pos"]) or 0) * 1000),
        "duration_ms": int((_send_command(["get_property", "duration"]) or 0) * 1000),
        "is_playing": not bool(_send_command(["get_property", "pause"])),
    }
