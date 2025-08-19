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
from concurrent.futures import ThreadPoolExecutor, as_completed

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
        # Batch / performance tuning knobs
        self.LARGE_LIST_THRESHOLD = 500   # Threshold to enable incremental batch logging
        self.BATCH_MATCH_SIZE = 100       # Matching batch size for large lists
        
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
            return [], None, "HTTP error occurred. Please check the URL.", []
        except requests.exceptions.ConnectionError:
            return [], None, "Connection error occurred. Please check your internet connection.", []
        except requests.exceptions.Timeout:
            return [], None, "Timeout error occurred. The request took too long to complete.", []
        except requests.exceptions.RequestException:
            return [], None, "An error occurred. Please try again.", []

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
        id_title_pairs = []  # (imdb_id, title)

        # Primary structured parse: div.lister-item
        lister_items = soup.find_all('div', class_=re.compile(r'lister-item.*'))
        if lister_items:
            for div in lister_items:
                a = div.find('a', href=True)
                if not a:
                    continue
                href = a['href']
                imdb_id_match = re.search(r'/title/(tt\d+)/', href)
                if imdb_id_match:
                    imdb_id = imdb_id_match.group(1)
                    title_text = a.get_text(strip=True)
                    if imdb_id not in imdb_ids:
                        imdb_ids.append(imdb_id)
                        if title_text:
                            id_title_pairs.append((imdb_id, title_text))
        else:
            # Fallback generic anchor scan
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                imdb_id_match = re.search(r'/title/(tt\d+)/', href)
                if imdb_id_match:
                    imdb_id = imdb_id_match.group(1)
                    if imdb_id not in imdb_ids:
                        imdb_ids.append(imdb_id)
                        title_text = a_tag.get_text(strip=True)
                        if title_text:
                            id_title_pairs.append((imdb_id, title_text))

        if imdb_ids:
            return imdb_ids, list_title, "Data fetched successfully.", id_title_pairs
        else:
            return [], list_title, "No IMDb IDs found in the provided URL.", []

    def create_plex_playlist(self, list_url, plex_playlist_name, library_name, callback=None):
        if not list_url.strip():
            callback(False, "URL is empty. Please provide a valid URL.")
            return
        # Extended fetch returns (ids, title, message, id_title_pairs)
        imdb_ids, derived_title, message, id_title_pairs = self.fetch_imdb_list_data(list_url)
        if not imdb_ids:
            callback(False, message)
            return
        if not plex_playlist_name.strip():
            if derived_title:
                plex_playlist_name = derived_title
            else:
                slug = list_url.rstrip('/').split('/')[-1]
                plex_playlist_name = slug.replace('-', ' ').title() if slug else 'IMDb List'
        # Decide whether to skip per-item fetches based on how many titles we already parsed
        fetched_titles = []
        if id_title_pairs and len(id_title_pairs) >= int(0.8 * len(imdb_ids)):
            fetched_titles = [t for _, t in id_title_pairs]
            logging.info(f"IMDb list: parsed {len(fetched_titles)} titles directly from list page (total IDs={len(imdb_ids)}). Skipping individual title fetch requests.")
        else:
            ia = imdb.Cinemagoer()
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

        if not fetched_titles:
            callback(False, "Failed to obtain any titles from the IMDb list.")
            return

        # Batch matching for large lists
        matched_items = []
        seen_rating_keys = set()
        if len(fetched_titles) >= self.LARGE_LIST_THRESHOLD:
            logging.info(f"Matching IMDb titles in batches of {self.BATCH_MATCH_SIZE} (total {len(fetched_titles)}).")
            for i in range(0, len(fetched_titles), self.BATCH_MATCH_SIZE):
                batch = fetched_titles[i:i+self.BATCH_MATCH_SIZE]
                batch_matches = self.find_matched_items(library_name, batch)
                added = 0
                for item in batch_matches:
                    if item.ratingKey not in seen_rating_keys:
                        seen_rating_keys.add(item.ratingKey)
                        matched_items.append(item)
                        added += 1
                logging.info(f"Matched batch {i//self.BATCH_MATCH_SIZE + 1}: {added} new items (cumulative {len(matched_items)}).")
        else:
            matched_items = self.find_matched_items(library_name, fetched_titles)
            seen_rating_keys = {m.ratingKey for m in matched_items}

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
        # Batch thresholds
        self.LARGE_LIST_THRESHOLD = 500
        self.BATCH_MATCH_SIZE = 100
        # Concurrency tuning (for missing-detail fetches only)
        self.MAX_CONCURRENT_FETCHES = 6   # Reasonable small number to avoid hammering
        self.MISSING_FETCH_JITTER = (0.15, 0.55)
        self.MISSING_RETRY = 3
        # Pagination safety cap
        self.MAX_LIST_PAGES = 30

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

        # Attempt enhanced zero / low additional request extraction.
        # 1. Collect titles we already have
        for item in item_objects:
            # Normalize if only title present without original_title
            if item.get('title') and not item.get('original_title'):
                item['original_title'] = item['title']

        pre_parsed_titles = [item['original_title'] for item in item_objects if item.get('original_title')]

        # 2. Determine which still lack titles
        missing = [item for item in item_objects if not item.get('original_title')]

        failures = []
        movie_titles = pre_parsed_titles.copy()

        if missing:
            logging.info(f"Letterboxd: {len(pre_parsed_titles)}/{len(item_objects)} titles from list page; fetching {len(missing)} missing concurrently.")
            fetched_missing = self._fetch_missing_titles_concurrently(missing)
            for slug_url, title in fetched_missing['success']:
                movie_titles.append(title)
            failures.extend(fetched_missing['fail'])
            if fetched_missing['fail']:
                logging.info(f"Letterboxd: {len(fetched_missing['fail'])} film page fetches failed (will continue with available titles).")
        else:
            logging.info(f"Letterboxd: all {len(pre_parsed_titles)} titles parsed from list page; no per-film fetches needed.")

        # Deduplicate while preserving order
        seen_titles = set()
        deduped = []
        for t in movie_titles:
            if t and t not in seen_titles:
                seen_titles.add(t)
                deduped.append(t)
        movie_titles = deduped

        if not movie_titles:
            callback(False, "Failed to obtain any titles from the Letterboxd list (all fetches failed).")
            return

        # Batch matching for large lists to provide incremental logging
        matched_items = []
        seen_rating_keys = set()
        if len(movie_titles) >= self.LARGE_LIST_THRESHOLD:
            logging.info(f"Matching Letterboxd titles in batches of {self.BATCH_MATCH_SIZE} (total {len(movie_titles)}).")
            for i in range(0, len(movie_titles), self.BATCH_MATCH_SIZE):
                batch = movie_titles[i:i+self.BATCH_MATCH_SIZE]
                batch_matches = self.find_matched_items(library_name, batch)
                added = 0
                for item in batch_matches:
                    if item.ratingKey not in seen_rating_keys:
                        seen_rating_keys.add(item.ratingKey)
                        matched_items.append(item)
                        added += 1
                logging.info(f"Matched batch {i//self.BATCH_MATCH_SIZE + 1}: {added} new items (cumulative {len(matched_items)}).")
        else:
            matched_items = self.find_matched_items(library_name, movie_titles)
            seen_rating_keys = {m.ratingKey for m in matched_items}
        requested_total = len(item_objects)
        fetched_count = len(movie_titles)
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
        # Normalize base list URL (strip any /page/<n>/ suffix)
        base_url = re.sub(r'/page/\d+/?$', '/', list_url.rstrip('/'))
        if not base_url.endswith('/'):
            base_url += '/'

        movies_data = []
        list_title = self._derive_slug_title(base_url)
        fetched_pages = 0
        max_pages_detected = None

        def fetch_page(url):
            try:
                resp = self.SESSION.get(url, headers=self.DEFAULT_HEADERS, timeout=15)
                resp.raise_for_status()
                return resp.text, None
            except requests.exceptions.HTTPError:
                return None, "HTTP error occurred."
            except requests.exceptions.ConnectionError:
                return None, "Connection error occurred."
            except requests.exceptions.Timeout:
                return None, "Timeout error occurred."
            except requests.exceptions.RequestException:
                return None, "Request error occurred."

        page_index = 1
        while True:
            if page_index == 1:
                page_url = base_url
            else:
                page_url = f"{base_url}page/{page_index}/"
            html, err = fetch_page(page_url)
            if not html:
                if page_index == 1 and err:
                    return [], None, err
                break  # stop on first missing subsequent page
            soup = BeautifulSoup(html, 'html.parser')
            poster_divs = soup.find_all('div', class_='film-poster')
            if not poster_divs:
                # No more items
                break
            for poster_div in poster_divs:
                movie_slug = poster_div.get('data-film-slug')
                film_id = poster_div.get('data-film-id')
                film_name = poster_div.get('data-film-name')
                original_title = poster_div.get('data-original-title') or film_name
                if (not film_name or not original_title):
                    img = poster_div.find('img')
                    if img and img.get('alt'):
                        alt_title = re.sub(r'\s*\(\d{4}\)$', '', img['alt']).strip()
                        if alt_title:
                            original_title = original_title or alt_title
                            film_name = film_name or alt_title
                if movie_slug and film_id:
                    entry = {
                        'slug': movie_slug.strip(),
                        'film_id': film_id.strip(),
                        'fullURL': f'https://letterboxd.com/film/{movie_slug.strip()}'
                    }
                    if film_name:
                        entry['title'] = film_name.strip()
                    if original_title:
                        entry['original_title'] = original_title.strip()
                    movies_data.append(entry)
            fetched_pages += 1
            # Attempt to detect total pages (only once) if not already known
            if max_pages_detected is None:
                page_nums = []
                for a in soup.find_all('a', href=True):
                    m = re.search(r'/page/(\d+)/', a['href'])
                    if m:
                        try:
                            page_nums.append(int(m.group(1)))
                        except ValueError:
                            pass
                if page_nums:
                    max_pages_detected = max(page_nums)
            # Decide whether to continue
            if max_pages_detected and page_index >= max_pages_detected:
                break
            if fetched_pages >= self.MAX_LIST_PAGES:
                logging.info(f"Letterboxd pagination cap reached ({self.MAX_LIST_PAGES} pages).")
                break
            page_index += 1

        # Deduplicate by slug
        unique = {}
        ordered = []
        for item in movies_data:
            slug = item['slug']
            if slug not in unique:
                unique[slug] = True
                ordered.append(item)
        movies_data = ordered

        if movies_data:
            if fetched_pages > 1:
                logging.info(f"Letterboxd: aggregated {len(movies_data)} items across {fetched_pages} page(s).")
            return movies_data, list_title, "Data fetched successfully."
        return [], list_title, "No movies found in the provided URL."
    
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

    # ---------------- Concurrency helper for missing titles -----------------
    def _fetch_missing_titles_concurrently(self, missing_items):
        """Fetch original titles concurrently for items lacking title info.

        Returns dict {'success': [(url,title),...], 'fail': [url,...]}.
        Concurrency kept modest; each worker jitter-sleeps before request.
        """
        results_success = []
        results_fail = []

        def worker(item):
            slug_url = item['fullURL']
            # light jitter to avoid burst
            time.sleep(random.uniform(*self.MISSING_FETCH_JITTER))
            headers = self.DEFAULT_HEADERS.copy()
            for attempt in range(1, self.MISSING_RETRY + 1):
                try:
                    resp = requests.get(slug_url, headers=headers, timeout=10)
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, 'html.parser')
                        og = soup.find('meta', property='og:title')
                        if og and og.get('content'):
                            title = re.sub(r'\s*\(\d{4}\)$', '', og['content']).strip()
                            if title:
                                return (slug_url, title)
                        return None
                    elif resp.status_code in (429, 503):
                        # exponential backoff with jitter
                        time.sleep((0.6 * (2 ** (attempt - 1))) + random.uniform(0.05, 0.25))
                        continue
                    else:
                        return None
                except Exception:
                    time.sleep(0.4 * attempt + random.uniform(0.05, 0.25))
            return None

        with ThreadPoolExecutor(max_workers=self.MAX_CONCURRENT_FETCHES) as ex:
            future_map = {ex.submit(worker, item): item for item in missing_items}
            for future in as_completed(future_map):
                item = future_map[future]
                slug_url = item['fullURL']
                try:
                    res = future.result()
                except Exception:
                    res = None
                if res:
                    results_success.append(res)
                else:
                    results_fail.append(slug_url)
        return {'success': results_success, 'fail': results_fail}
    
    
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