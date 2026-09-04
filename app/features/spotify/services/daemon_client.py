import json
import os
import time
import socket
from app.core.state import get_song_state, get_state
from app.core.config import SONG_STATE_FILE, RECENT_TRACKS_FILE

POLL_SOCKET_PATH = "/tmp/piphone-spotify-poll.sock"

_ignore_song_file_mtime = None

pending_seek_position = None
seek_start_time = 0

pending_play_state = None
play_start_time = 0

pending_track_change = False
track_before_change = None
expected_track_after_change = None
track_change_start = 0
track_request_started_ns = 0
track_before_progress = 0
_last_confirmed_song = None
_navigation_fallback_song = None
_restore_navigation_on_failure = False
_navigation_failed_at_ns = 0


def remember_confirmed_song(song):
    global _last_confirmed_song
    if song.get("source", "spotify") != "spotify" or not song.get("track_id"):
        return
    fields = ("track_id", "track", "artist", "album_id", "album_name",
              "progress_ms", "duration_ms", "is_playing", "image_url")
    _last_confirmed_song = {key: song.get(key) for key in fields}
    _last_confirmed_song["source"] = "spotify"

TRACK_CHANGE_TIMEOUT = 15
TRACK_CHANGE_SETTLE_TIME = 0.35
SEEK_CONFIRM_TIMEOUT = 5
SEEK_CONFIRM_TOLERANCE_MS = 1500

def request_immediate_poll(confirm=False):
    try:
        message = b"poll"
        if confirm:
            message = ("confirm:" + (expected_track_after_change or "")).encode("ascii")
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as client:
            client.sendto(message, POLL_SOCKET_PATH)
    except OSError:
        pass

def expect_track_change(expected_track_id=None, restore_on_failure=False):
    global pending_track_change, track_before_change, track_change_start
    global expected_track_after_change
    global pending_seek_position, seek_start_time
    global track_request_started_ns, track_before_progress
    global _navigation_fallback_song, _restore_navigation_on_failure
    global _navigation_failed_at_ns

    if restore_on_failure:
        if _last_confirmed_song is not None:
            _navigation_fallback_song = dict(_last_confirmed_song)
        elif not pending_track_change or _navigation_fallback_song is None:
            # Before the first confirmed observation, retain the previous
            # display as a fallback only; it will be explicitly unconfirmed.
            _navigation_fallback_song = dict(get_song_state())
    else:
        _navigation_fallback_song = None
    _restore_navigation_on_failure = restore_on_failure
    _navigation_failed_at_ns = 0
    get_state()["spotify_navigation_unconfirmed"] = False

    if not pending_track_change:
        track_before_change = get_song_state().get("track_id")
    track_before_progress = get_song_state().get("progress_ms", 0) or 0

    expected_track_after_change = expected_track_id
    pending_track_change = True
    track_change_start = time.time()
    track_request_started_ns = time.time_ns()
    pending_seek_position = 0
    seek_start_time = track_change_start
    get_state()["spotify_playback_pending"] = True
    get_state()["spotify_playback_error"] = None


def mark_track_change_unconfirmed():
    global pending_seek_position, pending_play_state
    global _navigation_failed_at_ns
    state = get_state()
    if get_song_state().get("source") != "spotify":
        return
    if not state.get("spotify_playback_error"):
        print(f"[PLAYBACK] Confirmation missing for {expected_track_after_change}")
    state["spotify_playback_pending"] = False
    if _restore_navigation_on_failure:
        if not _navigation_failed_at_ns:
            _navigation_failed_at_ns = time.time_ns()
            if _navigation_fallback_song and _navigation_fallback_song.get("track_id"):
                get_song_state().update(_navigation_fallback_song)
        state["spotify_navigation_unconfirmed"] = True
        state["spotify_playback_error"] = "Track change not confirmed."
    else:
        state["spotify_playback_error"] = "Playback not confirmed. Press Play to retry."
    get_song_state()["is_playing"] = False
    pending_seek_position = None
    pending_play_state = None
    # Keep pending_track_change: an old empty snapshot is NOT a confirmation.
    # A later matching observation can still recover without a second command.


def accept_track_observation(file_state, file_mtime, now):
    global pending_track_change, expected_track_after_change
    global pending_seek_position, pending_play_state
    if not pending_track_change:
        return True
    incoming = file_state.get("track_id")
    observed_at = file_state.get("observed_at_ns", file_mtime)
    fresh = observed_at >= track_request_started_ns
    if expected_track_after_change is not None:
        changed = incoming == expected_track_after_change
    else:
        changed = bool(incoming) and (
            incoming != track_before_change
            or (track_before_progress >= 3000
                and (file_state.get("progress_ms") or 0) < 2000)
        )
    if _restore_navigation_on_failure and _navigation_failed_at_ns:
        # After failure, a newly requested non-empty observation may confirm
        # that the OLD track is still playing. A late NEW track is valid too.
        changed = bool(incoming) and (
            changed or observed_at >= _navigation_failed_at_ns
        )
    settled = now - track_change_start >= TRACK_CHANGE_SETTLE_TIME
    if not (fresh and changed and settled):
        if now - track_change_start >= TRACK_CHANGE_TIMEOUT:
            mark_track_change_unconfirmed()
        return False
    pending_track_change = False
    expected_track_after_change = None
    pending_seek_position = None
    pending_play_state = None
    get_state()["spotify_playback_pending"] = False
    get_state()["spotify_playback_error"] = None
    get_state()["spotify_navigation_unconfirmed"] = False
    print(f"[PLAYBACK] Confirmed track={incoming}")
    return True

