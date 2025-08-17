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
import random
import logging
import difflib
import unicodedata

# Configure a basic logger (prints to console). Users can customize or replace.
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')

class PlexBaseApp(ABC):
    def __init__(self, server=None):
        self.server = server  # Server connection (plexapi.server.PlexServer)
        self.plex_account = None  # MyPlexAccount after authentication
        self.libraries = []  # Cached libraries metadata
        # Fuzzy matching support
        self._title_index = {}  # library_name -> {canonical_form: [items]}
        self.FUZZY_THRESHOLD = 0.88

    # ---------------- Normalization helpers -----------------
    @staticmethod
    def _strip_diacritics(text: str) -> str:
        return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))

    @staticmethod
    def _canonical_forms(title: str):
        """Return set of canonical forms for a title (lowercase, articles normalized, punctuation removed)."""
        if not title:
            return set()
        t = title.lower().strip()
        # Move trailing ", The" -> leading
        m = re.match(r'(.+),\s+(the|a|an)$', t)
        if m:
            t = f"{m.group(2)} {m.group(1)}"
        def basic(x: str):
            x = PlexBaseApp._strip_diacritics(x)
            x = re.sub(r'[\u2019'"`]+", '', x)  # remove quote-like chars
            x = re.sub(r'[^a-z0-9]+', ' ', x)  # non-alnum -> space
            x = re.sub(r'\s+', ' ', x).strip()
            return x
        base = basic(t)
        forms = {base}
        forms.add(re.sub(r'^(the|a|an)\s+', '', base))
        return {f for f in forms if f}

    def _ensure_library_index(self, library_name: str, library):
        if library_name in self._title_index:
            return
        idx = {}
        try:
            for item in library.all():
                for form in self._canonical_forms(item.title):
                    idx.setdefault(form, []).append(item)
            self._title_index[library_name] = idx
            logging.info(f"Indexed {len(idx)} canonical forms for library '{library_name}'.")
        except Exception as e:
            logging.error(f"Failed to build index for library '{library_name}': {e}")
            self._title_index[library_name] = {}
        
    @abstractmethod
    def create_plex_playlist(self, list_url, plex_playlist_name, library_name, callback=None):
        pass
    
    def find_matched_items(self, library_name, list_items):
        if self.server is None:
            logging.warning("Server connection is not established.")
            return []
        try:
            library = self.server.library.section(library_name)
        except Exception as e:
            logging.error(f"Unable to access library '{library_name}': {e}")
            return []

        # Build index if not present
        self._ensure_library_index(library_name, library)
        index = self._title_index.get(library_name, {})
        results = []
        seen = set()
        for raw_title in list_items:
            if not raw_title:
                continue
            wanted_forms = self._canonical_forms(raw_title)
            chosen = None
            # 1. Exact canonical form
            for form in wanted_forms:
                if form in index:
                    chosen = index[form][0]
                    break
            # 2. Fuzzy match if not found
            if not chosen and index:
                target = next(iter(wanted_forms)) if wanted_forms else ''
                candidates = index.keys()
                if target and target[0].isalpha():
                    subset = [c for c in candidates if c.startswith(target[0])]
                    if subset:
                        candidates = subset
                best_form = None
                best_ratio = 0.0
                for cand in candidates:
                    r = difflib.SequenceMatcher(None, target, cand).ratio()
                    if r > best_ratio:
                        best_ratio = r
                        best_form = cand
                if best_form and best_ratio >= self.FUZZY_THRESHOLD:
                    chosen = index[best_form][0]
                    logging.debug(f"Fuzzy matched '{raw_title}' -> '{chosen.title}' ({best_ratio:.2f}).")
            # 3. Legacy direct Plex search fallback
            if not chosen:
                try:
                    plex_res = library.search(title=raw_title)
                    for item in plex_res:
                        if item.title.lower() == raw_title.lower() or (self._canonical_forms(item.title) & wanted_forms):
                            chosen = item
                            break
                except Exception:
                    pass
            if chosen and chosen.ratingKey not in seen:
                seen.add(chosen.ratingKey)
                results.append(chosen)
        return results
    
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
                # Store account for subsequent server selection
                self.plex_account = plex_account
                # Auto-connect only if there is a single server; otherwise wait for user selection
                if len(servers) == 1:
                    try:
                        self.server = plex_account.resource(servers[0]).connect()
                        self.fetch_and_store_libraries()
                    except Exception as e:
                        logging.error(f"Failed to auto-connect to Plex server '{servers[0]}': {e}")
                        update_ui_callback(servers=servers, success=False)
                        return
                # Successfully fetched servers (and maybe libraries if auto-connected)
                update_ui_callback(servers=servers, success=True)
            else:
                update_ui_callback(servers=[], success=False)
        else:
            # Failed to log in, call the callback with success=False
            update_ui_callback(servers=None, success=False)

    def connect_to_server(self, server_name: str):
        """Connect to the specified Plex server name and refresh libraries.

        Returns True on success, False on failure.
        """
        if not self.plex_account:
            logging.error("Cannot connect to server; Plex account not authenticated.")
            return False
        try:
            self.server = self.plex_account.resource(server_name).connect()
            self.fetch_and_store_libraries()
            logging.info(f"Connected to Plex server '{server_name}' and loaded libraries.")
            return True
        except Exception as e:
            logging.error(f"Failed to connect to Plex server '{server_name}': {e}")
            return False
            
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
            return [], None, "HTTP error occurred. Please check the URL."
        except requests.exceptions.ConnectionError:
            return [], None, "Connection error occurred. Please check your internet connection."
        except requests.exceptions.Timeout:
            return [], None, "Timeout error occurred. The request took too long to complete."
        except requests.exceptions.RequestException:
            return [], None, "An error occurred. Please try again."

        soup = BeautifulSoup(response.text, 'html.parser')
        # Attempt to extract a list title from typical IMDb list structures
        list_title = None
        h1 = soup.find('h1')
        if h1 and h1.text.strip():
            list_title = h1.text.strip()
        if not list_title:
            og_title_tag = soup.find('meta', property='og:title')
            if og_title_tag and og_title_tag.get('content'):
                list_title = og_title_tag['content'].strip()
        if not list_title:
            slug = imdb_list_url.rstrip('/').split('/')[-1]
            if slug:
                list_title = slug.replace('-', ' ').title()
        
        imdb_ids = []
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            imdb_id_match = re.search(r'/title/(tt\d+)/', href)
            if imdb_id_match:
                imdb_ids.append(imdb_id_match.group(1))
        
        if imdb_ids:
            return imdb_ids, list_title, "Data fetched successfully."
        else:
            return [], list_title, "No IMDb IDs found in the provided URL."

        return [], list_title, "Failed to fetch data. Please check the URL format and try again."

    def create_plex_playlist(self, list_url, plex_playlist_name, library_name, callback=None):
        if not list_url.strip():
            callback(False, "URL is empty. Please provide a valid URL.")
            return
        
        imdb_ids, derived_title, message = self.fetch_imdb_list_data(list_url)
        if not imdb_ids:
            callback(False, message)
            return
        if not plex_playlist_name.strip():
            if derived_title:
                plex_playlist_name = derived_title
            else:
                slug = list_url.rstrip('/').split('/')[-1]
                plex_playlist_name = slug.replace('-', ' ').title() if slug else 'IMDb List'

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

        fetched_titles = [title for _, title in imdb_list_items]
        matched_items = self.find_matched_items(library_name, fetched_titles)
        matched_count = len(matched_items)
        total_fetched = len(fetched_titles)
        unmatched_count = total_fetched - matched_count
        if matched_items:
            self.server.createPlaylist(plex_playlist_name, items=matched_items)
            logging.info(
                f"Playlist created (IMDb): name='{plex_playlist_name}' matched={matched_count} "
                f"unmatched={unmatched_count} total_fetched={total_fetched}"
            )
            msg = (
                f"Created playlist '{plex_playlist_name}' with {matched_count} matched items. "
                f"{unmatched_count} not found in Plex." if unmatched_count else
                f"Created playlist '{plex_playlist_name}' with all {matched_count} items."
            )
            callback(True, msg)
        else:
            callback(False, "None of the fetched items were found in the Plex library.")

            
