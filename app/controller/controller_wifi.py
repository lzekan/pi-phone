from queue import Empty, Queue
from threading import Thread

from app.services.wifi_service import (
    WifiError,
    connect_wifi,
    get_wifi_snapshot,
)


class WifiController:
    def __init__(self, state):
        self.state = state
        self.busy = False
        self.results = Queue()

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

    def connect(self, interface, network, password, on_done):
        if self.busy:
            return False

        self.busy = True
        selected_network = dict(network)

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

            self.results.put((snapshot, error, on_done))

        Thread(target=worker, daemon=True).start()
        return True

    def poll(self, callback):
        try:
            snapshot, error, on_done = self.results.get_nowait()
        except Empty:
            return

        self.busy = False

        if snapshot is not None:
            self.state["wifi"] = snapshot

        handler = on_done if on_done is not None else callback
        handler(snapshot, error)