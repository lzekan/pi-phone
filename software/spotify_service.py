import requests
import os
import json

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
TOKEN_FILE = "/home/lukaz/pi-phone/tokens/tokens.json"

def _get_token():
    with open(TOKEN_FILE, "r") as f:
        refresh_token = json.load(f)["refresh_token"]

    response = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET
        }
    )

    return response.json()["access_token"]

def toggle():
    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"}

    r = requests.get("https://api.spotify.com/v1/me/player", headers=headers)

    if r.status_code == 200:
        data = r.json()
        if data["is_playing"]:
            requests.put("https://api.spotify.com/v1/me/player/pause", headers=headers)
        else:
            requests.put("https://api.spotify.com/v1/me/player/play", headers=headers)

def next_track():
    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"}
    requests.post("https://api.spotify.com/v1/me/player/next", headers=headers)

def prev_track():
    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"}
    requests.post("https://api.spotify.com/v1/me/player/previous", headers=headers)

def seek(position_ms):
    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"}
    requests.put(
        f"https://api.spotify.com/v1/me/player/seek?position_ms={position_ms}",
        headers=headers
    )