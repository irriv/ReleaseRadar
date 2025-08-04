import spotipy
import time
import os
import configparser
import io

from datetime import datetime, date
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

# Define "constants"
sp_scope = "user-library-read user-follow-read playlist-modify-public" # Permissions needed for Spotify API
cloud_scope = ["https://www.googleapis.com/auth/drive.file"]           # Permissions needed for Google Drive API

config_filename = "config.txt" # Config file for Spotify API
sp_token_filename = ".cache" # Spotify token file
cloud_credentials_folder = "Cloud" # Cloud credentials folder
cloud_credentials_filename = "credentials.json" # Cloud credentials file
credentials_path = os.path.join(cloud_credentials_folder, cloud_credentials_filename) # Cloud credentials path
cloud_token_filename = "token.json" # Cloud token file
cloud_folder_name = "ReleaseRadar" # Folder in cloud containing the below two files
date_filename = "LastRun.txt" # File to track the last run date
previous_tracks_filename = "PreviousTracks.txt" # File to track the previous run tracks
backup_folder_name = "Backup" # Folder to save the above two files locally if uploading to cloud fails

max_artist_fetch_limit = 50 # Max number of artists to fetch in each request
max_track_fetch_limit = 1   # Limit for fetching albums or singles per request
max_add_limit = 100         # Max number of tracks to add in each batch to the playlist
max_tries = 4               # How many times to request a response in case of failures
base_backoff = 2            # How long to wait between retries in seconds

# Read the configuration file to get the Spotify API credentials and playlist information
def get_config():
    if not os.path.exists(config_filename):
        raise FileNotFoundError(f"Configuration file '{config_filename}' not found.")
    config = configparser.ConfigParser()
    config.read(config_filename)
    return config

# Authentication using Spotipy's OAuth flow
def authenticate_spotify():
    # Extract configuration variables
    config = get_config()
    client_id = config["DEFAULT"]["client_id"]
    client_secret = config["DEFAULT"]["client_secret"]
    redirect_uri = config["DEFAULT"]["redirect_uri"]
    playlist_id = config["DEFAULT"]["playlist_id"]
    
    auth_manager = spotipy.oauth2.SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=sp_scope)
    
    if not os.path.exists(sp_token_filename):
        auth_url = auth_manager.get_authorize_url()
        print(f"Please visit this URL to authorize this application: {auth_url}")
    sp = spotipy.Spotify(auth_manager=auth_manager)

    user = sp.me() # Get the authenticated user details
    print(f"Authenticated with Spotify successfully as '{user['display_name']}' ({user['id']}).")
    return sp, playlist_id

# Establish the cloud service
def authenticate_cloud():
    creds = None
    if os.path.exists(cloud_token_filename):
        creds = Credentials.from_authorized_user_file(cloud_token_filename, cloud_scope)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
          creds.refresh(Request())
        else:
          flow = InstalledAppFlow.from_client_secrets_file(
              credentials_path, cloud_scope
          )
          creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(cloud_token_filename, "w") as token:
          token.write(creds.to_json())
    service = build("drive", "v3", credentials=creds) # On failure an exception is raised
    print("Authenticated successfully with cloud service.")
    return service

# Get cloud folder id
def get_cloud_folder_id(service):
    # Find the folder by name
    folder_query = f"name = '{cloud_folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    folder_results = service.files().list(q=folder_query, fields="files(id)").execute()
    folders = folder_results.get("files", [])
    if folders:
        return folders[0]['id']
    else:
        print(f"Folder '{cloud_folder_name}' not found.")

    # Create the folder if it doesn't exist
    metadata = {
        "name": cloud_folder_name,
        "mimeType": "application/vnd.google-apps.folder"
    }
    folder = service.files().create(body=metadata, fields="id").execute()
    print(f"Created folder '{cloud_folder_name}' on cloud.")
    return folder["id"]

