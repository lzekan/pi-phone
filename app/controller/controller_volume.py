from queue import Queue
from threading import Thread

from app.services import audio_output_service


VOLUME_STEP_PERCENT = 5

_volume_queue = Queue()


def _volume_worker():
    while True:
        step_percent = _volume_queue.get()
        try:
            audio_output_service.change_volume(step_percent)
        except Exception as error:
            print(f"[VOLUME ERROR] {error}")
        finally:
            _volume_queue.task_done()


Thread(target=_volume_worker, daemon=True).start()


def on_volume_up():
    _volume_queue.put(VOLUME_STEP_PERCENT)


def on_volume_down():
    _volume_queue.put(-VOLUME_STEP_PERCENT)
