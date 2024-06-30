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
        if self.server is None:
            print("Server connection is not established.")
            return []
            
        try:
            library = self.server.library.section(library_name)
            items_to_add = []
            for title in list_items:
                matched_items = library.search(title=title, libtype=library.TYPE)
                for item in matched_items:
                    if title.lower() == item.title.lower():
                        items_to_add.append(item)
                        break
            return items_to_add
        except Exception as e:
            print(f"An error occurred while finding matched items: {e}")
            return []
    
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
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
        }
        
        try:
            response = requests.get(imdb_list_url, headers=headers, timeout=10)
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            return [], "HTTP error occurred. Please check the URL."
        except requests.exceptions.ConnectionError:
            return [], "Connection error occurred. Please check your internet connection."
        except requests.exceptions.Timeout:
            return [], "Timeout error occurred. The request took too long to complete."
        except requests.exceptions.RequestException:
            return [], "An error occurred. Please try again."

        soup = BeautifulSoup(response.text, 'html.parser')
        
        imdb_ids = []
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            imdb_id_match = re.search(r'/title/(tt\d+)/', href)
            if imdb_id_match:
                imdb_ids.append(imdb_id_match.group(1))
        
        if imdb_ids:
            return imdb_ids, "Data fetched successfully."
        else:
            return [], "No IMDb IDs found in the provided URL."

        return [], "Failed to fetch data. Please check the URL format and try again."

    def create_plex_playlist(self, list_url, plex_playlist_name, library_name, callback=None):
        if not list_url.strip():
            callback(False, "URL is empty. Please provide a valid URL.")
            return
        
        imdb_ids, message = self.fetch_imdb_list_data(list_url)
        if not imdb_ids:
            callback(False, message) 
            return

        ia = imdb.Cinemagoer()
        # Prepare for multithreading
        threads = []
        queue = Queue()
        for imdb_id in imdb_ids:
            thread = Thread(target=self.fetch_item_details, args=(queue, ia, imdb_id))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        imdb_list_items = []
        while not queue.empty():
            imdb_list_items.append(queue.get())

        if not imdb_list_items:
            callback(False, "No matching items found for given IMDb IDs.")
            return

        matched_items = self.find_matched_items(library_name, [title for _, title in imdb_list_items])
        if matched_items:
            self.server.createPlaylist(plex_playlist_name, items=matched_items)
            callback(True, f"Created playlist '{plex_playlist_name}' with {len(matched_items)} items.")
        else:
            callback(False, "No matching items found in Plex library.")

            
class PlexLetterboxdApp(PlexBaseApp):
    def __init__(self, server=None):
        super().__init__(server=server)
        
    # Maybe eventually use the offcial Letterboxd API instead of web scraping
    def create_plex_playlist(self, list_url, plex_playlist_name, library_name, callback=None):
        if not list_url.strip():
            callback(False, "URL is empty. Please provide a valid URL.")
            return
        
        item_objects, message = self.fetch_letterboxd_list_data(list_url)
        if not item_objects:
            callback(False, message) 
            return
        
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
            callback(True, success_message)
        else:
            error_message = "No matching items found in Plex library."
            callback(False, error_message)
        
    def fetch_letterboxd_list_data(self, list_url):
        """
        Fetch movie slugs and film IDs from a Letterboxd list.
        
        :param list_url: URL of the Letterboxd list
        :return: A list of dictionaries, each containing a movie's slug and film ID
        """
        try:
            response = requests.get(list_url, timeout=10)
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            return [], "HTTP error occurred. Please check the URL."
        except requests.exceptions.ConnectionError:
            return [], "Connection error occurred. Please check your internet connection."
        except requests.exceptions.Timeout:
            return [], "Timeout error occurred. The request took too long to complete."
        except requests.exceptions.RequestException:
            return [], "An error occurred. Please try again."
    
        movies_data = []
        soup = BeautifulSoup(response.text, 'html.parser')

        poster_divs = soup.find_all('div', class_='film-poster')
        if not poster_divs:
            return [], "No movies found in the provided URL."

        for poster_div in poster_divs:
            movie_slug = poster_div.get('data-film-slug')
            film_id = poster_div.get('data-film-id')

            if movie_slug and film_id:
                movies_data.append({
                    'slug': movie_slug.strip(),
                    'film_id': film_id.strip(),
                    'fullURL': f'https://letterboxd.com/film/{movie_slug.strip()}'
                })

        if movies_data:
            return movies_data, "Data fetched successfully."
        else:
            return [], "Failed to parse movie data. Please check the URL format and try again."
    
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