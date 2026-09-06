from queue import Empty, Queue
from threading import Event, Thread

from app.services.wifi_service import get_network_status


NETWORK_CHECK_INTERVAL = 3


class NetworkMonitor:
    def __init__(self, state):
        self.state = state
        self.results = Queue()
        self.stop_event = Event()
        self.thread = None

    def start(self):
        if self.thread is not None and self.thread.is_alive():
            return

        self.stop_event.clear()
        self.thread = Thread(
            target=self._worker,
            daemon=True,
        )
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def _worker(self):
        while not self.stop_event.is_set():
            try:
                status = get_network_status()
            except Exception as error:
                print(f"[NETWORK MONITOR WARN] {error}")
                status = {
                    "checked": True,
                    "wifi_connected": False,
                    "internet_available": False,
                }

            self.results.put(status)
            self.stop_event.wait(NETWORK_CHECK_INTERVAL)

    def poll(self):
        latest_status = None

        while True:
            try:
                latest_status = self.results.get_nowait()
            except Empty:
                break

        if latest_status is None:
            return None

        self.state["network"].update(latest_status)
        return latest_status