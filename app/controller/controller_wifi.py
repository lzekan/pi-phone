from queue import Empty, Queue
from threading import Event, Thread
from concurrent.futures import CancelledError

from app.services.wifi_service import (
    WifiError,
    connect_wifi,
    get_wifi_snapshot,
    set_wifi_radio_enabled,
)
from app.features.spotify.services.daemon_client import (
    finish_spotify_recovery,
)
from app.features.spotify.services.spotify_service import (
    recover_spotify_connection,
    receiver_generation,
    restore_spotify_playback,
)

def _capture_spotify_playback(state):
    song = state.get("song", {})
    track_id = song.get("track_id")

    if (
        song.get("source") != "spotify"
        or not song.get("is_playing", False)
        or not track_id
    ):
        return None

    return {
        "track_id": track_id,
        "uri": f"spotify:track:{track_id}",
        "track": song.get("track", ""),
        "artist": song.get("artist", ""),
        "album_id": song.get("album_id", ""),
        "album_name": song.get("album_name", ""),
        "image_url": song.get("image_url"),
        "progress_ms": max(0, song.get("progress_ms", 0) or 0),
        "duration_ms": max(1, song.get("duration_ms", 1) or 1),
    }


class WifiController:
    def __init__(self, state):
        self.state = state
        self.busy = False
        self.results = Queue()
        self.recovery_results = Queue()
        self.recovery_generation = 0
        self.recovery_cancel = None

    def refresh(self, rescan=False):
        if self.busy:
            return False

        self.busy = True

        def worker():
            try:
                snapshot = get_wifi_snapshot(rescan=rescan)
                self.results.put((snapshot, None, None))
            except Exception as error:
                self.results.put((None, str(error), None))

        Thread(target=worker, daemon=True).start()
        return True

    def set_radio_enabled(self, enabled, on_done):
        if self.busy:
            return False

        # Promjena stanja radija poništava oporavak pokrenut nakon
        # prethodne promjene mreže.
        if self.recovery_cancel is not None:
            self.recovery_cancel.set()
            self.recovery_cancel = None

        self.recovery_generation += 1
        self.state["spotify_reconnecting"] = False
        self.state["spotify_reconnect_error"] = None
        self.busy = True

        def worker():
            error = None
            snapshot = None

            try:
                set_wifi_radio_enabled(enabled)
            except WifiError as exception:
                error = str(exception)
            except Exception:
                error = "An unexpected error occurred while changing Wi-Fi."

            # Uvijek pročitaj stvarno stanje umjesto da sučelje unaprijed
            # pretpostavi da je naredba uspjela.
            try:
                snapshot = get_wifi_snapshot(rescan=False)
            except Exception:
                if error is None:
                    error = (
                        "Wi-Fi was changed, but its current state could not "
                        "be read."
                    )

            self.results.put((snapshot, error, on_done))

        Thread(target=worker, daemon=True).start()
        return True

    def connect(self, interface, network, password, on_done):
        if self.busy:
            return False

        # Novo povezivanje poništava prethodni oporavak Spotifyja.
        if self.recovery_cancel is not None:
            self.recovery_cancel.set()

        self.recovery_generation += 1
        generation = self.recovery_generation

        cancel_event = Event()
        self.recovery_cancel = cancel_event

        selected_network = dict(network)
        song = self.state.get("song", {})
        playback_before_connection = _capture_spotify_playback(self.state)

        expect_active = (
            song.get("source") == "spotify"
            and bool(song.get("is_playing"))
        )

        self.busy = True
        self.state["spotify_reconnecting"] = True
        self.state["spotify_reconnect_error"] = None

        def worker():
            error = None
            snapshot = None

            try:
                connect_wifi(interface, selected_network, password)
            except WifiError as exception:
                error = str(exception)
            except Exception:
                error = "An unexpected error occurred while connecting."

            # Provjeri stvarnu vezu i nakon neuspjelog pokušaja.
            try:
                snapshot = get_wifi_snapshot(rescan=False)
            except Exception:
                if error is None:
                    error = (
                        "The connection command completed, but its status "
                        "could not be read. Refresh to check the connection."
                    )

            if error is None and snapshot is not None:
                if (
                    not snapshot["connected"]
                    or snapshot["connection"] != selected_network["ssid"]
                ):
                    error = (
                        "The selected connection could not be confirmed. "
                        "Refresh to check the current network."
                    )

            # Wi-Fi rezultat odmah šaljemo sučelju.
            # Korisnik ne mora čekati oporavak Spotifyja da izađe.
            self.results.put((snapshot, error, on_done))

            # I neuspjeli pokušaj može privremeno prekinuti staru vezu,
            # zato provjeravamo Spotify neovisno o Wi-Fi rezultatu.
            recovery_result = None
            recovery_error = None
            receiver_version = receiver_generation()

            try:
                recovery_result = recover_spotify_connection(
                    expect_active=expect_active,
                    cancel_event=cancel_event,
                )
                account_playback = (
                    recovery_result.get("account_playback") or {}
                )
                account_device = (
                    account_playback.get("device") or {}
                )

                another_device_is_playing = (
                    bool(account_playback.get("is_playing"))
                    and bool(account_device.get("id"))
                    and account_device.get("id")
                    != recovery_result.get("device_id")
                )

                playing_on_piphone = (
                    bool(recovery_result.get("active_here"))
                    and bool(account_playback.get("is_playing"))
                )

                if (
                    playback_before_connection is not None
                    and not playing_on_piphone
                    and not another_device_is_playing
                ):
                    restore_spotify_playback(
                        recovery_result["device_id"],
                        playback_before_connection,
                    )
                    recovery_result["restored_snapshot"] = (
                        playback_before_connection
                    )
            except CancelledError:
                # Otkazivanje nije pogreška za korisnika.
                recovery_result = {"cancelled": True}
            except RuntimeError as exception:
                recovery_error = str(exception)
            except Exception:
                recovery_error = (
                    "Spotify recovery failed. "
                    "Check the internet connection and try again."
                )
            finally:
                if not cancel_event.is_set():
                    self.recovery_results.put(
                        (generation, receiver_version,
                         recovery_result, recovery_error)
                    )

        Thread(target=worker, daemon=True).start()
        return True

    def poll(self, callback):
        try:
            snapshot, error, on_done = self.results.get_nowait()
        except Empty:
            pass
        else:
            self.busy = False

            if snapshot is not None:
                self.state["wifi"] = snapshot

            handler = on_done if on_done is not None else callback
            handler(snapshot, error)

        try:
            generation, receiver_version, result, error = (
                self.recovery_results.get_nowait()
            )
        except Empty:
            return

        # Rezultat je možda već bio u redu prije otkazivanja.
        # Samo najnoviji pokušaj smije promijeniti stanje.
        if generation != self.recovery_generation:
            return

        self.recovery_cancel = None
        # A source change invalidates results already queued by Wi-Fi recovery.
        if receiver_version != receiver_generation():
            return
        if (result or {}).get("cancelled"):
            self.state["spotify_reconnecting"] = False
            return

        # poll() se poziva iz glavne dretve sučelja:
        # ovdje sigurno primjenjujemo rezultat oporavka.
        finish_spotify_recovery(result=result, error=error)
