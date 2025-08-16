# PlexPlaylistMaker
PlexPlaylistMaker is a Python application that facilitates the creation of Plex Media Server playlists directly from IMDb and Letterboxd lists (supports both Movie and TV Show lists). It provides a seamless integration, allowing users to enrich their Plex viewing experience by leveraging curated lists from popular movie databases.

## Images of v1.0.0
<details>
  <summary>Click to view screenshots of version 1.0.0</summary>
  <img src="https://github.com/primetime43/PlexPlaylistMaker/assets/12754111/c6ad2b05-5df9-44d3-9821-7ede76573fb0">
  <img src="https://github.com/primetime43/PlexPlaylistMaker/assets/12754111/230cca13-7f2e-4cc1-b4cd-a2ab996eae4c">
</details>

# Features
* Support for IMDb and Letterboxd: Create Plex playlists from public IMDb and Letterboxd lists using web scraping and the Cinemagoer API.
* Seamless Plex Server Integration: Compatible with any accessible Plex Media Server for playlist management.
* Intuitive Graphical User Interface: Easy-to-navigate GUI for hassle-free list import and playlist creation.
* Robust Error Handling: Advanced error handling for reliable data fetching and playlist creation.
* Efficient Processing: Multi-threading for IMDb (and a polite sequential fetch for Letterboxd to mitigate rate limiting) data retrieval, offering fast synchronization.

# Disclaimer
PlexPlaylistMaker does not use the official APIs of IMDb or Letterboxd for data retrieval. Instead, it relies on web scraping techniques and the Cinemagoer API (a third-party IMDb interface) to gather list information.

# ToDo
* Support more sites possibly
* Add better logging
* Add UI progress bar/notification

## Letterboxd Rate Limiting Notes
Letterboxd can respond with HTTP 429 (Too Many Requests) if pages are fetched too quickly. The application now:

* Uses a single shared `requests.Session` with browser-like headers.
* Spaces film page requests by a minimum interval plus a small random jitter.
* Honors `Retry-After` headers when present on 429 responses.
* Applies exponential backoff with jitter for 429 and transient server/network errors.
* Provides partial success messaging (e.g., number of skipped items) instead of failing the entire playlist creation.

You can tune the constants near the top of the `PlexLetterboxdApp` class:

* `MAX_RETRIES`
* `BASE_DELAY`
* `MIN_INTERVAL`
* `JITTER_RANGE`

If you still encounter many 429 responses:
1. Increase `MIN_INTERVAL` (e.g., to 2.0 or 3.0 seconds).
2. Decrease list size for large batches (split large Letterboxd lists into smaller chunks).
3. Wait 10-15 minutes before retrying after heavy usage.

# Prerequisites
Before you can use PlexPlaylistMaker, ensure you have the following:

* Plex Media Server setup and accessible.
* Python 3.6+ installed on your system.
* Required Python packages: requests, plexapi, beautifulsoup4, imdbpy, json, threading, Pillow, customtkinter, and CTkMessagebox.

# Installation
1. Clone or download the program from the repository.
2. Install the required Python packages using the command below or by executing the provided batch file in the source code:
```bash
pip install requests plexapi beautifulsoup4 imdbpy Pillow customtkinter CTkMessagebox
```

# Usage
1. Launch the App: Open PlexPlaylistMaker and log in to your Plex account.
2. Select a Server: Choose the Plex server where the playlist will be created.
3. Enter List URL: Paste the URL from IMDb or Letterboxd.
4. Name Your Playlist: Define a unique name for your playlist.
5. Create: Click on "Create Playlist" and wait for the process to complete, especially for larger lists.

# Credits
* [primetime43](https://github.com/primetime43)
* [xlenore](https://github.com/xlenore) for the basic UI layout

## Command for packing into a single exe file
```
pyinstaller --onefile --noconsole --add-data "icons;icons" PlexPlaylistMakerGUI.py
```
