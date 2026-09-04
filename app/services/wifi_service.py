import json
import os
import subprocess
import sys
import time

from uuid import uuid4

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

def _saved_wifi_profiles(interface):
    output = _run([
        "--fields", "UUID,TYPE",
        "connection", "show",
    ])

    profiles = []

    for line in output.splitlines():
        fields = _split_row(line)
        if len(fields) != 2:
            continue

        profile_uuid, profile_type = fields
        if profile_type not in ("802-11-wireless", "wifi"):
            continue

        try:
            details = _run([
                "--fields",
                "802-11-wireless.ssid,"
                "connection.interface-name,"
                "802-11-wireless.bssid,"
                "802-11-wireless-security.key-mgmt",
                "connection", "show", "uuid", profile_uuid,
            ])
        except WifiError:
            # Profil je možda uklonjen ili više nije dostupan.
            continue

        values = {}
        for detail in details.splitlines():
            parts = _split_row(detail)
            if len(parts) >= 2:
                value = ":".join(parts[1:])
                values[parts[0]] = "" if value == "--" else value

        bound_interface = values.get("connection.interface-name", "")
        if bound_interface not in ("", interface):
            continue

        profiles.append({
            "uuid": profile_uuid,
            "ssid": values.get("802-11-wireless.ssid", ""),
            "bssid": values.get("802-11-wireless.bssid", "").upper(),
            "key_mgmt": values.get(
                "802-11-wireless-security.key-mgmt", ""
            ),
        })

    return profiles

def _matching_wifi_profile(profiles, network):
    security = network.get("security", "").upper()

    if security == "OPEN":
        expected_key_mgmt = ""
    elif (
        ("WPA1" in security or "WPA2" in security)
        and "802.1X" not in security
        and "EAP" not in security
    ):
        expected_key_mgmt = "wpa-psk"
    else:
        return None

    for profile in profiles:
        if profile["ssid"] != network["ssid"]:
            continue

        if profile["key_mgmt"] != expected_key_mgmt:
            continue

        # Ako je profil vezan uz određenu pristupnu točku,
        # mora odgovarati i njezina adresa.
        if (
            profile["bssid"]
            and profile["bssid"] != network.get("bssid", "").upper()
        ):
            continue

        return profile["uuid"]

    return None


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
    profiles = _saved_wifi_profiles(interface)

    for network in snapshot["networks"]:
        profile_uuid = _matching_wifi_profile(profiles, network)
        network["saved"] = profile_uuid is not None
        network["profile_uuid"] = profile_uuid
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

def _active_wifi_profile(interface):
    output = _run([
        "--fields", "GENERAL.STATE,GENERAL.CON-UUID",
        "device", "show", interface,
    ])

    values = {}
    for line in output.splitlines():
        fields = _split_row(line)
        if len(fields) >= 2:
            values[fields[0]] = ":".join(fields[1:])

    state = values.get("GENERAL.STATE", "").split(" ", 1)[0]
    profile_uuid = values.get("GENERAL.CON-UUID", "")

    if state == "100" and profile_uuid not in ("", "--"):
        return profile_uuid

    return None