# Get file from cloud folder
def get_cloud_file(service, folder_id, filename):
    # Find the file inside the folder
    file_query = f"'{folder_id}' in parents and name = '{filename}' and trashed = false"
    file_results = service.files().list(q=file_query, fields="files(id)").execute()
    files = file_results.get("files", [])
    if not files:
        print(f"File '{filename}' not found.")
        return None
    file_id = files[0]['id']
    
    # Download and return the file content
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    fh.seek(0)
    string_content = fh.read().decode()
    print(f"'{filename}' fetched.")
    return string_content
    
# Fetch the list of previous tracks  
def get_previous_tracks(service, folder_id):
    print("Fetching previous tracks for filtering.")
    previous_data = get_cloud_file(service, folder_id, previous_tracks_filename)
    previous_tracks = set(previous_data.strip().splitlines()) if previous_data else set()
    print(f"Previous tracks fetched ({len(previous_tracks)}).")
    return previous_tracks

# Fetch the last run date
def get_run_date(service, folder_id):
    print("Fetching last run date for filtering.")
    date_str = get_cloud_file(service, folder_id, date_filename)
    file_found = bool(date_str)
    if not file_found:
        date_str = str(date.today())
    run_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    print(f"Releases will be added from {run_date} onwards.")
    return run_date, file_found

# Save files locally as a backup
def write_local_backup(filename, content):
    os.makedirs(backup_folder_name, exist_ok=True) # Create the backup folder if it doesn't exist
    filepath = os.path.join(backup_folder_name, filename)
    with open(filepath, "w") as file:
        file.write(content)
    print(f"The file '{filename}' was saved locally to {filepath}.")

# Upload or update a file in cloud folder
def upload_file(service, folder_id, filename, content):
    print(f"Uploading '{filename}' to cloud.")
    try:
        query = f"'{folder_id}' in parents and name = '{filename}' and trashed = false"
        results = service.files().list(q=query, fields="files(id)").execute()
        files = results.get("files", [])
        content_bytes = io.BytesIO(content.encode("utf-8"))
        media = MediaIoBaseUpload(content_bytes, mimetype='text/plain')
        if files:
            # Update existing file
            file_id = files[0]['id']
            service.files().update(fileId=file_id, media_body=media).execute()
            print(f"Updated '{filename}' in cloud.")
        else:
            # Upload new file
            file_metadata = {
                'name': filename,
                'parents': [folder_id]
            }
            service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            print(f"Uploaded '{filename}' to cloud.")
    except Exception as e:
        print(f"Cloud upload failed ({type(e).__name__}): {e}")
        write_local_backup(filename, content)
        print(f"ATTENTION: Make sure to upload the file '{filename}' manually to cloud folder '{cloud_folder_name}'.")

# Validate Spotify playlist id
def validate_playlist(sp, playlist_id):
    try:
        playlist = sp.playlist(playlist_id)
        playlist_name = playlist["name"]
        print(f"Found Spotify playlist '{playlist_name}'.")
        return True
    except Exception as e:
        print(f"Validating Spotify playlist id failed ({type(e).__name__}): {e}")
        return False

# Function to fetch the list of tracks already in the playlist to avoid duplication
def fetch_playlist_tracks(sp, playlist_id):
    print("Fetching current playlist tracks for filtering.")
    track_ids = set()
    offset = 0
    
    while True:
        # Fetch playlist tracks
        for attempt in range(1, max_tries + 1):
            try:
                results = sp.playlist_tracks(playlist_id, offset=offset, limit=max_add_limit)
                break  # Success, break out of retry loop
            except Exception as e:
                print(f"{type(e).__name__} on attempt {attempt} while fetching playlist tracks batch: {e}")
                if attempt == max_tries:
                    print("Max retries reached while fetching playlist tracks. Please try again later.")
                    return None
                backoff_time = base_backoff ** attempt
                print(f"Retrying in {backoff_time} seconds...")
                time.sleep(backoff_time)

        tracks = results["items"]
        for item in tracks:
            track = item["track"]
            track_ids.add(track["id"])
            
        if len(tracks) < max_add_limit:
            break  # No more tracks to fetch
        offset += max_add_limit
    
    print(f"Current playlist tracks fetched ({len(track_ids)}).")
    return track_ids

