# PlexPlaylistMaker
PlexPlaylistMaker is a desktop Python application that lets you build Plex playlists directly from public IMDb and Letterboxd lists (Movies and TV Shows) with minimal friction. It authenticates with your Plex account (official PIN/OAuth flow), lets you pick a server & library, and then scrapes / fetches titles to assemble a Plex playlist—providing visibility into what matched and what did not.

## Screenshots
<details>
  <summary>Click to view screenshots (v1.0.0 baseline)</summary>
  <img src="https://github.com/primetime43/PlexPlaylistMaker/assets/12754111/c6ad2b05-5df9-44d3-9821-7ede76573fb0">
  <img src="https://github.com/primetime43/PlexPlaylistMaker/assets/12754111/230cca13-7f2e-4cc1-b4cd-a2ab996eae4c">
</details>

## Key Features
* IMDb & Letterboxd Support: Import public list URLs (movies & shows) using web scraping + Cinemagoer (IMDbPY) where needed.
* Smart Title Matching: Canonical form normalization + optional fuzzy matching (difflib) with an indexed in‑memory title map per library for speed.
* Large List Handling: Batched matching (configurable thresholds) to stay responsive and provide incremental progress logging.
* Letterboxd Rate‑Limit Resilience: Session reuse, polite pacing, retry with exponential backoff + jitter, `Retry-After` honoring, and partial success reporting.
* Fast IMDb Optimization: Attempts to parse most titles right from the list page; only falls back to per‑ID fetch when necessary, in parallel threads.
* Deterministic Auto‑Naming: If you leave the playlist name blank the app derives the name (IMDb: on‑page `<h1>`/og:title fallback to slug; Letterboxd: strict slug conversion only).
* Export Missing Titles: One click CSV export (with position + ID/URLs where available) for unmatched items—separate buttons per source tab.
* Live Log Window: Toggleable real‑time log viewer (Show/Hide Logs) with clear option and connection error suppression toggle (Ctrl+L).
* Update Check Banner: Window title adds “NEW VERSION AVAILABLE” when a newer GitHub release tag is detected.
* Responsive GUI: Uses background threads so the UI stays usable while lists are processed.

## How It Works (High Level)
1. Authenticate: Browser opens Plex PIN/OAuth page; on success the app lists owned servers.
2. Select Server & Library: Only Movie and TV Show libraries are offered for playlist creation.
3. Provide List URL: IMDb or Letterboxd (validated format). Optionally provide a custom playlist name.
4. Fetch & Parse: Source list is scraped; missing details fetched selectively (with backoff for Letterboxd).
5. Match Against Plex: Titles normalized, indexed, and fuzzily matched when needed; unmatched tracked separately.
6. Create Playlist: Plex playlist created with only matched Plex items; summary dialog shown.
7. Export Missing (Optional): Save a timestamped CSV listing unmatched entries (and metadata when available).

## Installation / Setup
Prerequisites:
* A reachable Plex Media Server (you must own/have access via your Plex account).
* Python 3.6+ (recommended 3.9+).
* Windows/macOS/Linux with GUI support.

Install dependencies (or run `install_requirements.bat` on Windows):
```bash
pip install requests plexapi beautifulsoup4 imdbpy Pillow customtkinter CTkMessagebox
```

Run the app:
```bash
python PlexPlaylistMakerGUI.py
```

## Usage Guide
1. Start the application – a browser window opens for Plex auth (allow popups).
2. After login, pick a server (if you own multiple). Libraries list will populate (Movies/Shows only).
3. Paste an IMDb list URL (format: `https://www.imdb.com/list/lsXXXXXXXXXX/`) or Letterboxd list URL (`https://letterboxd.com/<user>/list/<slug>/`).
4. (Optional) Leave Playlist Name blank to auto‑derive.
5. Click Create Playlist. Button animates while processing.
6. When finished a dialog summarizes matched vs unmatched counts.
7. (If there are unmatched titles) Click Export Missing to save a CSV like:
   * IMDb: Position, Title, IMDb ID, IMDb URL
   * Letterboxd: Position, Title, Original Title (if different), Film ID, Letterboxd URL, Slug
