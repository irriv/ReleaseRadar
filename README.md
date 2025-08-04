# ReleaseRadar

This program uses the **Spotify Web API** to collect new tracks from your followed artists and adds them to a specified playlist. It ensures no new releases go unnoticed by maintaining a record of the last run date and preventing duplicates by checking both the current playlist and previously added tracks.

To support usage across multiple devices, the program uses the **Google Drive API** to store and retrieve sync-related files such as the last run date and previously added tracks.

## Getting Started

The program is distributed as a **standalone executable file** `ReleaseRadar.exe` along with **configuration files** `config.txt` and `Cloud/credentials.json`. Follow the steps below to set it up and start using the program.

Alternatively `ReleaseRadar.py` can be run from the terminal with `python ReleaseRadar.py`. Running the script directly requires the following packages `pip install spotipy google-api-python-client google-auth-httplib2 google-auth-oauthlib`.

### 1. Generate Spotify API Credentials
1. Visit the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/).
2. Log in with your **Spotify account**.
3. Create a new **application**.
4. Copy the **Client ID** and **Client Secret** from your application settings.

### 2. Set the Redirect URI
In your Spotify application settings:
1. Under **Redirect URIs**, add the following URI:  
   `http://127.0.0.1:8888/callback`
2. Save the changes.

### 3. Update the `config.txt` File
The program comes with a `config.txt` file. Open it in a text editor and replace the placeholders with your **Spotify API credentials and playlist information**:

```ini
[DEFAULT]
client_id=your_client_id
client_secret=your_client_secret
redirect_uri=http://127.0.0.1:8888/callback
playlist_id=your_playlist_id
```

#### Replace the placeholders:
- **client_id**: Your Spotify application's **Client ID**.
- **client_secret**: Your Spotify application's **Client Secret**.
- **redirect_uri**: Use the provided `http://127.0.0.1:8888/callback` (this must match the **Redirect URI** in your Spotify application settings).
- **playlist_id**: The ID of the playlist where new tracks will be added. To find your **playlist ID**:
  1. Open Spotify and navigate to your playlist.
  2. Click on the "..." menu and select **Share > Copy Link to Playlist**.
  3. Extract the **playlist ID** from the link (it's the portion after `/playlist/`).

Example `config.txt`:

```ini
[DEFAULT]
client_id=12345abcdef67890
client_secret=abcdef1234567890abcdef1234567890
redirect_uri=http://127.0.0.1:8888/callback
playlist_id=37i9dQZF1DXcBWIGoYBM5M
```

### 4. Generate Google Drive API Credentials
1. Visit the [Google Cloud Console](https://console.cloud.google.com/).
2. Log in with your **Google account**.
3. Create a new **Google Cloud project**. There are no crucial settings for this step.
4. Enable the **Google Drive API** in the [Google Cloud Console](https://console.cloud.google.com/flows/enableapi?apiid=drive.googleapis.com).
5. Configure the **Google Auth Platform** in the [Google Cloud project](https://console.cloud.google.com/auth/branding).
6. Create an **OAuth client** in the [Google Cloud project](https://console.cloud.google.com/auth/clients/create).
   - Set **Application type** as **Desktop app**.
   - When you press the **Create** button, you will be prompted to download the **client credentials JSON file**.
7. Download the **client credentials JSON file**.

### 5. Set Google Coud project test users
Set your **Google account** as a test user for the [Google Auth Platform](https://console.cloud.google.com/auth/audience). You can set multiple test users.

### 6. Update the `credentials.json` File
1. Navigate to **ReleaseRadar/Cloud** folder.
2. Copy the contents of your downloaded **client credentials JSON file** and paste them into the `credentials.json` file.

Example `credentials.json`:

```
{"installed":{"client_id":"client_id.apps.googleusercontent.com","project_id":"project_id","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_secret":"client_secret","redirect_uris":["http://localhost"]}}
```

## Running the Program
1. Run `ReleaseRadar.exe`.
2. Follow the authentication flow in your browser to grant access to your Spotify account.
3. Follow the authentication flow in your browser to grant access to your Google Drive. The program has access only to the files it creates, which are located in the **ReleaseRadar/** folder in Google Drive.
4. The program will process new releases, add them to the specified playlist (if they are not already present), and record the current date for future runs.

## Notes
- The program creates a `LastRun.txt` file in Google Drive folder **ReleaseRadar/**. This file stores the date of the last run, ensuring only new releases are processed in subsequent executions.
- The date format used in `LastRun.txt` is `YYYY-MM-DD`. For example, if the script was last run on December 7, 2024, the file would contain `2024-12-07`.
- The program creates a `PreviousTracks.txt` file in Google Drive folder **ReleaseRadar/**. This file ensures that releases previously added to the playlist are not duplicated in future runs. If a track was added in a previous run but later removed from the playlist, the program will prevent it from being re-added, even if it was released on the same date as the last run.
- The program requires authentication through a browser only once. After completing the Spotify authentication flow, the program will generate a `.cache` file to store the authentication token. Similarly, the Google Drive authentication flow generates a `token.json` file. For future runs, the authentication will be handled automatically using the cached tokens, so you won’t need to authenticate again unless the cache expires or is deleted.
- Ensure the Spotify account used for authentication has **permissions** to modify the specified playlist.
- If there is an error when uploading files to Google Drive, the program will create the files locally in **ReleaseRadar/Backup/** folder. Update the files manually to Google Drive by replacing the existing files with the backup versions. If you delete the original files and upload new ones, the program does not have access to them since they were not created by the program itself.
