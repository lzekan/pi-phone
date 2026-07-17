def render_home(root, state):
    tracks = state["recent_tracks"]
    playlists = state["playlists"]

    # render samo ako treba (flag ili diff check)