from io import BytesIO
from queue import Empty, Queue
from threading import Thread

import requests
from PIL import Image, ImageTk


_cache = {}
_loading = {}


def get_photo_async(root, url, size, callback):
    if not url:
        callback(None)
        return

    key = (url, size)
    if key in _cache:
        callback(_cache[key])
        return

    if key in _loading:
        _loading[key]["callbacks"].append(callback)
        return

    result = Queue(maxsize=1)
    _loading[key] = {"callbacks": [callback], "result": result}

    def download():
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content)).convert("RGB")
            image.thumbnail(size, Image.Resampling.LANCZOS)
            result.put(image)
        except Exception:
            result.put(None)

    def deliver():
        try:
            image = result.get_nowait()
        except Empty:
            root.after(50, deliver)
            return

        callbacks = _loading.pop(key)["callbacks"]
        photo = ImageTk.PhotoImage(image) if image is not None else None
        if photo is not None:
            _cache[key] = photo

        for pending_callback in callbacks:
            pending_callback(photo)

    Thread(target=download, daemon=True).start()
    root.after(50, deliver)