# Function to fetch all followed artists
def fetch_artists(sp):
    print("Fetching all followed artists.")
    artists = []
    after = None

    while True:
        # Fetch artists
        for attempt in range(1, max_tries + 1):
            try:
                response = sp.current_user_followed_artists(
                    limit=max_artist_fetch_limit,
                    after=after)
                break # Success, break out of retry loop
            except Exception as e:
                print(f"{type(e).__name__} on attempt {attempt} while fetching followed artist batch: {e}")
                if attempt == max_tries:
                    print("Max retries reached while fetching followed artists. Please try again later.")
                    return None
                backoff_time = base_backoff ** attempt
                print(f"Retrying in {backoff_time} seconds...")
                time.sleep(backoff_time) # Retry after waiting

        # Extract and store artist data
        items = response["artists"]["items"]
        artists.extend(items)

        # Move to next batch using cursor
        after = response["artists"]["cursors"]["after"]
        if after is None:
            break # No more artists left
    
    artist_count = len(artists)
    if artist_count == 0:
        print("You need to follow artists to fetch new releases.")
    else:
        print(f"All followed artists fetched ({artist_count}).")
    return artists

# Function to fetch releases (albums or singles) for a given artist
def fetch_releases(sp, artist_id, album_type, run_date):
    releases = []
    fetched_count = 0

    while True:
        # Fetch releases
        for attempt in range(1, max_tries + 1):
            try:
                results = sp.artist_albums(
                    artist_id,
                    include_groups=album_type,
                    limit=max_track_fetch_limit,
                    offset=fetched_count)
                break # Success, break out of retry loop
            except Exception as e:
                print(f"{type(e).__name__} on attempt {attempt}: {e}")
                if attempt == max_tries:
                    print("Max tries reached, skipping this batch.")
                    return releases
                backoff_time = base_backoff ** attempt
                print(f"Retrying in {backoff_time} seconds...")
                time.sleep(backoff_time) # Retry after waiting
        
        # Process found items
        if results["items"]:
            for album in results["items"]:
                try:
                    release_date = datetime.strptime(album["release_date"], '%Y-%m-%d').date()
                    if release_date >= run_date:
                        releases.append(album)
                    else:
                        return releases # Stop fetching if the release date is earlier than the run date
                except ValueError:
                    continue # Skip albums with invalid release dates
        else:
            break # No releases found
        fetched_count += max_track_fetch_limit
    return releases

# Function to add fetched tracks to the playlist, ensuring no duplicates
def add_tracks_to_playlist(sp, releases, playlist_id, playlist_tracks, previous_tracks, added_tracks, added_tracks_strings):
    for release in releases:
        album_tracks = sp.album_tracks(release["id"])
        track_ids = [] # Tracks to be added to playlist
        for track in album_tracks["items"]:
            artist_names = ", ".join(artist["name"] for artist in track["artists"])
            track_string = f"{artist_names} - {track['name']}"
            if track["id"] in playlist_tracks:
                print(f"  Already in playlist: {track_string}") # Skip if track is already in the playlist
                continue
            if track["id"] in previous_tracks:
                print(f"  In playlist previously: {track_string}") # Skip if track was in the playlist after previous run
                continue
            if track["id"] not in added_tracks:
                track_ids.append(track["id"])
                added_tracks.add(track["id"]) # Track added to the set to avoid duplicates
                added_tracks_strings.append(track_string)
                print(f"  Added: {track_string}")
        if track_ids:
            # Add the tracks to the playlist in batches
            for i in range(0, len(track_ids), max_add_limit):
                sp.playlist_add_items(playlist_id, track_ids[i:i+max_add_limit])

