from threading import Thread
from tkinter import BOTH, BOTTOM, HORIZONTAL, LEFT, NORMAL, RIGHT, TOP, X
from tkinter import Button, Canvas, Entry, Frame, Label, Scrollbar

from app.controller.controller_home import load_home
from app.controller.controller_navigation import go_player, go_playlist
from app.controller.controller_player import on_toggle_play, play_selected_track
from app.controller.controller_search import load_search_results
from app.core.state import get_state
from app.services.image_cache import get_photo_async
from app.ui.components.virtual_keyboard import VirtualKeyboard


def _get_track_id(song):
    track_id = song.get("track_id")
    if track_id:
        return track_id
    if song.get("track") or song.get("artist"):
        return song.get("track"), song.get("artist"), song.get("duration_ms")
    return None


def render_home(root, state, button_style):
    frame = Frame(root, bg="black")

    header = Frame(frame, bg="black")
    Label(
        header,
        text="Home",
        fg="white",
        bg="black",
        font=("DejaVu Sans", 24, "bold"),
    ).pack(side=LEFT)
    Button(
        header,
        text="X",
        command=root.destroy,
        fg="white",
        bg="#2A2A2A",
        activeforeground="white",
        activebackground="#D64545",
        font=("DejaVu Sans", 14, "bold"),
        relief="flat",
        borderwidth=0,
        highlightthickness=0,
        takefocus=False,
        width=3,
        pady=4,
    ).pack(side=RIGHT)
    header.pack(fill=X, padx=12, pady=(12, 6))

    search_box = Frame(
        frame,
        bg="#202020",
        highlightbackground="#3A3A3A",
        highlightthickness=0.1,
    )
    search_box.pack(fill=X, padx=14, pady=(2, 16))

    search_icon = Canvas(
        search_box,
        width=42,
        height=48,
        bg="#202020",
        highlightthickness=0,
        cursor="hand2",
    )
    search_circle = search_icon.create_oval(
        10, 12, 27, 29, outline="#B3B3B3", width=3
    )
    search_handle = search_icon.create_line(
        25, 27, 33, 35, fill="#B3B3B3", width=3
    )
    search_icon.pack(side=LEFT)

    search_placeholder = "Search tracks..."
    search_has_placeholder = True
    search_entry = Entry(
        search_box,
        bg="#202020",
        fg="#B3B3B3",
        insertbackground="white",
        relief="flat",
        borderwidth=0,
        highlightthickness=0,
        font=("DejaVu Sans", 15, "bold"),
    )
    search_entry.insert(0, search_placeholder)
    search_entry.pack(side=LEFT, fill=X, expand=True, padx=(0, 14), pady=12)
    virtual_keyboard = VirtualKeyboard(frame)
    search_results_box = Frame(
        frame,
        bg="#181818",
        highlightbackground="#3A3A3A",
        highlightthickness=1,
    )
    search_results_canvas = Canvas(
        search_results_box,
        bg="#181818",
        highlightthickness=0,
    )
    search_results_scroll = Scrollbar(
        search_results_box,
        orient="vertical",
        command=search_results_canvas.yview,
        width=20,
    )
    search_results_list = Frame(search_results_canvas, bg="#181818")
    search_results_window = search_results_canvas.create_window(
        (0, 0),
        window=search_results_list,
        anchor="nw",
    )
    search_results_canvas.configure(yscrollcommand=search_results_scroll.set)
    search_results_canvas.pack(side=LEFT, fill=BOTH, expand=True)
    search_results_scroll.pack(side=RIGHT, fill="y")
    search_results_list.bind(
        "<Configure>",
        lambda _event: search_results_canvas.configure(
            scrollregion=search_results_canvas.bbox("all")
        ),
    )
    search_results_canvas.bind(
        "<Configure>",
        lambda event: search_results_canvas.itemconfigure(
            search_results_window,
            width=event.width,
        ),
    )
    search_results_canvas.bind(
        "<Button-4>",
        lambda _event: search_results_canvas.yview_scroll(-1, "units"),
    )
    search_results_canvas.bind(
        "<Button-5>",
        lambda _event: search_results_canvas.yview_scroll(1, "units"),
    )
    search_dropdown_open = False
    search_drag_start_y = 0
    search_dragged = False

    def submit_search(query=None):
        nonlocal search_dropdown_open
        if not isinstance(query, str):
            query = search_entry.get().strip()
        if search_has_placeholder or not query:
            return

        current_state = get_state()
        current_state["search_query"] = query
        current_state["search_results"] = []
        current_state["search_loading"] = True
        current_state["search_error"] = None
        search_dropdown_open = True
        virtual_keyboard.hide()
        Thread(target=load_search_results, args=(query,), daemon=True).start()

    def focus_search(_event):
        nonlocal search_has_placeholder
        search_box.config(highlightbackground="#1DB954")
        search_icon.itemconfig(search_circle, outline="#1DB954")
        search_icon.itemconfig(search_handle, fill="#1DB954")
        if search_has_placeholder:
            search_entry.delete(0, "end")
            search_entry.config(fg="white")
            search_has_placeholder = False
        virtual_keyboard.show(
            search_entry,
            on_submit=submit_search,
            on_close=close_search_and_clear_focus,
        )

    def reset_search_style():
        nonlocal search_has_placeholder
        search_box.config(highlightbackground="#3A3A3A")
        search_icon.itemconfig(search_circle, outline="#B3B3B3")
        search_icon.itemconfig(search_handle, fill="#B3B3B3")
        if not search_entry.get().strip():
            search_entry.delete(0, "end")
            search_entry.insert(0, search_placeholder)
            search_entry.config(fg="#888888")
            search_has_placeholder = True

    def leave_search(_event=None):
        if virtual_keyboard.frame.winfo_manager():
            return
        reset_search_style()

    def close_search(_event=None):
        nonlocal search_dropdown_open
        search_dropdown_open = False
        virtual_keyboard.hide()
        search_results_box.place_forget()
        reset_search_style()

    def close_search_and_clear_focus():
        close_search()
        root.after_idle(frame.focus_set)

    def click_outside_search(event):
        if not frame.winfo_ismapped():
            return

        widget_path = str(event.widget)
        keyboard_path = str(virtual_keyboard.frame)
        results_path = str(search_results_box)
        clicked_keyboard = (
            widget_path == keyboard_path
            or widget_path.startswith(f"{keyboard_path}.")
        )
        clicked_results = (
            widget_path == results_path
            or widget_path.startswith(f"{results_path}.")
        )
        if (
            event.widget in (search_entry, search_icon)
            or clicked_keyboard
            or clicked_results
        ):
            return

        search_is_active = (
            root.focus_get() == search_entry
            or bool(virtual_keyboard.frame.winfo_manager())
            or search_dropdown_open
        )
        if not search_is_active:
            return

        close_search()
        root.after_idle(frame.focus_set)

    search_entry.bind("<FocusIn>", focus_search)
    search_entry.bind("<Button-1>", focus_search)
    search_entry.bind("<FocusOut>", leave_search)
    search_icon.bind("<Button-1>", submit_search)
    search_entry.bind("<Escape>", close_search)
    frame.bind("<Unmap>", close_search)
    root.bind("<Button-1>", click_outside_search, add="+")

    content = Frame(frame, bg="black")
    content.pack(fill=BOTH, expand=True, padx=12)
    Label(
        content,
        text="Recently played",
        fg="white",
        bg="black",
        anchor="w",
        font=("DejaVu Sans", 16, "bold"),
    ).pack(fill=X, pady=(4, 4))
    recent_frame = Frame(content, bg="black")
    recent_frame.pack(fill=X)

    Label(
        content,
        text="Your playlists",
        fg="white",
        bg="black",
        anchor="w",
        font=("DejaVu Sans", 16, "bold"),
    ).pack(fill=X, pady=(20, 4))

    playlist_box = Frame(content, bg="#111111", height=190)
    playlist_box.pack(fill=X)
    playlist_box.pack_propagate(False)
    playlist_canvas = Canvas(playlist_box, bg="#111111", highlightthickness=0)
    playlist_scroll = Scrollbar(
        playlist_box, orient=HORIZONTAL, command=playlist_canvas.xview, width=24
    )
    playlist_list = Frame(playlist_canvas, bg="#111111")
    playlist_window = playlist_canvas.create_window((0, 0), window=playlist_list, anchor="nw")
    playlist_canvas.configure(xscrollcommand=playlist_scroll.set)
    playlist_canvas.pack(side=TOP, fill=BOTH, expand=True)
    playlist_scroll.pack(side=BOTTOM, fill=X)

    playlist_list.bind(
        "<Configure>",
        lambda _event: playlist_canvas.configure(scrollregion=playlist_canvas.bbox("all")),
    )
    playlist_canvas.bind(
        "<Configure>",
        lambda event: playlist_canvas.itemconfigure(playlist_window, height=event.height),
    )
    playlist_canvas.bind("<Button-4>", lambda _event: playlist_canvas.xview_scroll(-1, "units"))
    playlist_canvas.bind("<Button-5>", lambda _event: playlist_canvas.xview_scroll(1, "units"))

    playlist_drag_start_x = 0
    playlist_dragged = False

    def playlist_canvas_x(event):
        return event.x_root - playlist_canvas.winfo_rootx()

    def start_playlist_drag(event):
        nonlocal playlist_drag_start_x, playlist_dragged
        playlist_drag_start_x = event.x_root
        playlist_dragged = False
        playlist_canvas.scan_mark(playlist_canvas_x(event), 0)

    def drag_playlist(event):
        nonlocal playlist_dragged
        if abs(event.x_root - playlist_drag_start_x) > 5:
            playlist_dragged = True
        playlist_canvas.scan_dragto(playlist_canvas_x(event), 0, gain=1)

    def finish_playlist_press(_event, playlist_uri, playlist_name):
        if not playlist_dragged:
            state["current_collection_name"] = playlist_name
            state["current_collection_uri"] = playlist_uri
            state["current_collection_type"] = "playlist"
            go_playlist()

    for widget in (playlist_canvas, playlist_list):
        widget.bind("<ButtonPress-1>", start_playlist_drag)
        widget.bind("<B1-Motion>", drag_playlist)

    mini_player = Frame(frame, bg="#181818", height=72, cursor="hand2")
    mini_player.pack_propagate(False)
    mini_cover_frame = Frame(mini_player, width=56, height=56, bg="black")
    mini_cover_frame.pack(side=LEFT, padx=8, pady=8)
    mini_cover_frame.pack_propagate(False)
    mini_cover = Label(mini_cover_frame, bg="black", borderwidth=0)
    mini_cover.pack(fill=BOTH, expand=True)
    mini_text = Frame(mini_player, bg="#181818")
    mini_text.pack(side=LEFT, fill=BOTH, expand=True, pady=10)
    mini_track = Label(
        mini_text, fg="white", bg="#181818", anchor="w", font=("DejaVu Sans", 12, "bold")
    )
    mini_artist = Label(
        mini_text, fg="#aaaaaa", bg="#181818", anchor="w", font=("DejaVu Sans", 10)
    )
    mini_track.pack(fill=X)
    mini_artist.pack(fill=X)
    mini_play = Button(
        mini_player, text="||", command=on_toggle_play, width=3, **button_style
    )
    mini_play.pack(side=RIGHT, padx=8, pady=10)

    for widget in (mini_player, mini_cover_frame, mini_cover, mini_text, mini_track, mini_artist):
        widget.bind("<Button-1>", lambda _event: go_player())

    recent_signature = None
    playlist_signature = None
    search_results_signature = None
    mini_cover_key = None

    def search_canvas_y(event):
        return event.y_root - search_results_canvas.winfo_rooty()

    def start_search_drag(event):
        nonlocal search_drag_start_y, search_dragged
        search_drag_start_y = event.y_root
        search_dragged = False
        search_results_canvas.scan_mark(0, search_canvas_y(event))

    def drag_search_results(event):
        nonlocal search_dragged
        if abs(event.y_root - search_drag_start_y) > 5:
            search_dragged = True
        search_results_canvas.scan_dragto(0, search_canvas_y(event), gain=1)

    def finish_search_press(_event, uri):
        if search_dragged or not uri:
            return
        close_search()
        root.after_idle(frame.focus_set)
        play_selected_track(uri)

    for widget in (search_results_canvas, search_results_list):
        widget.bind("<ButtonPress-1>", start_search_drag)
        widget.bind("<B1-Motion>", drag_search_results)

    def rebuild_search_results(current_state):
        nonlocal search_results_signature

        results = current_state.get("search_results", [])
        new_signature = (
            search_dropdown_open,
            current_state.get("search_loading"),
            current_state.get("search_error"),
            tuple(
                (
                    track.get("uri"),
                    track.get("name"),
                    track.get("artist"),
                    track.get("image_url"),
                )
                for track in results
            ),
        )

        if not search_dropdown_open:
            search_results_box.place_forget()
            search_results_signature = new_signature
            return

        if new_signature != search_results_signature:
            search_results_signature = new_signature
            search_results_canvas.yview_moveto(0)
            for child in search_results_list.winfo_children():
                child.destroy()

            if current_state.get("search_loading"):
                Label(
                    search_results_list,
                    text="Searching...",
                    fg="#B3B3B3",
                    bg="#181818",
                    anchor="w",
                    padx=12,
                    pady=12,
                ).pack(fill=X)
            elif current_state.get("search_error"):
                Label(
                    search_results_list,
                    text="Search unavailable",
                    fg="#FF6B6B",
                    bg="#181818",
                    anchor="w",
                    padx=12,
                    pady=12,
                ).pack(fill=X)
            elif not results:
                Label(
                    search_results_list,
                    text="No tracks found",
                    fg="#B3B3B3",
                    bg="#181818",
                    anchor="w",
                    padx=12,
                    pady=12,
                ).pack(fill=X)
            else:
                for track in results[:10]:
                    row = Frame(search_results_list, bg="#181818", height=62, cursor="hand2")
                    row.pack(fill=X)
                    row.pack_propagate(False)

                    cover_frame = Frame(
                        row,
                        bg="#282828",
                        width=48,
                        height=48,
                        cursor="hand2",
                    )
                    cover_frame.pack(side=LEFT, padx=(7, 10), pady=7)
                    cover_frame.pack_propagate(False)
                    cover = Label(cover_frame, bg="#282828", cursor="hand2")
                    cover.pack(fill=BOTH, expand=True)

                    text_box = Frame(row, bg="#181818", cursor="hand2")
                    text_box.pack(side=LEFT, fill=BOTH, expand=True, pady=8)
                    name_label = Label(
                        text_box,
                        text=track.get("name", ""),
                        fg="white",
                        bg="#181818",
                        anchor="w",
                        font=("DejaVu Sans", 11, "bold"),
                        cursor="hand2",
                    )
                    name_label.pack(fill=X)
                    artist_label = Label(
                        text_box,
                        text=track.get("artist", ""),
                        fg="#B3B3B3",
                        bg="#181818",
                        anchor="w",
                        font=("DejaVu Sans", 9),
                        cursor="hand2",
                    )
                    artist_label.pack(fill=X)

                    uri = track.get("uri")

                    for widget in (
                        row,
                        cover_frame,
                        cover,
                        text_box,
                        name_label,
                        artist_label,
                    ):
                        widget.bind("<ButtonPress-1>", start_search_drag)
                        widget.bind("<B1-Motion>", drag_search_results)
                        widget.bind(
                            "<ButtonRelease-1>",
                            lambda event, selected_uri=uri: finish_search_press(
                                event,
                                selected_uri,
                            ),
                        )

                    def show_search_cover(photo, label=cover, expected_uri=uri):
                        current_uris = {
                            item.get("uri")
                            for item in get_state().get("search_results", [])
                        }
                        if expected_uri not in current_uris or not label.winfo_exists():
                            return
                        label.config(image=photo if photo is not None else "")
                        label.image = photo

                    get_photo_async(
                        root,
                        track.get("image_url"),
                        (48, 48),
                        show_search_cover,
                    )

        visible_rows = min(len(results), 5)
        dropdown_height = visible_rows * 62 if visible_rows else 46
        search_results_box.place(
            x=search_box.winfo_x(),
            y=search_box.winfo_y() + search_box.winfo_height(),
            width=search_box.winfo_width(),
            height=dropdown_height,
        )
        search_results_box.lift()

    def rebuild_lists(current_state):
        nonlocal recent_signature, playlist_signature

        tracks = current_state.get("recent_tracks", [])
        new_recent_signature = (
            current_state.get("home_loading"),
            current_state.get("home_error"),
            tuple((track.get("uri"), track.get("name"), track.get("artist")) for track in tracks),
        )
        if new_recent_signature != recent_signature:
            recent_signature = new_recent_signature
            for child in recent_frame.winfo_children():
                child.destroy()

            if not tracks:
                message = current_state.get("home_error") or (
                    "Loading..." if current_state.get("home_loading") else "No recently played tracks"
                )
                Label(recent_frame, text=message, fg="#aaaaaa", bg="black", anchor="w").pack(fill=X)
            else:
                for track in tracks:
                    text = f'{track.get("name", "")}  —  {track.get("artist", "")}'
                    Button(
                        recent_frame,
                        text=text,
                        command=lambda uri=track.get("uri"): play_selected_track(uri) if uri else None,
                        fg="white",
                        bg="#181818",
                        activeforeground="white",
                        activebackground="#333333",
                        anchor="w",
                        relief="flat",
                        borderwidth=0,
                        padx=8,
                        pady=4,
                    ).pack(fill=X, pady=1)

        playlists = current_state.get("playlists", [])
        new_playlist_signature = (
            current_state.get("home_loading"),
            current_state.get("home_error"),
            tuple(
                (
                    playlist.get("uri"),
                    playlist.get("name"),
                    playlist.get("owner"),
                    playlist.get("image_url"),
                )
                for playlist in playlists
            ),
        )
        if new_playlist_signature == playlist_signature:
            return

        playlist_signature = new_playlist_signature
        for child in playlist_list.winfo_children():
            child.destroy()

        if not playlists:
            message = current_state.get("home_error") or (
                "Loading..." if current_state.get("home_loading") else "No saved playlists"
            )
            Label(playlist_list, text=message, fg="#aaaaaa", bg="#111111", anchor="w").pack(
                fill=X, padx=8, pady=8
            )
            return

        for playlist in playlists:
            card = Frame(playlist_list, width=136, height=166, bg="#181818")
            card.pack(side=LEFT, padx=5, pady=5)
            card.pack_propagate(False)
            cover_frame = Frame(card, width=120, height=120, bg="#282828")
            cover_frame.pack(padx=8, pady=(8, 3))
            cover_frame.pack_propagate(False)
            cover = Label(cover_frame, bg="#282828", borderwidth=0, highlightthickness=0)
            cover.pack(fill=BOTH, expand=True)
            name_label = Label(
                card,
                text=playlist.get("name", ""),
                fg="white",
                bg="#181818",
                anchor="center",
                font=("DejaVu Sans", 9, "bold"),
            )
            name_label.pack(fill=X, padx=5)

            image_url = playlist.get("image_url")
            expected_uri = playlist.get("uri")
            if expected_uri:
                for widget in (card, cover_frame, cover, name_label):
                    widget.config(cursor="hand2")
                    widget.bind("<ButtonPress-1>", start_playlist_drag)
                    widget.bind("<B1-Motion>", drag_playlist)
                    widget.bind(
                        "<ButtonRelease-1>",
                        lambda event, uri=expected_uri, name=playlist.get("name", ""): (
                            finish_playlist_press(event, uri, name)
                        ),
                    )

            def show_playlist_cover(photo, label=cover, uri=expected_uri):
                current_uris = {item.get("uri") for item in get_state().get("playlists", [])}
                if uri not in current_uris or not label.winfo_exists():
                    return
                label.config(image=photo if photo is not None else "")
                label.image = photo

            get_photo_async(root, image_url, (120, 120), show_playlist_cover)

    def set_mini_cover(cover_key, url):
        mini_cover.config(image="")
        mini_cover.image = None

        def show_cover(photo):
            current_song = get_state()["song"]
            current_key = (_get_track_id(current_song), current_song.get("image_url"))
            if current_key != cover_key:
                return
            mini_cover.config(image=photo if photo is not None else "")
            mini_cover.image = photo

        get_photo_async(root, url, (56, 56), show_cover)

    def restore_cover(_event=None):
        photo = getattr(mini_cover, "image", None)
        if photo is not None:
            mini_cover.config(image=photo)

    root.bind("<Map>", restore_cover, add="+")
    root.bind("<Configure>", restore_cover, add="+")

    def update(current_state):
        nonlocal mini_cover_key

        song = current_state["song"]
        if song.get("track_id"):
            if not mini_player.winfo_manager():
                mini_player.pack(fill=X, side=BOTTOM, before=content)
        elif mini_player.winfo_manager():
            mini_player.pack_forget()

        rebuild_lists(current_state)
        rebuild_search_results(current_state)

        cover_key = (_get_track_id(song), song.get("image_url"))
        if cover_key != mini_cover_key:
            mini_cover_key = cover_key
            set_mini_cover(cover_key, song.get("image_url"))

        mini_track.config(text=song.get("track", "") or "Nothing playing")
        mini_artist.config(text=song.get("artist", ""))
        mini_play.config(text="||" if song.get("is_playing", False) else ">", state=NORMAL)

    Thread(target=load_home, daemon=True).start()
    update(state)
    return {"frame": frame, "update": update}
