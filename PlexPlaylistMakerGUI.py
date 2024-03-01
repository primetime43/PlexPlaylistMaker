import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
import tkinter as tk
import os
import threading
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
        self.servers = []  # Initialize an empty list to store server names
        
        # Initialize the server variable
        self.server_var = tk.StringVar(self)

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
            command=lambda: self.select_frame_by_name("imdb_frame"),
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
            command=lambda: self.select_frame_by_name("letterboxd_frame"),
        )
        self.Letterboxd.grid(row=2, column=0, sticky="ew")

        # endregion

        # region IMDb frame
        self.IMDB_frame = ctk.CTkFrame(
            self, corner_radius=0, fg_color="transparent"
        )

        # IMDb List URL textbox
        self.IMDB_playlist_url_textbox = ctk.CTkEntry(
            self.IMDB_frame, placeholder_text="IMDb List URL", width=200
        )
        self.IMDB_playlist_url_textbox.grid(
            row=0, column=0, padx=10, pady=10, sticky="w"
        )

        # Playlist name textbox
        self.IMDB_playlist_name_textbox = ctk.CTkEntry(
            self.IMDB_frame, placeholder_text="Playlist Name", width=200
        )
        self.IMDB_playlist_name_textbox.grid(
            row=1, column=0, padx=10, pady=10, sticky="w"
        )

        # Dropdown menu for Plex Servers
        self.IMDB_server_menu = ctk.CTkOptionMenu(
            self.IMDB_frame, 
            variable=self.server_var,
            values=["Loading servers..."]  # Placeholder text
        )
        self.IMDB_server_menu.grid(row=2, column=0, padx=10, pady=10, sticky="w")
        
        # IMDb Create Playlist Button
        self.imdb_create_playlist_button = ctk.CTkButton(
            self.IMDB_frame,
            text="Create Playlist",
            command=lambda: self.start_playlist_creation(
                self.IMDB_playlist_url_textbox.get(), 
                self.IMDB_playlist_name_textbox.get(),
                self.imdb_create_playlist_button
            )
        )
        self.imdb_create_playlist_button.grid(row=6, column=0, padx=10, pady=10, sticky="w")

        # endregion

        # region Letterboxd frame
        self.Letterboxd_frame = ctk.CTkFrame(
            self, corner_radius=0, fg_color="transparent")

        # Letterboxd List URL textbox
        self.Letterboxd_playlist_url_textbox = ctk.CTkEntry(
            self.Letterboxd_frame, placeholder_text="Letterboxd List URL", width=200
        )
        self.Letterboxd_playlist_url_textbox.grid(
            row=0, column=0, padx=10, pady=10, sticky="w"
        )

        # Playlist name textbox
        self.Letterboxd_playlist_name_textbox = ctk.CTkEntry(
            self.Letterboxd_frame, placeholder_text="Playlist Name", width=200
        )
        self.Letterboxd_playlist_name_textbox.grid(
            row=1, column=0, padx=10, pady=10, sticky="w"
        )

        # Dropdown menu for Plex Servers
        self.Letterboxd_server_menu = ctk.CTkOptionMenu(
            self.Letterboxd_frame, 
            variable=self.server_var,
            values=["Loading servers..."]  # Placeholder text
        )
        self.Letterboxd_server_menu.grid(row=2, column=0, padx=10, pady=10, sticky="w")
        
        # Letterboxd Create Playlist Button
        self.letterboxd_create_playlist_button = ctk.CTkButton(
            self.Letterboxd_frame,
            text="Create Playlist",
            command=lambda: self.start_playlist_creation(
                self.Letterboxd_playlist_url_textbox.get(), 
                self.Letterboxd_playlist_name_textbox.get(),
                self.letterboxd_create_playlist_button
            )
        )
        self.letterboxd_create_playlist_button.grid(row=6, column=0, padx=10, pady=10, sticky="w")

        # endregion
        
        self.current_frame = "imdb_frame"  # Default to IMDb frame
        
        # Overlay Frame for loading indication
        self.loading_overlay = ctk.CTkFrame(self, width=450, height=350, corner_radius=10)
        self.loading_overlay.place(x=0, y=0, relwidth=1, relheight=1)
        self.loading_overlay_label = ctk.CTkLabel(self.loading_overlay, text="Loading...", font=("MS Sans Serif", 16, "bold"))
        self.loading_overlay_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        self.loading_dots = 0
        self.loading_animation_id = None  # Will store the ID of the scheduled after() call
        # Hide the overlay immediately after creating it
        self.hide_overlay()  # This line ensures the overlay is hidden by default

    def select_frame_by_name(self, frame_name):
        """Selects and displays the specified frame, and performs common post-selection actions."""
        self.current_frame = frame_name  # Update the current frame name

        # Configure button appearances based on selected frame
        self.IMDB.configure(fg_color=("gray75", "gray25") if frame_name == "imdb_frame" else "transparent")
        self.Letterboxd.configure(fg_color=("gray75", "gray25") if frame_name == "letterboxd_frame" else "transparent")

        # Display the selected frame and hide the other
        if frame_name == "imdb_frame":
            self.IMDB_frame.grid(row=0, column=1, sticky="nsew")
            self.Letterboxd_frame.grid_forget()
        elif frame_name == "letterboxd_frame":
            self.Letterboxd_frame.grid(row=0, column=1, sticky="nsew")
            self.IMDB_frame.grid_forget()

        # Common functionality after selecting the frame (e.g., login and fetch servers)
        if not self.controller.server:
            threading.Thread(target=self.async_login_and_fetch_servers).start()


    def imdb_button_event(self):
        self.select_frame_by_name("imdb_frame")
        # Check if a server is already connected before attempting to log in again
        if not self.controller.server:
            # No server connection exists, so attempt to log in and fetch servers
            # Run the login and fetch operation in a separate thread
            threading.Thread(target=self.async_login_and_fetch_servers).start()
            
    def letterboxd_button_event(self):
        self.select_frame_by_name("letterboxd_frame")
        # Check if a server is already connected before attempting to log in again
        if not self.controller.server:
            # No server connection exists, so attempt to log in and fetch servers
            # Run the login and fetch operation in a separate thread
            threading.Thread(target=self.async_login_and_fetch_servers).start()
        
    def async_login_and_fetch_servers(self):
        """Fetch servers without blocking the UI, updating both menus on completion."""
        def fetch_servers():
            # Show the loading overlay
            self.show_overlay()
            # Perform the login and fetch operation. This method will run on a separate thread
            self.controller.login_and_fetch_servers(self.update_server_menus, self.server_var)
            # Schedule the hide_overlay to run on the main thread after completion
            self.after(0, self.hide_overlay)
            
        # Check if servers have already been loaded
        if not self.servers:
            threading.Thread(target=fetch_servers).start()
        else:
            self.update_server_menus(self.servers)
        
    def show_overlay(self):
        self.loading_overlay.configure(width=450, height=350)
        # Determine the frame on which to show the overlay based on the parameter
        if self.current_frame == "imdb_frame":
            frame = self.IMDB_frame
        elif self.current_frame == "letterboxd_frame":
            frame = self.Letterboxd_frame
        else:
            return  # If the frame is not recognized, do not show the overlay
        
        self.loading_overlay_label.place(relx=0.3, rely=0.4, anchor=tk.CENTER) # Center the label
        
        # Update layout to get current dimensions and positions
        frame.update_idletasks()
        x = frame.winfo_x()
        y = frame.winfo_y()

        # Place the overlay without trying to set width and height here
        self.loading_overlay.place(x=x, y=y, relwidth=1, relheight=1)
        
        # Start the loading text animation
        self.update_loading_text()

    def hide_overlay(self):
        self.loading_overlay.place_forget()
        # Stop the loading text animation by canceling the scheduled update
        if self.loading_animation_id is not None:
            self.after_cancel(self.loading_animation_id)
            self.loading_animation_id = None
        
    def update_loading_text(self):
        if not self.loading_overlay.winfo_ismapped():
            # If the overlay is no longer displayed, cancel further updates
            if self.loading_animation_id is not None:
                self.after_cancel(self.loading_animation_id)
                self.loading_animation_id = None
            return
        
        self.loading_dots = (self.loading_dots + 1) % 4  # Cycle through 0 to 3
        # Correctly form the new text for the label
        text = "Loading" + "." * self.loading_dots + " " * (3 - self.loading_dots)
        self.loading_overlay_label.configure(text=text)
        self.loading_animation_id = self.after(500, self.update_loading_text)  # Schedule next update
        
    def update_button_text(self, text, button):
        button.configure(text=text)
        
    def recreate_server_dropdown(self, frame, variable, servers, row, column, padx, pady, sticky):
        """
        Recreate a server dropdown menu with updated servers.

        Args:
            frame: The parent frame where the dropdown will be placed.
            variable: The tkinter variable associated with the dropdown.
            servers: The list of server names to populate the dropdown.
            row: The grid row where the dropdown will be placed.
            column: The grid column where the dropdown will be placed.
            padx: The padding along the x axis.
            pady: The padding along the y axis.
            sticky: The sticky option to define how the widget expands.
        """
        # Create a new CTkOptionMenu with the updated server names
        server_menu = ctk.CTkOptionMenu(
            frame,
            variable=variable,
            values=servers
        )
        server_menu.grid(row=row, column=column, padx=padx, pady=pady, sticky=sticky)

        # Set the default/selected server if the list is not empty
        if servers:
            variable.set(servers[0])

        # Return the newly created dropdown menu
        return server_menu
        
    def update_server_menus(self, servers, server_var=None):
        """Recreate IMDb and Letterboxd server dropdown menus with updated servers."""
        self.servers = servers  # Store the updated list of servers

        # Recreate the IMDb server dropdown menu with updated servers
        self.IMDB_server_menu = self.recreate_server_dropdown(
            frame=self.IMDB_frame,
            variable=self.server_var,
            servers=servers,
            row=2,
            column=0,
            padx=10,
            pady=10,
            sticky="w"
        )

        # Recreate the Letterboxd server dropdown menu with updated servers
        self.Letterboxd_server_menu = self.recreate_server_dropdown(
            frame=self.Letterboxd_frame,
            variable=self.server_var,
            servers=servers,
            row=2,
            column=0,
            padx=10,
            pady=10,
            sticky="w"
        )

    def start_playlist_creation(self, url, name, button):
        def run():
            # Update button text to indicate process start
            self.update_button_text_dynamically("Creating Playlist", button)
            
            # Call the create playlist method with a callback
            self.controller.create_plex_playlist(url, name, lambda success, message: self.after(0, self.playlist_creation_callback, success, message, button))
        
        threading.Thread(target=run).start()

    # Method to dynamically update button text with loading dots
    def update_button_text_dynamically(self, base_text, button):
        def update_text():
            nonlocal base_text, dots
            dots = (dots + 1) % 4
            self.after(500, update_text)
            self.update_button_text(f"{base_text}{'.' * dots}{' ' * (3 - dots)}", button)
        
        dots = 0
        update_text()

    # Callback method to be called once playlist creation is done
    def playlist_creation_callback(self, success, message, button):
        # Update the button text back to normal
        self.update_button_text("Create Playlist", button)
        
        # Display the message using CTkMessagebox based on success status
        if success:
            CTkMessagebox(title="Success", message=message, icon="check", option_1="OK")
        else:
            CTkMessagebox(title="Error", message=message, icon="cancel", option_1="OK")



if __name__ == "__main__":
    app = PlexPlaylistMakerGUI()
    app.mainloop()
