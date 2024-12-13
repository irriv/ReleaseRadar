# ReleaseRadar

This program uses Spotify's Web API to collect new tracks from your followed artists and adds them to a specified playlist. It ensures no new releases go unnoticed by maintaining a record of the last run date and preventing duplicates by checking both the current playlist and previously added tracks.

## Getting Started

The program is distributed as a standalone executable file `ReleaseRadar.exe` along with a configuration file `config.txt`. Follow the steps below to set it up and start using the program.

### 1. Generate Spotify API Credentials
1. Visit the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/).
2. Log in with your Spotify account.
3. Create a new application.
4. Copy the **Client ID** and **Client Secret** from your application settings.

### 2. Set the Redirect URI
In your Spotify application settings:
1. Under **Redirect URIs**, add the following URI:  
   `http://localhost:8888/callback`
2. Save the changes.

### 3. Update the `config.txt` File
The program comes with a `config.txt` file. Open it in a text editor and replace the placeholders with your Spotify API credentials and playlist information:

```ini
[DEFAULT]
client_id=your_client_id
client_secret=your_client_secret
redirect_uri=http://localhost:8888/callback
playlist_id=your_playlist_id
```

#### Replace the placeholders:
- **client_id**: Your Spotify application's Client ID.
- **client_secret**: Your Spotify application's Client Secret.
- **redirect_uri**: Use the provided `http://localhost:8888/callback` (this must match the Redirect URI in your Spotify application settings).
- **playlist_id**: The ID of the playlist where new tracks will be added. To find your playlist ID:
  1. Open Spotify and navigate to your playlist.
  2. Click on the "..." menu and select **Share > Copy Link to Playlist**.
  3. Extract the playlist ID from the link (it's the portion after `/playlist/`).

Example `config.txt`:

```ini
[DEFAULT]
client_id=12345abcdef67890
client_secret=abcdef1234567890abcdef1234567890
redirect_uri=http://localhost:8888/callback
playlist_id=37i9dQZF1DXcBWIGoYBM5M
```

## Running the Program
1. Run `ReleaseRadar.exe`.
2. Follow the authentication flow in your browser to grant access to your Spotify account.
3. The program will process new releases, add them to the specified playlist (if they are not already present), and record the current date for future runs.

## Notes
- The program creates a `LastRun.txt` file in the same directory as `ReleaseRadar.exe`. This file stores the date of the last run, ensuring only new releases are processed in subsequent executions.
- The date format used in `LastRun.txt` is `YYYY-MM-DD`. For example, if the script was last run on December 7, 2024, the file would contain `2024-12-07`.
- The program creates a `PreviousTracks.txt` file in the same directory as `ReleaseRadar.exe`. This file ensures that releases previously added to the playlist are not duplicated in future runs. If a track was added in a previous run but later removed from the playlist, the program will prevent it from being re-added, even if it was released on the same date as the last run.
- The program requires authentication through a browser only once. After completing the authentication flow, the program will generate a `.cache` file to store the authentication token. For future runs, the authentication will be handled automatically using this cached token, so you won’t need to authenticate again unless the cache expires or is deleted.
- Ensure the Spotify account used for authentication has permissions to modify the specified playlist.
