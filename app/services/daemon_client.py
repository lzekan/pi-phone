import json
import os
import time
from app.core.state import get_song_state, get_state
from app.core.config import SONG_STATE_FILE, RECENT_TRACKS_FILE

pending_seek_position = None
seek_start_time = 0

pending_play_state = None
play_start_time = 0

pending_track_change = False
track_before_change = None
track_change_start = 0

TRACK_CHANGE_TIMEOUT = 3
TRACK_CHANGE_SETTLE_TIME = 0.35


def expect_track_change():
    global pending_track_change, track_before_change, track_change_start
    global pending_seek_position, seek_start_time

    if not pending_track_change:
        track_before_change = get_song_state().get("track_id")
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
                get_state()["recent_tracks"] = recent_tracks
                recent_tracks_mtime_ns = mtime_ns
        except FileNotFoundError:
            get_state()["recent_tracks"] = []
        except (OSError, json.JSONDecodeError) as error:
            print("RECENT TRACKS ERROR:", error)

    def sync():
        global pending_seek_position, pending_play_state
        global seek_start_time, play_start_time
        global pending_track_change

        try:
            with open(SONG_STATE_FILE) as f:
                file_state = json.load(f)

            sync_recent_tracks()
            song_state = get_song_state()

            now = time.time()
            incoming_track_id = file_state.get("track_id")

            if pending_track_change:
                changed = incoming_track_id != track_before_change
                settled = now - track_change_start >= TRACK_CHANGE_SETTLE_TIME
                timed_out = now - track_change_start >= TRACK_CHANGE_TIMEOUT

                if not ((changed and settled) or timed_out):
                    root.after(300, sync)
                    return

                pending_track_change = False

            track_changed = incoming_track_id != song_state.get("track_id")
            get_state()["next_song"] = file_state.get("next_song")

            # ---- ALWAYS ----
            song_state["track_id"] = incoming_track_id
            song_state["track"] = file_state.get("track")
            song_state["artist"] = file_state.get("artist")
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
                if abs(incoming - pending_seek_position) < 1500 or now - seek_start_time > 2:
                    song_state["progress_ms"] = incoming
                    pending_seek_position = None

            # ---- PLAY ----
            incoming_play = file_state.get("is_playing", False)

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
