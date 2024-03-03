import json
import imdb
import re
import requests
from bs4 import BeautifulSoup
from threading import Thread
from queue import Queue
import webbrowser
from plexapi.myplex import MyPlexPinLogin, MyPlexAccount
import time
from imdb import IMDbDataAccessError  

class PlexBaseApp:
    def __init__(self):
        self.server = None # Initialize the server connection attribute
    
    def login_and_fetch_servers(self, update_ui_callback):
        headers = {'X-Plex-Client-Identifier': 'unique_client_identifier'}
        pinlogin = MyPlexPinLogin(headers=headers, oauth=True)
        oauth_url = pinlogin.oauthUrl()
        webbrowser.open(oauth_url)
        pinlogin.run(timeout=120)
        pinlogin.waitForLogin()
        if pinlogin.token:
            plex_account = MyPlexAccount(token=pinlogin.token)
            resources = [resource for resource in plex_account.resources() if resource.owned and resource.connections and resource.provides == 'server']
            servers = [resource.name for resource in resources]
            if servers:
                self.server = plex_account.resource(servers[0]).connect()
                # Successfully fetched servers, call the callback with success=True
                update_ui_callback(servers=servers, success=True)
        else:
            # Failed to log in, call the callback with success=False
            update_ui_callback(servers=None, success=False)
 
class PlexIMDbApp(PlexBaseApp):   
    def __init__(self):
        super().__init__()
        
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
        
    def create_plex_playlist(self, imdb_list_url, plex_playlist_name, callback=None):
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
            success_message = f"Created playlist '{plex_playlist_name}' with {len(movies_to_add)} movies."
            if callback:
                callback(True, success_message)  # Call the callback with success status and message
        else:
            error_message = "No matching movies found in Plex library."
            if callback:
                callback(False, error_message)  # Call the callback with failure status and message
            
class PlexLetterboxdApp(PlexBaseApp):
    def __init__(self):
        super().__init__()
    
    
def check_updates(version: str):
    try:
        # Fetch the latest release from GitHub API
        response = requests.get(
            "https://api.github.com/repos/primetime43/PlexPlaylistMaker/releases/latest"
        )
        data = response.json()

        # Check if 'tag_name' is in the response
        if 'tag_name' in data:
            rep_version = data['tag_name'].strip('v')

            try:
                rep_version = float(rep_version)
            except ValueError:
                rep_version = version
        else:
            rep_version = version

    except requests.exceptions.RequestException:
        rep_version = version

    return (
        f"PlexPlaylistMaker - {version}{' | NEW VERSION AVAILABLE' if version < rep_version else ''}"
    )