import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
import tkinter as tk
import json
import imdb
import re
import os
from PIL import Image
import requests
from bs4 import BeautifulSoup
from threading import Thread
from queue import Queue
import webbrowser
from plexapi.myplex import MyPlexPinLogin, MyPlexAccount
import time
from imdb import IMDbDataAccessError

VERSION = 1.0


class PlexPlaylistMakerGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(
            f"Plex Playlist Maker - {VERSION}"
        )
        # self.check_updates(VERSION)
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
        self.login_and_fetch_servers()

    def letterboxd_button_event(self):
        self.select_frame_by_name("letterboxd_frame")
        
    #move this function eventually    
    def login_and_fetch_servers(self):
        headers = {'X-Plex-Client-Identifier': 'unique_client_identifier'}  # Replace with your unique identifier
        pinlogin = MyPlexPinLogin(headers=headers, oauth=True)
        oauth_url = pinlogin.oauthUrl()
        webbrowser.open(oauth_url)
        pinlogin.run(timeout=120)
        pinlogin.waitForLogin()
        if pinlogin.token:
            plex_account = MyPlexAccount(token=pinlogin.token)
            resources = [resource for resource in plex_account.resources() if resource.owned and resource.connections and resource.provides == 'server']
            servers = [resource.name for resource in resources]
            self.server_var.set(servers[0] if servers else "")
            self.update_server_option_menu(servers)  # Update the option menu
            if servers:
                self.server = plex_account.resource(servers[0]).connect()
        else:
            CTkMessagebox(title="Error", message="Could not log in to Plex account", option_1="OK")
            
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
        
    def fetch_movie_details(self, queue, ia, imdb_id, retry_count=3, delay=1):
        attempts = 0
        while attempts < retry_count:
            try:
                movie = ia.get_movie(imdb_id[2:])  # Remove 'tt' prefix
                title = movie.data.get('original title', movie.get('title'))
                if title:
                    queue.put((imdb_id, title))
                    return
            except IMDbDataAccessError as e:
                print(f"Error fetching {imdb_id}: {e}. Attempt {attempts + 1} of {retry_count}")
                time.sleep(delay * (attempts + 1))  # Exponential back-off
                attempts += 1
            except Exception as e:
                print(f"Unexpected error fetching {imdb_id}: {e}")
                return
        print(f"Failed to fetch details for {imdb_id} after {retry_count} attempts.")
        
    def create_plex_playlist(self):
        # Retrieve the IMDb List URL from the textbox
        imdb_list_url = self.IMDB_covers_directory_textbox.get()
        # Retrieve the Playlist name from the textbox
        plex_playlist_name = self.IMDB_gamecache_textbox.get()

        # Initialize cinemagoer IMDb interface
        ia = imdb.Cinemagoer()

        # Fetch IMDb list data
        response = requests.get(imdb_list_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find the JSON data within the page
        json_str_match = re.search(r'<script type="application/ld\+json">(.+?)</script>', soup.prettify(), re.DOTALL)
        imdb_movies = []
        total_found_in_imdb_list = 0
        if json_str_match:
            json_str = json_str_match.group(1)
            try:
                data = json.loads(json_str)
                items = data.get("about", {}).get("itemListElement", [])
                total_found_in_imdb_list = len(items)  # Total number of movies in IMDb list
                threads = []
                queue = Queue()
                for item in items:
                    url = item.get("url", "")
                    imdb_id_match = re.search(r'/title/(tt\d+)/', url)
                    if imdb_id_match:
                        imdb_id = imdb_id_match.group(1)
                        thread = Thread(target=self.fetch_movie_details, args=(queue, ia, imdb_id))
                        threads.append(thread)
                        thread.start()

                # Wait for all threads to complete
                for thread in threads:
                    thread.join()

                # Collect all results
                while not queue.empty():
                    imdb_movies.append(queue.get())
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e}")
                return

        # Find the 'Movies' section in the Plex library and retrieve all movies
        library = self.server.library.section('Movies')
        all_movies = library.all()

        movies_to_add = []
        for imdb_id, title in imdb_movies:
            matched_movies = library.search(title=title, libtype='movie')
            for plex_movie in matched_movies:
                # Matching based on title (maybe look into other attributes like year, etc. for better matching)
                if title.lower() == plex_movie.title.lower():
                    movies_to_add.append(plex_movie)
                    break  # Break if a match is found to avoid adding duplicates

        # Create the playlist with the matched movies
        if movies_to_add:
            self.server.createPlaylist(plex_playlist_name, items=movies_to_add)
            success_message = f"Created playlist '{plex_playlist_name}' with {len(movies_to_add)} movies out of {total_found_in_imdb_list} found in the IMDb list."
            CTkMessagebox(title="Success", message=success_message, icon="check", option_1="OK")
        else:
            error_message = f"No matching movies found in Plex library out of {total_found_in_imdb_list} movies in the IMDb list."
            CTkMessagebox(title="Error", message=error_message, icon="cancel", option_1="OK")

    def check_updates(self, version: str):
        try:
            rep_version = requests.get(
                "URL_HERE"
            ).text.strip()

            try:
                rep_version = float(rep_version)
            except ValueError:
                rep_version = version

        except requests.exceptions.RequestException:
            rep_version = version

        self.title(
            f"Plex Playlist Maker - {version}{' | NEW VERSION AVAILABLE' if version !=
                                    rep_version else ''}"
        )


if __name__ == "__main__":
    app = PlexPlaylistMakerGUI()
    app.mainloop()
