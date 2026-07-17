from app.services.image_cache import get_photo_async

def render_player(root, state):
    song = state["song"]

    # primjer
    root.track_label.config(text=song["track"])
    root.artist_label.config(text=song["artist"])

    track_id = song.get("track_id") or (
        song.get("track"), song.get("artist"), song.get("duration_ms")
    )
    if getattr(root, "cover_track_id", None) == track_id:
        return

    root.cover_track_id = track_id

    def show_cover(photo):
        if root.cover_track_id != track_id:
            return
        root.cover_label.config(image=photo if photo is not None else "")
        root.cover_label.image = photo

    get_photo_async(root, song.get("image_url"), (300, 300), show_cover)
