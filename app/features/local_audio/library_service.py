import json
import subprocess
from pathlib import Path

from app.core.config import MUSIC_LIBRARY_DIR


SUPPORTED_EXTENSIONS = {".flac", ".mp3", ".wav", ".m4a", ".ogg", ".opus"}


def _fallback_names(path):
    parts = path.stem.split(" - ", 1)
    if len(parts) == 2:
        return parts[1].strip(), parts[0].strip()
    return path.stem, "Unknown artist"


def _probe_file(path):
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:format_tags=title,artist,album",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    data = json.loads(result.stdout or "{}")
    format_data = data.get("format") or {}
    tags = {
        str(key).lower(): value
        for key, value in (format_data.get("tags") or {}).items()
    }
    fallback_title, fallback_artist = _fallback_names(path)

    try:
        duration_ms = max(0, int(float(format_data.get("duration", 0)) * 1000))
    except (TypeError, ValueError):
        duration_ms = 0

    return {
        "path": str(path),
        "title": tags.get("title") or fallback_title,
        "artist": tags.get("artist") or fallback_artist,
        "album": tags.get("album") or "",
        "duration_ms": duration_ms,
        "format": path.suffix.lstrip(".").upper(),
        "size_bytes": path.stat().st_size,
    }


def scan_library(music_dir=MUSIC_LIBRARY_DIR):
    library_path = Path(music_dir).expanduser()
    if not library_path.exists():
        return []

    tracks = []
    for path in library_path.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        try:
            tracks.append(_probe_file(path))
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as error:
            fallback_title, fallback_artist = _fallback_names(path)
            tracks.append({
                "path": str(path),
                "title": fallback_title,
                "artist": fallback_artist,
                "album": "",
                "duration_ms": 0,
                "format": path.suffix.lstrip(".").upper(),
                "size_bytes": path.stat().st_size,
                "metadata_error": str(error),
            })

    tracks.sort(key=lambda track: (
        track["artist"].casefold(),
        track["title"].casefold(),
        track["path"].casefold(),
    ))
    return tracks
