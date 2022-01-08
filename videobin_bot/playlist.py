from pathlib import Path
import json
import re

import google
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors

YOUTUBE_VIDEO_PATTERN = re.compile(r"((?:https?:)?\/\/)?((?:www|m)\.)?((?:youtube\.com|youtu.be))(\/(?:[\w\-]+\?v=|embed\/|v\/)?)([\w\-]+)")

class Playlist:
    youtube = None

    def __init__(self, playlist_id):
        self.playlist_id = playlist_id

    @staticmethod
    def build_service():
        # Disable OAuthlib's HTTPS verification when running locally.
        # *DO NOT* leave this option enabled in production.
        # os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

        cr_file = Path('credentials.json')

        credentials = None
        api_service_name = "youtube"
        api_version = "v3"
        if cr_file.is_file():
            with cr_file.open('r') as f:
                http_request = google.auth.transport.requests.Request()
                credentials = google.oauth2.credentials.Credentials(**json.load(f))
                credentials.refresh(http_request)
        else:
            scopes = ["https://www.googleapis.com/auth/youtube.force-ssl"]
            client_secrets_file = "client_secret_1058197482445-9u16r1tjk89kjn9the4f54tm72b3jnom.apps.googleusercontent.com.json"

            # Get credentials and create an API client
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                client_secrets_file, scopes)
            credentials = flow.run_console()
            with cr_file.open('w') as f:
                f.write(credentials.to_json())

        return googleapiclient.discovery.build(api_service_name, api_version, credentials=credentials)

    @staticmethod
    def create():
        if not Playlist.youtube:
            Playlist.youtube = Playlist.build_service()

        request = Playlist.youtube.playlists().insert(
            part="snippet,status",
            body={
              "snippet": {
                "title": "Videobin",
              },
              "status": {
                "privacyStatus": "unlisted"
              }
            }
        )
        resp = request.execute()
        playlist_id = resp['id']

        return Playlist(playlist_id)

    def add(self, url):
        if not Playlist.youtube:
            Playlist.youtube = Playlist.build_service()

        if m := YOUTUBE_VIDEO_PATTERN.search(url):
            video_id = m.group(5)
            request = Playlist.youtube.playlistItems().insert(
                part="snippet",
                body={
                  "snippet": {
                    "playlistId": self.playlist_id,
                    "position": 0,
                    "resourceId": {
                      "kind": "youtube#video",
                      "videoId": video_id,
                    }
                  }
                }
            )
            return request.execute()
        else:
            raise ValueError(f"{url} just ain't right")
