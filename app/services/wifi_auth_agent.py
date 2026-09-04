import dbus
import dbus.service
import json
import os
import sys
import time

from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

NM_SERVICE = "org.freedesktop.NetworkManager"
AGENT_INTERFACE = "org.freedesktop.NetworkManager.SecretAgent"
AGENT_PATH = "/org/freedesktop/NetworkManager/SecretAgent"

class SecretsCancelled(dbus.DBusException):
    _dbus_error_name = (
        "org.freedesktop.NetworkManager.SecretAgent.UserCanceled"
    )


class SecretsUnavailable(dbus.DBusException):
    _dbus_error_name = (
        "org.freedesktop.NetworkManager.SecretAgent.NoSecrets"
    )


class AccessDenied(dbus.DBusException):
    _dbus_error_name = "org.freedesktop.DBus.Error.AccessDenied"


class WifiTrialAgent(dbus.service.Object):
    def __init__(self, bus, profile_uuid):
        self.profile_uuid = str(profile_uuid)
        self.nm_owner = str(bus.get_name_owner(NM_SERVICE))
        self.authentication_rejected = False

        super().__init__(bus, AGENT_PATH)

    def _check_sender(self, sender):
        if str(sender) != self.nm_owner:
            raise AccessDenied(
                "Only NetworkManager may call this agent."
            )

    @dbus.service.method(
        AGENT_INTERFACE,
        in_signature="a{sa{sv}}osasu",
        out_signature="a{sa{sv}}",
        sender_keyword="sender",
    )
    def GetSecrets(
        self,
        connection,
        connection_path,
        setting_name,
        hints,
        flags,
        sender=None,
    ):
        self._check_sender(sender)

        requested_uuid = str(
            connection.get("connection", {}).get("uuid", "")
        )

        if requested_uuid != self.profile_uuid:
            # Ne obrađujemo druge mrežne profile.
            raise SecretsUnavailable(
                "This profile is not handled by PiPhone."
            )

        # Lozinka za ovaj pokušaj već je zadana u odabranom profilu.
        # Ako je potrebna druga, završavamo pokušaj.
        self.authentication_rejected = True
        raise SecretsCancelled(
            "Enter a new password in the PiPhone application."
        )

    @dbus.service.method(
        AGENT_INTERFACE,
        in_signature="os",
        out_signature="",
        sender_keyword="sender",
    )
    def CancelGetSecrets(
        self, connection_path, setting_name, sender=None
    ):
        self._check_sender(sender)

    @dbus.service.method(
        AGENT_INTERFACE,
        in_signature="a{sa{sv}}o",
        out_signature="",
        sender_keyword="sender",
    )
    def SaveSecrets(self, connection, connection_path, sender=None):
        self._check_sender(sender)
        # Lozinke ne pohranjujemo u ovaj modul.

    @dbus.service.method(
        AGENT_INTERFACE,
        in_signature="a{sa{sv}}o",
        out_signature="",
        sender_keyword="sender",
    )
    def DeleteSecrets(self, connection, connection_path, sender=None):
        self._check_sender(sender)

def run_trial(profile_uuid, interface, bssid):
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus(private=True)
    loop = GLib.MainLoop()

    result = {"ok": False, "error": "Wi-Fi connection failed."}
    active_path = None
    registered = False
    timer_id = None
    agent = None

    def proxy(path, interface_name):
        return dbus.Interface(
            bus.get_object(NM_SERVICE, path),
            interface_name,
        )

    manager = proxy(
        "/org/freedesktop/NetworkManager",
        NM_SERVICE,
    )
    agent_manager = proxy(
        "/org/freedesktop/NetworkManager/AgentManager",
        NM_SERVICE + ".AgentManager",
    )

    def finish(error=None):
        result["ok"] = error is None
        result["error"] = error
        loop.quit()

    def activation_started(path):
        nonlocal active_path
        active_path = str(path)

    def activation_failed(error):
        finish(
            "NetworkManager could not start the connection: "
            + error.get_dbus_name()
        )

    try:
        settings = proxy(
            "/org/freedesktop/NetworkManager/Settings",
            NM_SERVICE + ".Settings",
        )
        profile_path = settings.GetConnectionByUuid(
            profile_uuid, timeout=5
        )
        profile_settings = proxy(
            profile_path,
            NM_SERVICE + ".Settings.Connection",
        ).GetSettings(timeout=5)

        connection = profile_settings.get("connection", {})
        if (
            str(connection.get("uuid", "")) != profile_uuid
            or str(connection.get("type", "")) != "802-11-wireless"
        ):
            raise ValueError("The selected profile is not a Wi-Fi profile.")

        device_path = manager.GetDeviceByIpIface(
            interface, timeout=5
        )
        wireless = proxy(
            device_path,
            NM_SERVICE + ".Device.Wireless",
        )

        access_point_path = "/" if not bssid else None
        paths = wireless.GetAllAccessPoints(timeout=5) if bssid else []
        for path in paths:
            properties = proxy(
                path, "org.freedesktop.DBus.Properties"
            )
            address = str(properties.Get(
                NM_SERVICE + ".AccessPoint",
                "HwAddress",
                timeout=3,
            ))
            if address.upper() == bssid.upper():
                access_point_path = path
                break

        if access_point_path is None:
            raise ValueError(
                "The access point is no longer available. Press Refresh."
            )

        agent = WifiTrialAgent(bus, profile_uuid)
        agent_manager.Register(
            f"org.piphone.wifi.p{os.getpid()}",
            timeout=5,
        )
        registered = True

        deadline = time.monotonic() + 40

        def check_status():
            if agent.authentication_rejected:
                finish(
                    "Authentication could not be completed "
                    "with the supplied password. Check the password."
                )
            elif time.monotonic() >= deadline:
                finish("The Wi-Fi connection attempt timed out.")
            elif active_path is not None:
                try:
                    properties = proxy(
                        active_path,
                        "org.freedesktop.DBus.Properties",
                    )
                    state = int(properties.Get(
                        NM_SERVICE + ".Connection.Active",
                        "State",
                        timeout=3,
                    ))

                    if state == 2:
                        finish()
                    elif state == 4:
                        finish("The Wi-Fi connection attempt failed.")
                except dbus.DBusException:
                    finish("The Wi-Fi connection attempt ended.")

            return True

        timer_id = GLib.timeout_add(250, check_status)

        manager.ActivateConnection(
            profile_path,
            device_path,
            access_point_path,
            reply_handler=activation_started,
            error_handler=activation_failed,
            timeout=10,
        )

        loop.run()

    except dbus.DBusException as error:
        result["error"] = (
            "NetworkManager error: " + error.get_dbus_name()
        )
    except ValueError as error:
        result["error"] = str(error)
    except Exception:
        result["error"] = "Could not complete the Wi-Fi trial."

    finally:
        if timer_id is not None:
            GLib.source_remove(timer_id)

        if not result["ok"] and active_path is not None:
            try:
                manager.DeactivateConnection(
                    active_path, timeout=5
                )
            except dbus.DBusException:
                # Pozivatelj će dodatno ukloniti probni profil.
                pass

        if registered:
            try:
                agent_manager.Unregister(timeout=5)
            except dbus.DBusException:
                pass

        if agent is not None:
            agent.remove_from_connection()

        bus.close()

    return result


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(json.dumps({
            "ok": False,
            "error": "Expected profile UUID, interface and BSSID.",
        }))
        raise SystemExit(2)

    outcome = run_trial(*sys.argv[1:])
    print(json.dumps(outcome), flush=True)
    raise SystemExit(0 if outcome["ok"] else 1)
