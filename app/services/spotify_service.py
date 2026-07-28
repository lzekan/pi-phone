import requests
import os
import json
import threading
import time
import subprocess

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

def get_device_id():
    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"}

    for recovery_attempt in range(2):
        for attempt in range(DEVICE_DISCOVERY_ATTEMPTS):
            response = requests.get(
                "https://api.spotify.com/v1/me/player/devices",
                headers=headers,
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()

            devices = response.json().get("devices", [])

            for device in devices:
                if device.get("name") == SPOTIFY_DEVICE_NAME:
                    return device["id"]

            time.sleep(DEVICE_DISCOVERY_DELAY)

        if recovery_attempt == 0:
            print("[WARN] PiPhone unavailable, restarting librespot")

            subprocess.run(
                [
                    "systemctl",
                    "--user",
                    "restart",
                    "piphone-spotify.service"
                ],
                timeout=10,
                check=True
            )    

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

def get_playlist_tracks(playlist_uri):
    token = _get_token()
    headers = {
        "Authorization": f"Bearer {token}"
    }
    tracks = []
    url = f"https://api.spotify.com/v1/playlists/{playlist_uri.split(':')[-1]}/items"

    while url:
        response = requests.get(
            url,
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
        tracks.extend(data.get("items", []))
        url = data.get("next")

    return tracks   

def get_album_tracks(album_id):
    token = _get_token()
    headers = {
        "Authorization": f"Bearer {token}"
    }

    tracks = []
    url = f"https://api.spotify.com/v1/albums/{album_id}/tracks"

    while url:
        response = requests.get(
            url, 
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )

        response.raise_for_status()
        data = response.json()
        tracks.extend(data.get("items", []))
        url = data.get("next")

    return tracks   



# ----------------------------------------------------


# ---------------- SEARCH ACTIONS --------------------

def search_tracks(query):
    token = _get_token()
    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = requests.get(
        "https://api.spotify.com/v1/search",
        headers=headers,
        params={
            "q": query,
            "type": "track",
            "limit": 10
        },
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()

    return response.json().get("tracks", {}).get("items", [])


# ----------------------------------------------------



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
