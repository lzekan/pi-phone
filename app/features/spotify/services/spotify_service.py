import requests
import os
import json
import threading
import time
import subprocess

from concurrent.futures import CancelledError

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
TOKEN_FILE = "/home/lukaz/pi-phone/tokens/tokens.json"
REQUEST_TIMEOUT = (3.05, 10)

SPOTIFY_DEVICE_NAME = "PiPhone"
DEVICE_DISCOVERY_ATTEMPTS = 5
DEVICE_DISCOVERY_DELAY = 1

_access_token = None
_token_expires_at = 0
_token_lock = threading.Lock()

# Serialize receiver lifecycle changes, never HTTP requests. Local playback
# must not wait for the network, and recovery must not undo an explicit stop.
_receiver_lock = threading.RLock()
_receiver_local_mode = False
_receiver_generation = 0


def receiver_generation():
    with _receiver_lock:
        return _receiver_generation


def stop_receiver_for_local():
    global _receiver_local_mode, _receiver_generation

    with _receiver_lock:
        _receiver_local_mode = True
        _receiver_generation += 1
        try:
            subprocess.run(
                ["systemctl", "--user", "stop", "piphone-spotify.service"],
                capture_output=True, text=True, timeout=10, check=True,
            )
            status = subprocess.run(
                ["systemctl", "--user", "show", "piphone-spotify.service",
                 "--property=ActiveState", "--value"],
                capture_output=True, text=True, timeout=3, check=True,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise RuntimeError(
                "Could not stop the Spotify receiver for local playback."
            ) from error
        if status.stdout.strip() not in ("inactive", "failed"):
            raise RuntimeError("Spotify receiver has not stopped yet.")


def start_receiver_for_spotify():
    global _receiver_local_mode, _receiver_generation

    with _receiver_lock:
        try:
            # ExecStartPre may wait for internet/time; do not block here.
            subprocess.run(
                ["systemctl", "--user", "--no-block", "start",
                 "piphone-spotify.service"],
                capture_output=True, text=True, timeout=5, check=True,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise RuntimeError("Could not start the Spotify receiver.") from error
        if _receiver_local_mode:
            _receiver_generation += 1
        _receiver_local_mode = False


def _check_receiver_generation(expected):
    with _receiver_lock:
        if _receiver_local_mode or expected != _receiver_generation:
            raise CancelledError("Spotify receiver ownership changed.")


def _restart_receiver(expected):
    with _receiver_lock:
        _check_receiver_generation(expected)
        subprocess.run(
            ["systemctl", "--user", "--no-block", "restart",
             "piphone-spotify.service"],
            capture_output=True, text=True, timeout=5, check=True,
        )

id_me = None

# ---------------- TOKEN -----------------

def _get_token():
    global _access_token, _token_expires_at

    if _access_token and time.time() < _token_expires_at - 30:
        return _access_token

    with _token_lock:
        if _access_token and time.time() < _token_expires_at - 30:
            return _access_token

        with open(TOKEN_FILE, "r") as f:
            refresh_token = json.load(f)["refresh_token"]

        response = requests.post(
            "https://accounts.spotify.com/api/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET
            },
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()

        _access_token = data["access_token"]
        _token_expires_at = time.time() + data.get("expires_in", 3600)
        return _access_token

# ----------------------------------------------------

def recover_spotify_connection(expect_active=False, cancel_event=None):
    generation = receiver_generation()
    if cancel_event is None:
        cancel_event = threading.Event()

    def check_cancelled():
        _check_receiver_generation(generation)
        if cancel_event.is_set():
            raise CancelledError("Spotify recovery cancelled.")    

    deadline = time.monotonic() + 45
    restart_after = time.monotonic() + 8
    restarted = False

    def read_api(path):
        check_cancelled()
        token = _get_token()
        check_cancelled()

        response = requests.get(
            f"https://api.spotify.com/v1/me/player{path}",
            headers={
                "Authorization": f"Bearer {token}"
            },
            timeout=(3, 5),
        )

        check_cancelled()

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "30")
            raise RuntimeError(
                f"Spotify is limiting requests. Retry after {retry_after}s."
            )

        if response.status_code in (401, 403):
            raise RuntimeError(
                "Spotify authorization failed. Check account access."
            )

        response.raise_for_status()

        if response.status_code == 204:
            return None

        return response.json()

    while time.monotonic() < deadline:
        check_cancelled()
        api_reachable = False

        try:
            devices_data = read_api("/devices") or {}
            api_reachable = True

            device = next(
                (
                    item
                    for item in devices_data.get("devices", [])
                    if item.get("name") == SPOTIFY_DEVICE_NAME
                    and item.get("id")
                    and not item.get("is_restricted", False)
                ),
                None,
            )

            if device is not None:
                playback = read_api("")
                playback_device = (playback or {}).get("device") or {}

                active_here = (
                    playback_device.get("id") == device["id"]
                )

                # Prije restarta očekujemo aktivnu sesiju ako je
                # PiPhone reproducirao glazbu prije promjene mreže.
                # Nakon restarta uređaj može biti dostupan, ali mirovan.
                if active_here or not expect_active or restarted:
                    return {
                        "device_id": device["id"],
                        "playback": playback if active_here else None,
                        "account_playback": playback,
                        "active_here": active_here,
                        "restarted": restarted,
                    }

        except (requests.ConnectionError, requests.Timeout):
            # Kratkotrajni prekid mreže: pokušaj ponovno u istom roku.
            pass

        except requests.HTTPError as error:
            status = (
                error.response.status_code
                if error.response is not None
                else None
            )

            if status is None or status < 500:
                raise RuntimeError(
                    f"Spotify recovery failed: HTTP {status}."
                ) from None

        if (
            not restarted
            and api_reachable
            and time.monotonic() >= restart_after
            and time.monotonic() < deadline
        ):
            try:
                check_cancelled()
                _restart_receiver(generation)
            except (OSError, subprocess.SubprocessError):
                raise RuntimeError(
                    "Could not restart the Spotify receiver."
                ) from None

            restarted = True

        remaining = deadline - time.monotonic()
        if remaining > 0:
            cancel_event.wait(min(2, remaining))

        check_cancelled()

    raise RuntimeError(
        "Spotify did not become available. Try reconnecting again."
    )

def get_device_id():
    generation = receiver_generation()
    _check_receiver_generation(generation)
    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"}

    for recovery_attempt in range(2):
        for attempt in range(DEVICE_DISCOVERY_ATTEMPTS):
            _check_receiver_generation(generation)
            response = requests.get(
                "https://api.spotify.com/v1/me/player/devices",
                headers=headers,
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            _check_receiver_generation(generation)

            devices = response.json().get("devices", [])

            for device in devices:
                if device.get("name") == SPOTIFY_DEVICE_NAME:
                    return device["id"]

            time.sleep(DEVICE_DISCOVERY_DELAY)

        if recovery_attempt == 0:
            print("[WARN] PiPhone unavailable, restarting librespot")

            _restart_receiver(generation)

    return None
# ----------------- SONG ACTIONS ---------------------

def set_playing(should_play):
    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"}
    action = "play" if should_play else "pause"

    response = requests.put(
        f"https://api.spotify.com/v1/me/player/{action}",
        headers=headers,
        timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()

def toggle():
    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"}

    r = requests.get(
        "https://api.spotify.com/v1/me/player",
        headers=headers,
        timeout=REQUEST_TIMEOUT
    )
    r.raise_for_status()

    if r.status_code == 200:
        data = r.json()
        set_playing(not data["is_playing"])
    else:
        raise RuntimeError("No active Spotify player")

def next_track():
    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(
        "https://api.spotify.com/v1/me/player/next",
        headers=headers,
        timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()

def prev_track():
    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(
        "https://api.spotify.com/v1/me/player/previous",
        headers=headers,
        timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()

def seek(position_ms):
    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.put(
        f"https://api.spotify.com/v1/me/player/seek?position_ms={position_ms}",
        headers=headers,
        timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()

def play_track(uri, context_uri=None):
    token = _get_token()
    device_id = get_device_id()
    if not device_id:
        raise RuntimeError("PiPhone Spotify receiver is not available yet.")

    headers = {
        "Authorization": f"Bearer {token}"
    }

    playback = {"uris": [uri]}
    if context_uri:
        playback = {
            "context_uri": context_uri,
            "offset": {"uri": uri},
            "position_ms": 0
        }

    response = requests.put(
        "https://api.spotify.com/v1/me/player/play",
        headers=headers,
        params={"device_id": device_id},
        json=playback,
        timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()

def restore_spotify_playback(device_id, snapshot):
    uri = (snapshot or {}).get("uri")

    if not device_id or not uri:
        raise RuntimeError(
            "Missing Spotify device or playback snapshot."
        )

    position_ms = max(
        0,
        int(snapshot.get("progress_ms", 0) or 0),
    )
    duration_ms = max(
        1,
        int(snapshot.get("duration_ms", 1) or 1),
    )

    # Ne pokušavaj nastaviti iza samoga kraja pjesme.
    position_ms = min(
        position_ms,
        max(0, duration_ms - 1000),
    )

    token = _get_token()

    response = requests.put(
        "https://api.spotify.com/v1/me/player/play",
        headers={
            "Authorization": f"Bearer {token}",
        },
        params={
            "device_id": device_id,
        },
        json={
            "uris": [uri],
            "position_ms": position_ms,
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()

# ----------------------------------------------------

# ----------- PLAYLIST ACTIONS -----------------------


def get_user_playlists():
    token = _get_token()

    headers = {
        "Authorization": f"Bearer {token}"
    }

    r = requests.get(
        "https://api.spotify.com/v1/me/playlists?limit=50",
        headers=headers,
        timeout=REQUEST_TIMEOUT
    )
    r.raise_for_status()

    if r.status_code == 200:
        return r.json().get("items", [])

    return []

def get_user_albums():
    token = _get_token()
    headers = {
        "Authorization": f"Bearer {token}"
    }

    albums = []
    url = "https://api.spotify.com/v1/me/albums?limit=50"

    while url:
        response = requests.get(
            url,
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
        albums.extend(data.get("items", []))
        url = data.get("next")

    return albums


def get_saved_tracks(limit=10, offset=0):
    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(
        "https://api.spotify.com/v1/me/tracks",
        headers=headers,
        params={"limit": limit, "offset": offset},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    items = data.get("items", [])

    return {
        "items": items,
        "next_offset": offset + len(items) if data.get("next") else None,
        "total": data.get("total", len(items)),
    }

def is_library_item_saved(uri):
    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(
        "https://api.spotify.com/v1/me/library/contains",
        headers=headers,
        params={"uris": uri},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    results = response.json()
    return bool(results and results[0])


def save_library_item(uri):
    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.put(
        "https://api.spotify.com/v1/me/library",
        headers=headers,
        params={"uris": uri},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()


def remove_library_item(uri):
    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.delete(
        "https://api.spotify.com/v1/me/library",
        headers=headers,
        params={"uris": uri},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()


def get_recently_played(limit=15):
    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(
        "https://api.spotify.com/v1/me/player/recently-played",
        headers=headers,
        params={"limit": limit},
        timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()
    return response.json().get("items", [])


def get_playlist_tracks(playlist_uri, limit=10, offset=0):
    token = _get_token()
    headers = {
        "Authorization": f"Bearer {token}"
    }
    url = f"https://api.spotify.com/v1/playlists/{playlist_uri.split(':')[-1]}/items"

    response = requests.get(
        url,
        headers=headers,
        params={"limit": limit, "offset": offset},
        timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()
    data = response.json()
    items = data.get("items", [])

    return {
        "items": items,
        "next_offset": offset + len(items) if data.get("next") else None,
        "total": data.get("total", len(items)),
    }

def get_album_tracks(album_id, limit=10, offset=0):
    token = _get_token()
    headers = {
        "Authorization": f"Bearer {token}"
    }

    url = f"https://api.spotify.com/v1/albums/{album_id}/tracks"

    response = requests.get(
        url,
        headers=headers,
        params={"limit": limit, "offset": offset},
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()
    data = response.json()
    items = data.get("items", [])

    return {
        "items": items,
        "next_offset": offset + len(items) if data.get("next") else None,
        "total": data.get("total", len(items)),
    }



# ----------------------------------------------------


# ---------------- SEARCH ACTIONS --------------------

def search_items(query, search_type="track"):
    if search_type not in ("track", "album"):
        raise ValueError(f"Unsupported search type: {search_type}")

    token = _get_token()
    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = requests.get(
        "https://api.spotify.com/v1/search",
        headers=headers,
        params={
            "q": query,
            "type": search_type,
            "limit": 10
        },
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()

    result_key = f"{search_type}s"
    return response.json().get(result_key, {}).get("items", [])


# ----------------------------------------------------


def add_to_queue(uri):
    token = _get_token()
    device_id = get_device_id()

    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = requests.post(
        "https://api.spotify.com/v1/me/player/queue",
        headers=headers,
        params={
            "uri": uri,
            "device_id": device_id
        },
        timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()



# ------------------ USER PROFILE ACTIONS ------------

def get_me():
    token = _get_token()

    headers = {
        "Authorization": f"Bearer {token}"
    }   

    r = requests.get(
        "https://api.spotify.com/v1/me",
        headers=headers,
        timeout=REQUEST_TIMEOUT
    )
    r.raise_for_status()

    if r.status_code == 200:
        return r.json()

    return None

# ----------------------------------------------------
