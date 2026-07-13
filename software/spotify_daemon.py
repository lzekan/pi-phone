# Program koji svako 1 sekundu salje zahtjev na Web API i dohvaca relevantne podatke o 
# pjesmi koja se trenutno pusta (title, artist, album, cover)

import requests
import time
import json
import os

CLIENT_ID = "82e8e1b184b54b5a9d534f6382a8f9e2"
CLIENT_SECRET = "93ed466fd50e498a8fb9c0e486ecebe7"
TOKEN_FILE = "/home/lukaz/pi-phone/software/tokens.json"

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
        }
    )

    data = response.json()

    access_token = data["access_token"]
    expires_in = data["expires_in"]

    # ako Spotify vrati novi refresh token → spremi ga
    if "refresh_token" in data:
        print("[INFO] Refresh token updated")
        save_refresh_token(data["refresh_token"])

    return access_token, expires_in


access_token, expires_in = get_access_token()
token_expiry_time = time.time() + expires_in

headers = {
    "Authorization": f"Bearer {access_token}"
}


while True:
    remaining = int(token_expiry_time - time.time())
    print(f"[DEBUG] Token expires in: {remaining}s")

    # proactive refresh (30s prije isteka)
    if remaining < 30:
        print("[INFO] Refreshing token (proactive)...")
        access_token, expires_in = get_access_token()
        token_expiry_time = time.time() + expires_in
        headers["Authorization"] = f"Bearer {access_token}"

    r = requests.get(
        "https://api.spotify.com/v1/me/player/currently-playing",
        headers=headers
    )

    if r.status_code == 200:
        data = r.json()

        if data and data.get("item"):
            track = data["item"]["name"]
            artist = data["item"]["artists"][0]["name"]

            print(f"{track} - {artist}")
        else:
            print("Nothing playing")

    elif r.status_code == 204:
        print("Nothing playing")

    elif r.status_code == 401:
        print("[WARN] Token expired → forcing refresh")
        access_token, expires_in = get_access_token()
        token_expiry_time = time.time() + expires_in
        headers["Authorization"] = f"Bearer {access_token}"

    else:
        print("Error:", r.status_code)

    time.sleep(1)