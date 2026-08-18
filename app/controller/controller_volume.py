from queue import Queue
from threading import Thread

from app.services import audio_output_service


VOLUME_STEP_PERCENT = 5

_volume_queue = Queue()


def _volume_worker():
    while True:
        step_percent, on_changed = _volume_queue.get()
        try:
            volume_percent = audio_output_service.change_volume(step_percent)
            if on_changed:
                on_changed(volume_percent)
        except Exception as error:
            print(f"[VOLUME ERROR] {error}")
        finally:
            _volume_queue.task_done()


Thread(target=_volume_worker, daemon=True).start()


def _apply_saved_volume_limit():
    try:
        audio_output_service.enforce_maximum_volume()
    except Exception as error:
        print(f"[VOLUME LIMIT ERROR] {error}")


Thread(target=_apply_saved_volume_limit, daemon=True).start()


def on_volume_up(on_changed=None):
    _volume_queue.put((VOLUME_STEP_PERCENT, on_changed))


def on_volume_down(on_changed=None):
    _volume_queue.put((-VOLUME_STEP_PERCENT, on_changed))
