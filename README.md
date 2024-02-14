# PlexPlaylistMaker
PlexPlaylistMaker is a Python application designed to automate the creation of playlists in Plex Media Server using IMDb lists. It enables users to easily synchronize their favorite IMDb lists with their Plex library, ensuring that their media collection is always up-to-date with their preferences.

# Features
* IMDb List Integration: Import any public IMDb list URL to create a corresponding playlist in Plex.
* Plex Server Compatibility: Works with any Plex Media Server where you have access to add playlists.
* GUI Interface: User-friendly graphical interface makes it easy to input IMDb lists and manage Plex servers.
* Error Handling: Robust error handling for IMDb data fetching and Plex playlist creation.
* Multi-threaded IMDb Fetching: Speeds up the process of fetching movie details from IMDb by utilizing multi-threading.

# ToDO
* Add support for other sites besides IMDb
* Add better logging and more informative UI
* Add UI progress bar/notification

# Prerequisites
Before you can use PlexPlaylistMaker, ensure you have the following:

* Plex Media Server setup and accessible.
* Python 3.6+ installed on your system.
* Required Python packages: tkinter, plexapi, requests, bs4 (BeautifulSoup), imdbpy, json, threading.

# Installation
Download the program

Install the required Python packages (or use the bat file in the source code):
`pip install plexapi requests beautifulsoup4 imdbpy` 

# Usage
* Login to Plex: Upon starting the application, click "Login and Fetch Servers" to authenticate with your Plex account.
* Select Server: Choose your Plex server from the dropdown menu.
* Enter IMDb List URL: Copy and paste the URL of the IMDb list you want to create a playlist for.
* Enter Playlist Name: Specify a name for your new Plex playlist.
* Submit: Click "Submit" to create the playlist in your Plex server based on the IMDb list. (Give it time if it is a large list)
