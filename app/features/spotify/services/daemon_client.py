import json
import os
import time
import socket
from app.core.state import get_song_state, get_state
from app.core.config import SONG_STATE_FILE, RECENT_TRACKS_FILE

POLL_SOCKET_PATH = "/tmp/piphone-spotify-poll.sock"

pending_seek_position = None
seek_start_time = 0

pending_play_state = None
play_start_time = 0

pending_track_change = False
track_before_change = None
expected_track_after_change = None
track_change_start = 0

TRACK_CHANGE_TIMEOUT = 15
TRACK_CHANGE_SETTLE_TIME = 0.35
UNEXPECTED_TRACK_FALLBACK_TIME = 2
SEEK_CONFIRM_TIMEOUT = 5
SEEK_CONFIRM_TOLERANCE_MS = 1500

def request_immediate_poll():
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as client:
            client.sendto(b"poll", POLL_SOCKET_PATH)
    except OSError:
        pass

def expect_track_change(expected_track_id=None):
    global pending_track_change, track_before_change, track_change_start
    global expected_track_after_change
    global pending_seek_position, seek_start_time

    if not pending_track_change:
        track_before_change = get_song_state().get("track_id")

    expected_track_after_change = expected_track_id
    pending_track_change = True
    track_change_start = time.time()
    pending_seek_position = 0
    seek_start_time = track_change_start


def start_sync(root):
    recent_tracks_mtime_ns = None

    def sync_recent_tracks():
        nonlocal recent_tracks_mtime_ns

        try:
            mtime_ns = os.stat(RECENT_TRACKS_FILE).st_mtime_ns
            if mtime_ns == recent_tracks_mtime_ns:
                return

            with open(RECENT_TRACKS_FILE, encoding="utf-8") as f:
                recent_tracks = json.load(f)

            if isinstance(recent_tracks, list):
                get_state()["device_recent_tracks"] = recent_tracks
                get_state()["recent_tracks"] = recent_tracks
                recent_tracks_mtime_ns = mtime_ns
        except FileNotFoundError:
            get_state()["device_recent_tracks"] = []
            get_state()["recent_tracks"] = []
        except (OSError, json.JSONDecodeError) as error:
            print("RECENT TRACKS ERROR:", error)

    def sync():
        global pending_seek_position, pending_play_state
        global seek_start_time, play_start_time
        global pending_track_change, expected_track_after_change

        try:
            with open(SONG_STATE_FILE) as f:
                file_state = json.load(f)

            sync_recent_tracks()
            song_state = get_song_state()

            # Local playback owns the shared song state until the user
            # explicitly starts a Spotify track again.
            if song_state.get("source") == "local":
                root.after(300, sync)
                return

            now = time.time()
            incoming_track_id = file_state.get("track_id")

            if pending_track_change:
                if expected_track_after_change is not None:
                    expected_track_started = (
                        incoming_track_id == expected_track_after_change
                    )
                    unexpected_track_started = (
                        incoming_track_id != track_before_change
                        and now - track_change_start
                        >= UNEXPECTED_TRACK_FALLBACK_TIME
                    )
                    changed = expected_track_started or unexpected_track_started
                else:
                    changed = incoming_track_id != track_before_change

                settled = now - track_change_start >= TRACK_CHANGE_SETTLE_TIME
                timed_out = now - track_change_start >= TRACK_CHANGE_TIMEOUT

                if not ((changed and settled) or timed_out):
                    root.after(300, sync)
                    return

                pending_track_change = False
                expected_track_after_change = None

            current_track_id = song_state.get("track_id")
            current_progress = song_state.get("progress_ms", 0) or 0
            duration_ms = song_state.get("duration_ms", 1) or 1
            incoming_progress = file_state.get("progress_ms", 0) or 0

            same_track_restarted = (
                incoming_track_id == current_track_id
                and pending_seek_position is None
                and incoming_progress <= 10000
                and current_progress >= max(10000, duration_ms - 20000)
            )

            track_changed = (
                incoming_track_id != current_track_id
                or same_track_restarted
            )

            get_state()["next_song"] = file_state.get("next_song")
            get_state()["queue"] = file_state.get("queue", [])

            # ---- ALWAYS ----
            song_state["source"] = "spotify"
            song_state["track_id"] = incoming_track_id
            song_state["track"] = file_state.get("track")
            song_state["artist"] = file_state.get("artist")
            song_state["album_id"] = file_state.get("album_id")
            song_state["album_name"] = file_state.get("album_name")
            song_state["duration_ms"] = file_state.get("duration_ms", 1)
            song_state["image_url"] = file_state.get("image_url")

            # ---- PROGRESS ----
            incoming = file_state.get("progress_ms", 0)

            if track_changed:
                song_state["progress_ms"] = incoming
                pending_seek_position = None
            elif pending_seek_position is None:
                current = song_state["progress_ms"]
                if song_state.get("is_playing"):
                    # file is ~1s behind while playing — never regress progress
                    if incoming >= current - 2000:
                        song_state["progress_ms"] = max(incoming, current)
                else:
                    song_state["progress_ms"] = incoming
            else:
                seek_elapsed = now - seek_start_time
                expected_position = pending_seek_position
                if song_state.get("is_playing"):
                    expected_position += seek_elapsed * 1000

                seek_confirmed = (
                    pending_seek_position - SEEK_CONFIRM_TOLERANCE_MS
                    <= incoming
                    <= expected_position + SEEK_CONFIRM_TOLERANCE_MS
                )

                if seek_confirmed:
                    song_state["progress_ms"] = max(incoming, int(expected_position))
                    pending_seek_position = None
                elif seek_elapsed >= SEEK_CONFIRM_TIMEOUT:
                    pending_seek_position = None

            # ---- PLAY ----
            incoming_play = file_state.get("is_playing", False)

            state = get_state()

            if incoming_play and state.get("playback_owner") != "local":
                state["playback_owner"] = "spotify"

            if track_changed:
                song_state["is_playing"] = incoming_play
                pending_play_state = None
            elif pending_play_state is None:
                song_state["is_playing"] = incoming_play
            elif incoming_play == pending_play_state:
                song_state["is_playing"] = incoming_play
                pending_play_state = None
            elif now - play_start_time > 2:
                song_state["is_playing"] = incoming_play
                pending_play_state = None

        except Exception as e:
            print("DAEMON ERROR:", e)

        root.after(300, sync)

    sync()
