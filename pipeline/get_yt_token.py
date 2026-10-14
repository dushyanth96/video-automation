"""One-time YouTube OAuth helper — prints REFRESH_TOKEN to paste into .env.
Usage: python pipeline/get_yt_token.py
"""
import os
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
except Exception:
    pass
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
flow = InstalledAppFlow.from_client_config(
    {"installed": {"client_id": os.getenv("YT_CLIENT_ID"), "client_secret": os.getenv("YT_CLIENT_SECRET"),
                   "redirect_uris": ["http://localhost"], "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                   "token_uri": "https://oauth2.googleapis.com/token"}},
    SCOPES)
creds = flow.run_local_server(port=0)
print("\nPaste this into .env as YT_REFRESH_TOKEN=\n" + creds.refresh_token)
