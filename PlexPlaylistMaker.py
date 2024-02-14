import tkinter as tk
from tkinter import messagebox, ttk
import webbrowser
from plexapi.myplex import MyPlexPinLogin, MyPlexAccount
import requests
from bs4 import BeautifulSoup
import re
import imdb
import json
from threading import Thread
from queue import Queue
from tkinter import messagebox
import time
from imdb import IMDbDataAccessError

# Declare the global server variable
server = None
# Declare the global playlist_name variable
playlist_name = None

def fetch_movie_details(queue, ia, imdb_id, retry_count=3, delay=1):
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

def login_and_fetch_servers():
    global server  # Use the global server variable
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
        server_var.set(servers[0] if servers else "")
        server_menu['menu'].delete(0, 'end')
        for server_name in servers:
            server_menu['menu'].add_command(label=server_name, command=tk._setit(server_var, server_name))
        # Connect to the first server by default or based on user selection
        selected_server = plex_account.resource(server_var.get())
        server = selected_server.connect()  # Update the global server variable
        return pinlogin.token
    else:
        messagebox.showerror("Error", "Could not log in to Plex account")
        return None

def create_plex_playlist(imdb_url):
    global server, playlist_name
    if server is None:
        return "Error", "Not connected to a Plex server"

    # Initialize cinemagoer IMDb interface
    ia = imdb.Cinemagoer()

    # Fetch IMDb list data
    response = requests.get(imdb_url)
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
                    thread = Thread(target=fetch_movie_details, args=(queue, ia, imdb_id))
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
    library = server.library.section('Movies')
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
        server.createPlaylist(playlist_name, items=movies_to_add)
        success_message = f"Created playlist '{playlist_name}' with {len(movies_to_add)} movies out of {total_found_in_imdb_list} found in the IMDb list."
        return "Success", success_message
    else:
        error_message = f"No matching movies found in Plex library out of {total_found_in_imdb_list} movies in the IMDb list."
        return "Error", error_message

def submit():
    global playlist_name  # Declare playlist_name as global to update its value
    imdb_url = entry_imdb_url.get()
    playlist_name = entry_playlist_name.get()  # Get the custom playlist name from the entry & Update the global playlist_name

    if imdb_url and playlist_name:
        try:
            token = login_and_fetch_servers()
            if token:
                status, message = create_plex_playlist(imdb_url)  # Unpack the returned status and message
                if status == "Success":
                    messagebox.showinfo(status, message)  # Show success message
                else:
                    messagebox.showerror(status, message)  # Show error message
        except Exception as e:
            error_message = f"An error occurred: {e}"
            messagebox.showerror("Error", error_message)
    else:
        messagebox.showerror("Error", "Please fill all fields.")

root = tk.Tk()
root.title("Plex IMDb Playlist")

frame = tk.Frame(root, padx=15, pady=15)
frame.grid(row=0, column=0)

label_imdb_url = tk.Label(frame, text="IMDb List URL:", width=20)
label_imdb_url.grid(row=0, column=0, sticky="W")

entry_imdb_url = tk.Entry(frame)
entry_imdb_url.grid(row=0, column=1)

label_server = tk.Label(frame, text="Plex Server:", width=20)
label_server.grid(row=1, column=0, sticky="W")

server_var = tk.StringVar(frame)
server_menu = ttk.OptionMenu(frame, server_var, "Select Server")
server_menu.grid(row=1, column=1)

label_playlist_name = tk.Label(frame, text="Playlist Name:", width=20)
label_playlist_name.grid(row=2, column=0, sticky="W")

entry_playlist_name = tk.Entry(frame)
entry_playlist_name.grid(row=2, column=1)

login_button = tk.Button(frame, text="Login and Fetch Servers", command=lambda: login_and_fetch_servers())
login_button.grid(row=3, column=0, columnspan=2)

submit_button = tk.Button(frame, text="Submit", command=submit)
submit_button.grid(row=4, column=0, columnspan=2)

root.mainloop()