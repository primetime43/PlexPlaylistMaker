import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
import tkinter as tk
import os
import threading
from PIL import Image
from PlexPlaylistMakerController import PlexIMDbApp, PlexLetterboxdApp, check_updates
import logging
import queue
import re

VERSION = 1.1

class QueueHandler(logging.Handler):
    """Thread-safe logging handler that funnels LogRecords into a queue for the GUI."""
    SUPPRESS_PATTERNS = [
        re.compile(r"Connection aborted", re.IGNORECASE),
        re.compile(r"Max retries exceeded", re.IGNORECASE),
        re.compile(r"Failed to establish a new connection", re.IGNORECASE),
        re.compile(r"actively refused it", re.IGNORECASE),
    ]
    def __init__(self, log_queue: queue.Queue, suppress_connection_errors: bool = True):
        super().__init__()
        self.log_queue = log_queue
        self.suppress_connection_errors = suppress_connection_errors
    def emit(self, record):
        try:
            if self.suppress_connection_errors and record.levelno >= logging.ERROR:
                txt = str(record.getMessage())
                # If any suppression pattern matches, drop it
                for pat in self.SUPPRESS_PATTERNS:
                    if pat.search(txt):
                        return
            msg = self.format(record)
            self.log_queue.put(msg)
        except Exception:
            self.handleError(record)

class PlexPlaylistMakerGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        # Logging queue & handler setup (before creating UI elements that may log)
        self.log_queue = queue.Queue()
        self.queue_handler = QueueHandler(self.log_queue, suppress_connection_errors=True)
        formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
        self.queue_handler.setFormatter(formatter)
        logging.getLogger().addHandler(self.queue_handler)
        # Avoid duplicate logs if basicConfig already set root to INFO
        logging.getLogger().setLevel(logging.INFO)
        self.log_window = None
        self.log_text_widget = None
        self.log_polling = False
        self.controller = None
        self.server_connection = None
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

        self.IMDB_frame.library_var = tk.StringVar(self)  # Initialize library_var for the IMDb frame
        
        # IMDb List URL textbox
        self.IMDB_playlist_url_textbox = ctk.CTkEntry(
            self.IMDB_frame, placeholder_text="IMDb List URL", width=200
        )
        self.IMDB_playlist_url_textbox.grid(
            row=0, column=0, padx=10, pady=10, sticky="w"
        )

        # Playlist name textbox
        self.IMDB_playlist_name_textbox = ctk.CTkEntry(
            self.IMDB_frame, placeholder_text="Leave blank for auto-title", width=200
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
        
        self.Letterboxd_frame.library_var = tk.StringVar(self)  # Initialize library_var for the Letterboxd frame

        # Letterboxd List URL textbox
        self.Letterboxd_playlist_url_textbox = ctk.CTkEntry(
            self.Letterboxd_frame, placeholder_text="Letterboxd List URL", width=200
        )
        self.Letterboxd_playlist_url_textbox.grid(
            row=0, column=0, padx=10, pady=10, sticky="w"
        )

        # Playlist name textbox
        self.Letterboxd_playlist_name_textbox = ctk.CTkEntry(
            self.Letterboxd_frame, placeholder_text="Leave blank for auto-title", width=200
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
        
        # Dropdown menu for selecting a library
        self.library_var = tk.StringVar(self)
        self.library_menu = ctk.CTkOptionMenu(
            self.Letterboxd_frame,
            variable=self.library_var,
            values=["Loading libraries..."]  # Placeholder text
        )
        self.library_menu.grid(row=3, column=0, padx=10, pady=10, sticky="w")
        
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

        self.create_logging_toggle_button()

        # Bind Ctrl+L to toggle connection error logging
        self.bind('<Control-L>', self.toggle_connection_error_logging)

    def create_logging_toggle_button(self):
        """Add a button in the navigation frame to open/close the log window."""
        self.log_toggle_button = ctk.CTkButton(
            self.navigation_frame,
            text="Show Logs",
            height=32,
            command=self.toggle_log_window,
            font=("MS Sans Serif", 11, "bold")
        )
        self.log_toggle_button.grid(row=3, column=0, padx=5, pady=5, sticky="ew")

    def toggle_log_window(self):
        if self.log_window and tk.Toplevel.winfo_exists(self.log_window):
            self.hide_log_window()
        else:
            self.show_log_window()

    def show_log_window(self):
        if self.log_window and tk.Toplevel.winfo_exists(self.log_window):
            return
        self.log_window = tk.Toplevel(self)
        self.log_window.title("Application Logs")
        self.log_window.geometry("650x300")
        self.log_window.protocol("WM_DELETE_WINDOW", self.hide_log_window)
        # Text widget with scrollbar
        frame = tk.Frame(self.log_window)
        frame.pack(fill=tk.BOTH, expand=True)
        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text_widget = tk.Text(frame, wrap='word', state='disabled', bg='#111111', fg='#e0e0e0')
        self.log_text_widget.pack(fill=tk.BOTH, expand=True)
        self.log_text_widget.configure(yscrollcommand=scrollbar.set)
        scrollbar.configure(command=self.log_text_widget.yview)
        # Control buttons
        btn_frame = tk.Frame(self.log_window)
        btn_frame.pack(fill=tk.X)
        clear_btn = tk.Button(btn_frame, text="Clear", command=self.clear_logs)
        clear_btn.pack(side=tk.LEFT, padx=4, pady=4)
        close_btn = tk.Button(btn_frame, text="Hide", command=self.hide_log_window)
        close_btn.pack(side=tk.LEFT, padx=4, pady=4)
        self.log_toggle_button.configure(text="Hide Logs")
        self.start_log_polling()

    def hide_log_window(self):
        if self.log_window and tk.Toplevel.winfo_exists(self.log_window):
            self.stop_log_polling()
            self.log_window.destroy()
        self.log_window = None
        self.log_text_widget = None
        self.log_toggle_button.configure(text="Show Logs")

    def clear_logs(self):
        if self.log_text_widget:
            self.log_text_widget.configure(state='normal')
            self.log_text_widget.delete('1.0', tk.END)
            self.log_text_widget.configure(state='disabled')

    def start_log_polling(self):
        if not self.log_polling:
            self.log_polling = True
            self.after(200, self.poll_log_queue)

    def stop_log_polling(self):
        self.log_polling = False

    def poll_log_queue(self):
        if not self.log_polling:
            return
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.append_log_message(msg)
        except queue.Empty:
            pass
        self.after(500, self.poll_log_queue)

    def append_log_message(self, msg: str):
        if not self.log_text_widget:
            return
        self.log_text_widget.configure(state='normal')
        self.log_text_widget.insert(tk.END, msg + "\n")
        self.log_text_widget.configure(state='disabled')
        self.log_text_widget.see(tk.END)

    def select_frame_by_name(self, frame_name):
        """Selects and displays the specified frame, and performs common post-selection actions."""
        self.current_frame = frame_name  # Update the current frame name

        # Configure button appearances based on selected frame
        self.IMDB.configure(fg_color=("gray75", "gray25") if frame_name == "imdb_frame" else "transparent")
        self.Letterboxd.configure(fg_color=("gray75", "gray25") if frame_name == "letterboxd_frame" else "transparent")

        """Selects and displays the specified frame, and updates the controller."""
        if frame_name == "imdb_frame":
            self.switch_to_imdb_controller()
        elif frame_name == "letterboxd_frame":
            self.switch_to_letterboxd_controller()
            
        # Display the selected frame and hide the other
        if frame_name == "imdb_frame":
            self.IMDB_frame.grid(row=0, column=1, sticky="nsew")
            self.Letterboxd_frame.grid_forget()
        elif frame_name == "letterboxd_frame":
            self.Letterboxd_frame.grid(row=0, column=1, sticky="nsew")
            self.IMDB_frame.grid_forget()

        if not self.server_connection:
            threading.Thread(target=self.async_login_and_fetch_servers).start()
            
    def switch_to_imdb_controller(self):
        """Switches the current controller to the IMDb controller."""
        if not isinstance(self.controller, PlexIMDbApp):
            self.controller = PlexIMDbApp(server=self.server_connection)
        # Ensure the server connection is set in the controller
        self.controller.server = self.server_connection
        # Ensure the correct library_var is used for IMDb
        self.library_var = self.IMDB_frame.library_var

    def switch_to_letterboxd_controller(self):
        """Switches the current controller to the Letterboxd controller."""
        if not isinstance(self.controller, PlexLetterboxdApp):
            self.controller = PlexLetterboxdApp(server=self.server_connection)
        # Ensure the server connection is set in the controller
        self.controller.server = self.server_connection
        # Ensure the correct library_var is used for Letterboxd
        self.library_var = self.Letterboxd_frame.library_var


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
            self.server_connection = self.controller.server  # Update the shared server connection
        
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
            self.update_library_dropdown(filtered_libraries, self.IMDB_frame)
            self.update_library_dropdown(filtered_libraries, self.Letterboxd_frame)
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
            
    def update_library_dropdown(self, libraries, target_frame):
        # Check if the library menu already exists in the target frame and destroy it if it does
        if hasattr(target_frame, 'library_menu'):
            target_frame.library_menu.destroy()

        # Create a new dropdown for the updated libraries in the target frame
        library_var = tk.StringVar(self)
        library_menu = ctk.CTkOptionMenu(
            target_frame,
            variable=library_var,
            values=libraries
        )
        library_menu.grid(row=3, column=0, padx=10, pady=10, sticky="w")

        # Set the default value if libraries are available
        if libraries:
            library_var.set(libraries[0])

        # Update the target frame attribute to hold the new library menu and variable
        target_frame.library_menu = library_menu
        target_frame.library_var = library_var
        
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
        # Determine which frame is currently active and get the selected library from the correct dropdown
        if self.current_frame == "imdb_frame":
            selected_library = self.IMDB_frame.library_var.get()
        elif self.current_frame == "letterboxd_frame":
            selected_library = self.Letterboxd_frame.library_var.get()
        else:
            CTkMessagebox(title="Error", message="Error: No active frame identified.", icon="cancel", option_1="OK")
            return
        
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

    def toggle_connection_error_logging(self, event=None):
        """Keyboard shortcut to flip suppression of noisy connection errors (Ctrl+L)."""
        if hasattr(self, 'queue_handler'):
            self.queue_handler.suppress_connection_errors = not self.queue_handler.suppress_connection_errors
            state = 'ON' if not self.queue_handler.suppress_connection_errors else 'OFF'
            # Inject an informational line so user knows the state changed
            self.log_queue.put(f"[LOG FILTER] Connection error messages now {('visible' if state=='ON' else 'hidden')}.")



if __name__ == "__main__":
    app = PlexPlaylistMakerGUI()
    app.mainloop()