# Loop through each artist and fetch new albums and singles    
def process_artists(sp, artists, playlist_id, playlist_tracks, previous_tracks, run_date):
    # Container for added track IDs and human-readable information
    added_tracks = set()
    added_tracks_strings = []
    artist_count = len(artists)
    artist_index_length = len(str(artist_count))
    for index, artist in enumerate(artists, start=1):
        formatted_index = str(index).zfill(artist_index_length)
        print(f'Checking releases from {formatted_index}/{artist_count} {artist["name"]}')
        albums  = fetch_releases(sp, artist["id"], "album", run_date)
        singles = fetch_releases(sp, artist["id"], "single", run_date)
        # appearances  = fetch_releases(sp, artist["id"], "appears_on",  run_date)
        # compilations = fetch_releases(sp, artist["id"], "compilation", run_date)
        releases = albums + singles
        add_tracks_to_playlist(sp, releases, playlist_id, playlist_tracks, previous_tracks, added_tracks, added_tracks_strings)
    return added_tracks, added_tracks_strings

# Update cloud files if necessary
def update_cloud_files(service, folder_id, added_tracks, playlist_tracks, run_date, run_date_file_found):
    # Write the current tracks as previous tracks for the next run
    all_tracks = added_tracks.union(playlist_tracks)
    if all_tracks:
        previous_tracks_content = "\n".join(all_tracks)
        upload_file(service, folder_id, previous_tracks_filename, previous_tracks_content)
    else:
        print(f"No tracks found in playlist. Skipping update of '{previous_tracks_filename}'.")
        
    # Write the current date as the new run date for future runs
    last_run_content = str(date.today())
    if not run_date_file_found or run_date != date.today():
        upload_file(service, folder_id, date_filename, last_run_content)
    else:
        print(f"No change in run date. Skipping update of '{date_filename}'.")
    
# Output the number and details of the added tracks    
def print_added_tracks(added_tracks, added_tracks_strings):
    new_releases_count = len(added_tracks)
    release_index_length = len(str(new_releases_count))
    print(f"Done. All new releases added ({new_releases_count}).")
    for index, track_string in enumerate(added_tracks_strings, start=1):
        formatted_index = str(index).zfill(release_index_length)
        print(f"{formatted_index}. {track_string}")

def main():       
    # Authentication using Spotipy's OAuth flow
    sp, playlist_id = authenticate_spotify()
    
    # Initialize cloud service
    service = authenticate_cloud()

    # Track the elapsed time for performance
    start = time.time()
    
    # Validate Spotify playlist id
    if not validate_playlist(sp, playlist_id):
        return

    # Fetch the list of tracks currently in the playlist
    playlist_tracks = fetch_playlist_tracks(sp, playlist_id)
    if playlist_tracks is None:
        return # Retrieving playlist tracks failed, stop execution

    # Fetch the list of previous tracks
    folder_id = get_cloud_folder_id(service)
    previous_tracks = get_previous_tracks(service, folder_id)
    
    # Read the date from which new releases should be processed
    run_date, run_date_file_found = get_run_date(service, folder_id)

    # Retrieve the list of followed artists
    artists = fetch_artists(sp)
    if not artists:
        return # Retrieving artists failed or no followed artists, stop execution

    # Add tracks from all artists to the playlist
    added_tracks, added_tracks_strings = process_artists(sp, artists, playlist_id, playlist_tracks, previous_tracks, run_date)

    # Update the cloud files
    update_cloud_files(service, folder_id, added_tracks, playlist_tracks, run_date, run_date_file_found)

    # Print added tracks
    print_added_tracks(added_tracks, added_tracks_strings)

    # Calculate and display the execution time
    stop = time.time()
    print(f"Execution time: {stop - start:.3f} seconds")
    
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"An error occurred ({type(e).__name__}): {e}")
    finally:
        input("Press Enter to exit...")
