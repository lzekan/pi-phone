# Program koji svako 1 sekundu salje zahtjev na Web API i dohvaca relevantne podatke o 
# pjesmi koja se trenutno pusta (title, artist, album, cover)

import requests
import time
import json
import os

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
TOKEN_FILE = "/home/lukaz/pi-phone/tokens/tokens.json"
SONG_STATE_FILE = "/home/lukaz/pi-phone/state/song_state.json"
RECENT_TRACKS_FILE = "/home/lukaz/pi-phone/state/recent_tracks.json"
PRELOAD_BEFORE_END_MS = 30000
QUEUE_REFRESH_SECONDS = 5
POLL_SECONDS = 3
RECENT_TRACKS_LIMIT = 5
REQUEST_TIMEOUT = (3.05, 10)


def track_payload(track):
    images = track.get("album", {}).get("images", [])
    return {
        "track_id": track.get("id"),
        "track": track.get("name", ""),
        "artist": track.get("artists", [{}])[0].get("name", ""),
        "album_id": track.get("album", {}).get("id"),
        "album_name": track.get("album", {}).get("name", ""),
        "uri": track.get("uri"),
        "duration_ms": track.get("duration_ms", 1),
        "image_url": images[0]["url"] if images else None
    }


def recent_track_payload(track):
    payload = track_payload(track)
    return {
        "track_id": payload["track_id"],
        "name": payload["track"],
        "artist": payload["artist"],
        "album_id": payload["album_id"],
        "album_name": payload["album_name"],
        "uri": payload["uri"],
        "image_url": payload["image_url"],
        "duration_ms": payload["duration_ms"],
        "played_at_ms": int(time.time() * 1000)
    }


def load_recent_tracks():
    try:
        with open(RECENT_TRACKS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []

        unique_tracks = []
        seen_track_ids = set()
        for track in data:
            track_id = track.get("track_id")
            if track_id in seen_track_ids:
                continue
            seen_track_ids.add(track_id)
            unique_tracks.append(track)

        return unique_tracks[:RECENT_TRACKS_LIMIT]
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_recent_tracks(tracks):
    temp_file = f"{RECENT_TRACKS_FILE}.tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(tracks, f, indent=4, ensure_ascii=False)
    os.replace(temp_file, RECENT_TRACKS_FILE)


def save_inactive_state():
    state = {
        "track_id": None,
        "track": "",
        "artist": "",
        "album_id": "",
        "album_name": "",
        "progress_ms": 0,
        "duration_ms": 1,
        "is_playing": False,
        "image_url": None,
        "next_song": None,
        "queue": []
    }

    with open(SONG_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4, ensure_ascii=False)

def load_refresh_token():
    with open(TOKEN_FILE, "r") as f:
        return json.load(f)["refresh_token"]


def save_refresh_token(new_token):
    with open(TOKEN_FILE, "w") as f:
        json.dump({"refresh_token": new_token}, f)


def get_access_token():
    refresh_token = load_refresh_token()

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

    access_token = data["access_token"]
    expires_in = data["expires_in"]

    # ako Spotify vrati novi refresh token → spremi ga
    if "refresh_token" in data:
        print("[INFO] Refresh token updated")
        save_refresh_token(data["refresh_token"])

    return access_token, expires_in


while True:
    try:
        access_token, expires_in = get_access_token()
        break
    except (requests.ConnectionError, requests.Timeout) as error:
        print(f"[WARN] Token connection failed: {error}. Retrying in {POLL_SECONDS}s")
        time.sleep(POLL_SECONDS)

token_expiry_time = time.time() + expires_in

headers = {
    "Authorization": f"Bearer {access_token}"
}

next_song = None
queue_tracks = []
last_queue_fetch = 0
last_track_id = None
recent_history = load_recent_tracks()
save_recent_tracks(recent_history)


while True:
    remaining = int(token_expiry_time - time.time())
    print(f"[DEBUG] Token expires in: {remaining}s")

    # proactive refresh (30s prije isteka)
    if remaining < 30:
        print("[INFO] Refreshing token (proactive)...")
        try:
            access_token, expires_in = get_access_token()
            token_expiry_time = time.time() + expires_in
            headers["Authorization"] = f"Bearer {access_token}"
        except requests.RequestException as error:
            print(f"[WARN] Token refresh failed: {error}. Retrying next cycle")
            time.sleep(POLL_SECONDS)
            continue

    try:
        r = requests.get(
            "https://api.spotify.com/v1/me/player/currently-playing",
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )
    except requests.RequestException as error:
        print(f"[WARN] Spotify poll failed: {error}. Retrying next cycle")
        time.sleep(POLL_SECONDS)
        continue

    if r.status_code == 200:
        data = r.json()

        if data and data.get("item"):
            images = data["item"]["album"]["images"]
            image_url = images[0]["url"] if images else None
            track_id = data["item"]["id"]

            new_track = track_id != last_track_id
            if new_track:
                next_song = None
                queue_tracks = []
                last_track_id = track_id
                last_queue_fetch = 0

                recent_track = recent_track_payload(data["item"])
                recent_history = [
                    track for track in recent_history
                    if track.get("track_id") != track_id                    # uklanjanje duplikata iz Recently Played
                ]
                recent_history.insert(0, recent_track)
                recent_history = recent_history[:RECENT_TRACKS_LIMIT]
                save_recent_tracks(recent_history)

            remaining_ms = data["item"]["duration_ms"] - data["progress_ms"]
            now = time.time()
            near_end = remaining_ms <= PRELOAD_BEFORE_END_MS
            queue_refresh_due = now - last_queue_fetch >= QUEUE_REFRESH_SECONDS
            if new_track or (near_end and queue_refresh_due):
                last_queue_fetch = now
                try:
                    queue_response = requests.get(
                        "https://api.spotify.com/v1/me/player/queue",
                        headers=headers,
                        timeout=REQUEST_TIMEOUT
                    )
                    if queue_response.status_code == 200:
                        queue_items = queue_response.json().get("queue", [])
                        queue_tracks = [track_payload(item) for item in queue_items]
                        next_song = queue_tracks[0] if queue_tracks else None
                except requests.RequestException as error:
                    print(f"[WARN] Queue preload failed: {error}. Keeping current state")

            state = {
                "track_id": track_id,
                "track": data["item"]["name"],
                "artist": data["item"]["artists"][0]["name"],
                "album_name": data["item"]["album"]["name"],
                "album_id": data["item"]["album"]["id"],
                "progress_ms": data["progress_ms"],
                "duration_ms": data["item"]["duration_ms"],
                "is_playing": data["is_playing"],
                "image_url": image_url,
                "next_song": next_song,
                "queue": queue_tracks
            }

            with open(SONG_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=4, ensure_ascii=False)

            print(state)

        else:
            next_song = None
            queue_tracks = []
            save_inactive_state()
            print("Nothing playing")

    elif r.status_code == 204:
        next_song = None
        queue_tracks = []
        save_inactive_state()
        print("Nothing playing")

    elif r.status_code == 401:
        print("[WARN] Token expired → forcing refresh")
        try:
            access_token, expires_in = get_access_token()
            token_expiry_time = time.time() + expires_in
            headers["Authorization"] = f"Bearer {access_token}"
        except requests.RequestException as error:
            print(f"[WARN] Forced token refresh failed: {error}. Retrying next cycle")

    elif r.status_code == 429:
        retry_after = int(r.headers.get("Retry-After", 30))
        print(f"[WARN] Rate limited, retrying in {retry_after}s")
        time.sleep(retry_after)
        continue

    else:
        print("Error:", r.status_code)

    time.sleep(POLL_SECONDS)
