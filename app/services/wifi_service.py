import os
import subprocess
import time


class WifiError(RuntimeError):
    pass


def _run(arguments):
    try:
        result = subprocess.run(
            ["nmcli", "--terse", "--escape", "yes", "--wait", "10", *arguments],
            capture_output=True, text=True, timeout=15,
            env={**os.environ, "LC_ALL": "C"}, check=False,
        )
    except FileNotFoundError as error:
        raise WifiError("NetworkManager tools are not installed.") from error
    except subprocess.TimeoutExpired as error:
        raise WifiError("Wi-Fi query timed out. Try refreshing again.") from error
    except OSError as error:
        raise WifiError("Could not read Wi-Fi information.") from error
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise WifiError(detail or "NetworkManager could not complete the request.")
    return result.stdout


def _split_row(line):
    
    fields, current, escaped = [], [], False
    for character in line:
        if escaped:
            current.append(character)
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == ":":
            fields.append("".join(current))
            current = []
        else:
            current.append(character)
    if escaped:
        current.append("\\")
    fields.append("".join(current))
    return fields


def _networks(output):
    networks = {}
    for line in output.splitlines():
        fields = _split_row(line)
        if len(fields) != 5:
            continue
        active, ssid, bssid, signal, security = fields
        if not ssid:
            continue  # Hidden networks have no selectable name in this first step.
        try:
            signal = max(0, min(100, int(signal)))
        except ValueError:
            continue
        item = {"ssid": ssid, "bssid": bssid, "signal": signal,
                "security": security if security not in ("", "--") else "Open",
                "connected": active == "*"}
        key = (ssid, item["security"])
        previous = networks.get(key)
        if previous is None or (item["connected"], signal) > (
                previous["connected"], previous["signal"]):
            networks[key] = item
    return sorted(networks.values(), key=lambda n: (
        not n["connected"], -n["signal"], n["ssid"].casefold()))