8. Open the Log window anytime to monitor detailed progress & backoff behavior. Press Ctrl+L inside the main window to toggle noisy connection error suppression.

## Configuration Knobs (Advanced)
Inside `PlexIMDbApp` / `PlexLetterboxdApp` you can adjust constants:
* Matching / Batching: `LARGE_LIST_THRESHOLD`, `BATCH_MATCH_SIZE`.
* Fuzzy Matching: `FUZZY_THRESHOLD` (in `PlexBaseApp`).
* Letterboxd Rate Limiting: `MAX_RETRIES`, `BASE_DELAY`, `MIN_INTERVAL`, `JITTER_RANGE`.
* Letterboxd Missing Detail Fetching: `MAX_CONCURRENT_FETCHES`, `MISSING_FETCH_JITTER`, `MISSING_RETRY`, `MAX_LIST_PAGES`.

Increase `MIN_INTERVAL` or reduce `MAX_CONCURRENT_FETCHES` if you still see many HTTP 429 responses for Letterboxd.

## Letterboxd Notes
The app tries to collect all title text from list pagination without visiting each film. Only slugs still lacking a resolvable title trigger limited concurrent fetches with exponential backoff. If a very large list repeatedly triggers 429, split it manually or increase delays.

Slug Title Derivation Example:
`https://letterboxd.com/crew/list/10-most-obsessively-rewatched-animation-films/` → `10 Most Obsessively Rewatched Animation Films`

## IMDb Notes
If ≥ ~80% of titles can be parsed directly from the list HTML the app skips per‑movie Cinemagoer fetches for speed. Otherwise it fetches remaining details concurrently with retry on transient failures.

## Exported CSV Examples
File name pattern: `Missing_<PlaylistName>_YYYYMMDD_HHMMSS.csv`.
Columns are dynamic based on source (IMDb vs Letterboxd) and available metadata.

## Building a Standalone Executable (PyInstaller)
```bash
pyinstaller --onefile --noconsole --add-data "icons;icons" PlexPlaylistMakerGUI.py
```
On Windows this produces `dist/PlexPlaylistMakerGUI.exe`. Ensure the `icons` directory is bundled (the `--add-data` argument above handles this for PyInstaller on Windows). Adjust the path separator (`:` vs `;`) depending on your platform.

## Logging & Troubleshooting
* Real‑time logs: Show/Hide via left navigation.
* Clear logs: Use the Clear button in the log window.
* Suppress noisy network error bursts: Press Ctrl+L to toggle.
* Update notice: Title bar appends `| NEW VERSION AVAILABLE` if a newer GitHub release tag exists.
* If nothing matches: Verify you selected the correct Plex library (Movies vs TV) and that the media actually exists in Plex with expected titles.

## Limitations / Disclaimer
* Unofficial: Uses web scraping for IMDb & Letterboxd (subject to site markup changes and rate limits). No affiliation with IMDb, Letterboxd, or Plex.
* Lists must be public / accessible without authentication.
* Fuzzy matching can occasionally pick an unintended title if multiple similar names exist—review playlist items for critical workflows.
* Large lists (thousands of items) will take time; batching reduces memory overhead but still depends on Plex library size.

## Roadmap / To Do
* Additional source sites (e.g., Trakt, TMDb lists) – evaluation.
* Optional progress bar widget (beyond log window) inside main frame.
* Configurable persistence for last used server/library.
* Enhanced filtering (limit playlist by year / rating / watched state).

## Credits
* [primetime43](https://github.com/primetime43)
* [xlenore](https://github.com/xlenore) – initial UI layout inspiration.
* Cinemagoer (IMDbPY) project for IMDb data access.

## License / Use
See `LICENSE` file. Use at your own risk; scraping behavior may break without notice if upstream sites change.

## Feedback / Issues
Please open a GitHub Issue with:
* Source list URL (if public)
* Log snippet (copy from log window)
* Platform / Python version
* Brief description of the mismatch or failure

Pull requests welcome for new sources, performance improvements, or UI enhancements.
