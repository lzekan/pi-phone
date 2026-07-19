import requests
import os
import json
import threading
import time

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
TOKEN_FILE = "/home/lukaz/pi-phone/tokens/tokens.json"
REQUEST_TIMEOUT = (3.05, 10)

_access_token = None
_token_expires_at = 0
_token_lock = threading.Lock()

id_me = None

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

def get_recently_played():
    token = _get_token()

    headers = {
        "Authorization": f"Bearer {token}"
    }

    r = requests.get(
        "https://api.spotify.com/v1/me/player/recently-played?limit=10",
        headers=headers,
        timeout=REQUEST_TIMEOUT
    )
    r.raise_for_status()

    if r.status_code == 200:
        return r.json().get("items", [])

    return []

def play_track(uri):
    token = _get_token()

    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = requests.put(
        "https://api.spotify.com/v1/me/player/play",
        headers=headers,
        json={"uris": [uri]},
        timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()

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

def get_playlist_tracks(playlist_uri):
    token = _get_token()
    headers = {
        "Authorization": f"Bearer {token}"
    }
    tracks = []
    url = f"https://api.spotify.com/v1/playlists/{playlist_uri.split(':')[-1]}/items?limit=50"

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