def _last_scan(device_path):
    try:
        result = subprocess.run(
            ["busctl", "--system", "--timeout=3", "get-property",
             "org.freedesktop.NetworkManager", device_path,
             "org.freedesktop.NetworkManager.Device.Wireless", "LastScan"],
            capture_output=True, text=True, timeout=4, check=False,
            env={**os.environ, "LC_ALL": "C"},
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise WifiError("Could not check whether Wi-Fi scanning has finished.") from error
    fields = result.stdout.split()
    if result.returncode or len(fields) != 2 or fields[0] != "x":
        raise WifiError("Could not read Wi-Fi scan status from NetworkManager.")
    try:
        return int(fields[1])
    except ValueError as error:
        raise WifiError("NetworkManager returned an invalid Wi-Fi scan status.") from error


def _scan_and_wait(interface):
    device_path = _run([
        "--get-values", "GENERAL.DBUS-PATH", "device", "show", interface
    ]).strip()
    if not device_path.startswith("/org/freedesktop/NetworkManager/Devices/"):
        raise WifiError("Could not find the Wi-Fi adapter in NetworkManager.")
    previous_scan = _last_scan(device_path)
    _run(["device", "wifi", "rescan", "ifname", interface])
    deadline = time.monotonic() + 15
    # Runs in the controller's worker, never on the Tk thread. LastScan changes
    # when a scan finishes; accepting the request alone is not sufficient.
    while time.monotonic() < deadline:
        if _last_scan(device_path) > previous_scan:
            return
        time.sleep(0.25)
    raise WifiError("Wi-Fi scanning did not finish within 15 seconds. Try again.")


def get_wifi_snapshot(rescan=False):
    devices = [_split_row(line) for line in _run(
        ["--fields", "DEVICE,TYPE,STATE", "device", "status"]).splitlines()]
    adapters = [row for row in devices if len(row) == 3 and row[1] == "wifi"]
    snapshot = {"interface": None, "connected": False, "connection": "",
                "ip_address": "", "radio_enabled": False, "networks": [],
                "scan_error": None}
    if not adapters:
        return snapshot
    adapter = next((row for row in adapters if row[2].startswith("connected")), adapters[0])
    interface = adapter[0]
    snapshot["interface"] = interface
    snapshot["radio_enabled"] = _run(["radio", "wifi"]).strip() == "enabled"
    details = _run(["--fields", "GENERAL.STATE,GENERAL.CONNECTION,IP4.ADDRESS",
                    "device", "show", interface])
    for line in details.splitlines():
        fields = _split_row(line)
        if len(fields) < 2:
            continue
        key, value = fields[0], ":".join(fields[1:])
        if key == "GENERAL.STATE":
            snapshot["connected"] = value.split(" ", 1)[0] == "100"
        elif key == "GENERAL.CONNECTION":
            snapshot["connection"] = "" if value == "--" else value
        elif key.startswith("IP4.ADDRESS") and not snapshot["ip_address"]:
            snapshot["ip_address"] = value.split("/", 1)[0]
    if not snapshot["connected"]:
        snapshot["connection"] = ""
        snapshot["ip_address"] = ""
    if not snapshot["radio_enabled"]:
        return snapshot
    if rescan:
        try:
            _scan_and_wait(interface)
        except WifiError as error:
            # Keep the current connection and cached list visible if scan is denied.
            snapshot["scan_error"] = str(error)
    output = _run(["--fields", "IN-USE,SSID,BSSID,SIGNAL,SECURITY",
                   "device", "wifi", "list", "ifname", interface, "--rescan", "no"])
    snapshot["networks"] = _networks(output)
    active = next((n for n in snapshot["networks"] if n["connected"]), None)
    if active and snapshot["connected"]:
        snapshot["connection"] = active["ssid"]
    return snapshot

def _find_wifi_profile(interface, ssid):
    output = _run([
        "--fields", "UUID,TYPE",
        "connection", "show",
    ])

    for line in output.splitlines():
        fields = _split_row(line)
        if len(fields) != 2:
            continue

        profile_uuid, profile_type = fields
        if profile_type not in ("802-11-wireless", "wifi"):
            continue

        details = _run([
            "--fields",
            "802-11-wireless.ssid,connection.interface-name,"
            "802-11-wireless-security.key-mgmt",
            "connection", "show", "uuid", profile_uuid,
        ])

        values = {}
        for detail in details.splitlines():
            parts = _split_row(detail)
            if len(parts) >= 2:
                values[parts[0]] = ":".join(parts[1:])

        if values.get("802-11-wireless.ssid") != ssid:
            continue

        bound_interface = values.get("connection.interface-name", "")
        if bound_interface not in ("", "--", interface):
            continue

        key_mgmt = values.get("802-11-wireless-security.key-mgmt", "")
        return profile_uuid, key_mgmt

    return None, None

def connect_wifi(interface, network, password):
    if not interface:
        raise WifiError("No Wi-Fi adapter is available.")

    security = network.get("security", "").upper()
    is_open = security == "OPEN"

    if not is_open:
        if "802.1X" in security or "EAP" in security:
            raise WifiError(
                "Enterprise networks are not supported by this form."
            )

        if "WPA1" not in security and "WPA2" not in security:
            raise WifiError(
                "This form currently supports open and WPA/WPA2 networks."
            )

        if not password:
            raise WifiError("Enter the network password.")

    bssid = network.get("bssid")
    if not bssid:
        raise WifiError(
            "Refresh the network list and select the network again."
        )

    def run_connection_command(arguments):
        try:
            result = subprocess.run(
                [
                    "nmcli",
                    "--colors", "no",
                    "--wait", "40",
                    *arguments,
                ],
                capture_output=True,
                text=True,
                timeout=45,
                check=False,
                env={**os.environ, "LC_ALL": "C"},
            )
        except subprocess.TimeoutExpired:
            raise WifiError(
                "The operation timed out. Refresh to check the connection."
            ) from None
        except OSError:
            raise WifiError(
                "Could not start the Wi-Fi connection command."
            ) from None

        if result.returncode == 0:
            return

        detail = (result.stderr or result.stdout).strip()

        if password:
            detail = detail.replace(password, "[hidden]")

        if (
            "not authorized" in detail.lower()
            or "permission denied" in detail.lower()
        ):
            raise WifiError(
                "The application does not have permission to connect."
            )

        if result.returncode == 3:
            raise WifiError(
                "The operation timed out. Refresh to check the connection."
            )

        raise WifiError(detail or "Connection failed.")

    profile_uuid, key_mgmt = _find_wifi_profile(
        interface, network["ssid"]
    )

    if profile_uuid is not None:
        if is_open:
            if key_mgmt not in ("", "--"):
                raise WifiError(
                    "The saved profile does not match this network's security."
                )
        else:
            if key_mgmt != "wpa-psk":
                raise WifiError(
                    "The saved profile is not a WPA/WPA2 Personal profile."
                )

            # Ažuriraj lozinku uz očuvanje vrste zaštite profila.
            run_connection_command([
                "connection", "modify", "uuid", profile_uuid,
                "802-11-wireless-security.key-mgmt", "wpa-psk",
                "802-11-wireless-security.psk", password,
            ])

        # Aktiviraj postojeći profil na odabranoj pristupnoj točki.
        run_connection_command([
            "connection", "up", "uuid", profile_uuid,
            "ifname", interface,
            "ap", bssid,
        ])

    else:
        # Za novu mrežu NetworkManager izrađuje profil i povezuje se.
        arguments = [
            "device", "wifi", "connect", bssid,
            "ifname", interface,
        ]

        if not is_open:
            arguments.extend(["password", password])

        run_connection_command(arguments)
