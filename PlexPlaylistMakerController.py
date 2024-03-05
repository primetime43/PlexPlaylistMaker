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
from abc import ABC, abstractmethod

class PlexBaseApp(ABC):
    def __init__(self, server=None):
        self.server = None # Initialize the server connection
        self.libraries = []  # Initialize the libraries attribute
        
    @abstractmethod
    def create_plex_playlist(self, list_url, plex_playlist_name, library_name, callback=None):
        pass
    
    def find_matched_items(self, library_name, list_items):
        library = self.server.library.section(library_name)
        items_to_add = []
        for title in list_items:
            matched_items = library.search(title=title, libtype=library.TYPE)
            for item in matched_items:
                if title.lower() == item.title.lower():
                    items_to_add.append(item)
                    break
        return items_to_add
    
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
    def __init__(self, server=None):
        super().__init__(server=server)
        
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

    def create_plex_playlist(self, list_url, plex_playlist_name, library_name, callback=None):
        ia = imdb.Cinemagoer()
        imdb_ids = self.fetch_imdb_list_data(list_url)
        
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
    def __init__(self, server=None):
        super().__init__(server=server)
        
    # Maybe eventually use the offcial Letterboxd API instead of web scraping
    def create_plex_playlist(self, list_url, plex_playlist_name, library_name, callback=None):
        item_objects = self.fetch_letterboxd_list_data(list_url)
        
        # Prepare for multithreading
        threads = []
        queue = Queue()
        for item in item_objects:
            slug_url = item['fullURL']
            # Start a thread for each movie slug URL
            thread = Thread(target=self.fetch_movie_details_from_slug_with_retry, args=(slug_url, queue))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Collect all results
        movie_details_list = []
        while not queue.empty():
            movie_details_list.append(queue.get())

        # Extract movie titles using the 'original_title' key
        movie_titles = [details['original_title'] for details in movie_details_list]

        # Find matched items in the Plex library
        matched_items = self.find_matched_items(library_name, movie_titles)
        
        # Create the playlist if matched items were found
        if matched_items:
            self.server.createPlaylist(plex_playlist_name, items=matched_items)
            success_message = f"Created playlist '{plex_playlist_name}' with {len(matched_items)} items."
            if callback: callback(True, success_message)
        else:
            error_message = "No matching items found in Plex library."
            if callback: callback(False, error_message)
        
    def fetch_letterboxd_list_data(self, list_url):
        """
        Fetch movie slugs and film IDs from a Letterboxd list.
        
        :param list_url: URL of the Letterboxd list
        :return: A list of dictionaries, each containing a movie's slug and film ID
        """
        movies_data = []
        
        response = requests.get(list_url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all divs that contain movie poster information
            poster_divs = soup.find_all('div', class_='film-poster')
            for poster_div in poster_divs:
                movie_slug = poster_div.get('data-film-slug')
                film_id = poster_div.get('data-film-id')
                
                if movie_slug and film_id:
                    movies_data.append({
                        'slug': movie_slug.strip(),
                        'film_id': film_id.strip(),
                        'fullURL': f'https://letterboxd.com/film/{movie_slug.strip()}'
                    })

        return movies_data
    
    def fetch_movie_details_from_slug_with_retry(self, slug_url, queue, retry_count=3, delay=1):
        """
        Fetch movie original title from a Letterboxd film page using the slug URL with retries.

        :param slug_url: The full URL to the film's page on Letterboxd.
        :param queue: A queue to store the fetched movie details.
        :param retry_count: Number of retries in case of request failure.
        :param delay: Delay between retries in seconds.
        """
        for attempt in range(retry_count):
            try:
                response = requests.get(slug_url)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    # Search for the specific meta tag that contains the original title
                    og_title_tag = soup.find('meta', property='og:title')
                    if og_title_tag:
                        og_title = og_title_tag['content']
                        # Use regular expression to strip the year from the title (if present)
                        title_without_year = re.sub(r'\s*\(\d{4}\)$', '', og_title).strip()
                        queue.put({'original_title': title_without_year, 'url': slug_url})  # Store modified title in dictionary
                        return
                    else:
                        print(f"No original title found for {slug_url}.")
                else:
                    print(f"Failed to fetch data for {slug_url}. Status code: {response.status_code}")
            except Exception as e:
                print(f"Error fetching data for {slug_url}: {e}")
            time.sleep(delay * (attempt + 1))  # Exponential back-off
        print(f"Failed to fetch details for {slug_url} after {retry_count} attempts.")
    
    
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