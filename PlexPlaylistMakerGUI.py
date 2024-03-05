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
        
        # Dropdown menu for selecting a library
        self.library_var = tk.StringVar(self)
        self.library_menu = ctk.CTkOptionMenu(
            self.IMDB_frame,
            variable=self.library_var,
            values=["Loading libraries..."]  # Placeholder text
        )
        self.library_menu.grid(row=3, column=0, padx=10, pady=10, sticky="w")
        
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
        # Disable the buttons to prevent multiple clicks
        self.IMDB.configure(state=ctk.DISABLED)
        self.Letterboxd.configure(state=ctk.DISABLED)
        
        def fetch_servers():
            # Show the loading overlay
            self.show_overlay()
            # Perform the login and fetch operation. This method will run on a separate thread
            self.controller.login_and_fetch_servers(self.server_login_callback)
        
        # Start the server fetching process
        threading.Thread(target=fetch_servers).start()
    
    def server_login_callback(self, servers, success):
        # Re-enable the IMDb and Letterboxd buttons after server fetch completes.
        self.IMDB.configure(state=ctk.NORMAL)
        self.Letterboxd.configure(state=ctk.NORMAL)
        
        if success:
            # Update the UI with the server list if login was successful.
            self.update_server_menus(servers)
            filtered_libraries = [lib['name'] for lib in self.controller.libraries if lib['type'] in ('movie', 'show')]
            self.update_library_dropdown(filtered_libraries)
        else:
            # Show an error message if login failed.
            CTkMessagebox.show_error("Login Failed", "Could not log in to Plex account.")
        
        # Hide the overlay in all cases.
        self.hide_overlay()
    
    def re_enable_buttons_and_hide_overlay(self):
        """Re-enable the IMDb and Letterboxd buttons after server fetch completes."""
        self.IMDB.configure(state=ctk.NORMAL)
        self.Letterboxd.configure(state=ctk.NORMAL)
        self.hide_overlay()

    def show_overlay(self):
        self.loading_overlay.configure(width=450, height=350)
        self.loading_dots = 0
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
        """Update the loading text with animated dots."""
        if not self.loading_overlay.winfo_ismapped():
            # If the overlay is no longer displayed, cancel further updates
            if self.loading_animation_id is not None:
                self.after_cancel(self.loading_animation_id)
                self.loading_animation_id = None
            return

        # Update the label with an increasing number of dots
        self.loading_dots = (self.loading_dots + 1) % 4
        loading_text = "Loading" + "." * self.loading_dots + " " * (3 - self.loading_dots)
        self.loading_overlay_label.configure(text=loading_text)
        
        # Reschedule this method to update the text again
        self.loading_animation_id = self.after(500, self.update_loading_text)
        
    def update_button_text(self, text, button):
        button.configure(text=text)
        
    # Method to update the library dropdown menu
    #REMOVE
    def update_library_menu(self):
        # Filter libraries for 'movie' and 'show' types
        filtered_libraries = [lib['name'] for lib in self.controller.libraries if lib['type'] in ('movie', 'show')]
        
        # Update the option menu values
        self.library_menu.set_values(filtered_libraries)
        
        # Set the default value if there are any filtered libraries
        if filtered_libraries:
            self.library_var.set(filtered_libraries[0])
            
    def update_library_dropdown(self, libraries):
        # Destroy the old dropdown if it exists
        if hasattr(self, 'library_menu'):
            self.library_menu.destroy()

        # Create a new dropdown with the updated libraries
        self.library_var = tk.StringVar(self)
        self.library_menu = ctk.CTkOptionMenu(
            self.IMDB_frame, 
            variable=self.library_var,
            values=libraries
        )
        self.library_menu.grid(row=3, column=0, padx=10, pady=10, sticky="w")

        # Set the default value if libraries are available
        if libraries:
            self.library_var.set(libraries[0])
        
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
        selected_library = self.library_var.get()  # Get the selected library name
        def run():
            # Update button text to indicate process start and disable it
            self.after(0, lambda: self.update_button_text_dynamically("Creating Playlist", button, disable=True))
            
            # Call the create playlist method with the selected library
            self.controller.create_plex_playlist(url, name, selected_library, lambda success, message: self.after(0, self.playlist_creation_callback, success, message, button))
        
        threading.Thread(target=run).start()

    # Method to dynamically update button text with loading dots
    def update_button_text_dynamically(self, base_text, button, disable=False):
        # Cancel any existing animation
        if hasattr(button, '_animation_id'):
            self.after_cancel(button._animation_id)
            delattr(button, '_animation_id')

        if disable:
            # Store the original command to restore it later
            if not hasattr(button, '_original_command'):
                button._original_command = button.cget('command')
                button.configure(command=lambda: None, state=ctk.DISABLED)  # Disable the button

            def animate_dots(dots=1):
                # Update the text with the next number of dots
                button.configure(text=f"{base_text}{'.' * dots}")
                # Schedule the next update, cycling back to 1 dot after 3
                button._animation_id = self.after(500, animate_dots, (dots % 3) + 1)

            animate_dots()  # Start the animation
        else:
            # Stop the animation and restore the button to its original state
            if hasattr(button, '_original_command'):
                button.configure(command=button._original_command)
                delattr(button, '_original_command')
            button.configure(text=base_text, state=ctk.NORMAL)  # Re-enable the button

    # Callback method to be called once playlist creation is done
    def playlist_creation_callback(self, success, message, button):
        # Stop any ongoing text animation and reset the button text and state
        self.update_button_text_dynamically("Create Playlist", button, disable=False)
        
        # Display the message using CTkMessagebox based on success status
        if success:
            CTkMessagebox(title="Success", message=message, icon="check", option_1="OK")
        else:
            CTkMessagebox(title="Error", message=message, icon="cancel", option_1="OK")



if __name__ == "__main__":
    app = PlexPlaylistMakerGUI()
    app.mainloop()