class PlexLetterboxdApp(PlexBaseApp):
    def __init__(self, server=None):
        super().__init__(server=server)
        # Configuration knobs
        self.MAX_RETRIES = 6              # Total attempts per film page
        self.BASE_DELAY = 1.0             # Base delay for exponential backoff (seconds)
        self.MIN_INTERVAL = 1.2           # Minimum spacing between successive requests (seconds)
        self.JITTER_RANGE = (0.05, 0.35)  # Added random jitter to reduce burst patterns
        self.SESSION = requests.Session() # Reuse TCP connection & cookies
        self.DEFAULT_HEADERS = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
            ),
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,'
                      'image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Connection': 'keep-alive'
        }
        self._last_request_time = 0.0

    @staticmethod
    def _derive_slug_title(list_url: str) -> str:
        """Derive a human-friendly title strictly from the list slug in the URL.

        Example:
            https://letterboxd.com/crew/list/10-most-obsessively-rewatched-animation-films/
            -> "10 Most Obsessively Rewatched Animation Films"
        """
        # Extract segment after '/list/' ignoring trailing slash
        slug_match = re.search(r"/list/([^/]+)/?", list_url)
        slug = slug_match.group(1) if slug_match else list_url.rstrip('/').split('/')[-1]
        slug = slug or 'Letterboxd List'
        words = re.split(r'[-_]+', slug)
        # Title case each word unless it's all caps already
        titled = ' '.join(w if w.isupper() else w.capitalize() for w in words)
        return titled.strip()
        
    # Maybe eventually use the offcial Letterboxd API instead of web scraping
    def create_plex_playlist(self, list_url, plex_playlist_name, library_name, callback=None):
        if not list_url.strip():
            callback(False, "URL is empty. Please provide a valid URL.")
            return

        item_objects, derived_title, message = self.fetch_letterboxd_list_data(list_url)
        if not item_objects:
            callback(False, message)
            return
        # Auto-name if user left playlist name blank
        if not plex_playlist_name.strip():
            if derived_title:
                plex_playlist_name = derived_title
            else:
                slug = list_url.rstrip('/').split('/')[-1]
                plex_playlist_name = slug.replace('-', ' ').title() if slug else 'Letterboxd List'

        # Sequential polite fetching to avoid triggering aggressive rate limits.
        movie_details_list = []
        failures = []
        for idx, item in enumerate(item_objects, start=1):
            slug_url = item['fullURL']
            details = self.fetch_movie_details_from_slug_with_retry(slug_url)
            if details:
                movie_details_list.append(details)
                logging.info(f"[{idx}/{len(item_objects)}] Acquired: {details['original_title']}")
            else:
                failures.append(slug_url)

        if not movie_details_list:
            # If all failed, surface richer error context
            if failures:
                callback(False, (
                    f"Failed to fetch any film data. Total attempts: {len(failures)}. "
                    f"Rate limiting may have blocked requests. Try again later or reduce list size."))
            else:
                callback(False, "No movies found or parsed from the provided URL.")
            return

        movie_titles = [details['original_title'] for details in movie_details_list]
        matched_items = self.find_matched_items(library_name, movie_titles)
        requested_total = len(item_objects)
        fetched_count = len(movie_details_list)
        failures_count = len(failures)
        matched_count = len(matched_items)
        unmatched_fetched = fetched_count - matched_count

        if matched_items:
            self.server.createPlaylist(plex_playlist_name, items=matched_items)
            logging.info(
                "Playlist created (Letterboxd): name='%s' requested=%d fetched=%d matched=%d "
                "unmatched_fetched=%d fetch_failures=%d" % (
                    plex_playlist_name, requested_total, fetched_count, matched_count, unmatched_fetched, failures_count)
            )
            parts = [f"Created playlist '{plex_playlist_name}' with {matched_count} matched items."]
            if unmatched_fetched:
                parts.append(f"{unmatched_fetched} fetched but not in Plex.")
            if failures_count:
                parts.append(f"{failures_count} failed to fetch.")
            callback(True, " ".join(parts))
        else:
            # None matched
            if fetched_count:
                msg = (f"Fetched {fetched_count} title(s) but none matched Plex library.")
                if failures_count:
                    msg += f" {failures_count} failed to fetch."
                logging.info(
                    "Playlist creation aborted (Letterboxd): name='%s' requested=%d fetched=%d matched=0 fetch_failures=%d" % (
                        plex_playlist_name, requested_total, fetched_count, failures_count)
                )
                callback(False, msg)
            else:
                # fetched_count == 0 already handled earlier, but just in case
                callback(False, "No matching items found in Plex library.")
        
    def fetch_letterboxd_list_data(self, list_url):
        """
        Fetch movie slugs and film IDs from a Letterboxd list.
        
        :param list_url: URL of the Letterboxd list
        :return: (movies_data, list_title, message)
        """
        try:
            # Include headers & session reuse for list page too
            response = self.SESSION.get(list_url, headers=self.DEFAULT_HEADERS, timeout=15)
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            return [], None, "HTTP error occurred. Please check the URL."
        except requests.exceptions.ConnectionError:
            return [], None, "Connection error occurred. Please check your internet connection."
        except requests.exceptions.Timeout:
            return [], None, "Timeout error occurred. The request took too long to complete."
        except requests.exceptions.RequestException:
            return [], None, "An error occurred. Please try again."
    
        movies_data = []
        soup = BeautifulSoup(response.text, 'html.parser')
        list_title = self._derive_slug_title(list_url)
        logging.debug(f"Letterboxd slug title='{list_title}' from URL '{list_url}'")

        poster_divs = soup.find_all('div', class_='film-poster')
        if not poster_divs:
            return [], list_title, "No movies found in the provided URL."

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
            return movies_data, list_title, "Data fetched successfully."
        else:
            return [], list_title, "Failed to parse movie data. Please check the URL format and try again."
    
    def fetch_movie_details_from_slug_with_retry(self, slug_url):
        """Fetch movie original title from a Letterboxd film page with robust retry & backoff.

        Returns dict {'original_title': title, 'url': slug_url} or None.
        Implements:
          - Exponential backoff with jitter
          - Honor Retry-After header on 429
          - Minimum request spacing
          - Browser-like headers & session reuse
        """
        for attempt in range(1, self.MAX_RETRIES + 1):
            # Enforce minimum spacing between requests
            elapsed = time.time() - self._last_request_time
            if elapsed < self.MIN_INTERVAL:
                sleep_needed = self.MIN_INTERVAL - elapsed + random.uniform(*self.JITTER_RANGE)
                time.sleep(sleep_needed)
            try:
                response = self.SESSION.get(slug_url, headers=self.DEFAULT_HEADERS, timeout=15)
                self._last_request_time = time.time()
                status = response.status_code
                if status == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    og_title_tag = soup.find('meta', property='og:title')
                    if og_title_tag:
                        og_title = og_title_tag['content']
                        title_without_year = re.sub(r'\s*\(\d{4}\)$', '', og_title).strip()
                        return {'original_title': title_without_year, 'url': slug_url}
                    logging.warning(f"Missing og:title meta for {slug_url}")
                    return None
                elif status == 404:
                    logging.warning(f"404 Not Found for {slug_url}; skipping.")
                    return None
                elif status == 429:
                    # Respect Retry-After if provided, else exponential backoff
                    retry_after_header = response.headers.get('Retry-After')
                    if retry_after_header and retry_after_header.isdigit():
                        wait_time = int(retry_after_header) + random.uniform(*self.JITTER_RANGE)
                    else:
                        wait_time = (self.BASE_DELAY * (2 ** (attempt - 1))) + random.uniform(*self.JITTER_RANGE)
                    logging.debug(f"429 rate limited attempt {attempt}/{self.MAX_RETRIES} for {slug_url}; wait {wait_time:.2f}s")
                    time.sleep(wait_time)
                    continue
                elif status in (500, 502, 503, 504):
                    wait_time = (self.BASE_DELAY * (2 ** (attempt - 1))) + random.uniform(*self.JITTER_RANGE)
                    logging.debug(f"Server error {status} attempt {attempt}/{self.MAX_RETRIES} for {slug_url}; retry in {wait_time:.2f}s")
                    time.sleep(wait_time)
                    continue
                else:
                    logging.warning(f"Unexpected status {status} for {slug_url}; no retry.")
                    return None
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                wait_time = (self.BASE_DELAY * (2 ** (attempt - 1))) + random.uniform(*self.JITTER_RANGE)
                logging.debug(f"Network issue '{e}' attempt {attempt}/{self.MAX_RETRIES} for {slug_url}; retry in {wait_time:.2f}s")
                time.sleep(wait_time)
            except Exception as e:
                logging.error(f"Unhandled exception fetching {slug_url}: {e}")
                return None
        logging.error(f"Failed to fetch details for {slug_url} after {self.MAX_RETRIES} attempts.")
        return None
    
    
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