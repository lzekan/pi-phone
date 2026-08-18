import socket


PISUGAR_SOCKET = "/tmp/pisugar-server.sock"
REQUEST_TIMEOUT = 1.0


def get_battery_status():
    commands = (
        "get battery\n"
        "get battery_power_plugged\n"
        "get battery_charging\n"
    )

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(REQUEST_TIMEOUT)
        client.connect(PISUGAR_SOCKET)
        client.sendall(commands.encode("utf-8"))

        response = b""
        while response.count(b"\n") < 3:
            chunk = client.recv(1024)
            if not chunk:
                break
            response += chunk

    values = {}
    for line in response.decode("utf-8", errors="replace").splitlines():
        key, separator, value = line.partition(":")
        if separator:
            values[key.strip()] = value.strip()

    percentage = round(float(values["battery"]))
    return {
        "percentage": max(0, min(100, percentage)),
        "power_plugged": values.get("battery_power_plugged") == "true",
        "charging": values.get("battery_charging") == "true",
    }