def _run_connection_command(arguments, password=None):
    try:
        result = subprocess.run(
            [
                "nmcli",
                "--colors", "no",
                "--wait", "40",
                *arguments,
            ],
            stdin=subprocess.DEVNULL,
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
        return result.stdout

    detail = (result.stderr or result.stdout).strip()

    if password:
        detail = detail.replace(password, "[hidden]")

    if (
        "not authorized" in detail.lower()
        or "permission denied" in detail.lower()
    ):
        raise WifiError(
            "The application does not have permission "
            "to perform this network operation."
        )

    if result.returncode == 3:
        raise WifiError(
            "The operation timed out. Refresh to check the connection."
        )

    raise WifiError(detail or "Network operation failed.")

def _create_wifi_trial(interface, network, password):
    trial_uuid = str(uuid4())
    trial_name = f"piphone-trial-{trial_uuid}"

    arguments = [
        "connection", "add",
        "save", "no",
        "type", "wifi",
        "ifname", interface,
        "con-name", trial_name,
        "ssid", network["ssid"],
        "connection.uuid", trial_uuid,
        "connection.autoconnect", "no",
        "ipv4.method", "auto",
        "ipv6.method", "auto",
    ]

    if network["security"] != "Open":
        if not password:
            raise WifiError("Enter the network password.")

        arguments.extend([
            "802-11-wireless-security.key-mgmt", "wpa-psk",
            "802-11-wireless-security.psk", password,
            "802-11-wireless-security.psk-flags", "0",
        ])

    try:
        _run_connection_command(arguments, password=password)
    except WifiError:
        # Ako je stvaranje djelomično uspjelo, pokušaj ukloniti
        # samo profil s UUID-om generiranim za ovaj pokušaj.
        try:
            _run_connection_command([
                "connection", "delete", "uuid", trial_uuid,
            ])
        except WifiError:
            pass
        raise

    return trial_uuid

def _activate_wifi_profile(profile_uuid, interface, bssid=""):
    helper = os.path.join(os.path.dirname(__file__), "wifi_auth_agent.py")
    try:
        process = subprocess.run(
            [sys.executable, helper, profile_uuid, interface, bssid],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=75,
            check=False,
        )
        result = json.loads(process.stdout)
        if not isinstance(result, dict):
            raise ValueError("Invalid result")
        if process.returncode == 0 and result.get("ok") is True:
            return
        error = result.get("error") or "Wi-Fi connection failed."
    except subprocess.TimeoutExpired:
        error = "The Wi-Fi connection attempt timed out."
    except (OSError, ValueError):
        error = "Could not read the Wi-Fi connection result."

    # Prekid pomoćnog procesa ne poništava već poslanu aktivaciju.
    try:
        _run_connection_command([
            "connection", "down", "uuid", profile_uuid,
        ])
    except WifiError:
        pass
    raise WifiError(str(error))


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

    bssid = network.get("bssid")
    if not bssid:
        raise WifiError(
            "Refresh the network list and select the network again."
        )

    profiles = _saved_wifi_profiles(interface)
    profile_uuid = _matching_wifi_profile(profiles, network)
    previous_uuid = _active_wifi_profile(interface)

    # Ako je odabrani profil već aktivan i ne mijenjamo
    # lozinku, ostavi postojeću vezu netaknutom.
    if (
        profile_uuid is not None
        and profile_uuid == previous_uuid
        and not password
    ):
        return

    if not is_open and not password and profile_uuid is None:
        raise WifiError(
            "No matching saved profile was found. "
            "Enter the network password."
        )

    trial_uuid = None
    try:
        if profile_uuid is not None and not password:
            _activate_wifi_profile(profile_uuid, interface, bssid)
            return

        trial_uuid = _create_wifi_trial(interface, network, password)
        _activate_wifi_profile(trial_uuid, interface, bssid)

        if profile_uuid is not None:
            # Novu lozinku spremi tek nakon uspješnog probnog povezivanja.
            if not is_open:
                _run_connection_command([
                    "connection", "modify", "uuid", profile_uuid,
                    "802-11-wireless-security.key-mgmt", "wpa-psk",
                    "802-11-wireless-security.psk", password,
                ], password=password)
            # Zadrži izvorni profil i njegove IP/DNS postavke.
            _activate_wifi_profile(profile_uuid, interface, bssid)
        else:
            # Spremi uspješnu novu mrežu bez dodatnog reconnecta.
            _run_connection_command([
                "connection", "modify", "uuid", trial_uuid,
                "connection.id", network["ssid"],
                "connection.autoconnect", "yes",
            ], password=password)
            trial_uuid = None

    except WifiError as error:
        notes = []
        if trial_uuid is not None:
            try:
                _run_connection_command([
                    "connection", "delete", "uuid", trial_uuid,
                ])
            except WifiError:
                notes.append("Could not remove the temporary profile.")
        if previous_uuid is not None:
            try:
                if _active_wifi_profile(interface) != previous_uuid:
                    _activate_wifi_profile(previous_uuid, interface)
                notes.append("Previous Wi-Fi connection restored.")
            except WifiError:
                notes.append("Could not restore the previous Wi-Fi connection.")
        raise WifiError(" ".join([str(error), *notes])) from None

    if trial_uuid is not None:
        try:
            _run_connection_command([
                "connection", "delete", "uuid", trial_uuid,
            ])
        except WifiError:
            raise WifiError(
                "Connected, but the temporary profile could not be removed."
            ) from None
