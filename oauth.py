import os, json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/drive"]

def main():
    client_secrets_file = "client_secret_861253117407-qs0f9lv9eiv1n6rher9jk9bgqsimisf6.apps.googleusercontent.com.json"
    creds = None
    token_path = "token.json"

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
            creds = flow.run_local_server(port=0)  # will open browser
        with open(token_path, "w") as token:
            token.write(creds.to_json())

    print("Stored token at:", token_path)
    if creds.refresh_token:
        print("Refresh token present. Save it for server use.")
        print("client_id:", creds.client_id)
        print("client_secret:", creds.client_secret)
        print("refresh_token:", creds.refresh_token)

if __name__ == "__main__":
    main()