def finish_spotify_recovery(result=None, error=None):
    global _ignore_song_file_mtime
    global pending_track_change, expected_track_after_change
    global pending_seek_position, pending_play_state

    state = get_state()
    restored_snapshot = (result or {}).get("restored_snapshot")
    confirm_restored_track = False

    try:
        _ignore_song_file_mtime = os.stat(
            SONG_STATE_FILE
        ).st_mtime_ns
    except OSError:
        _ignore_song_file_mtime = -1

    pending_track_change = False
    expected_track_after_change = None
    pending_seek_position = None
    pending_play_state = None

    state["spotify_reconnect_error"] = error
    state["spotify_playback_pending"] = False
    state["spotify_playback_error"] = None
    state["spotify_navigation_unconfirmed"] = False

    try:
        song = get_song_state()

        if song.get("source") == "local":
            return

        if error is not None:
            return

        if restored_snapshot is not None:
            song.update({
                "source": "spotify",
                "track_id": restored_snapshot.get("track_id"),
                "track": restored_snapshot.get("track") or "",
                "artist": restored_snapshot.get("artist") or "",
                "album_id": restored_snapshot.get("album_id") or "",
                "album_name": restored_snapshot.get("album_name") or "",
                "duration_ms": (
                    restored_snapshot.get("duration_ms") or 1
                ),
                "progress_ms": (
                    restored_snapshot.get("progress_ms") or 0
                ),
                "is_playing": True,
                "image_url": restored_snapshot.get("image_url"),
            })

            state["next_song"] = None
            state["queue"] = []
            state["playback_owner"] = "spotify"

            expect_track_change(
                restored_snapshot.get("track_id")
            )
            confirm_restored_track = True

            print(
                "[SPOTIFY] Restored playback, waiting for "
                f"confirmation track={song['track_id']}"
            )
            return

        playback = (result or {}).get("playback") or {}
        item = playback.get("item") or {}
        album = item.get("album") or {}
        artists = item.get("artists") or []
        images = album.get("images") or []

        song.update({
            "source": "spotify",
            "track_id": item.get("id"),
            "track": item.get("name") or "",
            "artist": ", ".join(
                artist.get("name", "") for artist in artists
            ),
            "album_id": album.get("id") or "",
            "album_name": album.get("name") or "",
            "duration_ms": item.get("duration_ms") or 1,
            "progress_ms": playback.get("progress_ms") or 0,
            "is_playing": bool(
                item and playback.get("is_playing")
            ),
            "image_url": (
                images[0].get("url") if images else None
            ),
        })
        remember_confirmed_song(song)

        state["next_song"] = None
        state["queue"] = []

        if song["is_playing"]:
            state["playback_owner"] = "spotify"
        elif state.get("playback_owner") == "spotify":
            state["playback_owner"] = None

    finally:
        state["spotify_reconnecting"] = False
        request_immediate_poll(
            confirm=confirm_restored_track
        )


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
        global _ignore_song_file_mtime
        global pending_seek_position, pending_play_state
        global seek_start_time, play_start_time
        global pending_track_change, expected_track_after_change

        # Also expire the optimistic display if the daemon/file is unavailable.
        if (pending_track_change and get_song_state().get("source") == "spotify"
                and not get_state().get("spotify_reconnecting", False)
                and time.time() - track_change_start >= TRACK_CHANGE_TIMEOUT):
            mark_track_change_unconfirmed()

        try:
            with open(SONG_STATE_FILE) as f:
                file_mtime = os.fstat(f.fileno()).st_mtime_ns
                file_state = json.load(f)

            sync_recent_tracks()
            song_state = get_song_state()

            # Local playback owns the shared song state until the user
            # explicitly starts a Spotify track again.
            if song_state.get("source") == "local":
                root.after(300, sync)
                return
            
            if get_state().get("spotify_reconnecting", False):
                root.after(300, sync)
                return

            if _ignore_song_file_mtime is not None:
                if file_mtime == _ignore_song_file_mtime:
                    root.after(300, sync)
                    return

                _ignore_song_file_mtime = None

            now = time.time()
            incoming_track_id = file_state.get("track_id")

            if not accept_track_observation(file_state, file_mtime, now):
                root.after(300, sync)
                return

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

            # Cache the actual observation, never optimistic UI metadata.
            remember_confirmed_song(file_state)

        except Exception as e:
            print("DAEMON ERROR:", e)

        root.after(300, sync)

    sync()
