import spotipy
import time
import os
import configparser
from datetime import datetime, date

try:
    # Read the configuration file to get the Spotify API credentials and playlist information
    config_filename = "config.txt"
    if not os.path.exists(config_filename):
        raise FileNotFoundError(f"Configuration file '{config_filename}' not found.")
    config = configparser.ConfigParser()
    config.read(config_filename)

    # Extract configuration variables
    client_id = config["DEFAULT"]["client_id"]
    client_secret = config["DEFAULT"]["client_secret"]
    redirect_uri = config["DEFAULT"]["redirect_uri"]
    playlist_id = config["DEFAULT"]["playlist_id"]
    scope = "user-library-read user-follow-read playlist-modify-public"  # Permissions needed for Spotify API
    filename = "LastRun.txt"     # File to track the last run date
    max_artist_fetch_limit = 50  # Max number of artists to fetch in each request
    max_track_fetch_limit = 1    # Limit for fetching albums or singles per request
    max_add_limit = 100          # Max number of tracks to add in each batch to the playlist

    # Function to read the date of the last run from the 'LastRun.txt' file
    def read_date():
        if os.path.exists(filename):
            print(f"'{filename}' found.")
            with open(filename, "r") as file:
                date_str = file.read()
        else:
            print(f"'{filename}' not found.")
            date_str = str(date.today())  # Default to today's date if no file exists
        return date_str

    # Function to write the current date to 'LastRun.txt' for tracking the next run date
    def write_date():
        with open(filename, "w") as file:
            current_date_str = str(date.today())
            file.write(current_date_str)
        print(f"'{filename}' date updated to {current_date_str}.")

    # Function to fetch all followed artists
    def fetch_artists():
        artists = []
        tmp_artists = sp.current_user_followed_artists(limit=max_artist_fetch_limit)
        for artist in tmp_artists["artists"]["items"]:
            artists.append(artist)
        while tmp_artists["artists"]["cursors"]["after"] is not None:
            tmp_artists = sp.current_user_followed_artists(limit=max_artist_fetch_limit, 
                                                           after=tmp_artists["artists"]["cursors"]["after"])
            for artist in tmp_artists["artists"]["items"]:
                artists.append(artist)
        return artists

    # Function to fetch releases (albums or singles) for a given artist
    def fetch_releases(artist_id, album_type, run_date):
        releases = []
        keep_searching = True
        fetched_count = 0

        while keep_searching:
            results = sp.artist_albums(
                artist_id,
                album_type=album_type,
                limit=max_track_fetch_limit,
                offset=fetched_count
            )
            if results["items"]:
                for album in results["items"]:
                    try:
                        release_date = datetime.strptime(album["release_date"], '%Y-%m-%d').date()
                        if release_date >= run_date:
                            releases.append(album)
                        else:
                            keep_searching = False  # Stop fetching if the release date is earlier than the run date
                    except ValueError:
                        continue  # Skip albums with invalid release dates
            else:
                keep_searching = False
            fetched_count += max_track_fetch_limit
        return releases

    # Function to add fetched tracks to the playlist, ensuring no duplicates
    def add_tracks_to_playlist(releases):
        for release in releases:
            album_tracks = sp.album_tracks(release["id"])
            track_ids = []  # Tracks to be added to playlist
            for track in album_tracks["items"]:
                artist_names = ", ".join(artist["name"] for artist in track["artists"])
                track_string = f"{artist_names} - {track['name']}"
                if track["id"] in playlist_tracks:
                    print(f"  Already in playlist: {track_string}")  # Skip if track is already in the playlist
                    continue
                if track["id"] not in added_tracks:
                    track_ids.append(track["id"])
                    added_tracks.add(track["id"])  # Track added to the set to avoid duplicates
                    added_tracks_strings.append(track_string)
                    print(f"  Added: {track_string}")
            if track_ids:
                # Add the tracks to the playlist in batches
                for i in range(0, len(track_ids), max_add_limit):
                    sp.playlist_add_items(playlist_id, track_ids[i:i+max_add_limit])
    
    # Function to fetch the list of tracks already in the playlist to avoid duplication
    def fetch_playlist_tracks(playlist_id):
        track_ids = set()
        offset = 0
        limit = max_add_limit
        results = sp.playlist_tracks(playlist_id, offset=offset, limit=limit)
        while results["items"]:
            tracks = results["items"]
            for item in tracks:
                track = item["track"]
                track_ids.add(track["id"])
            if len(tracks) < limit:
                break
            offset += limit
            results = sp.playlist_tracks(playlist_id, offset=offset, limit=limit)

        return track_ids

    # Authentication using Spotipy's OAuth flow
    sp = spotipy.Spotify(auth_manager=spotipy.oauth2.SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=scope))
    user = sp.me()  # Get the authenticated user details
    print(f"Authenticated successfully as '{user['display_name']}' ({user['id']}).")

    # Track the elapsed time for performance
    start = time.time()
    
    # Fetch the list of tracks currently in the playlist
    print("Fetching current playlist tracks for filtering.")
    playlist_tracks = fetch_playlist_tracks(playlist_id)
    print(f"Current playlist tracks fetched ({len(playlist_tracks)}).")

    # Retrieve the list of followed artists
    print("Retrieving all followed artists.")
    artists = fetch_artists()
    artist_count = len(artists)
    artist_index_length = len(str(artist_count))
    print(f"Followed artists retrieved ({artist_count}).")

    # Read the date from which new releases should be processed
    date_str = read_date()
    print(f"Releases will be added from {date_str} onwards.")
    run_date = datetime.strptime(date_str, '%Y-%m-%d').date()

    # Container for added track IDs and human-readable information
    added_tracks = set()
    added_tracks_strings = []

    # Loop through each artist and fetch new albums and singles
    for index, artist in enumerate(artists, start=1):
        formatted_index = str(index).zfill(artist_index_length)
        print(f'Checking releases from {formatted_index}/{artist_count} {artist["name"]}')
        albums = fetch_releases(artist["id"], "album", run_date)
        singles = fetch_releases(artist["id"], "single", run_date)
        add_tracks_to_playlist(albums + singles)

    # Write the current date as the new run date for future runs
    write_date()

    # Output the number and details of the added tracks
    new_releases_count = len(added_tracks)
    release_index_length = len(str(new_releases_count))
    print(f"Done. All new releases added ({new_releases_count}).")
    for index, track_string in enumerate(added_tracks_strings, start=1):
        formatted_index = str(index).zfill(release_index_length)
        print(f"{formatted_index}. {track_string}")

    # Calculate and display the execution time
    stop = time.time()
    print(f"Execution time: {stop - start:.3f} seconds")

    input("Press Enter to exit...")

except Exception as e:
    print(f"An error occurred: {e}")
    input("Press Enter to exit...")
