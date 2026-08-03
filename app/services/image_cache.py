from io import BytesIO
from queue import Empty, Queue
import socket
from threading import BoundedSemaphore, Thread
from urllib.parse import urlparse

import requests
import urllib3
from PIL import Image, ImageTk


_cache = {}
_loading = {}
_download_slots = BoundedSemaphore(4)


def _download_content(url):
    if url.startswith("https://mosaic.scdn.co/"):
        parsed = urlparse(url)
        ip_address = socket.gethostbyname("scdnco.spotify.map.fastly.net")
        pool = urllib3.HTTPSConnectionPool(
            ip_address,
            port=443,
            assert_hostname="mosaic.scdn.co",
            server_hostname="mosaic.scdn.co",
            cert_reqs="CERT_REQUIRED",
            ca_certs=requests.certs.where(),
        )
        try:
            response = pool.request(
                "GET",
                parsed.path,
                headers={"Host": "mosaic.scdn.co"},
                timeout=urllib3.Timeout(connect=3.05, read=10),
            )
            if response.status >= 400:
                raise RuntimeError(f"Image request failed: HTTP {response.status}")
            return response.data
        finally:
            pool.close()

    download_url = url.replace(
        "https://i.scdn.co/",
        "https://image-cdn-ak.spotifycdn.com/",
        1,
    )
    response = requests.get(download_url, timeout=(3.05, 10))
    response.raise_for_status()
    return response.content


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
            with _download_slots:
                content = _download_content(url)
            image = Image.open(BytesIO(content)).convert("RGB")
            image.thumbnail(size, Image.Resampling.LANCZOS)
            result.put(image)
        except Exception as error:
            print(f"[IMAGE ERROR] {url}: {error}")
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
