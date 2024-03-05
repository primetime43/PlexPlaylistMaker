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
        self.libraries = []  # Initialize the libraries attribute
    
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
                # Connect to the first server
                self.server = plex_account.resource(servers[0]).connect()
                # Fetch and store libraries after successfully connecting to the server
                self.fetch_and_store_libraries()
                # Successfully fetched servers and libraries, call the callback with success=True
                update_ui_callback(servers=servers, success=True)
        else:
            # Failed to log in, call the callback with success=False
            update_ui_callback(servers=None, success=False)
            
    def fetch_and_store_libraries(self):
        if self.server:
            # Retrieve all library sections from the server
            libraries = self.server.library.sections()
            self.libraries = [library.title for library in libraries]
            # Storing more detailed information in a list of dictionaries:
            self.libraries = [{'name': library.title, 'type': library.type, 'uuid': library.uuid} for library in libraries]
 
class PlexIMDbApp(PlexBaseApp):   
    def __init__(self):
        super().__init__()
        
    def fetch_item_details(self, queue, ia, imdb_id, retry_count=3, delay=1):
        attempts = 0
        while attempts < retry_count:
            try:
                movie = ia.get_movie(imdb_id[2:])  # Remove 'tt' prefix (works with movies/tv shows)
                title = movie.get('title')
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
        
    def fetch_imdb_list_data(self, imdb_list_url):
        response = requests.get(imdb_list_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        json_str_match = re.search(r'<script type="application/ld\+json">(.+?)</script>', soup.prettify(), re.DOTALL)
        if json_str_match:
            json_str = json_str_match.group(1)
            data = json.loads(json_str)
            itemListElements = data.get("about", {}).get("itemListElement", [])
            imdb_ids = []
            for item in itemListElements:
                url = item.get("url", "")
                imdb_id_match = re.search(r'/title/(tt\d+)/', url)
                if imdb_id_match:
                    imdb_id = imdb_id_match.group(1)
                    # Validate the extracted IMDb ID
                    if imdb_id and imdb_id.startswith("tt") and imdb_id[2:].isdigit():
                        imdb_ids.append(imdb_id)
            return imdb_ids
        return []

    def find_matched_items(self, library_name, imdb_list_items):
        library = self.server.library.section(library_name)
        items_to_add = []
        for title in imdb_list_items:
            matched_items = library.search(title=title, libtype=library.TYPE)
            for item in matched_items:
                if title.lower() == item.title.lower():
                    items_to_add.append(item)
                    break
        return items_to_add

    def create_plex_playlist(self, imdb_list_url, plex_playlist_name, library_name, callback=None):
        ia = imdb.Cinemagoer()
        imdb_ids = self.fetch_imdb_list_data(imdb_list_url)
        
        # Prepare for multithreading
        threads = []
        queue = Queue()
        for imdb_id in imdb_ids:
            # Start a thread for each IMDb ID
            thread = Thread(target=self.fetch_item_details, args=(queue, ia, imdb_id))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Collect all results
        imdb_list_items = []
        while not queue.empty():
            imdb_list_items.append(queue.get())

        # Find matched items in Plex library
        matched_items = self.find_matched_items(library_name, [title for _, title in imdb_list_items])
        
        # Create the playlist
        if matched_items:
            self.server.createPlaylist(plex_playlist_name, items=matched_items)
            success_message = f"Created playlist '{plex_playlist_name}' with {len(matched_items)} items."
            if callback: callback(True, success_message)
        else:
            error_message = "No matching items found in Plex library."
            if callback: callback(False, error_message)

            
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