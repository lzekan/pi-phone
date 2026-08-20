from threading import Thread
from tkinter import BOTH, HORIZONTAL, LEFT, RIGHT, TOP, X
from tkinter import Button, Canvas, Entry, Frame, Label, Scrollbar
from tkinter import font as tkfont

from app.features.spotify.controllers.home import (
    load_home,
    load_recently_played,
    load_saved_albums,
)
from app.controller.controller_navigation import go_launcher, go_playlist
from app.features.spotify.controllers.player import play_selected_track
from app.features.spotify.controllers.queue import add_to_manual_queue
from app.features.spotify.controllers.search import load_search_results
from app.core.state import get_state
from app.services.image_cache import get_photo_async
from app.ui.components.mini_player import create_mini_player
from app.ui.components.virtual_keyboard import VirtualKeyboard
from app.ui.theme import (
    ACCENT,
    BG,
    CARD,
    DANGER,
    DIVIDER,
    FONT,
    PAGE_PAD,
    SURFACE,
    SURFACE_ACTIVE,
    SURFACE_ALT,
    TEXT,
    TEXT_DIM,
    TEXT_MUTED,
)


def _two_line_ellipsis(text, font, max_width):
    remaining = " ".join((text or "").split())
    if not remaining:
        return ""

    lines = []
    for line_index in range(2):
        if font.measure(remaining) <= max_width:
            lines.append(remaining)
            return "\n".join(lines)

        suffix = "..." if line_index == 1 else ""
        low = 0
        high = len(remaining)
        while low < high:
            middle = (low + high + 1) // 2
            candidate = remaining[:middle].rstrip() + suffix
            if font.measure(candidate) <= max_width:
                low = middle
            else:
                high = middle - 1

        cut = low
        if line_index == 0:
            word_break = remaining.rfind(" ", 0, cut + 1)
            if word_break > 0:
                cut = word_break
            lines.append(remaining[:cut].rstrip())
            remaining = remaining[cut:].lstrip()
        else:
            lines.append(remaining[:cut].rstrip() + "...")

    return "\n".join(lines)


