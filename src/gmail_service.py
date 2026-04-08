import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


def get_gmail_service():
    creds = None
    token_path = os.path.join("config", "token.json")

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

        with open(token_path, "w", encoding="utf-8") as token:
            token.write(creds.to_json())

    if not creds:
        raise ValueError(
            "No se pudo cargar config\\token.json con permisos de lectura y envío. "
            "Debes regenerarlo incluyendo gmail.send."
        )

    return build("gmail", "v1", credentials=creds)