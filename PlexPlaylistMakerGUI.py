import customtkinter as ctk
import tkinter as tk
import os
from PIL import Image
from PlexPlaylistMakerController import PlexIMDbApp, check_updates

VERSION = 1.0

class PlexPlaylistMakerGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.controller = PlexIMDbApp()
        self.title(check_updates(VERSION))
        self.geometry("450x350")
        self.resizable(False, False)
        self.font = ("MS Sans Serif", 12, "bold")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        # Initialize the server variable
        self.server_var = tk.StringVar(self)
        self.server = None  # This will hold the connected server object
        self.testServersArray = []

        # region nav frame
        self.navigation_frame = ctk.CTkFrame(self, corner_radius=0)
        self.navigation_frame.grid(row=0, column=0, sticky="nsew")
        self.navigation_frame.grid_rowconfigure(4, weight=1)

        image_path = os.path.join(os.path.dirname(
            os.path.realpath(__file__)), "icons")

        self.IMDb_image = ctk.CTkImage(
            Image.open(image_path + "/IMDb.png"), size=(20, 20)
        )

        self.Letterboxd_image = ctk.CTkImage(
            Image.open(image_path + "/Letterboxd.png"), size=(20, 20)
        )

        self.IMDB = ctk.CTkButton(
            self.navigation_frame,
            corner_radius=0,
            height=40,
            border_spacing=10,
            font=self.font,
            text="IMDb",
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray30"),
            anchor="w",
            image=self.IMDb_image,
            command=self.imdb_button_event,
        )
        self.IMDB.grid(row=1, column=0, sticky="ew")

        self.Letterboxd = ctk.CTkButton(
            self.navigation_frame,
            corner_radius=0,
            height=40,
            border_spacing=10,
            font=self.font,
            text="Letterboxd",
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray30"),
            anchor="w",
            image=self.Letterboxd_image,
            command=self.letterboxd_button_event,
            state="disabled",
        )
        self.Letterboxd.grid(row=2, column=0, sticky="ew")

        # endregion

        # region IMDb frame
        self.IMDB_frame = ctk.CTkFrame(
            self, corner_radius=0, fg_color="transparent"
        )

        # IMDb List URL textbox
        self.IMDB_covers_directory_textbox = ctk.CTkEntry(
            self.IMDB_frame, placeholder_text="IMDb List URL", width=200
        )
        self.IMDB_covers_directory_textbox.grid(
            row=0, column=0, padx=10, pady=10, sticky="w"
        )

        # Playlist name textbox
        self.IMDB_gamecache_textbox = ctk.CTkEntry(
            self.IMDB_frame, placeholder_text="Playlist Name", width=200
        )
        self.IMDB_gamecache_textbox.grid(
            row=1, column=0, padx=10, pady=10, sticky="w"
        )

        # Dropdown menu for Plex Servers
        self.IMDB_server_var = tk.StringVar(self.IMDB_frame)
        self.IMDB_server_menu = ctk.CTkOptionMenu(
            self.IMDB_frame, 
            variable=self.server_var,
            values=self.testServersArray
        )
        self.IMDB_server_menu.grid(row=2, column=0, padx=10, pady=10, sticky="w")
        
        # IMDb Create Playlist Button
        self.start_download_button = ctk.CTkButton(
            self.IMDB_frame,
            text="Create Playlist",
            command=lambda: self.create_plex_playlist()
        )
        self.start_download_button.grid(
            row=6, column=0, padx=10, pady=10, sticky="w")

        # endregion

        # region Letterboxd frame
        self.Letterboxd_frame = ctk.CTkFrame(
            self, corner_radius=0, fg_color="transparent")

        # Letterboxd covers Dir textbox
        self.Letterboxd_covers_directory_textbox = ctk.CTkEntry(
            self.Letterboxd_frame, placeholder_text="Cover Directory", width=200
        )
        self.Letterboxd_covers_directory_textbox.grid(
            row=0, column=0, padx=10, pady=10, sticky="w"
        )

        # Letterboxd browser button
        self.Letterboxd_covers_directory_button = ctk.CTkButton(
            self.Letterboxd_frame,
            text="Browse",
            command=lambda: self.select_directory("Letterboxd", False),
            width=10,
        )
        self.Letterboxd_covers_directory_button.grid(
            row=0, column=1, padx=5, pady=5, sticky="e"
        )

        # Letterboxd cache textbox
        self.Letterboxd_gamecache_textbox = ctk.CTkEntry(
            self.Letterboxd_frame, placeholder_text="Game Cache", width=200
        )
        self.Letterboxd_gamecache_textbox.grid(
            row=1, column=0, padx=10, pady=10, sticky="w")

        # Letterboxd browser button
        self.Letterboxd_gamecache_button = ctk.CTkButton(
            self.Letterboxd_frame,
            text="Browse",
            command=lambda: self.select_directory("Letterboxd", True),
            width=10,
        )
        self.Letterboxd_gamecache_button.grid(
            row=1, column=1, padx=5, pady=5, sticky="e")

        self.Letterboxd_cover_type_var = tk.IntVar(value=0)

        # Letterboxd covertype radiobuttons
        self.Letterboxd_label_radio_group = ctk.CTkLabel(
            master=self.Letterboxd_frame, text="Cover Type:"
        )
        self.Letterboxd_label_radio_group.grid(
            row=2, column=0, padx=10, pady=10, sticky="w")

        self.Letterboxd_radio_button_1 = ctk.CTkRadioButton(
            master=self.Letterboxd_frame,
            text="Default",
            variable=self.Letterboxd_cover_type_var,
            value=0,
        )
        self.Letterboxd_radio_button_1.grid(
            row=3, column=0, pady=10, padx=20, sticky="w")

        self.Letterboxd_radio_button_2 = ctk.CTkRadioButton(
            master=self.Letterboxd_frame,
            text="3D",
            variable=self.Letterboxd_cover_type_var,
            value=1,
        )
        self.Letterboxd_radio_button_2.grid(
            row=4, column=0, pady=10, padx=20, sticky="w")

        # Letterboxd use_ssl button
        self.Letterboxd_use_ssl_checkbox = ctk.CTkCheckBox(
            self.Letterboxd_frame, text="Use SSL")
        self.Letterboxd_use_ssl_checkbox.grid(
            row=5, column=0, padx=10, pady=10, sticky="w")

        # Letterboxd download button
        self.start_download_button = ctk.CTkButton(
            self.Letterboxd_frame,
            text="Start Download",
            command=lambda: self.start_download("Letterboxd"),
        )
        self.start_download_button.grid(
            row=6, column=0, padx=10, pady=10, sticky="w")

        # endregion

    def select_frame_by_name(self, name):
        self.IMDB.configure(
            fg_color=("gray75", "gray25")
            if name == "imdb_frame"
            else "transparent"
        )
        self.Letterboxd.configure(
            fg_color=(
                "gray75", "gray25") if name == "letterboxd_frame" else "transparent"
        )

        # show selected frame
        if name == "imdb_frame":
            self.IMDB_frame.grid(row=0, column=1, sticky="nsew")
            self.Letterboxd_frame.grid_forget()
        elif name == "letterboxd_frame":
            self.Letterboxd_frame.grid(row=0, column=1, sticky="nsew")
            self.IMDB_frame.grid_forget()

    def imdb_button_event(self):
        self.select_frame_by_name("imdb_frame")
        # Call login_and_fetch_servers to populate the servers dropdown
        self.controller.login_and_fetch_servers(self.update_server_dropdown, self.server_var)

    def letterboxd_button_event(self):
        self.controller.select_frame_by_name("letterboxd_frame")
        
    def update_server_dropdown(self, servers, server_var):
        # Update the server dropdown based on the fetched servers
        server_var.set(servers[0] if servers else "")
        self.update_server_option_menu(servers)

    def update_server_option_menu(self, server_names):
        # Destroy the existing option menu widget, if it exists
        if hasattr(self, 'IMDB_server_menu'):
            self.IMDB_server_menu.destroy()
        
        # Create a new CTkOptionMenu with the updated server names
        self.IMDB_server_menu = ctk.CTkOptionMenu(
            self.IMDB_frame,
            variable=self.server_var,
            values=server_names  # Pass the updated list of server names here
        )
        self.IMDB_server_menu.grid(row=2, column=0, padx=10, pady=10, sticky="w")

if __name__ == "__main__":
    app = PlexPlaylistMakerGUI()
    app.mainloop()