def render_home(root, state, button_style):
    frame = Frame(root, bg=BG)
    card_name_font_spec = (FONT, 9, "bold")
    card_name_font = tkfont.Font(root=root, font=card_name_font_spec)
    queue_toast_after_id = None

    queue_toast = Label(
        frame,
        text="Added to queue",
        fg=TEXT,
        bg=ACCENT,
        font=(FONT, 10, "bold"),
        padx=14,
        pady=7,
    )

    def show_queue_toast():
        nonlocal queue_toast_after_id

        if queue_toast_after_id is not None:
            root.after_cancel(queue_toast_after_id)

        queue_toast.place(relx=0.5, rely=0.82, anchor="center")
        queue_toast.lift()

        def hide_toast():
            nonlocal queue_toast_after_id
            queue_toast.place_forget()
            queue_toast_after_id = None

        queue_toast_after_id = root.after(2000, hide_toast)

    header = Frame(frame, bg=BG)
    title_box = Frame(header, bg=BG)
    title_box.pack(side=LEFT)
    Label(
        title_box,
        text="YOUR MUSIC",
        fg=ACCENT,
        bg=BG,
        anchor="w",
        font=(FONT, 9, "bold"),
    ).pack(fill=X)
    Label(
        title_box,
        text="Home",
        fg=TEXT,
        bg=BG,
        anchor="w",
        font=(FONT, 25, "bold"),
    ).pack(fill=X)
    Button(
        header,
        text="X",
        command=go_launcher,
        fg=TEXT_MUTED,
        bg=SURFACE_ALT,
        activeforeground=TEXT,
        activebackground=DANGER,
        font=(FONT, 12, "bold"),
        relief="flat",
        borderwidth=0,
        highlightthickness=0,
        takefocus=False,
        width=3,
        pady=4,
    ).pack(side=RIGHT)
    header.pack(fill=X, padx=PAGE_PAD, pady=(12, 8))

    search_box = Frame(
        frame,
        bg=SURFACE_ALT,
        highlightbackground=DIVIDER,
        highlightthickness=1,
    )
    search_box.pack(fill=X, padx=PAGE_PAD, pady=(2, 14))

    search_icon = Canvas(
        search_box,
        width=42,
        height=48,
        bg=SURFACE_ALT,
        highlightthickness=0,
        cursor="hand2",
    )
    search_circle = search_icon.create_oval(
        10, 12, 27, 29, outline=TEXT_MUTED, width=3
    )
    search_handle = search_icon.create_line(
        25, 27, 33, 35, fill=TEXT_MUTED, width=3
    )
    search_icon.pack(side=LEFT)

    search_type_labels = {
        "track": "Tracks",
        "album": "Albums",
    }
    search_type = state.get("search_type", "track")
    search_placeholder = f"Search {search_type_labels[search_type].lower()}..."
    search_has_placeholder = True
    search_entry = Entry(
        search_box,
        bg=SURFACE_ALT,
        fg=TEXT_MUTED,
        insertbackground=TEXT,
        relief="flat",
        borderwidth=0,
        highlightthickness=0,
        font=(FONT, 14, "bold"),
    )
    search_entry.insert(0, search_placeholder)
    search_entry.pack(side=LEFT, fill=X, expand=True, padx=(0, 14), pady=12)
    filter_button = Button(
        search_box,
        text=f"{search_type_labels[search_type]}  ▾",
        fg=TEXT,
        bg=SURFACE,
        activeforeground=TEXT,
        activebackground=SURFACE_ACTIVE,
        font=(FONT, 10, "bold"),
        relief="flat",
        borderwidth=0,
        highlightthickness=0,
        takefocus=False,
        padx=10,
        pady=7,
    )
    filter_button.pack(side=RIGHT, padx=(0, 7), pady=7)
    virtual_keyboard = VirtualKeyboard(frame)
    search_results_box = Frame(
        frame,
        bg=SURFACE,
        highlightbackground=DIVIDER,
        highlightthickness=1,
    )
    search_results_canvas = Canvas(
        search_results_box,
        bg=SURFACE,
        highlightthickness=0,
    )
    search_results_scroll = Scrollbar(
        search_results_box,
        orient="vertical",
        command=search_results_canvas.yview,
        width=20,
    )
    search_results_list = Frame(search_results_canvas, bg=SURFACE)
    search_results_window = search_results_canvas.create_window(
        (0, 0),
        window=search_results_list,
        anchor="nw",
    )
    search_results_canvas.configure(yscrollcommand=search_results_scroll.set)
    search_results_canvas.pack(side=LEFT, fill=BOTH, expand=True)
    search_results_scroll.pack(side=RIGHT, fill="y")
    filter_menu = Frame(
        frame,
        bg=SURFACE,
        highlightbackground=DIVIDER,
        highlightthickness=1,
    )
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
    search_drag_start_x = 0
    search_drag_start_y = 0
    search_dragged = False
    search_drag_axis = None
    search_dragged_info_frame = None

    def submit_search(query=None):
        nonlocal search_dropdown_open
        if not isinstance(query, str):
            query = search_entry.get().strip()
        if search_has_placeholder or not query:
            return

        current_state = get_state()
        current_state["search_query"] = query
        current_state["search_type"] = search_type
        current_state["search_results"] = []
        current_state["search_loading"] = True
        current_state["search_error"] = None
        search_dropdown_open = True
        virtual_keyboard.hide()
        Thread(
            target=load_search_results,
            args=(query, search_type),
            daemon=True,
        ).start()

    def close_filter_menu():
        filter_menu.place_forget()

    def select_search_type(selected_type):
        nonlocal search_type, search_placeholder, search_has_placeholder

        search_type = selected_type
        get_state()["search_type"] = selected_type
        search_placeholder = (
            f"Search {search_type_labels[selected_type].lower()}..."
        )
        filter_button.config(text=f"{search_type_labels[selected_type]}  ▾")
        close_filter_menu()

        if search_has_placeholder:
            search_entry.delete(0, "end")
            search_entry.insert(0, search_placeholder)

        query = search_entry.get().strip()
        if not search_has_placeholder and len(query) >= 3:
            submit_search(query)

    def toggle_filter_menu():
        if filter_menu.winfo_manager():
            close_filter_menu()
            return

        root.update_idletasks()
        menu_width = 142
        filter_menu.place(
            x=(
                search_box.winfo_x()
                + search_box.winfo_width()
                - menu_width
            ),
            y=search_box.winfo_y() + search_box.winfo_height(),
            width=menu_width,
        )
        filter_menu.lift()

    for option_type in ("track", "album"):
        Button(
            filter_menu,
            text=search_type_labels[option_type],
            command=lambda selected=option_type: select_search_type(selected),
            fg=TEXT,
            bg=SURFACE,
            activeforeground=TEXT,
            activebackground=SURFACE_ACTIVE,
            font=(FONT, 10, "bold"),
            anchor="w",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            takefocus=False,
            padx=12,
            pady=9,
        ).pack(fill=X)

    filter_button.config(command=toggle_filter_menu)

    def focus_search(_event):
        nonlocal search_has_placeholder
        search_box.config(highlightbackground=ACCENT)
        search_icon.itemconfig(search_circle, outline=ACCENT)
        search_icon.itemconfig(search_handle, fill=ACCENT)
        if search_has_placeholder:
            search_entry.delete(0, "end")
            search_entry.config(fg=TEXT)
            search_has_placeholder = False
        virtual_keyboard.show(
            search_entry,
            on_submit=submit_search,
            on_close=close_search_and_clear_focus,
        )

    def reset_search_style():
        nonlocal search_has_placeholder
        search_box.config(highlightbackground=DIVIDER)
        search_icon.itemconfig(search_circle, outline=TEXT_MUTED)
        search_icon.itemconfig(search_handle, fill=TEXT_MUTED)
        if not search_entry.get().strip():
            search_entry.delete(0, "end")
            search_entry.insert(0, search_placeholder)
            search_entry.config(fg=TEXT_DIM)
            search_has_placeholder = True

    def leave_search(_event=None):
        if virtual_keyboard.frame.winfo_manager():
            return
        reset_search_style()

    def close_search(_event=None):
        nonlocal search_dropdown_open
        search_dropdown_open = False
        close_filter_menu()
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
        filter_path = str(filter_menu)
        clicked_keyboard = (
            widget_path == keyboard_path
            or widget_path.startswith(f"{keyboard_path}.")
        )
        clicked_results = (
            widget_path == results_path
            or widget_path.startswith(f"{results_path}.")
        )
        clicked_filter = (
            event.widget == filter_button
            or widget_path == filter_path
            or widget_path.startswith(f"{filter_path}.")
        )
        if (
            event.widget in (search_entry, search_icon)
            or clicked_keyboard
            or clicked_results
            or clicked_filter
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

    content_box = Frame(frame, bg=BG)
    content_box.pack(fill=BOTH, expand=True, padx=PAGE_PAD)
    content_canvas = Canvas(content_box, bg=BG, highlightthickness=0)
    content = Frame(content_canvas, bg=BG)
    content_window = content_canvas.create_window(
        (0, 0),
        window=content,
        anchor="nw",
    )
    content_canvas.pack(fill=BOTH, expand=True)
    content.bind(
        "<Configure>",
        lambda _event: content_canvas.configure(
            scrollregion=content_canvas.bbox("all")
        ),
    )
    content_canvas.bind(
        "<Configure>",
        lambda event: content_canvas.itemconfigure(
            content_window,
            width=event.width,
        ),
    )
    content_canvas.bind(
        "<Button-4>",
        lambda _event: content_canvas.yview_scroll(-1, "units"),
    )
    content_canvas.bind(
        "<Button-5>",
        lambda _event: content_canvas.yview_scroll(1, "units"),
    )

    home_drag_start_x = 0
    home_drag_start_y = 0
    home_drag_mode = None
    home_dragged_info_frame = None
    recent_swipe_targets = {}

    def event_is_in_home_content(event):
        if not frame.winfo_ismapped():
            return False
        widget_path = str(event.widget)
        content_path = str(content)
        canvas_path = str(content_canvas)
        return (
            widget_path == content_path
            or widget_path.startswith(f"{content_path}.")
            or widget_path == canvas_path
        )

    def content_canvas_y(event):
        return event.y_root - content_canvas.winfo_rooty()

    def start_home_drag(event):
        nonlocal home_drag_start_x, home_drag_start_y, home_drag_mode
        nonlocal home_dragged_info_frame
        if not event_is_in_home_content(event):
            return
        home_drag_start_x = event.x_root
        home_drag_start_y = event.y_root
        home_drag_mode = None
        target = recent_swipe_targets.get(str(event.widget))
        home_dragged_info_frame = target[0] if target else None
        content_canvas.scan_mark(0, content_canvas_y(event))

    def drag_home(event):
        nonlocal home_drag_mode
        if not event_is_in_home_content(event):
            return

        dx = event.x_root - home_drag_start_x
        dy = event.y_root - home_drag_start_y
        if home_drag_mode is None and max(abs(dx), abs(dy)) > 5:
            home_drag_mode = "vertical" if abs(dy) > abs(dx) else "horizontal"

        if home_drag_mode == "vertical":
            content_canvas.scan_dragto(
                0,
                content_canvas_y(event),
                gain=1,
            )
        elif home_drag_mode == "horizontal" and home_dragged_info_frame is not None:
            if home_dragged_info_frame.winfo_exists():
                home_dragged_info_frame.pack_configure(
                    padx=(min(max(dx, 0), 76), 0)
                )

    def finish_recent_press(event, track_uri, track_data, info_frame):
        delta_x = event.x_root - home_drag_start_x

        if info_frame.winfo_exists():
            info_frame.pack_configure(padx=0)

        if home_drag_mode == "horizontal" and delta_x >= 60 and track_uri:
            add_to_manual_queue(track_data)
            show_queue_toast()
        elif home_drag_mode is None and track_uri:
            play_selected_track(track_uri, track_data=track_data)

    root.bind("<ButtonPress-1>", start_home_drag, add="+")
    root.bind("<B1-Motion>", drag_home, add="+")
    Label(
        content,
        text="Recently played",
        fg=TEXT,
        bg=BG,
        anchor="w",
        font=(FONT, 17, "bold"),
    ).pack(fill=X, pady=(6, 8))
    recent_frame = Frame(content, bg=BG)
    recent_frame.pack(fill=X)

    liked_songs_card = Frame(
        content,
        bg=CARD,
        height=76,
        cursor="hand2",
        highlightbackground=DIVIDER,
        highlightthickness=1,
    )
    liked_songs_card.pack(fill=X, pady=(18, 0))
    liked_songs_card.pack_propagate(False)

    liked_songs_icon = Label(
        liked_songs_card,
        text="♥",
        fg=TEXT,
        bg=ACCENT,
        width=4,
        font=(FONT, 22, "bold"),
        cursor="hand2",
    )
    liked_songs_icon.pack(side=LEFT, fill="y")

    liked_songs_text = Frame(liked_songs_card, bg=CARD, cursor="hand2")
    liked_songs_text.pack(side=LEFT, fill=BOTH, expand=True, padx=14, pady=12)
    liked_songs_title = Label(
        liked_songs_text,
        text="Liked Songs",
        fg=TEXT,
        bg=CARD,
        anchor="w",
        font=(FONT, 13, "bold"),
        cursor="hand2",
    )
    liked_songs_title.pack(fill=X)
    liked_songs_subtitle = Label(
        liked_songs_text,
        text="Your saved tracks",
        fg=TEXT_MUTED,
        bg=CARD,
        anchor="w",
        font=(FONT, 9),
        cursor="hand2",
    )
    liked_songs_subtitle.pack(fill=X)

    def open_liked_songs(_event=None):
        if home_drag_mode is not None:
            return
        state["current_collection_name"] = "Liked Songs"
        state["current_collection_uri"] = "spotify:collection:tracks"
        state["current_collection_type"] = "liked"
        state["current_collection_image_url"] = None
        go_playlist()

    for widget in (
        liked_songs_card,
        liked_songs_icon,
        liked_songs_text,
        liked_songs_title,
        liked_songs_subtitle,
    ):
        widget.bind("<ButtonRelease-1>", open_liked_songs)

    Label(
        content,
        text="Your playlists",
        fg=TEXT,
        bg=BG,
        anchor="w",
        font=(FONT, 17, "bold"),
    ).pack(fill=X, pady=(20, 4))

    playlist_box = Frame(content, bg=BG, height=174)
    playlist_box.pack(fill=X)
    playlist_box.pack_propagate(False)
    playlist_canvas = Canvas(playlist_box, bg=BG, highlightthickness=0)
    playlist_list = Frame(playlist_canvas, bg=BG)
    playlist_window = playlist_canvas.create_window((0, 0), window=playlist_list, anchor="nw")
    playlist_canvas.pack(fill=BOTH, expand=True)

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

    def finish_playlist_press(_event, playlist_uri, playlist_name, image_url):
        if not playlist_dragged and home_drag_mode != "vertical":
            state["current_collection_name"] = playlist_name
            state["current_collection_uri"] = playlist_uri
            state["current_collection_type"] = "playlist"
            state["current_collection_image_url"] = image_url
            go_playlist()

    for widget in (playlist_canvas, playlist_list):
        widget.bind("<ButtonPress-1>", start_playlist_drag)
        widget.bind("<B1-Motion>", drag_playlist)

    Label(
        content,
        text="Your albums",
        fg=TEXT,
        bg=BG,
        anchor="w",
        font=(FONT, 17, "bold"),
    ).pack(fill=X, pady=(20, 4))

    album_box = Frame(content, bg=BG, height=174)
    album_box.pack(fill=X, pady=(0, 24))
    album_box.pack_propagate(False)
    album_canvas = Canvas(album_box, bg=BG, highlightthickness=0)
    album_list = Frame(album_canvas, bg=BG)
    album_window = album_canvas.create_window(
        (0, 0),
        window=album_list,
        anchor="nw",
    )
    album_canvas.pack(fill=BOTH, expand=True)

    album_list.bind(
        "<Configure>",
        lambda _event: album_canvas.configure(
            scrollregion=album_canvas.bbox("all")
        ),
    )
    album_canvas.bind(
        "<Configure>",
        lambda event: album_canvas.itemconfigure(
            album_window,
            height=event.height,
        ),
    )
    album_canvas.bind(
        "<Button-4>",
        lambda _event: album_canvas.xview_scroll(-1, "units"),
    )
    album_canvas.bind(
        "<Button-5>",
        lambda _event: album_canvas.xview_scroll(1, "units"),
    )

    album_drag_start_x = 0
    album_dragged = False

    def album_canvas_x(event):
        return event.x_root - album_canvas.winfo_rootx()

    def start_album_drag(event):
        nonlocal album_drag_start_x, album_dragged
        album_drag_start_x = event.x_root
        album_dragged = False
        album_canvas.scan_mark(album_canvas_x(event), 0)

    def drag_album(event):
        nonlocal album_dragged
        if abs(event.x_root - album_drag_start_x) > 5:
            album_dragged = True
        album_canvas.scan_dragto(album_canvas_x(event), 0, gain=1)

    def finish_album_press(_event, album_uri, album_name, image_url):
        if not album_dragged and home_drag_mode != "vertical":
            state["current_collection_name"] = album_name
            state["current_collection_uri"] = album_uri
            state["current_collection_type"] = "album"
            state["current_collection_image_url"] = image_url
            go_playlist()

    for widget in (album_canvas, album_list):
        widget.bind("<ButtonPress-1>", start_album_drag)
        widget.bind("<B1-Motion>", drag_album)

    mini_player = create_mini_player(
        root,
        frame,
        button_style,
        before=content_box,
    )

    recent_signature = None
    playlist_signature = None
    album_signature = None
    search_results_signature = None

    def search_canvas_y(event):
        return event.y_root - search_results_canvas.winfo_rooty()

    def start_search_drag(event, info_frame=None):
        nonlocal search_drag_start_x, search_drag_start_y, search_dragged
        nonlocal search_drag_axis, search_dragged_info_frame
        search_drag_start_x = event.x_root
        search_drag_start_y = event.y_root
        search_dragged = False
        search_drag_axis = None
        search_dragged_info_frame = info_frame
        search_results_canvas.scan_mark(0, search_canvas_y(event))

    def drag_search_results(event):
        nonlocal search_dragged, search_drag_axis
        delta_x = event.x_root - search_drag_start_x
        delta_y = event.y_root - search_drag_start_y

        if search_drag_axis is None and max(abs(delta_x), abs(delta_y)) > 6:
            search_dragged = True
            search_drag_axis = (
                "horizontal" if abs(delta_x) > abs(delta_y) else "vertical"
            )

        if search_drag_axis == "horizontal":
            if (
                search_dragged_info_frame is not None
                and search_dragged_info_frame.winfo_exists()
            ):
                search_dragged_info_frame.pack_configure(
                    padx=(min(max(delta_x, 0), 76), 0)
                )
            return

        if search_drag_axis == "vertical":
            search_results_canvas.scan_dragto(0, search_canvas_y(event), gain=1)

    def finish_search_press(event, uri, result_data, info_frame):
        delta_x = event.x_root - search_drag_start_x

        if info_frame is not None and info_frame.winfo_exists():
            info_frame.pack_configure(padx=0)

        result_type = result_data.get("result_type", "track")
        if (
            result_type == "track"
            and search_drag_axis == "horizontal"
            and delta_x >= 60
            and uri
        ):
            add_to_manual_queue(result_data)
            show_queue_toast()
        elif not search_dragged and uri:
            close_search()
            root.after_idle(frame.focus_set)
            if result_type == "track":
                play_selected_track(uri, track_data=result_data)
            else:
                current_state = get_state()
                current_state["current_collection_type"] = result_type
                current_state["current_collection_uri"] = uri
                current_state["current_collection_name"] = result_data.get(
                    "name", ""
                )
                current_state["current_collection_image_url"] = result_data.get(
                    "image_url"
                )
                go_playlist()

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
            current_state.get("search_type"),
            tuple(
                (
                    track.get("result_type"),
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
                    fg=TEXT_MUTED,
                    bg=SURFACE,
                    anchor="w",
                    padx=12,
                    pady=12,
                ).pack(fill=X)
            elif current_state.get("search_error"):
                Label(
                    search_results_list,
                    text="Search unavailable",
                    fg=DANGER,
                    bg=SURFACE,
                    anchor="w",
                    padx=12,
                    pady=12,
                ).pack(fill=X)
            elif not results:
                Label(
                    search_results_list,
                    text="No tracks found",
                    fg=TEXT_MUTED,
                    bg=SURFACE,
                    anchor="w",
                    padx=12,
                    pady=12,
                ).pack(fill=X)
            else:
                for track in results[:10]:
                    row = Frame(search_results_list, bg=SURFACE, height=62, cursor="hand2")
                    row.pack(fill=X)
                    row.pack_propagate(False)

                    cover_frame = Frame(
                        row,
                        bg=SURFACE_ALT,
                        width=48,
                        height=48,
                        cursor="hand2",
                    )
                    cover_frame.pack(side=LEFT, padx=(7, 10), pady=7)
                    cover_frame.pack_propagate(False)
                    cover = Label(cover_frame, bg=SURFACE_ALT, cursor="hand2")
                    cover.pack(fill=BOTH, expand=True)

                    text_box = Frame(row, bg=SURFACE, cursor="hand2")
                    text_box.pack(side=LEFT, fill=BOTH, expand=True, pady=8)
                    name_label = Label(
                        text_box,
                        text=track.get("name", ""),
                        fg=TEXT,
                        bg=SURFACE,
                        anchor="w",
                        font=(FONT, 11, "bold"),
                        cursor="hand2",
                    )
                    name_label.pack(fill=X)
                    artist_label = Label(
                        text_box,
                        text=track.get("artist", ""),
                        fg=TEXT_MUTED,
                        bg=SURFACE,
                        anchor="w",
                        font=(FONT, 9),
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
                        widget.bind(
                            "<ButtonPress-1>",
                            lambda event, swipe_frame=(
                                text_box
                                if track.get("result_type") == "track"
                                else None
                            ): (
                                start_search_drag(event, swipe_frame)
                            ),
                        )
                        widget.bind("<B1-Motion>", drag_search_results)
                        widget.bind(
                            "<ButtonRelease-1>",
                            lambda event, selected_uri=uri, selected_track=track,
                            swipe_frame=text_box: (
                                finish_search_press(
                                    event,
                                    selected_uri,
                                    selected_track,
                                    swipe_frame,
                                )
                            )
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
        nonlocal recent_signature, playlist_signature, album_signature

        tracks = current_state.get("recent_tracks", [])
        new_recent_signature = (
            current_state.get("home_loading"),
            current_state.get("home_error"),
            tuple(
                (
                    track.get("uri"),
                    track.get("name"),
                    track.get("artist"),
                    track.get("image_url"),
                )
                for track in tracks
            ),
        )
        if new_recent_signature != recent_signature:
            recent_signature = new_recent_signature
            recent_swipe_targets.clear()
            for child in recent_frame.winfo_children():
                child.destroy()

            if not tracks:
                message = current_state.get("home_error") or (
                    "Loading..." if current_state.get("home_loading") else "No recently played tracks"
                )
                Label(
                    recent_frame,
                    text=message,
                    fg=TEXT_MUTED,
                    bg=BG,
                    anchor="w",
                ).pack(fill=X)
            else:
                for track in tracks:
                    row = Frame(
                        recent_frame,
                        bg=SURFACE,
                        height=56,
                        cursor="hand2",
                    )
                    row.pack(fill=X, pady=2)
                    row.pack_propagate(False)
                    cover_frame = Frame(
                        row,
                        width=44,
                        height=44,
                        bg=SURFACE_ALT,
                        cursor="hand2",
                    )
                    cover_frame.pack(side=LEFT, padx=6, pady=6)
                    cover_frame.pack_propagate(False)
                    cover = Label(
                        cover_frame,
                        bg=SURFACE_ALT,
                        borderwidth=0,
                        cursor="hand2",
                    )
                    cover.pack(fill=BOTH, expand=True)
                    text_box = Frame(row, bg=SURFACE, cursor="hand2")
                    text_box.pack(side=LEFT, fill=BOTH, expand=True, pady=7)
                    name_label = Label(
                        text_box,
                        text=track.get("name", ""),
                        fg=TEXT,
                        bg=SURFACE,
                        anchor="w",
                        font=(FONT, 11, "bold"),
                        cursor="hand2",
                    )
                    name_label.pack(fill=X)
                    artist_label = Label(
                        text_box,
                        text=track.get("artist", ""),
                        fg=TEXT_MUTED,
                        bg=SURFACE,
                        anchor="w",
                        font=(FONT, 9),
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
                        recent_swipe_targets[str(widget)] = (text_box, track)
                        widget.bind(
                            "<ButtonRelease-1>",
                            lambda event, selected_uri=uri, selected_track=track,
                            swipe_frame=text_box: (
                                finish_recent_press(
                                    event,
                                    selected_uri,
                                    selected_track,
                                    swipe_frame,
                                )
                            ),
                        )

                    def show_recent_cover(photo, label=cover, expected_uri=uri):
                        current_uris = {
                            item.get("uri")
                            for item in get_state().get("recent_tracks", [])
                        }
                        if expected_uri not in current_uris or not label.winfo_exists():
                            return
                        label.config(image=photo if photo is not None else "")
                        label.image = photo

                    get_photo_async(
                        root,
                        track.get("image_url"),
                        (44, 44),
                        show_recent_cover,
                    )

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
        if new_playlist_signature != playlist_signature:
            playlist_signature = new_playlist_signature
            for child in playlist_list.winfo_children():
                child.destroy()

            if not playlists:
                message = current_state.get("home_error") or (
                    "Loading..." if current_state.get("home_loading") else "No saved playlists"
                )
                Label(
                    playlist_list,
                    text=message,
                    fg=TEXT_MUTED,
                    bg=BG,
                    anchor="w",
                ).pack(fill=X, padx=8, pady=8)
            else:
                for playlist in playlists:
                    card = Frame(playlist_list, width=136, height=166, bg=CARD)
                    card.pack(side=LEFT, padx=(0, 8), pady=4)
                    card.pack_propagate(False)
                    cover_frame = Frame(card, width=120, height=120, bg=SURFACE_ALT)
                    cover_frame.pack(padx=8, pady=(8, 3))
                    cover_frame.pack_propagate(False)
                    cover = Label(
                        cover_frame,
                        bg=SURFACE_ALT,
                        borderwidth=0,
                        highlightthickness=0,
                    )
                    cover.pack(fill=BOTH, expand=True)
                    name_label = Label(
                        card,
                        text=_two_line_ellipsis(
                            playlist.get("name", ""),
                            card_name_font,
                            120,
                        ),
                        fg=TEXT,
                        bg=CARD,
                        anchor="center",
                        justify="center",
                        height=2,
                        font=card_name_font_spec,
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
                                lambda event,
                                uri=expected_uri,
                                name=playlist.get("name", ""),
                                cover_url=image_url: finish_playlist_press(
                                    event,
                                    uri,
                                    name,
                                    cover_url,
                                ),
                            )

                    def show_playlist_cover(photo, label=cover, uri=expected_uri):
                        current_uris = {
                            item.get("uri")
                            for item in get_state().get("playlists", [])
                        }
                        if uri not in current_uris or not label.winfo_exists():
                            return
                        label.config(image=photo if photo is not None else "")
                        label.image = photo

                    get_photo_async(
                        root,
                        image_url,
                        (120, 120),
                        show_playlist_cover,
                    )

        albums = current_state.get("albums", [])
        new_album_signature = (
            current_state.get("home_loading"),
            current_state.get("home_error"),
            tuple(
                (
                    album.get("uri"),
                    album.get("name"),
                    album.get("artist"),
                    album.get("image_url"),
                )
                for album in albums
            ),
        )
        if new_album_signature == album_signature:
            return

        album_signature = new_album_signature
        for child in album_list.winfo_children():
            child.destroy()

        if not albums:
            message = current_state.get("home_error") or (
                "Loading..." if current_state.get("home_loading") else "No saved albums"
            )
            Label(
                album_list,
                text=message,
                fg=TEXT_MUTED,
                bg=BG,
                anchor="w",
            ).pack(fill=X, padx=8, pady=8)
            return

        for album in albums:
            card = Frame(album_list, width=136, height=166, bg=CARD)
            card.pack(side=LEFT, padx=(0, 8), pady=4)
            card.pack_propagate(False)
            cover_frame = Frame(card, width=120, height=120, bg=SURFACE_ALT)
            cover_frame.pack(padx=8, pady=(8, 3))
            cover_frame.pack_propagate(False)
            cover = Label(
                cover_frame,
                bg=SURFACE_ALT,
                borderwidth=0,
                highlightthickness=0,
            )
            cover.pack(fill=BOTH, expand=True)
            name_label = Label(
                card,
                text=_two_line_ellipsis(
                    album.get("name", ""),
                    card_name_font,
                    120,
                ),
                fg=TEXT,
                bg=CARD,
                anchor="center",
                justify="center",
                height=2,
                font=card_name_font_spec,
            )
            name_label.pack(fill=X, padx=5)

            image_url = album.get("image_url")
            expected_uri = album.get("uri")
            if expected_uri:
                for widget in (card, cover_frame, cover, name_label):
                    widget.config(cursor="hand2")
                    widget.bind("<ButtonPress-1>", start_album_drag)
                    widget.bind("<B1-Motion>", drag_album)
                    widget.bind(
                        "<ButtonRelease-1>",
                        lambda event,
                        uri=expected_uri,
                        name=album.get("name", ""),
                        cover_url=image_url: finish_album_press(
                            event,
                            uri,
                            name,
                            cover_url,
                        ),
                    )

            def show_album_cover(photo, label=cover, uri=expected_uri):
                current_uris = {
                    item.get("uri")
                    for item in get_state().get("albums", [])
                }
                if uri not in current_uris or not label.winfo_exists():
                    return
                label.config(image=photo if photo is not None else "")
                label.image = photo

            get_photo_async(
                root,
                image_url,
                (120, 120),
                show_album_cover,
            )

    def update(current_state):
        rebuild_lists(current_state)
        rebuild_search_results(current_state)
        mini_player["update"](current_state)

    def on_show():
        Thread(target=load_recently_played, daemon=True).start()
        Thread(target=load_saved_albums, daemon=True).start()

    Thread(target=load_home, daemon=True).start()
    update(state)
    return {"frame": frame, "update": update, "on_show": on_show}
